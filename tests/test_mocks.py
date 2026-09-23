"""Proves the bug reproduces and the fix resolves it.
Prerequisite: mocks must be running (scripts/start_all.sh).
Run with: uv run pytest tests/test_mocks.py -v
"""
import time
import httpx
import pytest

ORDER = "http://localhost:4001"
BILLING = "http://localhost:4002"
ERP = "http://localhost:4003"


def _running():
    try:
        return httpx.get(f"{ORDER}/health", timeout=1).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _running(), reason="Mocks not running. Start with scripts/start_all.sh")


def _reset_all():
    for svc in (ORDER, BILLING, ERP):
        httpx.post(f"{svc}/reset", timeout=5)


def _seed_order():
    from mocks.common.db import get_conn
    conn = get_conn("order")
    conn.execute(
        "INSERT INTO orders (order_id, customer_id, amount, status, updated_at) "
        "VALUES ('ORD-001', 'ACC-042', 1500.00, 'PENDING', datetime('now'))"
    )
    conn.close()


def _capture_payment():
    httpx.post(f"{BILLING}/payments/capture", json={
        "order_id": "ORD-001", "amount": 1500.00,
        "idempotency_key": "pchk-0001-key", "payment_id": "PAY-001",
    }, timeout=5)


def _wait_for_quiet(seconds=8):
    time.sleep(seconds)


def _get_state(service):
    return httpx.get(f"{service}/state", timeout=5).json()


def test_naive_strategy_reproduces_the_bug():
    _reset_all()
    _seed_order()
    _capture_payment()
    _wait_for_quiet()

    order_state = _get_state(ORDER)
    billing_state = _get_state(BILLING)
    erp_state = _get_state(ERP)

    assert order_state["orders"][0]["status"] == "PENDING", "Order should be stuck in PENDING (the bug)"
    assert billing_state["payments"][0]["status"] == "PAID", "Billing has captured funds"
    assert erp_state["fulfillments"] == [], "ERP never received the trigger"


def test_commit_check_strategy_resolves_the_bug():
    import os
    if os.getenv("IDEMPOTENCY_STRATEGY") != "commit_check":
        pytest.skip("Set IDEMPOTENCY_STRATEGY=commit_check and restart order-service")

    _reset_all()
    _seed_order()
    _capture_payment()
    _wait_for_quiet()

    order_state = _get_state(ORDER)
    erp_state = _get_state(ERP)

    assert order_state["orders"][0]["status"] == "PAID"
    assert len(erp_state["fulfillments"]) == 1
    assert erp_state["fulfillments"][0]["order_id"] == "ORD-001"