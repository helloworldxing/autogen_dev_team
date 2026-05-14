from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional
from uuid import uuid4
import re

# Import autogen first to avoid encoding issues
import autogen

from src.agents.factory import ROLE_ORDER, build_base_agents, build_rag_agents
from src.app.architecture_guard import (
    build_layered_architecture_fix_prompt,
    list_delivery_files,
    validate_layered_architecture,
)
from src.app.artifacts import materialize_code_files, print_delivery_artifacts
from src.app.runtime import enable_streaming_with_mongo_logging
from src.app.stack_policy import infer_stack_policy
from src.app.workspace import create_delivery_workspace, ensure_user_guide
from src.config import llm_config, llm_settings, patch_autogen_streaming_token_count
from src.persistence.mongo_logger import MongoConversationLogger
from src.rag.compression_integration import (
    CompressionConfig,
    CompressedGroupChatManager,
    CoordinatorCompressionMixin,
    MessageRouter,
    create_compressed_coordinator_wrapper,
    patch_group_chat_for_compression,
)
from src.rag.knowledge_base import RAGKnowledgeManager
from src.rag.message_compressor import CompressionLevel, create_compressor

OUTPUT_ROOT = Path("coding").resolve()
QUIET = os.getenv("QUIET_OUTPUT", "false").strip().lower() in {"1", "true", "yes", "on"}
MAX_ARCHITECTURE_RETRY = int(os.getenv("MAX_ARCHITECTURE_RETRY", "2"))
MAX_CHAT_ROUNDS = int(os.getenv("GROUPCHAT_MAX_ROUND", "12"))


def _print(*args, **kwargs):
    if not QUIET:
        try:
            print(*args, **kwargs)
        except UnicodeEncodeError:
            # 处理 Unicode 编码错误，移除或替换问题字符
            safe_args = []
            encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
            for arg in args:
                if isinstance(arg, str):
                    safe_args.append(arg.encode(encoding, "replace").decode(encoding))
                else:
                    safe_args.append(arg)
            print(*safe_args, **kwargs)


def get_user_task() -> str:
    _print("\n请输入你的任务描述（支持多行，输入空行结束）：")

    while True:
        lines: List[str] = []
        while True:
            line = input()
            if line.strip() == "":
                break
            lines.append(line)

        task_text = "\n".join(lines).strip()
        if task_text:
            return task_text

        _print("任务不能为空，请重新输入：")


def _normalize_content(message) -> str:
    """Extract text content from autogen message (dict/str/list)."""
    if isinstance(message, str):
        return message
    if isinstance(message, dict):
        content = message.get("content", "")
    else:
        content = ""

    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)

    if isinstance(content, str):
        return content
    return str(content) if content is not None else ""


def _is_termination(message) -> bool:
    content = _normalize_content(message).strip()
    if not content:
        return False
    has_terminate = bool(
        re.search(r"(?:^|\n)\s*TERMINATE\s*[。.!！?？]*\s*$", content, re.IGNORECASE)
    )
    if has_terminate:
        _print(f"[DEBUG] 检测到 TERMINATE 关键词")
    return has_terminate


def _speaker_selection_with_hard_stop(last_speaker, groupchat):
    """Stop group chat immediately once the latest message is a termination message."""
    if groupchat.messages:
        last_msg = groupchat.messages[-1]
        if _is_termination(last_msg):
            _print(f"[DEBUG] 硬停止触发：当前消息轮数 {len(groupchat.messages)}")
            return None
    return "auto"


def create_user_proxy(output_dir: Path) -> autogen.UserProxyAgent:
    return autogen.UserProxyAgent(
        name="User_Proxy",
        human_input_mode="NEVER",
        max_consecutive_auto_reply=10,
        is_termination_msg=_is_termination,
        code_execution_config={
            "work_dir": str(output_dir),
            "use_docker": False,
        },
    )


def build_group_chat(
    agents: List[autogen.AssistantAgent], user_proxy: autogen.UserProxyAgent
):
    groupchat = autogen.GroupChat(
        agents=[user_proxy, *agents],
        messages=[],
        max_round=MAX_CHAT_ROUNDS,
        speaker_selection_method=_speaker_selection_with_hard_stop,
    )

    # Create base manager first
    base_manager = autogen.GroupChatManager(
        groupchat=groupchat,
        llm_config=llm_config,
        system_message=(
            "You are the chat manager. Your primary role is to follow the instructions of the Coordinator. "
            "The Coordinator will decide who speaks next. Do not intervene unless instructed."
        ),
    )

    if CompressionConfig.ENABLED:
        compressor = create_compressor(
            level=CompressionConfig.LEVEL,
            preserve_structure=CompressionConfig.PRESERVE_STRUCTURE,
        )
        compressed_manager = CompressedGroupChatManager(
            base_manager=base_manager,
            compressor=compressor,
            config=CompressionConfig(),
        )
        manager = compressed_manager
        _print(f"消息压缩已启用 (级别: {CompressionConfig.LEVEL})")
    else:
        manager = base_manager

    return groupchat, manager


def print_knowledge_stats(knowledge_manager: RAGKnowledgeManager) -> None:
    _print("\n📊 知识库统计:")
    stats = knowledge_manager.get_all_knowledge_stats()
    for role, count in stats.items():
        _print(f"  • {role}: {count} 条知识")


def run_task(
    task: str, event_callback: Optional[Callable[[Dict[str, object]], None]] = None
) -> Dict[str, object]:
    """Run one end-to-end multi-agent task and return execution artifacts."""
    if event_callback is not None:
        event_callback({"type": "status", "stage": "init", "message": "开始初始化任务"})

    patch_autogen_streaming_token_count()

    session_id = str(uuid4())
    mongo_logger = MongoConversationLogger()
    seen_hashes: set[str] = set()

    enable_streaming_with_mongo_logging(
        mongo_logger=mongo_logger,
        session_id=session_id,
        seen_hashes=seen_hashes,
        stream_enabled=llm_settings.stream,
        on_event=event_callback,
    )

    _print("=" * 60)
    enable_rag = os.getenv("EXPERIMENT_ENABLE_RAG", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    multi_agent = os.getenv("EXPERIMENT_MULTI_AGENT", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    single_agent_role = (
        os.getenv("EXPERIMENT_SINGLE_AGENT_ROLE", "engineer").strip().lower()
    )
    if single_agent_role not in ROLE_ORDER:
        single_agent_role = "engineer"

    _print("🚀 初始化系统...")
    _print("=" * 60)
    knowledge_manager: Optional[RAGKnowledgeManager] = None
    if enable_rag:
        knowledge_manager = RAGKnowledgeManager()
        _print("\n📚 加载角色专属知识库...")
        knowledge_manager.initialize_default_knowledge()
    else:
        _print("\n📚 RAG 已禁用（EXPERIMENT_ENABLE_RAG=false）")

    if event_callback is not None:
        event_callback(
            {
                "type": "status",
                "stage": "knowledge_ready",
                "message": "知识库加载完成，开始创建智能体",
            }
        )
    # 移除知识库统计输出，避免在web端显示无关信息
    # print_knowledge_stats(knowledge_manager)

    _print("=" * 60)
    _print("🤖 创建增强型智能体...")
    _print("=" * 60)
    if enable_rag and knowledge_manager is not None:
        agents_map = build_rag_agents(knowledge_manager)
    else:
        agents_map = build_base_agents()

    selected_roles = ROLE_ORDER if multi_agent else [single_agent_role]
    ordered_agents = [agents_map[role] for role in selected_roles]
    _print("所有智能体已创建并增强！\n")
    _print(
        f"🧪 实验配置: mode={'multi-agent' if multi_agent else 'single-agent'}; "
        f"rag={'on' if enable_rag else 'off'}; roles={selected_roles}"
    )

    _print("=" * 60)
    _print("🎯 启动任务...")
    _print("=" * 60)
    _print(f"🧾 会话ID: {session_id}")
    project_tag, output_dir = create_delivery_workspace(task, OUTPUT_ROOT)
    _print(f"🏷 项目标识: {project_tag}")
    _print(f"📁 代码执行与交付目录: {output_dir}")
    stack_policy = infer_stack_policy(task)
    _print(f"🧭 技术栈策略: {stack_policy.guidance}")

    user_proxy = create_user_proxy(output_dir)
    groupchat, manager = build_group_chat(ordered_agents, user_proxy)

    _print(f"\n📋 任务描述:\n{task}\n")
    _print("=" * 60)
    _print("🔄 开始多智能体协作流程...")
    _print(f"[DEBUG] max_round={MAX_CHAT_ROUNDS}")
    _print("=" * 60)
    _print()

    if multi_agent:
        initial_message = f"""用户想要开发一个应用程序。以下是请求内容：

{task}

⚠️ 重要工作流程规则：
1. 🎯 产品经理必须首先创建完整的产品需求文档 (PRD)
2. 🔄 所有产品决策必须经由产品经理批准
3. 👥 每个角色都应专注于自身专长，不得越权行事
4. 📋 工程师在 PRD 获得批准前不得开始编码
5. 🧪 测试人员在代码编写完成前不得开始测试
6. 📘 每次交付必须包含用户手册（README.md 或 USER_GUIDE.md）
7. 🏷 生成文件命名需要体现项目特征，建议核心文件使用“{project_tag}_”前缀
8. 📁 所有交付文件必须写入目录：{output_dir}
9. 🧭 技术栈强约束：{stack_policy.guidance}
10. 🧱 文件后缀限制：仅允许 {sorted(stack_policy.allowed_extensions)}
11. ✂️ 输出风格：禁止废话和过程解释，只输出最终结果与交付内容。

✅ Java/Maven 额外交付强约束（如任务包含 Java/Spring/Maven/后端）:
A. 必须是 Maven 标准目录，Java 源码只能放在：
   - src/main/java/<base-package>/...
   - src/test/java/<base-package>/...
B. 资源文件只能放在：src/main/resources/...

C. 必须提供 pom.xml（含 spring-boot-maven-plugin）。
D. 每个文件必须用一行明确的“filename: <相对路径>”标注，严禁使用无路径的扁平文件名。
E. 若同一类文件已生成在根目录（如 controller/、service/、entity/），需迁移到 src/main/java 的正确包路径下，并删除/停止输出旧路径。

协调员，请您首先联系产品经理，请其分析需求并创建 PRD。
"""
    else:
        initial_message = f"""你现在处于单智能体实验模式，请独立完成以下任务，并直接输出最终可交付结果：

{task}

要求：
1. 输出结构化交付内容（目录树 + 文件代码 + 运行方式）。
2. 只输出结果，不输出推理过程。
3. 最后一行输出 TERMINATE。
"""

    _print("[DEBUG] 启动群聊")
    user_proxy.initiate_chat(manager, message=initial_message)
    _print(f"[DEBUG] 群聊已完成，消息轮数: {len(groupchat.messages)}")

    if event_callback is not None:
        event_callback(
            {
                "type": "status",
                "stage": "chat_done",
                "message": "群聊结束，正在整理交付产物",
            }
        )

    created_code_files = materialize_code_files(
        groupchat.messages,
        output_dir,
        project_tag,
        default_code_extension=stack_policy.default_code_extension,
        allowed_extensions=stack_policy.allowed_extensions,
    )
    if created_code_files:
        _print("\n🧩 已从对话中自动落盘代码文件:")
        for rel_path in created_code_files:
            _print(f"  - {rel_path}")
    else:
        _print("\n⚠ 未检测到可落盘的 Python 代码块，请检查工程师输出格式。")

    architecture_result = validate_layered_architecture(list_delivery_files(output_dir))
    architecture_retry = 0

    while (
        not architecture_result.is_valid and architecture_retry < MAX_ARCHITECTURE_RETRY
    ):
        architecture_retry += 1
        _print("\n⚠ 检测到交付未满足分层架构规范，触发自动补交流程...")
        for reason in architecture_result.reasons:
            _print(f"  - {reason}")

        if event_callback is not None:
            event_callback(
                {
                    "type": "status",
                    "stage": "architecture_retry",
                    "message": f"分层架构校验未通过，正在进行第 {architecture_retry} 次补交",
                }
            )

        fix_prompt = build_layered_architecture_fix_prompt(
            architecture_result, output_dir
        )
        _print(f"[DEBUG] 启动补交流程 #{architecture_retry}")
        user_proxy.initiate_chat(manager, message=fix_prompt)
        _print(f"[DEBUG] 补交流程 #{architecture_retry} 完成")

        created_code_files = materialize_code_files(
            groupchat.messages,
            output_dir,
            project_tag,
            default_code_extension=stack_policy.default_code_extension,
            allowed_extensions=stack_policy.allowed_extensions,
        )
        architecture_result = validate_layered_architecture(
            list_delivery_files(output_dir)
        )

    if architecture_result.is_valid:
        _print("\n✅ 分层架构校验通过。")
    else:
        _print("\n⚠ 分层架构校验未通过，已达到自动补交上限。")
        for reason in architecture_result.reasons:
            _print(f"  - {reason}")

    guide_path = ensure_user_guide(output_dir, project_tag, task)

    _print("\n" + "=" * 60)
    _print("✅ 任务完成！")
    _print("=" * 60)
    _print(f"📘 用户手册: {guide_path}")
    print_delivery_artifacts(output_dir, project_tag)

    if CompressionConfig.ENABLED and hasattr(groupchat, "messages"):
        _print("\n📊 消息压缩统计:")
        _print(f"  • 消息总数: {len(groupchat.messages)}")
        total_original = sum(
            len(str(m.get("content", "")))
            for m in groupchat.messages
            if isinstance(m, dict)
        )
        _print(f"  • 原始内容总长度: {total_original} 字符")

    mongo_logger.close()

    if event_callback is not None:
        event_callback(
            {
                "type": "status",
                "stage": "done",
                "message": "任务执行完成",
            }
        )

    return {
        "session_id": session_id,
        "project_tag": project_tag,
        "output_dir": str(output_dir),
        "guide_path": str(guide_path),
        "created_code_files": created_code_files,
        "experiment": {
            "enable_rag": enable_rag,
            "multi_agent": multi_agent,
            "single_agent_role": single_agent_role,
            "selected_roles": selected_roles,
        },
        "architecture_validation": {
            "is_valid": architecture_result.is_valid,
            "reasons": architecture_result.reasons,
            "detected_layers": architecture_result.detected_layers,
            "code_file_count": architecture_result.code_file_count,
            "primary_language": architecture_result.primary_language,
            "retry_count": architecture_retry,
        },
    }


def run() -> None:
    task = get_user_task()
    run_task(task)


if __name__ == "__main__":
    run()
