# Blameless Post-Mortem: pchk-0001-corr

## 1. Executive Summary & Impact Metric

On the date of record, a payment/order processing transaction identified by idempotency key `pchk-0001-key` suffered a **crash-induced state desynchronization** between business-logic execution and idempotency-record persistence. The result was a duplicate ERP fulfillment event for a single customer order.

| Metric | Value |
|---|---|
| **Incident ID** | pchk-0001-corr |
| **Severity** | HIGH |
| **Classification** | Unclassified (pending taxonomy assignment) |
| **Blast Radius (infra nodes)** | 0 nodes — failure is transactional/application-layer, not infrastructure-layer |
| **Affected Transactions** | 1 confirmed (order tied to `pchk-0001-key`) |
| **Duplicate Fulfillments Triggered** | 1 (second ERP fulfillment call) |
| **Financial Risk Exposure** | Direct — duplicate shipment/billing risk per affected order; systemic risk scales with retry volume under crash-prone windows |
| **Remediation Status** | **Not yet applied** — root cause identified, fix outstanding |

**Risk statement:** Because the underlying defect is a race between business-logic execution and idempotency-key commit, this is not a one-off anomaly but a **systemic exposure** present on every request path that (a) performs side-effecting business logic and (b) commits idempotency state as a separate, non-atomic step. Until remediated, the defect can recur on any retried request that intersects a mid-transaction crash window, with severity scaling linearly with retry-driven traffic and ERP fulfillment cost per duplicate.

---

## 2. Chronological Incident Timeline

> **Note on evidentiary basis:** The SQLite audit trail queried for this incident returned **zero rows**. No persisted audit records exist for the `pchk-0001-key` transaction lifecycle, which is itself a material finding (see Section 3, Why #4). The timeline below is reconstructed from the documented root-cause narrative and system-behavior inference; it should be treated as a **best-effort sequence reconstruction**, not a verified audit-log extract, and is flagged accordingly.

| Step | Timestamp | Actor / Component | Action Taken | Audit Evidence |
|---|---|---|---|---|
| 1 | T+0.000s (reconstructed) | Client | Submits order request with idempotency key `pchk-0001-key` | ❌ No audit row found |
| 2 | T+0.020s (reconstructed) | Payment/Order Processor | Receives request; begins business-logic execution (payment authorization, order-state computation) | ❌ No audit row found |
| 3 | T+0.180s (reconstructed) | Payment/Order Processor | Completes business logic successfully; prepares idempotency-key/order-status record for commit | ❌ No audit row found |
| 4 | T+0.185s (reconstructed) | Payment/Order Processor | **Process crash** occurs prior to commit of idempotency/order-status record | ❌ No audit row found (crash prevented write) |
| 5 | T+~5s (reconstructed, client-side retry interval) | Client | Times out awaiting response; issues retry with **new** idempotency key `pchk-0001-key-retry-1` | ❌ No audit row found |
| 6 | T+~5.05s (reconstructed) | Payment/Order Processor | Idempotency lookup for `pchk-0001-key-retry-1` finds no match (correctly — it is a novel key) and classifies request as `PROCESS_NEW` | ❌ No audit row found |
| 7 | T+~5.20s (reconstructed) | Payment/Order Processor → ERP System | Executes second, duplicate fulfillment call for the same underlying order | ❌ No audit row found |
| 8 | Post-incident | Reliability/Monitoring | Discrepancy detected (duplicate ERP fulfillment for single order); incident opened as `pchk-0001-corr` | Manual/downstream detection — origin unspecified in available records |

**Timeline integrity finding:** The absence of *any* rows in the audit store for a HIGH-severity financial transaction is a standalone defect and is treated as a first-class remediation item, not merely a reporting inconvenience.

---

## 3. Deep Root-Cause Analysis (5 Whys Framework)

**Problem statement:** A single customer order received two ERP fulfillment executions.

**Why #1 — Why did the order receive two ERP fulfillments?**
Because the retried request (`pchk-0001-key-retry-1`) was classified as `PROCESS_NEW` rather than as a duplicate of the original, already-fulfilled request.

**Why #2 — Why was the retry classified as `PROCESS_NEW` instead of a duplicate?**
Because the retry arrived with a **different idempotency key** than the original request, and the system's duplicate-detection logic keys exclusively off exact idempotency-key match rather than off a stable, order-level correlation identifier.

**Why