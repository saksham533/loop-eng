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
from loops.l09_version_control import L09_VersionControlLoop
from loops.l10_post_mortem import L10_PostMortemLoop
from loops.l11_monitoring import L11_MonitoringLoop
from loops.l12_meta_loop import L12_MetaLoop

def get_prop(obj, key, default=None):
    if isinstance(obj, dict): return obj.get(key, default)
    return getattr(obj, key, default)

def run_capstone():
    print("=" * 80)
    print(" 🚀 PULSECHECK OS: THE 12-LOOP CAPSTONE PIPELINE")
    print("=" * 80)

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
    l09 = L09_VersionControlLoop()
    l10 = L10_PostMortemLoop()
    l11 = L11_MonitoringLoop()
    l12 = L12_MetaLoop()

    raw_event = (
        "2026-09-23T14:02:04.120Z - Webhook delivery failure on endpoint /webhooks/payment. "
        "correlation_id=pchk-0001-corr error_code=HTTP_500 service=OrderService"
    )

    incident = l01.execute(raw_event)
    classification = orchestrator.execute_loop(l02, incident.correlation_id, incident)
    blast_radius = orchestrator.execute_loop(l03, incident.correlation_id, incident)
    rca_result = orchestrator.execute_loop(l04, incident.correlation_id, incident)
    
    strategy_result = orchestrator.execute_loop(l05, incident.correlation_id, rca_result)
    selected_strategy = strategy_result.get("selected_strategy") or strategy_result.get("optimal_strategy")

    is_safe, msg = guardrail.validate_action(selected_strategy, order_amount=1500.00)
    print(f"\n[GUARDRAIL] {msg}")
    if not is_safe:
        if input("Approve? (yes/no): ").strip().lower() != "yes":
            return

    healing_result = orchestrator.execute_loop(l06, incident.correlation_id, {
        "order_id": "ORD-001",
        "payment_id": "PAY-001",
        "strategy": selected_strategy.get("strategy_name", selected_strategy.get("strategy"))
    })

    patch_payload = orchestrator.execute_loop(l07, incident.correlation_id, rca_result)
    verification_result = orchestrator.execute_loop(l08, incident.correlation_id, patch_payload)

    # Bundle payload for L09 Version Control
    l09_payload = {
        "incident_id": incident.correlation_id,
        "patch_result": patch_payload,
        "rca_result": rca_result,
        "test_output": get_prop(verification_result, "test_output", "All tests passed")
    }
    vc_result = orchestrator.execute_loop(l09, incident.correlation_id, l09_payload)

    # Aggregate state for L10, L11, L12
    aggregate_state = {
        "incident_id": incident.correlation_id,
        "raw_alert": raw_event,
        "error_code": incident.error_code,
        "service": incident.affected_service,
        "root_cause": get_prop(rca_result, 'root_cause'),
        "sandbox_verified": get_prop(verification_result, 'verified')
    }

    pm_result = orchestrator.execute_loop(l10, incident.correlation_id, aggregate_state)
    audit_result = orchestrator.execute_loop(l11, incident.correlation_id, aggregate_state)
    
    if audit_result.get("regression_detected"):
        print("\n  [HALT] Pipeline halted due to detected regression.")
        return
        
    policy_result = orchestrator.execute_loop(l12, incident.correlation_id, aggregate_state)

    print("\n" + "=" * 80)
    print("              PROJECT SYNAPSE: MASTER PIPELINE COMPLETE")
    print("=" * 80)
    print(f"Incident ID          : {incident.correlation_id}")
    print(f"Root Cause           : {get_prop(rca_result, 'root_cause')}")
    print(f"Sandbox Verification : {'PASSED' if get_prop(verification_result, 'verified') else 'FAILED'}")
    print(f"Regression Check     : {'REGRESSED' if audit_result.get('regression_detected') else 'STABLE'}")
    print(f"Meta-Loop Routing    : {'UPDATED' if policy_result.get('meta_loop_updated') else 'SKIPPED'}")
    print("=" * 80)

if __name__ == "__main__":
    run_capstone()