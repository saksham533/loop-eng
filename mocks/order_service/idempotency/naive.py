from .strategies import IdempotencyStrategy, Decision


class NaiveStrategy(IdempotencyStrategy):
    """Assumes: if an attempt row exists, the whole operation succeeded.
    Reality: the process can crash AFTER writing the attempt but BEFORE
    committing order status — so the retry gets silently skipped forever."""

    def should_process(self, key, attempt, current_state) -> Decision:
        if attempt is not None:
            return Decision.SKIP_AS_DUPLICATE
        return Decision.PROCESS_NEW