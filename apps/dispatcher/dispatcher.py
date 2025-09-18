"""Lightweight dispatcher that feeds queued jobs to available workers.

- Exposes POST /enqueue for new jobs (same payload as worker /run expects).
- Tracks worker availability; only forwards a job when a worker is idle.
- Worker callbacks hit POST /cb, which marks the worker free and optionally
  forwards the payload back to the original application callback.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel


class GitUser(BaseModel):
    name: str
    email: str


class JobInput(BaseModel):
    jobId: Optional[str] = None
    repo: str
    branch: str
    base: str
    task: str
    instructions: Optional[str] = None
    changes: List[Dict[str, Any]] = []
    callbackUrl: Optional[str] = None
    callbackSecret: Optional[str] = None
    gitUser: Optional[GitUser] = None
    githubToken: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


WORKERS = [url.strip() for url in os.getenv("WORKERS", "").split(",") if url.strip()]
if not WORKERS:
    raise RuntimeError("WORKERS environment variable is required")

DISPATCHER_PORT = int(os.getenv("DISPATCHER_PORT", "8099"))
CALLBACK_SECRET = os.getenv("CALLBACK_SECRET", "")
ORIGINAL_CALLBACK_URL = os.getenv("ORIGINAL_CALLBACK_URL", "")
MAX_QUEUE = int(os.getenv("MAX_QUEUE", "1000"))

app = FastAPI(title="Codimir Worker Dispatcher")

queue: asyncio.Queue[JobInput] = asyncio.Queue(maxsize=MAX_QUEUE)
worker_status: Dict[str, bool] = {worker: True for worker in WORKERS}
status_lock = asyncio.Lock()


async def post_json(url: str, payload: Dict[str, Any], headers: Dict[str, str] | None = None) -> None:
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(url, json=payload, headers=headers or {})
        response.raise_for_status()


def now_ms() -> int:
    return int(time.time() * 1000)


async def scheduler_loop() -> None:
    while True:
        job = await queue.get()
        assigned = False
        while not assigned:
            async with status_lock:
                target = next((worker for worker, free in worker_status.items() if free), None)
                if target:
                    worker_status[target] = False
            if not target:
                await asyncio.sleep(0.25)
                continue

            original_callback = job.callbackUrl or ORIGINAL_CALLBACK_URL or ""
            metadata = dict(job.metadata or {})
            metadata["_dispatcher"] = {
                "assigned_worker": target,
                "original_callback_url": original_callback,
                "enqueued_at": now_ms(),
            }

            payload = job.model_copy(update={
                "jobId": job.jobId or f"disp-{uuid.uuid4()}",
                "callbackUrl": f"http://dispatcher:{DISPATCHER_PORT}/cb",
                "callbackSecret": CALLBACK_SECRET,
                "metadata": metadata,
            })

            try:
                await post_json(f"{target}/run", payload.model_dump())
            except Exception:
                async with status_lock:
                    worker_status[target] = True
                await asyncio.sleep(1.0)
                continue

            assigned = True


@app.on_event("startup")
async def _startup() -> None:
    asyncio.create_task(scheduler_loop())


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "workers": [{"url": worker, "free": worker_status[worker]} for worker in WORKERS],
        "queued": queue.qsize(),
    }


@app.post("/enqueue")
async def enqueue(job: JobInput) -> Dict[str, Any]:
    if queue.full():
        raise HTTPException(status_code=429, detail="Queue is full")
    await queue.put(job)
    position = queue.qsize()
    return {"accepted": True, "jobId": job.jobId, "position": position}


@app.post("/cb")
async def callback(request: Request) -> Dict[str, Any]:
    try:
        body = await request.json()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    # Accept either header name from worker or SDK
    secret = (
        request.headers.get("x-callback-secret")
        or request.headers.get("x-ci-callback-secret")
        or body.get("secret")
    )
    if CALLBACK_SECRET and secret != CALLBACK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid callback secret")

    dispatcher_meta = (body.get("metadata") or {}).get("_dispatcher") or {}
    assigned_worker = dispatcher_meta.get("assigned_worker")
    if assigned_worker:
        async with status_lock:
            if assigned_worker in worker_status:
                worker_status[assigned_worker] = True

    original_callback = dispatcher_meta.get("original_callback_url") or ORIGINAL_CALLBACK_URL
    if original_callback:
        try:
            await post_json(original_callback, body, headers={"x-callback-secret": CALLBACK_SECRET})
        except Exception:
            pass

    return {"ok": True}

