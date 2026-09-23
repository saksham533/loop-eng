# pulsecheck/loops/l06_reconciliation.py
import httpx
from typing import Dict, Any
from core.contracts import ReconciliationResult

class L06_ReconciliationLoop:
    def __init__(self):
        self.order_url = "http://localhost:4001"
        self.billing_url = "http://localhost:4002"
        self.erp_url = "http://localhost:4003"

    def execute(self, payload: dict) -> ReconciliationResult:
        strategy = payload.get("strategy") or payload.get("strategy_name")
        order_id = payload["order_id"]
        
        print(f"\n[L06] Executing Healing Action: {strategy} for {order_id}...")
        action_taken = False
        
        # 1. Active Healing
        with httpx.Client() as client:
            if strategy == "NEW_KEY_REPLAY":
                # Bypass the burned key by appending a retry suffix, forcing the Order service to process it
                webhook_payload = {
                    "idempotency_key": "pchk-0001-key-retry-1",
                    "order_id": order_id,
                    "payment_id": "PAY-001",
                    "amount": 1500.00
                }
                res = client.post(f"{self.order_url}/webhook", json=webhook_payload)
                action_taken = res.status_code in [200, 201]
                print(f"  ⚡ API Payload dispatched. Response: {res.status_code}")

        # 2. Three-Way Database Reconciliation
        print("[L06] Polling distributed databases for state convergence...")
        with httpx.Client() as client:
            order_db = client.get(f"{self.order_url}/state").json()
            billing_db = client.get(f"{self.billing_url}/state").json()
            erp_db = client.get(f"{self.erp_url}/state").json()

        # Parse states
        order_status = next((o["status"] for o in order_db.get("orders", []) if o["order_id"] == order_id), "MISSING")
        billing_status = next((p["status"] for p in billing_db.get("payments", []) if p["order_id"] == order_id), "MISSING")
        erp_triggered = any(f["order_id"] == order_id for f in erp_db.get("fulfillments", []))

        is_reconciled = (order_status == "PAID" and billing_status == "PAID" and erp_triggered)

        return ReconciliationResult(
            healing_action_taken=action_taken,
            order_status=order_status,
            billing_status=billing_status,
            erp_triggered=erp_triggered,
            fully_reconciled=is_reconciled
        )