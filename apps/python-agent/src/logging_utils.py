import os
import requests
from typing import Any, Optional

def _emit_console(payload: dict) -> None:
    if os.environ.get("LOG_TO_STDOUT", "1") != "1":
        return
    status = payload.get("status", "progress")
    message = payload.get("message", "")
    run_id = payload.get("runId", "")
    prefix = f"[{status}]" + (f"[{run_id}]" if run_id else "")
    print(f"{prefix} {message}", flush=True)
    logs = payload.get("logs")
    if logs:
        if isinstance(logs, str):
            print(logs, flush=True)
        else:
            print(str(logs), flush=True)

def _post(url: str, secret: str, payload: dict) -> None:
    _emit_console(payload)
    try:
        requests.post(
            url,
            headers={"Content-Type": "application/json", "x-ci-callback-secret": secret},
            json=payload,
            timeout=20,
        )
    except Exception:
        pass

def progress(url: str, secret: str, job_id: str, message: str, logs: Optional[Any] = None, run_id: Optional[str] = None) -> None:
    payload = {"jobId": job_id, "status": "progress", "message": message}
    if logs is not None:
        payload["logs"] = logs
    if run_id:
        payload["runId"] = run_id
    _post(url, secret, payload)

def done(url: str, secret: str, job_id: str, ok: bool, message: str, logs: Optional[Any] = None, run_id: Optional[str] = None) -> None:
    payload = {"jobId": job_id, "status": "success" if ok else "error", "message": message}
    if logs is not None:
        payload["logs"] = logs
    if run_id:
        payload["runId"] = run_id
    _post(url, secret, payload)

