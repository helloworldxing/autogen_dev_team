from __future__ import annotations

import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List

from flask import Flask, jsonify, render_template, request
from requests.exceptions import ReadTimeout, Timeout

from src.app.main import run_task

BASE_DIR = Path(__file__).resolve().parent.parent

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "web" / "templates"),
    static_folder=str(BASE_DIR / "web" / "static"),
)


@app.get("/")
def index():
    return render_template("index.html")


JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


def _append_event(job_id: str, event: Dict[str, Any]) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        event = {**event, "index": len(job["events"])}
        job["events"].append(event)


def _execute_job(job_id: str, task: str) -> None:
    _append_event(
        job_id, {"type": "status", "stage": "queued", "message": "任务已入队"}
    )
    with JOBS_LOCK:
        if job_id in JOBS:
            JOBS[job_id]["status"] = "running"

    try:

        def event_callback_wrapper(event):
            # 调试：记录所有事件
            import sys

            event_type = event.get("type", "unknown")
            if event_type == "message":
                sender = event.get("sender", "unknown")
                content_len = len(event.get("content", ""))
                sys.stderr.write(
                    f"[WEB-DEBUG] type={event_type}, sender={sender}, len={content_len}\n"
                )
                sys.stderr.flush()
            _append_event(job_id, event)

        result = run_task(task, event_callback=event_callback_wrapper)
        with JOBS_LOCK:
            if job_id in JOBS:
                JOBS[job_id]["status"] = "success"
                JOBS[job_id]["result"] = result
        # 发送任务完成信号
        _append_event(
            job_id, {"type": "status", "stage": "complete", "message": "✅ 任务已完成"}
        )
    except (ReadTimeout, Timeout) as exc:  # pragma: no cover - runtime fallback
        timeout_message = "模型调用读超时，请稍后重试，或将 LLM_TIMEOUT 调大后再执行。"
        with JOBS_LOCK:
            if job_id in JOBS:
                JOBS[job_id]["status"] = "error"
                JOBS[job_id]["error"] = timeout_message
        _append_event(
            job_id,
            {
                "type": "status",
                "stage": "error",
                "message": timeout_message,
            },
        )
    except Exception as exc:  # pragma: no cover - runtime fallback
        with JOBS_LOCK:
            if job_id in JOBS:
                JOBS[job_id]["status"] = "error"
                JOBS[job_id]["error"] = str(exc)
        _append_event(job_id, {"type": "status", "stage": "error", "message": str(exc)})


@app.post("/api/run")
def api_run_task():
    payload = request.get_json(silent=True) or {}
    task = str(payload.get("task", "")).strip()

    if not task:
        return jsonify({"ok": False, "error": "任务不能为空"}), 400

    job_id = str(uuid.uuid4())
    with JOBS_LOCK:
        JOBS[job_id] = {
            "status": "queued",
            "task": task,
            "events": [],
            "result": None,
            "error": None,
        }

    thread = threading.Thread(target=_execute_job, args=(job_id, task), daemon=True)
    thread.start()

    return jsonify({"ok": True, "job_id": job_id})


@app.get("/api/events/<job_id>")
def api_job_events(job_id: str):
    cursor_raw = request.args.get("cursor", "0")
    try:
        cursor = max(0, int(cursor_raw))
    except ValueError:
        cursor = 0

    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return jsonify({"ok": False, "error": "任务不存在"}), 404

        events: List[Dict[str, Any]] = job["events"][cursor:]
        next_cursor = cursor + len(events)

        payload = {
            "ok": True,
            "status": job["status"],
            "events": events,
            "next_cursor": next_cursor,
            "result": job["result"],
            "error": job["error"],
        }

    return jsonify(payload)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
