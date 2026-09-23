# pulsecheck/loops/l05_parallel_evaluator.py
import asyncio
import os
import json
import re
from typing import Dict, Any
from pydantic import BaseModel
from core.opencode_service import OpenCodeService

class StrategyEvaluation(BaseModel):
    strategy_name: str
    feasibility_score: float
    risk_level: str
    estimated_cost: float
    rationale: str

class L05_ParallelStrategyEvaluator:
    def __init__(self):
        self.model = os.getenv("FRONTIER_MODEL", OpenCodeService.get_configured_model("model"))

    def _extract_json(self, text: str) -> dict:
        text = text.strip()
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
        
        try:
            return json.loads(text)
        except Exception:
            return {}

    async def _evaluate_single_strategy(self, strategy_name: str, description: str, rca_summary: str) -> StrategyEvaluation:
        prompt = f"""
        Evaluate this proposed remediation strategy for a distributed transaction failure.
        Strategy Name: {strategy_name}
        Description: {description}
        Root Cause Context: {rca_summary}

        Return raw JSON only matching this schema:
        {{
            "strategy_name": "{strategy_name}",
            "feasibility_score": 0.85,
            "risk_level": "LOW",
            "estimated_cost": 0.0,
            "rationale": "Brief explanation"
        }}
        """
        try:
            raw = OpenCodeService.send(
                model_id=self.model,
                system_prompt="You are a senior SRE risk evaluator. Output strict JSON only.",
                user_prompt=prompt,
                max_tokens=400
            )
            
            parsed = self._extract_json(raw)
            
            # Ensure safe fallbacks if the model misses a key
            return StrategyEvaluation(
                strategy_name=parsed.get("strategy_name", strategy_name),
                feasibility_score=float(parsed.get("feasibility_score", 0.0)),
                risk_level=parsed.get("risk_level", "HIGH").upper(),
                estimated_cost=float(parsed.get("estimated_cost", 0.0)),
                rationale=parsed.get("rationale", "No rationale provided")
            )
        except Exception as e:
            return StrategyEvaluation(
                strategy_name=strategy_name,
                feasibility_score=0.0,
                risk_level="HIGH",
                estimated_cost=0.0,
                rationale=f"Evaluation failure: {str(e)}"
            )

    def execute(self, rca_result: dict) -> Dict[str, Any]:
        print("[L05] Initializing Concurrent Strategy Evaluators (3 Workers)...")
        strategies = [
            ("STANDARD_REPLAY", "Replay the webhook payload to trigger normal idempotency recovery."),
            ("NEW_KEY_REPLAY", "Directly patch Order state to PAID and invoke ERP fulfillment API."),
            ("FULL_REFUND", "Issue a full billing refund and cancel the order.")
        ]

        async def run_evaluations():
            tasks = [
                self._evaluate_single_strategy(name, desc, rca_result.get("root_cause", ""))
                for name, desc in strategies
            ]
            return await asyncio.gather(*tasks)

        # Execute all three judges concurrently
        evaluations = asyncio.run(run_evaluations())
        
        # Select the strategy with the highest feasibility score that is NOT high risk
        viable_strategies = [e for e in evaluations if e.risk_level != "HIGH"]
        if not viable_strategies:
            viable_strategies = evaluations # Fallback

        best_strategy = max(viable_strategies, key=lambda x: x.feasibility_score)
        
        for eval in evaluations:
            print(f"  -> Evaluated {eval.strategy_name}: Score {eval.feasibility_score} | Risk: {eval.risk_level}")
            
        print(f"[L05] Optimal Strategy Selected: {best_strategy.strategy_name}")
        
        # Extract plain dictionaries so SQLite can serialize the JSON
        def to_dict(obj):
            return obj.model_dump() if hasattr(obj, "model_dump") else vars(obj)

        return {
            "evaluations": [to_dict(e) for e in evaluations],
            "selected_strategy": to_dict(best_strategy)
        }