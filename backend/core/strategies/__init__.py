"""Compatibility re-exports for strategy implementations.

After migrating strategy implementations into `backtesting_backend.strategies`,
we re-export the public strategy symbols here so existing imports in the Live
Backend continue to resolve. This file acts as a compatibility shim and should
be removed once the cutover is finalized.
"""

from backtesting_backend.strategies import *  # re-export all canonical strategy symbols

try:
    __all__
except NameError:
    __all__ = [k for k in globals().keys() if not k.startswith("_")]
