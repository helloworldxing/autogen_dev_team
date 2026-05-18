from __future__ import annotations

import json
import queue
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List

import anyio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from requests.exceptions import ReadTimeout, Timeout

from src.app.main import run_task

BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = BASE_DIR / "web" / "templates"
STATIC_DIR = BASE_DIR / "web" / "static"

app = FastAPI()
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request},
    )


@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)


JOBS: Dict[str, Dict[str, Any]] = {}
JOBS_LOCK = threading.Lock()


def _append_event(job_id: str, event: Dict[str, Any]) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        event = {**event, "index": len(job["events"])}
        job["events"].append(event)
        job["queue"].put(event)


def _finalize_job(job_id: str) -> None:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            return
        job["queue"].put(None)


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
        _append_event(job_id, {"type": "result", "result": result})
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
    finally:
        _finalize_job(job_id)


@app.post("/api/run")
def api_run_task(payload: Dict[str, Any]):
    task = str(payload.get("task", "")).strip()

    if not task:
        return JSONResponse(
            status_code=400, content={"ok": False, "error": "任务不能为空"}
        )

    job_id = str(uuid.uuid4())
    with JOBS_LOCK:
        JOBS[job_id] = {
            "status": "queued",
            "task": task,
            "events": [],
            "result": None,
            "error": None,
            "queue": queue.Queue(),
        }

    thread = threading.Thread(target=_execute_job, args=(job_id, task), daemon=True)
    thread.start()

    return {"ok": True, "job_id": job_id}


@app.get("/api/events/{job_id}")
def api_job_events(job_id: str, cursor: int = 0):
    cursor = max(0, cursor)
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="任务不存在")

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

    return payload


@app.get("/api/stream/{job_id}")
async def api_job_stream(job_id: str, cursor: int = 0):
    cursor = max(0, cursor)

    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="任务不存在")
        queue_ref = job["queue"]
        history = list(job["events"][cursor:])
        status = job["status"]

    async def event_stream():
        for event in history:
            yield _format_sse(event)

        if status in {"success", "error"}:
            return

        while True:
            try:
                with anyio.fail_after(15):
                    event = await anyio.to_thread.run_sync(queue_ref.get)
            except TimeoutError:
                yield ": ping\n\n"
                continue

            if event is None:
                return

            yield _format_sse(event)

            with JOBS_LOCK:
                current = JOBS.get(job_id)
                if not current:
                    return
                current_status = current["status"]

            if current_status in {"success", "error"}:
                return

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _format_sse(event: Dict[str, Any]) -> str:
    payload = json.dumps(event, ensure_ascii=False)
    event_id = event.get("index")
    if event_id is None:
        return f"data: {payload}\n\n"
    return f"id: {event_id}\ndata: {payload}\n\n"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.app.web:app", host="127.0.0.1", port=5000, reload=False)
