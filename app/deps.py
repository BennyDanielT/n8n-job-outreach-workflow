"""Shared FastAPI dependencies."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

import yaml
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import session_factory
from app.llm import LLM, LLMError, build_llm
from app.schemas import MasterResume


@lru_cache
def _llm() -> LLM:
    return build_llm(get_settings())


def get_llm() -> LLM:
    try:
        return _llm()
    except LLMError as e:
        raise HTTPException(503, f"LLM not configured: {e}") from e


def load_master(path: Path) -> MasterResume:
    with open(path, encoding="utf-8") as f:
        return MasterResume.model_validate(yaml.safe_load(f))


def get_master(s: Settings = Depends(get_settings)) -> MasterResume:
    return load_master(s.master_resume_path)


def get_db(s: Settings = Depends(get_settings)) -> Iterator[Session]:
    with session_factory(s.database_url)() as session:
        yield session


class RateLimiter:
    """Sliding window per client. In-memory: fine for one replica; use Redis when scaling out."""

    def __init__(self, limit: int, window_s: int):
        self.limit, self.window = limit, window_s
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def __call__(self, request: Request) -> None:
        key = request.headers.get("x-forwarded-for", request.client.host if request.client else "?").split(",")[0]
        now, q = time.monotonic(), self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            raise HTTPException(429, "Too many requests. Try again in a few minutes.")
        q.append(now)


tailor_limit = RateLimiter(limit=20, window_s=600)
