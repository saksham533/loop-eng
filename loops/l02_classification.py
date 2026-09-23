# loops/l02_classification.py
import yaml
import os
import json
import re
from core.contracts import IncidentSchema, ClassificationResult
from core.opencode_service import OpenCodeService

class L02_ClassificationLoop:
    def __init__(self):
        self.standard_model = OpenCodeService.get_configured_model("small_model")
        self.rule_engine = self._initialize_rules()

    def _initialize_rules(self):
        try:
            with open("config/rules.yaml", "r") as config_file:
                return yaml.safe_load(config_file).get("rules", {})
        except FileNotFoundError:
            return {}

    def _extract_json_object(self, text: str) -> dict:
        """Finds and parses the first JSON object inside the text payload."""
        if not text:
            raise ValueError("Received empty response from model.")
        
        # 1. Direct parse attempt
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            pass

        # 2. Strip code fences if present
        if "```" in text:
            clean = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
            try:
                return json.loads(clean)
            except Exception:
                pass

        # 3. Regex search for the outermost {...} block
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        raise ValueError(f"No valid JSON object found in output. Raw response:\n{text}")

    def execute(self, incident: IncidentSchema) -> ClassificationResult:
        # Phase 1: Static Rule Evaluation (Deterministic)
        if incident.error_code in self.rule_engine:
            matched_policy = self.rule_engine[incident.error_code]
            print(f"[L02] Policy match resolved for error code: {incident.error_code}. Bypassing stochastic inference.")
            return ClassificationResult(
                severity=matched_policy["severity"],
                category=matched_policy["category"],
                confidence=1.0
            )

        # Phase 2: Stochastic Inference via Centralized Router
        print(f"[L02] Unclassified error code '{incident.error_code}' detected. Routing to {self.standard_model} for analysis...")
        
        sys_prompt = f"""
        Analyze the following incident parameters and determine the appropriate classification.
        Output MUST be strictly formatted JSON conforming to this schema:
        {ClassificationResult.model_json_schema()}
        Provide a calculated 'confidence' metric (0.0 to 1.0).
        """

        raw_response = OpenCodeService.send(
            model_id=self.standard_model,
            system_prompt=sys_prompt,
            user_prompt=f"Incident Data: {incident.model_dump_json()}"
        )

        try:
            classification_payload = self._extract_json_object(raw_response)
            evaluation_result = ClassificationResult(**classification_payload)
        except Exception as e:
            raise ValueError(f"Structural validation failure. Model output deviated from defined schema: {e}")

        # Phase 3: The Watchdog Supervisor (Bounded Autonomy)
        if evaluation_result.confidence < 0.8:
            print(f"[L02] WATCHDOG ALERT: Model confidence ({evaluation_result.confidence}) violates the minimum safety threshold (0.8).")
            evaluation_result.requires_hitl = True
            return evaluation_result
            
        return evaluation_result