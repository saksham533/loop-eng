from .strategies import IdempotencyStrategy, Decision


class DynamicStrategy(IdempotencyStrategy):
    """Distinguishes between an idempotency attempt being *recorded* and the
    underlying business transaction actually being *committed*.

    The naive strategy conflated these two facts: it treated the mere
    existence of an attempt row as proof that the entire operation
    (including the order status commit and downstream ERP forwarding)
    had completed successfully. That assumption breaks under a very
    common failure mode in distributed systems: a process crash between
    two writes that are not covered by a single atomic transaction.

    Sequence that must be handled correctly:
      1. Webhook attempt 1 arrives -> attempt key written (PROCESS_NEW).
      2. Process crashes before order status is committed.
      3. Webhook attempt 2 (retry) arrives -> attempt key already exists.

    A correct strategy must inspect the *actual* downstream state
    (current_state["status"]) rather than trusting the attempt record
    alone, because the attempt record only proves that processing was
    *started*, not that it *finished*.

    Decision matrix:
      - attempt is None                          -> PROCESS_NEW
          (first time we've ever seen this idempotency key)
      - attempt exists AND status == 'PAID'      -> SKIP_AS_DUPLICATE
          (the full transaction, including commit, has already
           completed successfully; reprocessing would cause a
           duplicate charge/order/ERP trigger)
      - attempt exists AND status != 'PAID'      -> RECOVER_PARTIAL
          (an attempt was recorded but the order was never committed
           to a terminal success state -- this is a crash-recovery
           scenario, not a duplicate. The retry must be allowed to
           resume/complete the transaction: commit order status and
           forward to ERP, rather than being silently dropped.)
    """

    TERMINAL_SUCCESS_STATUS = "PAID"

    def should_process(self, key, attempt, current_state) -> Decision:
        # No prior attempt recorded at all -> genuinely new work.
        if attempt is None:
            return Decision.PROCESS_NEW

        # Safely extract status; default to something that is not the
        # terminal success status so ambiguous/missing state is treated
        # as recoverable rather than silently skipped.
        status = None
        if current_state is not None:
            status = current_state.get("status")

        # Attempt exists AND the downstream state is fully committed:
        # this really is a duplicate delivery of an already-completed
        # operation. Safe to skip.
        if status == self.TERMINAL_SUCCESS_STATUS:
            return Decision.SKIP_AS_DUPLICATE

        # Attempt exists but state was never committed to success
        # (e.g. still PENDING, or missing/unknown). This indicates a
        # crash between recording the attempt and committing the
        # order state. The retry must be used to recover/complete the
        # transaction rather than being dropped.
        return Decision.RECOVER_PARTIAL
