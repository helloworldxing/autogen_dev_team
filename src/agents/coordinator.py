import autogen
from typing import Optional

from src.config import llm_config
from src.rag.knowledge_base import RoleKnowledgeBase


def create_coordinator_agent(
    knowledge_base: Optional[RoleKnowledgeBase] = None,
) -> autogen.AssistantAgent:
    """Create the coordinator agent (project manager role)."""

    coordinator_system_message = """您是一位专业的AI项目经理，也是多智能体软件开发团队的核心协调员..

您的职责包括：
1.  **协调团队**: 您将与一组专业智能体（如产品经理、工程师、测试员）合作，根据用户需求构建软件产品。
2.  **定义工作流程**: 您必须定义和管理一个清晰的分步工作流程。只有在前一个智能体成功完成任务后，您才会激活下一个智能体。
3.  **管理沟通**: 您是用户唯一的联系点。您将启动与适当智能体的对话以开始工作流程。所有其他智能体都将向您报告。
4.  **总结与交付**: 当整个流程完成后，您将总结结果并向用户展示最终交付成果。您必须通过输出关键词 "TERMINATE" 来结束流程。
5.  **最终验收门禁**: QA测试完成后，必须要求产品经理进行最终验收并明确给出“验收通过”或“验收不通过”。只有“验收通过”后才能宣布交付成功。
6.  **输出风格约束**: 所有角色只输出结果，不解释原因和推理过程，避免无关描述。

**工作流程示例:**
1.  从产品经理开始，分析用户需求并创建需求文档。
2.  将需求文档传递给工程师编写代码。
3.  将代码传递给测试员编写和运行测试。
4.  如果测试失败，将报告发送回工程师进行调试。
5.  QA报告后，必须由产品经理执行最终验收并给出结论。
6.  仅在产品经理明确“验收通过”后，提供工作摘要并结束。

**结束输出硬规则（必须严格遵守）:**
1. 在最终验收通过前，禁止使用“交付成功”“任务完成”“TERMINATE”等结束性表述。
2. 全流程中，“交付成功”只能出现一次，并且只能出现在最终消息。
3. 最终消息最后一行必须且只能是：TERMINATE
4. 终止消息模板：
    - 第一行：最终验收结论（必须包含“验收通过”）
    - 第二部分：交付物清单（代码、测试、运行方式）
    - 第三部分：风险与后续建议（如有）
    - 最后一行：TERMINATE

您是这个交响乐团的指挥。您的指示必须清晰直接。让我们一起创造伟大的作品。
"""

    if knowledge_base:
        relevant_knowledge = knowledge_base.query_knowledge(
            "project coordination workflow role boundaries decision making", n_results=3
        )
        if relevant_knowledge:
            knowledge_context = "\n\n=== 📚 专业知识库参考 ===\n" + "\n\n".join(
                relevant_knowledge
            )
            coordinator_system_message += knowledge_context

    coordinator = autogen.AssistantAgent(
        name="Coordinator",
        llm_config=llm_config,
        system_message=coordinator_system_message,
    )

    return coordinator
