# pulsecheck/services/system_tools.py
import httpx
from services.circuit_breaker import circuit_breaker, CircuitBreakerOpenException

ORDER_SERVICE_URL = "http://localhost:4001"
BILLING_SERVICE_URL = "http://localhost:4002"
ERP_SERVICE_URL = "http://localhost:4003"

def fetch_order_logs(order_id: str, window_minutes: int = 10) -> list:
    """Tool: Queries local order service execution logs around the incident window."""
    if not circuit_breaker.can_execute("ORDER_SERVICE"):
        raise CircuitBreakerOpenException("Circuit open for ORDER_SERVICE")
    try:
        res = httpx.get(f"{ORDER_SERVICE_URL}/logs?order_id={order_id}&window={window_minutes}", timeout=5.0)
        if res.status_code == 200:
            circuit_breaker.record_success("ORDER_SERVICE")
            return res.json()
        circuit_breaker.record_failure("ORDER_SERVICE")
        return [{"error": f"Order service returned HTTP {res.status_code}"}]
    except Exception as e:
        circuit_breaker.record_failure("ORDER_SERVICE")
        return [{"error": f"Failed to connect to Order Service: {str(e)}"}]

def fetch_billing_logs(payment_id: str, window_minutes: int = 10) -> list:
    """Tool: Queries billing gateway webhook and payment logs."""
    if not circuit_breaker.can_execute("BILLING_SERVICE"):
        raise CircuitBreakerOpenException("Circuit open for BILLING_SERVICE")
    try:
        res = httpx.get(f"{BILLING_SERVICE_URL}/logs?payment_id={payment_id}&window={window_minutes}", timeout=5.0)
        if res.status_code == 200:
            circuit_breaker.record_success("BILLING_SERVICE")
            return res.json()
        circuit_breaker.record_failure("BILLING_SERVICE")
        return [{"error": f"Billing service returned HTTP {res.status_code}"}]
    except Exception as e:
        circuit_breaker.record_failure("BILLING_SERVICE")
        return [{"error": f"Failed to connect to Billing Service: {str(e)}"}]

def fetch_erp_logs(order_id: str) -> list:
    """Tool: Queries downstream ERP fulfillment trigger queue."""
    if not circuit_breaker.can_execute("ERP_SERVICE"):
        raise CircuitBreakerOpenException("Circuit open for ERP_SERVICE")
    try:
        res = httpx.get(f"{ERP_SERVICE_URL}/logs?order_id={order_id}", timeout=5.0)
        if res.status_code == 200:
            circuit_breaker.record_success("ERP_SERVICE")
            return res.json()
        circuit_breaker.record_failure("ERP_SERVICE")
        return [{"error": f"ERP service returned HTTP {res.status_code}"}]
    except Exception as e:
        circuit_breaker.record_failure("ERP_SERVICE")
        return [{"error": f"Failed to connect to ERP Service: {str(e)}"}]

AVAILABLE_TOOLS = {
    "fetch_order_logs": fetch_order_logs,
    "fetch_billing_logs": fetch_billing_logs,
    "fetch_erp_logs": fetch_erp_logs
}