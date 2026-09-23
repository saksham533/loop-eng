from .strategies import IdempotencyStrategy, Decision


class NaiveStrategy(IdempotencyStrategy):
    """Determines how to handle a request based on the *logical order's*
    current state rather than solely on whether an idempotency-key row was
    found. This guards against the case where a retry is issued with a
    different idempotency key than the original attempt (e.g. due to a
    client-generated 'retry-N' suffix): callers are expected to resolve
    `current_state` by the underlying order identity, not by the key alone,
    so that a mismatched key on retry still surfaces the true order status
    instead of masquerading as a brand-new request.

    Decision rules:
      1. No prior attempt recorded at all -> PROCESS_NEW.
      2. The order has already reached a terminal PAID state -> the request
         is a duplicate of completed work -> SKIP_AS_DUPLICATE.
      3. A prior attempt exists but the order never reached PAID -> the
         earlier attempt crashed or stalled mid-flight -> RECOVER_PARTIAL,
         so the operation resumes instead of silently no-op'ing or
         re-triggering downstream side effects like ERP forwarding.
    """

    def should_process(self, key, attempt, current_state) -> Decision:
        if attempt is None:
            return Decision.PROCESS_NEW

        if current_state is not None and current_state.get("status") == "PAID":
            return Decision.SKIP_AS_DUPLICATE

        return Decision.RECOVER_PARTIAL