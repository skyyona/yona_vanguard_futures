"""Core modules for Engine Backend."""

# Expose a stable symbol `execute_order` by aliasing the synchronous implementation
# `execute_order_sync` from the executor module. Tests and callers expect
# `engine_backend.core.execute_order` to be available.
from .order_executor import execute_order_sync as execute_order

__all__ = ["execute_order"]
