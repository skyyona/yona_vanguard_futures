"""Simple Redis Stream producer helper used by Live Backend to publish orders/commands.
This module uses `redis` (redis-py). For POC, errors are logged and not fatal.
"""
import logging
import json
from typing import Dict, Any

try:
    import redis
except Exception:
    redis = None

from backend.utils.config_loader import ENGINE_BROKER_URL, ENGINE_BROKER_STREAM

logger = logging.getLogger(__name__)


def get_redis():
    if redis is None:
        raise RuntimeError("redis library is not available; install redis package to use broker")
    return redis.from_url(ENGINE_BROKER_URL)


def publish_to_stream(payload: Dict[str, Any], stream: str = None) -> str:
    """Publish a dict payload to the configured Redis stream. Returns XADD id.

    payload values are JSON-encoded under field 'data'.
    """
    s = stream or ENGINE_BROKER_STREAM
    try:
        r = get_redis()
        # store JSON string under 'data' field
        xid = r.xadd(s, {"data": json.dumps(payload)})
        logger.info(f"Published message to stream {s}: id={xid}")
        return xid
    except Exception as e:
        logger.error(f"Failed to publish to redis stream {s}: {e}")
        return ""
