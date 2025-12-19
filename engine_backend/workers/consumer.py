"""Redis Streams consumer for Engine Backend POC.

Consumes messages from a Redis stream (default `orders_stream`) and processes them.
This is a proof-of-concept: production-grade consumer should include robust error handling,
dead-letter queue, retries, monitoring, and graceful shutdown.
"""
import os
import time
import json
import logging
import socket
import threading

try:
    import redis
except Exception:
    redis = None

from engine_backend.core.order_store import persist_order
from engine_backend.core.order_executor import execute_order_sync
from engine_backend.core.strategy_store import upsert_strategy

from backend.utils.config_loader import ENGINE_BROKER_URL, ENGINE_BROKER_STREAM

logger = logging.getLogger(__name__)

# readiness event for tests/coordination
_ready_event = threading.Event()


def is_ready() -> bool:
    return _ready_event.is_set()


def wait_until_ready(timeout: float = 5.0) -> bool:
    """Block until consumer is ready or timeout (seconds). Returns True if ready."""
    return _ready_event.wait(timeout=timeout)


def get_redis():
    if redis is None:
        raise RuntimeError("redis library not installed; pip install redis to use consumer")
    return redis.from_url(ENGINE_BROKER_URL)


def run_consumer(group_name: str = "engine_group", consumer_name: str = None, block_ms: int = 5000, stop_event=None):
    """Run the consumer loop.

    Args:
        group_name: Redis consumer group name.
        consumer_name: unique consumer name.
        block_ms: block timeout for XREADGROUP in milliseconds.
        stop_event: optional threading.Event; if set, the loop will exit.
    """
    if consumer_name is None:
        consumer_name = f"{socket.gethostname()}-{os.getpid()}"
    if stop_event is None:
        # create a dummy event if not provided so we can check .is_set()
        try:
            import threading as _th
            stop_event = _th.Event()
        except Exception:
            stop_event = None

    r = get_redis()
    stream = ENGINE_BROKER_STREAM

    # Create consumer group if not exists
    try:
        r.xgroup_create(stream, group_name, id="$", mkstream=True)
        logger.info(f"Created consumer group {group_name} on stream {stream}")
    except Exception:
        # ignore if group already exists
        logger.info(f"Consumer group {group_name} may already exist")

    logger.info(f"Starting consumer {consumer_name} for stream {stream} (group={group_name})")
    # signal readiness to callers/tests
    try:
        _ready_event.set()
    except Exception:
        pass

    while True:
        if stop_event is not None and stop_event.is_set():
            logger.info("Stop event set; exiting consumer loop")
            break
        try:
            entries = r.xreadgroup(group_name, consumer_name, {stream: '>'}, count=1, block=block_ms)
            if not entries:
                continue

            for st, msgs in entries:
                for msg_id, fields in msgs:
                    try:
                        data_raw = fields.get(b"data") or fields.get("data")
                        if isinstance(data_raw, bytes):
                            data_raw = data_raw.decode("utf-8")
                        payload = json.loads(data_raw)
                        logger.info(f"Received message {msg_id}: {payload}")

                        mtype = payload.get("type") or payload.get("command") or payload.get("action")
                        if mtype == "ORDER":
                            # Expect payload to contain order fields similar to OrderRequest
                            order = {
                                "engine": payload.get("engine"),
                                "symbol": payload.get("symbol"),
                                "side": payload.get("side"),
                                "type": payload.get("order_type") or payload.get("type") or "MARKET",
                                "quantity": payload.get("quantity"),
                                "price": payload.get("price"),
                                "reduceOnly": payload.get("reduceOnly", False),
                                "status": "PENDING",
                            }
                            oid = persist_order(order)
                            logger.info(f"Persisted order {oid} from stream message {msg_id}")
                            # execute synchronously (in POC this runs in same process)
                            res = execute_order_sync(oid)
                            logger.info(f"Execution result for {oid}: {res}")

                        elif mtype == "PREPARE_SYMBOL":
                            # Handle platform command: persist as a control record or trigger other logic.
                            logger.info(f"Received PREPARE_SYMBOL for {payload.get('symbol')} (engine={payload.get('engine')})")
                            # For POC, persist a lightweight control record
                            ctrl = {
                                "engine": payload.get("engine"),
                                "symbol": payload.get("symbol"),
                                "side": "PREPARE",
                                "type": "CONTROL",
                                "quantity": 0,
                                "status": "PROCESSED",
                            }
                            persist_order(ctrl)
                        elif mtype == "STRATEGY_ASSIGNED":
                            # Persist assigned strategy configuration for engine-side use
                            try:
                                cfg = {
                                    "symbol": payload.get("symbol"),
                                    "interval": payload.get("interval"),
                                    "engine": payload.get("engine"),
                                    "parameter_set_id": payload.get("parameter_set_id"),
                                    "parameters": payload.get("parameters") or {},
                                    "assigned_at": payload.get("assigned_at"),
                                    "assigned_by": payload.get("assigned_by"),
                                    "note": payload.get("note"),
                                }
                                sid = upsert_strategy(cfg)
                                logger.info(
                                    "Upserted strategy config id=%s for %s (engine=%s)",
                                    sid,
                                    cfg.get("symbol"),
                                    cfg.get("engine"),
                                )
                            except Exception as cfg_ex:
                                logger.exception("Failed to persist STRATEGY_ASSIGNED config: %s", cfg_ex)
                        else:
                            logger.warning(f"Unknown message type: {mtype}")

                        # Acknowledge message
                        r.xack(stream, group_name, msg_id)
                        logger.info(f"Acknowledged message {msg_id}")

                    except Exception as ex:
                        logger.exception(f"Failed to process message {msg_id}: {ex}")
                        # In POC we ack to avoid blocking; production should move to DLQ
                        try:
                            r.xack(stream, group_name, msg_id)
                        except Exception:
                            pass

        except Exception as e:
            logger.exception(f"Consumer loop error: {e}")
            # check stop_event periodically
            if stop_event is not None and stop_event.is_set():
                logger.info("Stop event set during exception; exiting")
                break
            time.sleep(1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_consumer()
