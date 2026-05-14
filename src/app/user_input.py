"""User input helpers."""

from __future__ import annotations


def prompt_task() -> str:
    print("\n请输入你的任务描述（支持多行，输入空行结束）：")
    while True:
        lines = []
        while True:
            line = input()
            if line.strip() == "":
                break
            lines.append(line)

        task_text = "\n".join(lines).strip()
        if task_text:
            return task_text

        print("任务不能为空，请重新输入：")
