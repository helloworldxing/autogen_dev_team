from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Dict, List


@dataclass(frozen=True)
class ExperimentGroup:
    name: str
    enable_rag: bool
    multi_agent: bool
    single_agent_role: str = "engineer"


GROUPS = [
    ExperimentGroup(name="A_full", enable_rag=True, multi_agent=True),
    ExperimentGroup(name="B_no_rag", enable_rag=False, multi_agent=True),
    ExperimentGroup(name="C_single_with_rag", enable_rag=True, multi_agent=False),
]


def resolve_task_file(task_file: Path) -> Path:
    """Resolve task file path with common fallbacks for CLI convenience."""
    if task_file.exists():
        return task_file

    repo_root = Path(__file__).resolve().parent
    candidates = [
        repo_root / task_file,
        repo_root / "test_out_script" / task_file.name,
        repo_root / "test_out_script" / "experiment_tasks.txt",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    searched = [str(task_file), *[str(c) for c in candidates]]
    raise FileNotFoundError(
        "未找到任务文件。请检查 --tasks 参数。已尝试路径:\n- " + "\n- ".join(searched)
    )


def load_tasks(task_file: Path) -> List[str]:
    resolved = resolve_task_file(task_file)
    lines = resolved.read_text(encoding="utf-8").splitlines()
    tasks = [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]
    if not tasks:
        raise ValueError("任务文件为空，请至少提供 1 条任务。")
    return tasks


def run_single(task: str, group: ExperimentGroup, env_base: Dict[str, str]) -> Dict:
    env = dict(env_base)
    env["EXPERIMENT_ENABLE_RAG"] = "true" if group.enable_rag else "false"
    env["EXPERIMENT_MULTI_AGENT"] = "true" if group.multi_agent else "false"
    env["EXPERIMENT_SINGLE_AGENT_ROLE"] = group.single_agent_role
    env["EXP_TASK"] = task

    code = (
        "import json,os;"
        "from src.app.main import run_task;"
        "result=run_task(os.environ['EXP_TASK']);"
        "print('__RESULT__'+json.dumps(result, ensure_ascii=False))"
    )

    start = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(Path(__file__).resolve().parent),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = time.perf_counter() - start

    result_payload = None
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith("__RESULT__"):
            result_payload = line[len("__RESULT__") :]
            break

    run_info: Dict = {
        "ok": proc.returncode == 0 and result_payload is not None,
        "returncode": proc.returncode,
        "elapsed_sec": round(elapsed, 3),
        "stdout_tail": "\n".join(proc.stdout.splitlines()[-20:]),
        "stderr_tail": "\n".join(proc.stderr.splitlines()[-20:]),
        "result": None,
    }

    if result_payload:
        try:
            run_info["result"] = json.loads(result_payload)
        except json.JSONDecodeError:
            run_info["ok"] = False

    return run_info


def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_runs_csv(rows: List[Dict], output_path: Path) -> None:
    headers = [
        "group",
        "task_index",
        "repeat_index",
        "task",
        "ok",
        "returncode",
        "elapsed_sec",
        "session_id",
        "project_tag",
        "output_dir",
        "enable_rag",
        "multi_agent",
        "selected_roles",
        "created_code_files_count",
        "architecture_is_valid",
        "architecture_retry_count",
        "architecture_code_file_count",
        "architecture_primary_language",
        "error_hint",
    ]

    with output_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def write_summary_csv(rows: List[Dict], output_path: Path) -> None:
    grouped: Dict[str, List[Dict]] = {}
    for row in rows:
        grouped.setdefault(row["group"], []).append(row)

    summary_rows: List[Dict] = []
    for group, items in grouped.items():
        total = len(items)
        success = sum(1 for i in items if str(i["ok"]).lower() == "true")
        arch_pass = sum(
            1 for i in items if str(i["architecture_is_valid"]).lower() == "true"
        )

        elapsed_vals = [
            float(i["elapsed_sec"]) for i in items if i["elapsed_sec"] != ""
        ]
        file_vals = [
            int(i["created_code_files_count"])
            for i in items
            if i["created_code_files_count"] != ""
        ]
        retry_vals = [
            int(i["architecture_retry_count"])
            for i in items
            if i["architecture_retry_count"] != ""
        ]

        summary_rows.append(
            {
                "group": group,
                "samples": total,
                "success_rate": round(success / total, 4) if total else 0.0,
                "architecture_pass_rate": round(arch_pass / total, 4) if total else 0.0,
                "avg_elapsed_sec": round(mean(elapsed_vals), 3) if elapsed_vals else "",
                "avg_created_files": round(mean(file_vals), 3) if file_vals else "",
                "avg_architecture_retry": (
                    round(mean(retry_vals), 3) if retry_vals else ""
                ),
            }
        )

    with output_path.open("w", newline="", encoding="utf-8-sig") as f:
        headers = [
            "group",
            "samples",
            "success_rate",
            "architecture_pass_rate",
            "avg_elapsed_sec",
            "avg_created_files",
            "avg_architecture_retry",
        ]
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(summary_rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="A/B/C 批量实验执行与指标汇总")
    parser.add_argument(
        "--tasks",
        default="test_out_script/experiment_tasks.txt",
        help="任务列表文件路径（每行一条任务，# 开头为注释）",
    )
    parser.add_argument("--repeats", type=int, default=3, help="每条任务重复次数")
    parser.add_argument(
        "--output-dir",
        default="test_out_script/experiment_results",
        help="结果输出目录",
    )
    args = parser.parse_args()

    task_file = Path(args.tasks)
    output_dir = Path(args.output_dir)
    ensure_output_dir(output_dir)

    tasks = load_tasks(task_file)
    env_base = dict(os.environ)

    all_rows: List[Dict] = []

    for group in GROUPS:
        for task_index, task in enumerate(tasks, start=1):
            for repeat_index in range(1, args.repeats + 1):
                print(
                    f"[RUN] group={group.name} task={task_index}/{len(tasks)} repeat={repeat_index}/{args.repeats}"
                )
                run_info = run_single(task=task, group=group, env_base=env_base)
                result = run_info.get("result") or {}
                experiment = result.get("experiment") or {}
                arch = result.get("architecture_validation") or {}

                row = {
                    "group": group.name,
                    "task_index": task_index,
                    "repeat_index": repeat_index,
                    "task": task,
                    "ok": run_info["ok"],
                    "returncode": run_info["returncode"],
                    "elapsed_sec": run_info["elapsed_sec"],
                    "session_id": result.get("session_id", ""),
                    "project_tag": result.get("project_tag", ""),
                    "output_dir": result.get("output_dir", ""),
                    "enable_rag": experiment.get("enable_rag", ""),
                    "multi_agent": experiment.get("multi_agent", ""),
                    "selected_roles": ",".join(
                        experiment.get("selected_roles", []) or []
                    ),
                    "created_code_files_count": len(
                        result.get("created_code_files", []) or []
                    ),
                    "architecture_is_valid": arch.get("is_valid", ""),
                    "architecture_retry_count": arch.get("retry_count", ""),
                    "architecture_code_file_count": arch.get("code_file_count", ""),
                    "architecture_primary_language": arch.get("primary_language", ""),
                    "error_hint": run_info["stderr_tail"][:500],
                }
                all_rows.append(row)

    runs_csv = output_dir / "runs.csv"
    summary_csv = output_dir / "summary.csv"
    write_runs_csv(all_rows, runs_csv)
    write_summary_csv(all_rows, summary_csv)

    print("\n实验完成。")
    print(f"逐次结果: {runs_csv}")
    print(f"汇总结果: {summary_csv}")


if __name__ == "__main__":
    main()
