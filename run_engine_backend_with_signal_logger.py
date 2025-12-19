"""Run the engine backend with extra signal logging to capture who/what triggers shutdown.

Usage:
  python run_engine_backend_with_signal_logger.py [--port 8202]

This is a helper for local debugging — it does not modify application code.
"""
import argparse
import logging
import signal
import sys
from datetime import datetime

from importlib import import_module

LOG_PATH = "engine_backend_signal_debug.log"


def setup_logger():
    logger = logging.getLogger("engine_backend_signal_debug")
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    # also mirror to stdout
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    return logger


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8202)
    args = parser.parse_args()

    logger = setup_logger()
    logger.info("Starting engine backend wrapper (signal logger)")

    def log_signal(signum, frame):
        try:
            name = signal.Signals(signum).name
        except Exception:
            name = str(signum)
        logger.warning(f"Received signal: {signum} ({name}) — frame={frame}")

    # Register common signals
    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(s, log_signal)
        except Exception:
            pass

    # Import app and run uvicorn programmatically so we capture exceptions
    try:
        mod = import_module("engine_backend.app_main")
        app = getattr(mod, "app", None)
        if app is None:
            logger.error("engine_backend.app_main.app not found — cannot run")
            sys.exit(2)

        import uvicorn

        logger.info(
            f"Running uvicorn for engine_backend.app_main:app on port {args.port}"
        )
        # run with lifetime blocking call
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="debug")

    except Exception as e:
        logger.exception("Exception while running engine backend: %s", e)
        raise
    finally:
        logger.info("Wrapper exiting at %s", datetime.utcnow().isoformat())


if __name__ == "__main__":
    main()
