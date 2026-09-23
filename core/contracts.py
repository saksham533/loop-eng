# pulsecheck/core/contracts.py
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class IncidentSchema(BaseModel):
    correlation_id: str
    error_code: str
    affected_service: str
    raw_payload: str

class ClassificationResult(BaseModel):
    category: str
    severity: str
    confidence: float
    requires_hitl: bool = False

class StrategyEvaluation(BaseModel):
    strategy_name: str
    feasibility_score: float = Field(ge=0.0, le=1.0)
    risk_level: str
    estimated_cost: float
    rationale: str

class FieldReconciliationRecord(BaseModel):
    field_name: str
    order_val: Optional[Any] = None
    billing_val: Optional[Any] = None
    erp_val: Optional[Any] = None
    resolved_val: Any
    resolution_method: str

class ReconciliationResult(BaseModel):
    healing_action_taken: bool
    order_status: str
    billing_status: str
    erp_triggered: bool
    fully_reconciled: bool

class CodeFixProposal(BaseModel):
    module_name: str
    code_content: str
    rationale: str

class ReplayAssertionResult(BaseModel):
    step_name: str
    expected: str
    actual: str
    passed: bool
    diagnostic_details: Optional[str] = None

class ValidationReport(BaseModel):
    attempt_number: int
    passed: bool
    assertions: List[ReplayAssertionResult]
    feedback_for_l07: Optional[str] = None