"""Helpers for workspace creation and artifact surfacing."""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Tuple


def build_project_tag(task_text: str) -> str:
    # 生成符合编程规范的项目标签（只使用英文、数字和下划线）
    normalized = "".join(
        [ch.lower() if ch.isalnum() else "_" for ch in task_text]
    ).strip("_")
    # 如果结果为空，使用默认值
    if not normalized:
        return "project"
    # 截取长度并确保以字母开头
    tag = normalized[:40]
    # 如果以数字开头，添加前缀
    if tag and tag[0].isdigit():
        tag = "project_" + tag
    return tag


def create_delivery_workspace(task_text: str, output_root: Path) -> Tuple[str, Path]:
    project_tag = build_project_tag(task_text)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = output_root / f"{project_tag}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return project_tag, output_dir


def ensure_user_guide(output_dir: Path, project_tag: str, task_text: str) -> Path:
    guide_candidates = ["README.md", "readme.md", "USER_GUIDE.md", "用户使用手册.md"]
    for candidate in guide_candidates:
        candidate_path = output_dir / candidate
        if candidate_path.is_file():
            return candidate_path

    generated_guide_path = output_dir / "USER_GUIDE.md"
    files: List[str] = []
    for root, _, filenames in os.walk(output_dir):
        for filename in filenames:
            rel_path = Path(root, filename).relative_to(output_dir)
            files.append(str(rel_path))
    files.sort()

    file_list = "\n".join([f"- {file}" for file in files]) if files else "- (暂无文件)"
    lower_files = [file.lower() for file in files]
    is_java_project = any(file == "pom.xml" for file in lower_files) or any(
        file.startswith("src/main/java/") for file in lower_files
    )
    if is_java_project:
        quick_start = """1. 进入交付目录。
2. 确保本机已安装 JDK 17+ 和 Maven。
3. 如需先验证项目是否可编译，执行 `mvn test`。
4. 启动项目使用 `mvn spring-boot:run`，或先打包再运行 `mvn clean package`。"""
        run_hint = "Java 项目可尝试: mvn test 或 mvn spring-boot:run"
    else:
        quick_start = """1. 进入交付目录。
2. 如存在 `requirements.txt`，执行 `pip install -r requirements.txt`。
3. 优先查看 `main.py`、`app.py` 或脚本入口文件。
4. 使用 `python main.py` 或 `python app.py` 启动。"""
        run_hint = "Python 项目可尝试: python main.py 或 python app.py"
    guide_content = f"""# 用户使用手册

## 项目信息
- 项目标识: {project_tag}
- 任务描述: {task_text}

## 交付文件
{file_list}

## 快速开始
{quick_start}

## 说明
本手册由系统自动生成，用于保证每次交付都有可用说明文档。
"""

    generated_guide_path.write_text(guide_content, encoding="utf-8")
    return generated_guide_path


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
    content: str, block_index: int, project_tag: str, code: str
) -> str:
    patterns = [
        r"(?:文件名|filename|file)\s*[:：]\s*([A-Za-z0-9_./\\-]+\.py)",
        r"###\s*([A-Za-z0-9_./\\-]+\.py)",
        r"##\s*([A-Za-z0-9_./\\-]+\.py)",
    ]
    for pattern in patterns:
        match = re.search(pattern, content, flags=re.IGNORECASE)
        if match:
            return match.group(1).replace("\\", "/")

    if "def test_" in code or "pytest" in code:
        return f"{project_tag}_test_{block_index}.py"
    if 'if __name__ == "__main__"' in code:
        return f"{project_tag}_main.py"
    return f"{project_tag}_module_{block_index}.py"


def materialize_code_files(
    messages: Iterable[dict], output_dir: Path, project_tag: str
) -> List[str]:
    import re

    code_block_pattern = re.compile(
        r"```(?:python|py)?\s*(.*?)```", re.DOTALL | re.IGNORECASE
    )
    created_files: List[str] = []
    block_counter = 1

    for message in messages:
        content = message.get("content", "")
        if not isinstance(content, str) or "```" not in content:
            continue

        for match in code_block_pattern.finditer(content):
            code = match.group(1).strip()
            if not code:
                continue

            target_name = _infer_filename_from_message(
                content, block_counter, project_tag, code
            )
            target_path = (output_dir / target_name).resolve()

            if not str(target_path).startswith(str(output_dir.resolve())):
                target_path = output_dir / f"{project_tag}_module_{block_counter}.py"

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(code + "\n", encoding="utf-8")

            rel_path = str(target_path.relative_to(output_dir))
            if rel_path not in created_files:
                created_files.append(rel_path)
            block_counter += 1

    return created_files


def print_delivery_artifacts(output_dir: Path, project_tag: str) -> None:
    print("\n" + "=" * 60)
    print("📦 交付产物信息")
    print("=" * 60)
    print(f"🏷 项目标识: {project_tag}")
    print(f"📁 交付目录: {output_dir}")

    if not output_dir.is_dir():
        print("⚠️ 交付目录不存在，可能本次对话没有生成可执行文件。")
        return

    files: List[str] = []
    for root, _, filenames in os.walk(output_dir):
        for filename in filenames:
            rel_path = Path(root, filename).relative_to(output_dir)
            files.append(str(rel_path))

    if not files:
        print("⚠️ 交付目录为空，可能智能体只给出了方案但未实际落盘。")
        return

    files.sort()
    lower_files = [file.lower() for file in files]
    is_java_project = any(file == "pom.xml" for file in lower_files) or any(
        file.startswith("src/main/java/") for file in lower_files
    )
    run_hint = (
        "Java 项目可尝试: mvn test 或 mvn spring-boot:run"
        if is_java_project
        else "Python 项目可尝试: python main.py 或 python app.py"
    )
    print("📄 生成文件清单:")
    for rel_path in files:
        print(f"  - {rel_path}")

    if is_java_project:
        runnable_candidates = [
            f
            for f in files
            if f.lower().endswith(("pom.xml", "readme.md", "user_guide.md"))
            or f.lower().startswith("src/main/java/")
        ]
    else:
        runnable_candidates = [
            f for f in files if f.lower().endswith((".py", ".sh", ".bat", "readme.md"))
        ]
    if runnable_candidates:
        print("\n▶ 推荐先查看/运行:")
        for rel_path in runnable_candidates[:5]:
            print(f"  - {rel_path}")

    print("\n💡 使用方式:")
    print(f"  1) 进入目录: cd {output_dir}")
    print("  2) 先查看 README.md（若存在）")
    print(f"  3) {run_hint}")
