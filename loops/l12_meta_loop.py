# loops/l12_meta_loop.py
import yaml
import json
from pathlib import Path
from core.opencode_service import OpenCodeService

class L12_MetaLoop:
    def __init__(self):
        self.client = OpenCodeService()
        self.routing_file = Path("routing.yaml")

    def execute(self, payload: dict) -> dict:
        incident_id = payload.get("incident_id")
        error_code = payload.get("error_code")
        print(f"\n[L12] Initializing Meta-Loop Oscillation Guard for {incident_id}...")
        
        prompt = f"""
        Generate a new routing rule based on this resolved incident to skip LLM inference next time.
        Error Code: {error_code}
        RCA: {payload.get('root_cause')}

        Return strictly valid JSON:
        {{"signature": "webhook_crash_recovery", "error_code": "{error_code}", "target_script": "remediation_scripts/idempotency_fix.py"}}
        """
        
        try:
            raw_result = OpenCodeService.send(
                model_id=self.client.get_configured_model("model"),
                system_prompt="You are a routing policy generator. Output raw JSON only.",
                user_prompt=prompt,
                max_tokens=300
            )
            clean_json = raw_result.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            new_rule = json.loads(clean_json)
            
            if self.routing_file.exists():
                with open(self.routing_file, "r") as f:
                    routing_data = yaml.safe_load(f) or {"rules": []}
            else:
                routing_data = {"rules": []}

            if "rules" not in routing_data:
                routing_data["rules"] = []

            for rule in routing_data["rules"]:
                if rule.get("error_code") == new_rule.get("error_code"):
                    print(f"  🛡️ [L12] Oscillation Guard: Rule for {new_rule.get('error_code')} already exists. Skipping update.")
                    return {"meta_loop_updated": False}

            routing_data["rules"].append(new_rule)
            
            with open(self.routing_file, "w") as f:
                yaml.safe_dump(routing_data, f, default_flow_style=False, sort_keys=False)
                
            print(f"  ✅ [L12] Policy updated. {new_rule.get('error_code')} is now handled deterministically.")
            return {"meta_loop_updated": True}
            
        except Exception as e:
            print(f"  ⚠️ [L12] Meta-Loop policy generation failed: {e}")
            return {"meta_loop_updated": False}