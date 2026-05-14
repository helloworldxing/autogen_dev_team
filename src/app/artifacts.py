from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path
from typing import List, Optional, Set


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def sanitize_terminal_text(content: str) -> str:
    text = content
    text = text.replace("```python", "")
    text = text.replace("```", "")
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"__(.*?)__", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"^\s{0,3}#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _infer_filename_from_message(
    content: str, block_index: int, project_tag: str, code: str, lang: str = ""
) -> str:
    # Prefer explicit file hints in text, allow any extension.
    patterns = [
        r"(?:文件名|filename|file)\s*[:：]\s*([A-Za-z0-9_.\\/\\-]+)",
        r"(?:(?:^|\n)\s*(?:\*+)?([A-Za-z0-9_.\\/\\-]+\.[A-Za-z0-9]+)(?:\*+)?\s*(?:\n|$))",
        r"###\s*([A-Za-z0-9_.\\/\\-]+)",
        r"##\s*([A-Za-z0-9_.\\/\\-]+)",
    ]
    latest_pos = -1
    latest_name = ""

    def _normalize_candidate(name: str) -> str:
        """清理标题/列表前缀，避免 '### 9. path' 被解析成 '9.' 或包含多余标点。"""
        cleaned = (name or "").strip()
        cleaned = cleaned.replace("\\", "/")
        # remove leading bullets
        cleaned = re.sub(r"^[\-*•]+\s*", "", cleaned)
        # remove leading heading markers
        cleaned = re.sub(r"^#+\s*", "", cleaned)
        # remove leading index like '9.' / '10)' / '9、'
        cleaned = re.sub(r"^\d+\s*[.)、：:]\s*", "", cleaned)
        cleaned = cleaned.strip().rstrip(":：；;，,。.)]")
        return cleaned

    for pattern in patterns:
        for match in re.finditer(pattern, content, flags=re.IGNORECASE):
            matched_name = _normalize_candidate(match.group(1))
            if "." not in matched_name:
                continue
            if match.start() >= latest_pos:
                latest_pos = match.start()
                latest_name = matched_name

    if latest_name:
        return latest_name

    # Heuristics by code content
    lower_code = code.lower()
    if "<html" in lower_code or "<!doctype" in lower_code:
        return f"{project_tag}_module_{block_index}.html"
    if "def test_" in code or "pytest" in code:
        return f"{project_tag}_test_{block_index}.py"
    if 'if __name__ == "__main__"' in code:
        return f"{project_tag}_main.py"

    # Heuristics by language tag
    lang = lang.lower()
    if lang in ["text", "txt"]:
        return f"{project_tag}_module_{block_index}.txt"
    if lang in ["md", "markdown"]:
        return f"{project_tag}_module_{block_index}.md"
    if lang in ["sh", "bash"]:
        return f"{project_tag}_module_{block_index}.sh"

    # Check if it looks like a requirements.txt
    if "==" in code and "\n" in code and "def " not in code and "import " not in code:
        return "requirements.txt"

    return f"{project_tag}_module_{block_index}.py"


def _extract_content(message: dict) -> str:
    """Normalize message content to string (handles str or OpenAI-style list)."""
    content = message.get("content", "")
    if isinstance(content, str):
        return content
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
    return ""


def is_valid_python_code(code: str) -> bool:
    """检查是否是有效的Python代码"""
    try:
        compile(code, "<string>", "exec")
        return True
    except SyntaxError:
        return False


def materialize_code_files(
    messages: List[dict],
    output_dir: Path,
    project_tag: str,
    *,
    default_code_extension: str = ".py",
    allowed_extensions: Optional[Set[str]] = None,
) -> List[str]:
    # 捕获所有代码块
    code_block_pattern = re.compile(
        r"```([a-zA-Z0-9_\-.]+)?\s*(.*?)```", re.DOTALL | re.IGNORECASE
    )
    created_files: List[str] = []
    block_counter = 1

    # 防止同一文件在多轮补交/重复输出中被反复写入
    written_targets: Set[str] = set()

    normalized_default_ext = (
        default_code_extension
        if default_code_extension.startswith(".")
        else f".{default_code_extension}"
    ).lower()

    # Java/Maven 严格落盘：仅接受标准目录树路径，禁止回退扁平 *_module_N.java
    strict_java_maven = normalized_default_ext == ".java"
    allowed_java_prefixes = (
        "src/main/java/",
        "src/test/java/",
        "src/main/resources/",
    )

    for message in messages:
        content = _extract_content(message)
        if not content or "```" not in content:
            continue

        for match in code_block_pattern.finditer(content):
            lang = (match.group(1) or "").lower()
            code = match.group(2).strip()
            if not code:
                continue

            context_before_block = content[: match.start()]
            target_name = _infer_filename_from_message(
                context_before_block or content, block_counter, project_tag, code, lang
            )
            target_name_norm = target_name.replace("\\", "/")

            # 严格 Java/Maven：没有给出标准 filename 的代码块一律不落盘
            if strict_java_maven:
                is_java_file = target_name_norm.lower().endswith(".java")
                is_resource = target_name_norm.startswith(allowed_java_prefixes)
                is_pom = Path(target_name_norm).name.lower() == "pom.xml"
                if is_java_file and not target_name_norm.startswith(
                    ("src/main/java/", "src/test/java/")
                ):
                    block_counter += 1
                    continue
                if not (is_resource or is_pom or is_java_file):
                    # 例如随手输出的 .sh/.md 或无路径 java，全部跳过（避免污染交付目录）
                    block_counter += 1
                    continue

            target_name_suffix = Path(target_name).suffix.lower()
            normalized_default_ext = (
                default_code_extension
                if default_code_extension.startswith(".")
                else f".{default_code_extension}"
            ).lower()

            if not target_name_suffix:
                target_name = f"{target_name}{normalized_default_ext}"
                target_name_suffix = normalized_default_ext

            if allowed_extensions and target_name_suffix not in allowed_extensions:
                target_name = (
                    f"{project_tag}_module_{block_counter}{normalized_default_ext}"
                )
                target_name_suffix = normalized_default_ext

            # 只有当明确是 Python 文件，才做有效的 Python 代码检查
            if target_name.endswith(".py") or (
                lang in ["python", "py"]
                and not target_name.endswith(
                    (".txt", ".md", ".sh", ".html", ".js", ".css")
                )
            ):
                if not is_valid_python_code(code):
                    continue

            output_dir_resolved = output_dir.resolve()
            target_path = (output_dir_resolved / target_name).resolve()

            # 去重：同一路径仅写一次
            target_key = str(target_path)
            if target_key in written_targets or target_path.exists():
                block_counter += 1
                continue
            written_targets.add(target_key)

            if not str(target_path).startswith(str(output_dir_resolved)):
                fallback_ext = (
                    target_name.split(".")[-1] if "." in target_name else "py"
                )
                target_path = (
                    output_dir_resolved
                    / f"{project_tag}_module_{block_counter}.{fallback_ext}"
                )

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(code + "\n", encoding="utf-8")

            rel_path = target_path.relative_to(output_dir_resolved).as_posix()
            if rel_path not in created_files:
                created_files.append(rel_path)
            block_counter += 1

    return created_files


def _safe_print(*args, **kwargs):
    """安全打印函数，处理Unicode编码错误"""
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


def print_delivery_artifacts(output_dir: Path, project_tag: str) -> None:
    _safe_print("\n" + "=" * 60)
    _safe_print("交付产物信息")
    _safe_print("=" * 60)
    _safe_print(f"项目标识: {project_tag}")
    _safe_print(f"交付目录: {output_dir}")

    if not output_dir.is_dir():
        _safe_print("交付目录不存在，可能本次对话没有生成可执行文件。")
        return

    files = sorted(
        [
            p.relative_to(output_dir).as_posix()
            for p in output_dir.rglob("*")
            if p.is_file()
        ]
    )

    if not files:
        _safe_print("交付目录为空，可能智能体只给出了方案但未实际落盘。")
        return

    _safe_print("生成文件清单:")
    for rel_path in files:
        _safe_print(f"  - {rel_path}")

    runnable_candidates = [
        f for f in files if f.lower().endswith((".py", ".sh", ".bat", "readme.md"))
    ]
    if runnable_candidates:
        _safe_print("\n推荐先查看/运行:")
        for rel_path in runnable_candidates[:5]:
            _safe_print(f"  - {rel_path}")

    _safe_print("\n使用方式:")
    _safe_print(f"  1) 进入目录: cd {output_dir}")
    _safe_print("  2) 先查看 README.md（若存在）")
    _safe_print("  3) Python 项目可尝试: python main.py 或 python app.py")


def streaming_printer_factory(
    mongo_logger,
    session_id: str,
    seen_hashes: set[str],
    original_print,
    on_event=None,
):
    quiet = _env_bool("QUIET_OUTPUT", False)

    def printer(self, message, sender=None, **kwargs):

        if isinstance(message, dict):
            content = message.get("content", "")
        else:
            content = message

        if isinstance(content, str) and content.strip():
            cleaned_for_terminal = sanitize_terminal_text(content)
            # 确保sender_name正确获取，避免显示为用户身份
            sender_name = getattr(sender, "name", "unknown")
            # 将 User_Proxy 统一视为系统级编排消息，避免被前端渲染成普通用户
            if sender_name == "User_Proxy":
                sender_name = "System"
            # 如果系统编排消息明确在描述协调员，则按协调员显示
            elif sender_name == "System" and (
                "协调员" in cleaned_for_terminal
                or "Coordinator" in cleaned_for_terminal
            ):
                sender_name = "Coordinator"
            receiver_name = getattr(self, "name", "unknown")
            dedupe_key = (
                f"{sender_name}->{receiver_name}:{cleaned_for_terminal.strip()}"
            )
            dedupe_hash = hashlib.sha1(
                dedupe_key.encode("utf-8", errors="ignore")
            ).hexdigest()

            if dedupe_hash in seen_hashes:
                return
            seen_hashes.add(dedupe_hash)

            if not quiet:
                try:
                    sys.stdout.write("\n" + "▌ ")
                    sys.stdout.flush()
                    for char in cleaned_for_terminal:
                        sys.stdout.write(char)
                        sys.stdout.flush()
                    sys.stdout.write("\n")
                    sys.stdout.flush()
                except UnicodeEncodeError:
                    # 处理 Unicode 编码错误，使用替换字符
                    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
                    safe_content = cleaned_for_terminal.encode(
                        encoding, "replace"
                    ).decode(encoding)
                    sys.stdout.write("\n" + "▌ ")
                    sys.stdout.flush()
                    sys.stdout.write(safe_content)
                    sys.stdout.flush()
                    sys.stdout.write("\n")
                    sys.stdout.flush()

            if on_event is not None:
                try:
                    on_event(
                        {
                            "type": "message",
                            "session_id": session_id,
                            "sender": sender_name,
                            "receiver": receiver_name,
                            "content": cleaned_for_terminal,
                        }
                    )
                except Exception:
                    # Do not break the agent loop when UI event forwarding fails.
                    pass

            mongo_logger.log_message(
                session_id=session_id,
                receiver=receiver_name,
                sender=sender_name,
                content=content,
                raw_message=message,
            )
            return

        if quiet:
            return
        return original_print(self, message, sender, **kwargs)

    return printer
