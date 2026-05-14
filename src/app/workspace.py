from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Tuple


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


def create_delivery_workspace(
    task_text: str, output_root: Path | str
) -> Tuple[str, Path]:
    project_tag = build_project_tag(task_text)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(output_root) / f"{project_tag}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return project_tag, output_dir


def ensure_user_guide(output_dir: Path, project_tag: str, task_text: str) -> Path:
    guide_candidates = ["README.md", "readme.md", "USER_GUIDE.md", "用户使用手册.md"]
    for candidate in guide_candidates:
        candidate_path = output_dir / candidate
        if candidate_path.is_file():
            return candidate_path

    generated_guide_path = output_dir / "USER_GUIDE.md"
    # 确保目录存在
    output_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(
        [
            p.relative_to(output_dir).as_posix()
            for p in output_dir.rglob("*")
            if p.is_file()
        ]
    )
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
    else:
        quick_start = """1. 进入交付目录。
2. 如存在 `requirements.txt`，执行 `pip install -r requirements.txt`。
3. 优先查看 `main.py`、`app.py` 或脚本入口文件。
4. 使用 `python main.py` 或 `python app.py` 启动。"""
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
