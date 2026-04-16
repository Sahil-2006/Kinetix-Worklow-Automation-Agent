from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from redis import Redis
from rq import Queue

from .core.config import REDIS_URL

logger = logging.getLogger(__name__)

_redis: Redis | None = None
_queue: Queue | None = None


def get_redis() -> Optional[Redis]:
    global _redis
    if not REDIS_URL:
        return None
    if _redis is None:
        _redis = Redis.from_url(REDIS_URL)
    return _redis


def get_queue() -> Optional[Queue]:
    global _queue
    conn = get_redis()
    if conn is None:
        return None
    if _queue is None:
        _queue = Queue("kinetix", connection=conn, default_timeout=300)
    return _queue


def enqueue_job(func_path: str, *args: Any, **kwargs: Any):
    queue = get_queue()
    if queue is None:
        return None
    try:
        return queue.enqueue(func_path, *args, **kwargs)
    except Exception as exc:
        logger.warning("Queue enqueue failed: %s", exc)
        return None
