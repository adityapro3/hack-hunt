import asyncio
import inspect
import json
import logging
import threading
from collections.abc import Callable
from queue import Queue
from typing import Any

from fastapi.responses import StreamingResponse


logger = logging.getLogger(__name__)

_SENTINEL = object()


def _format_sse_event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, default=str, separators=(',', ':'))}\n\n"


def stream_admin_job(job_name: str, job: Callable[[Callable[[str], None]], Any]) -> StreamingResponse:
    events: Queue[dict[str, Any] | object] = Queue()

    def emit_log(line: str) -> None:
        events.put({"type": "log", "line": line})

    def run_job() -> None:
        try:
            result = job(emit_log)
            if inspect.isawaitable(result):
                result = asyncio.run(result)
            events.put({"type": "done", "result": result})
        except Exception as exc:
            logger.exception("Admin job %s failed", job_name)
            events.put({"type": "error", "detail": str(exc)})
        finally:
            events.put(_SENTINEL)

    threading.Thread(target=run_job, daemon=True).start()

    async def event_stream():
        while True:
            item = await asyncio.to_thread(events.get)
            if item is _SENTINEL:
                break
            yield _format_sse_event(item)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )