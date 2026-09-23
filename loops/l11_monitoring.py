# loops/l11_monitoring.py
import json
from core.opencode_service import OpenCodeService

class L11_MonitoringLoop:
    def __init__(self):
        self.client = OpenCodeService()

    def execute(self, payload: dict) -> dict:
        incident_id = payload.get("incident_id")
        print(f"\n[L11] Initiating Continuous Monitoring for {incident_id}...")
        
        if not payload.get("sandbox_verified"):
            print("  ⏭️ [L11] Monitoring skipped; patch was not verified.")
            return {"regression_detected": False}

        service = payload.get("service")
        simulated_telemetry = self._poll_recent_telemetry(service)
        
        prompt = f"""
        Analyze the post-deployment telemetry for regressions.
        Original Incident: {incident_id}
        Service: {service}
        Post-Patch Telemetry: {simulated_telemetry}
        Root Cause Diagnosed: {payload.get('root_cause')}

        If the error rate has spiked, or the root cause diagnosis appears entirely unrelated to the service, flag a regression.
        Return strictly valid JSON:
        {{"regression_detected": true/false, "analysis": "string"}}
        """

        try:
            raw_result = OpenCodeService.send(
                model_id=self.client.get_configured_model("model"),
                system_prompt="You are a strict SRE monitoring agent. Output raw JSON only.",
                user_prompt=prompt,
                max_tokens=300
            )
            clean_json = raw_result.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            result = json.loads(clean_json)
            
            if result.get("regression_detected"):
                print(f"  🚨 [L11] REGRESSION DETECTED: {result.get('analysis')}")
            else:
                print("  ✅ [L11] System stable. No post-deployment regressions detected.")
            return result
                
        except Exception as e:
            print(f"  ⚠️ [L11] Monitoring evaluation failed: {e}")
            return {"regression_detected": False, "error": str(e)}

    def _poll_recent_telemetry(self, service: str) -> str:
        return f"[{service}] 200 OK: 45 req/s | 500 ERROR: 0 req/s"