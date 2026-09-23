# PR: fix(order_service): prevent duplicate ERP fulfillment on crash-interrupted idempotency commit

**Branch:** `synapse/fix-pchk-0001-corr`
**Target:** `main`

## Context & Problem
The order/payment processor is vulnerable to a critical duplicate-fulfillment bug. When the service crashes after executing business logic (charging payment, advancing order status) but before persisting the idempotency-key record, a client-initiated retry generates a **new** idempotency key (`pchk-0001-key-retry-1`) rather than reusing the original (`pchk-0001-key`). Since the naive idempotency implementation keys its duplicate-detection solely on the literal key value, it has no way to recognize the retry as belonging to the same logical order operation, resulting in the order being processed a second time and a duplicate ERP fulfillment trigger.

## Root Cause Analysis
The root cause is a **non-atomic commit boundary** combined with **key-based (not resource-based) idempotency checking**:

1. The processor executes side-effecting business logic (order status transition, ERP trigger) and only *afterward* attempts to commit the idempotency-key record.
2. A transient crash between "business logic execution" and "status commit" leaves the system in an inconsistent state: the original key `pchk-0001-key` was never durably recorded as processed, even though partial/full business effects may have already occurred.
3. Client-side retry logic generates a fresh idempotency key (`key-retry-1`) instead of reusing the original key for the same logical request, which is a common but incorrect retry pattern when no key persistence confirmation was received.
4. The naive idempotency store has no concept of a "logical operation/order ID" separate from the "idempotency key" — it cannot correlate `key-retry-1` back to the in-flight/crashed `pchk-0001-key` operation, so it correctly-but-wrongly classifies it as `PROCESS_NEW`.

This is a textbook **write-ahead idempotency gap**: the idempotency record must be committed (or at least marked "in-progress") *before* irreversible side effects (ERP calls) are triggered, not after.

## Validation & Verification Proof
Sandbox regression suite executed against the patched `naive.py` idempotency handler and order processing flow:

- Reproduced the exact incident sequence (crash-before-commit on `pchk-0001-key`, followed by retry with `pchk-0001-key-retry-1`).
- Verified that the fix enforces write-ahead marking of the idempotency record (`IN_PROGRESS` state persisted prior to ERP trigger) so that a crash mid-operation leaves a recoverable record rather than a silent gap.
- Verified retries are now correlated via a stable logical order/request identifier rather than solely the transient client-generated key, preventing a second ERP trigger even when the client mints a new key on retry.
- Full existing idempotency test suite (duplicate detection, concurrent request handling, TTL expiry, crash-recovery simulation) executed in sandbox.

**Result: All tests passed.**

## Risk & Rollback Strategy
**Risk:** Low-to-moderate. The change affects the commit ordering and correlation logic of a core order-processing safety mechanism. Any regression could cause requests to be incorrectly flagged as duplicates (false-positive SKIP), blocking legitimate new orders, rather than the prior failure mode of false-negative duplicate ERP triggers. This is considered a safer failure direction but should be monitored closely.

**Rollback:**
1. This is a mock/reference implementation (`mocks/order_service/idempotency/naive.py