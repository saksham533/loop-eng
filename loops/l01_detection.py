# pulsecheck/loops/l01_detection.py
import time
import hashlib
import re
import os
import json
from core.contracts import IncidentSchema
from core.opencode_service import OpenCodeService # Centralized router from Lab 0

class L01_DetectionLoop:
    def __init__(self):
        # Enforce economical extraction routing
        self.standard_model = os.getenv("CHEAP_MODEL", "anthropic/claude-haiku-4-5-20251001")
        self.temporal_registry = {}
        self.suppression_window_seconds = 300

    def _generate_canonical_signature(self, unstructured_log: str) -> str:
        """Removes volatile data prior to hashing to guarantee signature uniformity."""
        # Strips standard ISO 8601 timestamps to evaluate the core exception logic.
        canonical_string = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z?', '', unstructured_log)
        return hashlib.sha256(canonical_string.encode()).hexdigest()

    def _strip_markdown(self, text: str) -> str:
        """Proactively removes markdown wrappers to prevent JSON parser failures."""
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.rfind("```") != -1:
                text = text[:text.rfind("```")]
        return text.strip()

    def execute(self, unstructured_log: str) -> IncidentSchema:
        # Phase 1: Deterministic Filtering
        signature = self._generate_canonical_signature(unstructured_log)
        current_epoch = time.time()

        if signature in self.temporal_registry:
            if current_epoch - self.temporal_registry[signature] < self.suppression_window_seconds:
                print(f"[L01] Filtered: Redundant telemetry signature ({signature[:8]}). Preserving token budget.")
                return None

        # Register novel signature
        self.temporal_registry[signature] = current_epoch
        print(f"[L01] Processing novel telemetry signature ({signature[:8]}). Routing to {self.standard_model}...")

        # Phase 2: Schema Extraction via Centralized Router
        sys_prompt = f"""
        Extract the incident parameters from the provided log string. 
        Output MUST be strictly formatted JSON conforming to this schema. No preamble text is permitted.
        Schema Definition: {IncidentSchema.model_json_schema()}
        """
        
        raw_response = OpenCodeService.send(
            model_id=self.standard_model,
            system_prompt=sys_prompt,
            user_prompt=f"Log Data: {unstructured_log}"
        )

        try:
            cleaned_text = self._strip_markdown(raw_response)
            extracted_payload = json.loads(cleaned_text)
            return IncidentSchema(**extracted_payload)
        except Exception as e:
            raise ValueError(f"Structural validation failure. Model output deviated from defined schema: {e}")