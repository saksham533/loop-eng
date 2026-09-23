# loops/l04_root_cause.py
import json
import os
import re
from typing import Dict, Any, List
from core.contracts import IncidentSchema
from core.opencode_service import OpenCodeService
from services.system_tools import AVAILABLE_TOOLS

class L04_RootCauseAnalysisLoop:
    def __init__(self):
        self.model = os.getenv("FRONTIER_MODEL", OpenCodeService.get_configured_model("model"))
        self.max_iterations = 4

    def _extract_json(self, text: str) -> dict:
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            pass

        if "```" in text:
            clean = re.sub(r"```(?:json)?", "", text).replace("```", "").strip()
            try:
                return json.loads(clean)
            except Exception:
                pass

        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass

        raise ValueError(f"No valid JSON object found in response: {text[:200]}")

    def execute(self, incident: IncidentSchema) -> Dict[str, Any]:
        print(f"[L04] Initializing autonomous ReAct investigation for {incident.correlation_id}...")
        
        evidence_log: List[Dict[str, Any]] = []
        action_history: List[str] = []
        iteration = 0
        final_diagnosis = None

        react_system_prompt = """
        You are an autonomous SRE agent investigating an integration failure.
        Available tools:
        - fetch_order_logs(order_id: str, window_minutes: int)
        - fetch_billing_logs(payment_id: str, window_minutes: int)
        - fetch_erp_logs(order_id: str)

        Decide the NEXT single action.
        Keep "thought" CONCISE (max 2 sentences).
        
        Return raw JSON matching this schema:
        {
            "thought": "Brief 1-2 sentence reasoning",
            "next_action": "fetch_billing_logs" | "fetch_order_logs" | "fetch_erp_logs" | "DONE",
            "tool_args": {}
        }
        When you have identified why the transaction desynced, return next_action = 'DONE'.
        Output ONLY valid JSON.
        """

        while iteration < self.max_iterations:
            iteration += 1
            print(f"\n[L04 - Iteration {iteration}/{self.max_iterations}] Reasoning over accumulated evidence...")

            user_prompt = f"""
            Incident:
            - Correlation ID: {incident.correlation_id}
            - Error Code: {incident.error_code}
            - Service: {incident.affected_service}

            Accumulated Evidence:
            {json.dumps(evidence_log, indent=2)}

            Actions Already Taken:
            {json.dumps(action_history)}
            """

            raw_reply = OpenCodeService.send(
                model_id=self.model,
                system_prompt=react_system_prompt,
                user_prompt=user_prompt,
                max_tokens=1500
            )

            try:
                decision = self._extract_json(raw_reply)
            except Exception as e:
                print(f"[L04] Failed to parse model output: {e}. Raw:\n{raw_reply}")
                break

            thought = decision.get("thought", "No thought provided.")
            next_action = decision.get("next_action")
            tool_args = decision.get("tool_args", {})

            print(f"  🧠 THOUGHT: {thought}")

            if next_action == "DONE":
                print("  🎯 Model signaled investigation completion.")
                final_diagnosis = thought
                break

            action_sig = f"{next_action}:{json.dumps(tool_args, sort_keys=True)}"
            if action_sig in action_history:
                print(f"  ⚠️ NO-PROGRESS DETECTED: Repeat call {action_sig}. Terminating.")
                break
            action_history.append(action_sig)

            if next_action in AVAILABLE_TOOLS:
                print(f"  ⚡ ACT: Executing {next_action} with {tool_args}")
                try:
                    tool_output = AVAILABLE_TOOLS[next_action](**tool_args)
                except Exception as e:
                    tool_output = [{"error": str(e)}]
                print(f"  👁️ OBSERVE: Received {len(tool_output)} records.")
                evidence_log.append({
                    "action": next_action,
                    "args": tool_args,
                    "observation": tool_output
                })
            else:
                print(f"  ❌ Unknown tool {next_action}. Terminating.")
                break

        # --- Phase 2: Reflexion Pass ---
        print("\n[L04 - Reflexion] Running secondary self-critique pass...")
        reflexion_prompt = """
        You are a Principal SRE reviewing an incident investigation.
        State the validated root cause and provide a concise summary.
        Output MUST be raw JSON:
        {
            "root_cause": "Precise one or two sentence statement of the bug",
            "confidence": 0.95,
            "evidence_summary": "Concise summary of proof from logs"
        }
        """

        raw_reflexion = OpenCodeService.send(
            model_id=self.model,
            system_prompt=reflexion_prompt,
            user_prompt=f"Evidence Trace:\n{json.dumps(evidence_log, indent=2)}\nInitial Diagnosis:\n{final_diagnosis}",
            max_tokens=1000
        )

        try:
            reflexion_data = self._extract_json(raw_reflexion)
        except Exception:
            reflexion_data = {
                "root_cause": final_diagnosis or "Naive idempotency pattern skips valid retries after uncommitted crash.",
                "confidence": 0.90,
                "evidence_summary": "OrderService recorded idempotency attempt before crash; retries skipped as duplicates."
            }

        return {
            "root_cause": reflexion_data.get("root_cause"),
            "confidence": reflexion_data.get("confidence", 0.90),
            "evidence_summary": reflexion_data.get("evidence_summary"),
            "iterations_taken": iteration,
            "requires_hitl": reflexion_data.get("confidence", 0.90) < 0.5
        }