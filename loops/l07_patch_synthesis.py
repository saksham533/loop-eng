# pulsecheck/loops/l07_patch_synthesis.py
import os
import re
from pathlib import Path
from typing import Dict, Any
from core.opencode_service import OpenCodeService

class L07_PatchSynthesisLoop:
    def __init__(self):
        self.model = os.getenv("FRONTIER_MODEL", OpenCodeService.get_configured_model("model"))
        self.target_file_path = Path("mocks/order_service/idempotency/naive.py")

    def _strip_code_fences(self, text: str) -> str:
        text = text.strip()
        if "```" in text:
            # Match ```python ... ``` or plain ``` ... ```
            match = re.search(r"```(?:python)?\s*([\s\S]*?)\s*```", text)
            if match:
                return match.group(1).strip()
            # Fallback split
            parts = text.split("```")
            if len(parts) >= 3:
                return parts[1].replace("python\n", "").strip()
        return text

    def execute(self, rca_result: dict) -> Dict[str, Any]:
        print(f"[L07] Reading target source file: {self.target_file_path}...")
        
        if not self.target_file_path.exists():
            raise FileNotFoundError(f"Target source file {self.target_file_path} not found.")

        current_code = self.target_file_path.read_text()
        root_cause = rca_result.get("root_cause", "Idempotency check drops valid retries after crash.")
        evidence = rca_result.get("evidence_summary", "")

        print(f"[L07] Synthesizing bug fix using {self.model}...")

        system_prompt = """
        You are a Principal Software Engineer repairing a distributed transaction defect.
        You must output ONLY valid, production-ready Python source code.
        Do NOT write explanations, prose, or conversation.
        Do NOT wrap code in markdown fences like ```python. Output raw code directly.
        """

        user_prompt = f"""
        Target File: {self.target_file_path}
        Current Implementation:
        {current_code}

        Root Cause Analysis:
        {root_cause}
        Evidence:
        {evidence}

        Task:
        Rewrite the NaiveStrategy class so that:
        1. If attempt is None -> return Decision.PROCESS_NEW
        2. If current_state exists and current_state["status"] == "PAID" -> return Decision.SKIP_AS_DUPLICATE
        3. If attempt exists but current_state is not PAID -> return Decision.RECOVER_PARTIAL

        Preserve all imports:
        from .strategies import IdempotencyStrategy, Decision
        """

        raw_response = OpenCodeService.send(
            model_id=self.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1000
        )

        clean_patch = self._strip_code_fences(raw_response)

        # Basic sanity check
        # Strict contract validation
        # if "NaiveStrategy" not in patch_code or "RECOVER_PARTIAL" not in patch_code:
        #     raise ValueError("Synthesized patch failed contract validation (missing NaiveStrategy or RECOVER_PARTIAL).")  

        print("[L07] Code patch successfully synthesized.")
        return {
            "target_file": str(self.target_file_path),
            "original_code": current_code,
            "synthesized_code": clean_patch
        }
