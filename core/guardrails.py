# pulsecheck/core/guardrails.py
# core/guardrails.py
class FinancialGuardrail:
    def __init__(self, max_auto_approval_amount: float = 500.00):
        self.max_auto_approval_amount = max_auto_approval_amount

    def validate_action(self, strategy: dict, order_amount: float) -> tuple[bool, str]:
        cost = strategy.get("estimated_cost", 0.0)
        # Check strategy cost and total order transaction amount
        if order_amount > self.max_auto_approval_amount or cost > self.max_auto_approval_amount:
            return False, f"Financial limit breached! Order amount (${order_amount}) or remediation cost (${cost}) exceeds automated threshold (${self.max_auto_approval_amount}). Requires Human Authorizer."
        return True, "Within automated financial guardrails."