# pulsecheck/main.py
from core.orchestrator import LoopOrchestrator
from core.guardrails import FinancialGuardrail
from loops.l01_detection import L01_DetectionLoop
from loops.l02_classification import L02_ClassificationLoop
from loops.l03_dependency import L03_DependencyMappingLoop
from loops.l04_root_cause import L04_RootCauseAnalysisLoop
from loops.l05_parallel_evaluator import L05_ParallelStrategyEvaluator
from loops.l06_reconciliation import L06_ReconciliationLoop
from loops.l07_patch_synthesis import L07_PatchSynthesisLoop
from loops.l08_sandbox_verifier import L08_SandboxVerifierLoop

def get_prop(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def run_pipeline():
    print("=" * 70)
    print("   PULSECHECK OS: COMPLETE SELF-HEALING RUNTIME (L01 - L08)")
    print("=" * 70)

    orchestrator = LoopOrchestrator()
    guardrail = FinancialGuardrail(max_auto_approval_amount=500.00)

    l01 = L01_DetectionLoop()
    l02 = L02_ClassificationLoop()
    l03 = L03_DependencyMappingLoop()
    l04 = L04_RootCauseAnalysisLoop()
    l05 = L05_ParallelStrategyEvaluator()
    l06 = L06_ReconciliationLoop()
    l07 = L07_PatchSynthesisLoop()
    l08 = L08_SandboxVerifierLoop()

    raw_event = (
        "2026-09-23T14:02:04.120Z - Webhook delivery failure on endpoint /webhooks/payment. "
        "correlation_id=pchk-0001-corr error_code=HTTP_500 service=OrderService "
        "details='Transaction timeout while updating order status to PAID'"
    )

    print("\n[EVENT INGESTION]")
    print(f"Raw Telemetry: {raw_event}")

    # --- Phase 1: Triage (L01 & L02) ---
    incident = l01.execute(raw_event)
    if not incident:
        print("[L01] Event suppressed as duplicate.")
        return

    classification = orchestrator.execute_loop(l02, incident.correlation_id, incident)
    if get_prop(classification, "requires_hitl", False):
        print("[SYSTEM HALTED] Manual classification required.")
        return

    # --- Phase 2: Investigation (L03 & L04) ---
    blast_radius = orchestrator.execute_loop(l03, incident.correlation_id, incident)
    if get_prop(blast_radius, "requires_hitl", False):
        print("[SYSTEM HALTED] Large blast radius requires approval.")
        return

    rca_result = orchestrator.execute_loop(l04, incident.correlation_id, incident)
    if get_prop(rca_result, "requires_hitl", False):
        print("[SYSTEM HALTED] Low-confidence RCA requires human review.")
        return

    # --- Phase 3: Strategy & Guardrails (L05 & L06) ---
    strategy_result = orchestrator.execute_loop(l05, incident.correlation_id, rca_result)
    
    # Safely fall back if your L05 returned "optimal_strategy" instead of "selected_strategy"
    selected_strategy = strategy_result.get("selected_strategy") or strategy_result.get("optimal_strategy")

    is_safe, guardrail_msg = guardrail.validate_action(selected_strategy, order_amount=1500.00)
    print(f"\n[GUARDRAIL CHECK] {guardrail_msg}")

    if not is_safe:
        print("\n" + "!" * 70)
        print(" [HUMAN AUTHORIZER CHECKPOINT] Automated remediation exceeds $500 cap.")
        print("!" * 70)
        user_choice = input("Approve execution of remediation strategy anyway? (yes/no): ").strip().lower()
        if user_choice != "yes":
            print("[ABORT] Authorizer rejected plan. Exiting.")
            return
  
    healing_result = orchestrator.execute_loop(l06, incident.correlation_id, {
        "order_id": "ORD-001",
        "payment_id": "PAY-001",
        "strategy": selected_strategy.get("strategy_name", selected_strategy.get("strategy")) 
    })

    # --- Phase 4: Permanent Code Remediation (L07 & L08) ---
    patch_payload = orchestrator.execute_loop(l07, incident.correlation_id, rca_result)
    verification_result = orchestrator.execute_loop(l08, incident.correlation_id, patch_payload)

# --- Final Executive Summary ---
    print("\n" + "=" * 70)
    print("            PROJECT SYNAPSE: MASTER INCIDENT REPORT")
    print("=" * 70)
    print(f"Incident Ref        : {incident.correlation_id}")
    print(f"Classification      : {get_prop(classification, 'category')} | Severity: {get_prop(classification, 'severity')}")
    print(f"Blast Radius        : {get_prop(blast_radius, 'blast_radius_count', 0)} nodes identified")
    print(f"Root Cause          : {get_prop(rca_result, 'root_cause')}")
    print(f"Data Reconciliation : {'CONVERGED & RESOLVED' if get_prop(healing_result, 'fully_reconciled') else 'INCOMPLETE'}")
    print(f"Code Patch Target   : {get_prop(verification_result, 'target_file')}")
    print(f"Sandbox Verification: {'VERIFIED & PROMOTED (All tests passing)' if get_prop(verification_result, 'verified') else 'FAILED (Rolled back)'}")
    print("=" * 70)

if __name__ == "__main__":
    run_pipeline()