# pulsecheck/loops/l08_validate.py
import httpx
from typing import List
from core.contracts import ValidationReport, ReplayAssertionResult

class L08_ValidationLoop:
    def __init__(self):
        self.order = "http://localhost:4001"
        self.erp = "http://localhost:4003"

    def execute(self, module_name: str, attempt: int = 1) -> ValidationReport:
        print(f"\n[L08] Executing Sandboxed Replay Verification against live cluster...")
        assertions: List[ReplayAssertionResult] = []
        payload = {"idempotency_key": "pchk-0001-key", "order_id": "ORD-001", "payment_id": "PAY-001", "amount": 1500.0}

        with httpx.Client(timeout=5.0) as client:
            # 1. Reset State & Hot-Swap Strategy
            client.post(f"{self.order}/reset")
            client.post(f"{self.erp}/reset")
            client.post(f"{self.order}/control/strategy", json={"strategy_name": module_name})

            # Seed the initial order state
            client.post(f"{self.order}/webhook", json=payload) # Force the schema init if needed
            client.post(f"{self.order}/reset")
            
            # The mock expects ORD-001 to exist in PENDING state before webhook hits
            import sqlite3
            conn = sqlite3.connect("data/mocks/order.db", isolation_level=None)
            conn.execute("INSERT INTO orders (order_id, customer_id, amount, status, updated_at) VALUES ('ORD-001', 'ACC-042', 1500.00, 'PENDING', datetime('now'))")
            conn.close()

            # 2. Dispatch Webhook 1 (Expect Transient Crash due to SIMULATE_FIRST_CRASH)
            try:
                client.post(f"{self.order}/webhook", json=payload)
            except Exception:
                pass # HTTP 500 expected here

            # Verify Webhook 1 logic via logs
            logs_res = client.get(f"{self.order}/logs").json()
            wh1_decision = next((log["message"] for log in logs_res["logs"] if "decision=" in log["message"]), "MISSING")
            p1 = "decision=PROCESS_NEW" in wh1_decision
            assertions.append(ReplayAssertionResult(step_name="Webhook 1 Evaluation", expected="PROCESS_NEW", actual=wh1_decision, passed=p1))

            # 3. Dispatch Webhook 2 (The Retry)
            wh2_res = client.post(f"{self.order}/webhook", json=payload)
            wh2_decision = wh2_res.json().get("decision", "UNKNOWN") if wh2_res.status_code == 200 else f"HTTP {wh2_res.status_code}"
            
            p2 = wh2_decision == "RECOVER_PARTIAL"
            assertions.append(ReplayAssertionResult(step_name="Webhook 2 Evaluation (Retry)", expected="RECOVER_PARTIAL", actual=wh2_decision, passed=p2))

            # 4. Assert Final Distributed State
            final_order = client.get(f"{self.order}/state").json()
            o_stat = final_order["orders"][0]["status"] if final_order["orders"] else "MISSING"
            p3 = o_stat == "PAID"
            assertions.append(ReplayAssertionResult(step_name="Order Service Final State", expected="PAID", actual=o_stat, passed=p3))

            final_erp = client.get(f"{self.erp}/state").json()
            erp_trig = "TRIGGERED" if final_erp["fulfillments"] else "WAITING"
            p4 = erp_trig == "TRIGGERED"
            assertions.append(ReplayAssertionResult(step_name="ERP Fulfillment Trigger", expected="TRIGGERED", actual=erp_trig, passed=p4))

        all_passed = all(a.passed for a in assertions)
        feedback = None
        if not all_passed:
            failed = [f"{a.step_name}: expected '{a.expected}', got '{a.actual}'" for a in assertions if not a.passed]
            feedback = f"Replay failed: {'; '.join(failed)}. Ensure `should_process` returns RECOVER_PARTIAL when attempt exists but order is PENDING."

        for a in assertions:
            mark = "✅" if a.passed else "❌"
            print(f"    {mark} {a.step_name:30} : Expected [{a.expected}], Got [{a.actual}]")

        return ValidationReport(attempt_number=attempt, passed=all_passed, assertions=assertions, feedback_for_l07=feedback)