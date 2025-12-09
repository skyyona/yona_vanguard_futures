"""backtesting_backend.engine_host package shim for tests

This package provides a minimal engine_host module when the real
implementation isn't present in the checked-out branch. It's intended
only to satisfy imports during local test runs and CI while migration
work is in progress.
"""

__all__ = ["main"]
