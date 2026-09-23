# pulsecheck/services/circuit_breaker.py
import time
from typing import Dict, Any

class CircuitBreakerOpenException(Exception):
    """Raised when an external call is attempted on an open circuit."""
    pass

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 60.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        # Key: service_name -> {"failures": int, "opened_at": float, "state": str}
        self.registry: Dict[str, Dict[str, Any]] = {}

    def _get_entry(self, service_key: str) -> Dict[str, Any]:
        if service_key not in self.registry:
            self.registry[service_key] = {"failures": 0, "opened_at": 0.0, "state": "CLOSED"}
        return self.registry[service_key]

    def can_execute(self, service_key: str) -> bool:
        entry = self._get_entry(service_key)
        if entry["state"] == "OPEN":
            if time.time() - entry["opened_at"] > self.recovery_timeout:
                entry["state"] = "HALF_OPEN"
                return True
            return False
        return True

    def record_success(self, service_key: str):
        entry = self._get_entry(service_key)
        entry["failures"] = 0
        entry["state"] = "CLOSED"

    def record_failure(self, service_key: str):
        entry = self._get_entry(service_key)
        entry["failures"] += 1
        if entry["failures"] >= self.failure_threshold:
            entry["state"] = "OPEN"
            entry["opened_at"] = time.time()
            print(f"[CIRCUIT_BREAKER] Threshold breached. Circuit OPEN for: {service_key}")

# Global singleton
circuit_breaker = CircuitBreaker()