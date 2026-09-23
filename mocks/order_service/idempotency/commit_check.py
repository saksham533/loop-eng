from .strategies import IdempotencyStrategy, Decision


class CommitCheckStrategy(IdempotencyStrategy):
    """Distinguishes 'attempt recorded' from 'state committed'."""

    def should_process(self, key, attempt, current_state) -> Decision:
        if attempt is None:
            return Decision.PROCESS_NEW
        if current_state and current_state["status"] == "PAID":
            return Decision.SKIP_AS_DUPLICATE
        return Decision.RECOVER_PARTIAL