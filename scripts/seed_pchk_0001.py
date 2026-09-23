"""Seed PCHK-0001: the saga failure scenario.

Usage:
  python scripts/seed_pchk_0001.py            # seed + run the saga
  python scripts/seed_pchk_0001.py --reset    # reset first
  python scripts/seed_pchk_0001.py --report   # just show state
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import time
import httpx

ORDER = "http://localhost:4001"
BILLING = "http://localhost:4002"
ERP = "http://localhost:4003"


def reset():
    for svc in (ORDER, BILLING, ERP):
        httpx.post(f"{svc}/reset", timeout=5)
    print("[seed] All mocks reset.")


def seed():
    httpx.post(f"{ORDER}/reset", timeout=5)
    from mocks.common.db import get_conn
    conn = get_conn("order")
    conn.execute(
        "INSERT INTO orders (order_id, customer_id, amount, status, updated_at) "
        "VALUES ('ORD-001', 'ACC-042', 1500.00, 'PENDING', datetime('now'))"
    )
    conn.close()
    print("[seed] Order ORD-001 created in PENDING.")

    r = httpx.post(f"{BILLING}/payments/capture", json={
        "order_id": "ORD-001",
        "amount": 1500.00,
        "idempotency_key": "pchk-0001-key",
        "payment_id": "PAY-001",
    }, timeout=5)
    print(f"[seed] Billing capture: {r.json()}")

    print("[seed] Waiting for webhook dispatch + retry...")
    time.sleep(8)


def report():
    print("\n=== Current state ===")
    for name, url in [("ORDER", ORDER), ("BILLING", BILLING), ("ERP", ERP)]:
        state = httpx.get(f"{url}/state", timeout=5).json()
        print(f"\n{name}:")
        for key, rows in state.items():
            for row in rows:
                print(f"  {row}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--reset", action="store_true")
    p.add_argument("--report", action="store_true")
    args = p.parse_args()

    if args.report:
        report()
    else:
        if args.reset:
            reset()
        seed()
        report()
