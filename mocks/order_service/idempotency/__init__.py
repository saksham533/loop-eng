"""Idempotency strategy loader. Selected by env var IDEMPOTENCY_STRATEGY. Default: 'naive' (buggy)."""
import os
from .strategies import IdempotencyStrategy, Decision


def load_strategy() -> IdempotencyStrategy:
    name = os.getenv("IDEMPOTENCY_STRATEGY", "naive")
    if name == "naive":
        from .naive import NaiveStrategy
        return NaiveStrategy()
    if name == "commit_check":
        from .commit_check import CommitCheckStrategy
        return CommitCheckStrategy()
    raise ValueError(f"Unknown idempotency strategy: {name}")