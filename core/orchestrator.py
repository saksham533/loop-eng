# core/orchestrator.py
from core.state import LoopStateRepository
from core.contracts import ClassificationResult, IncidentSchema

class LoopOrchestrator:
    def __init__(self):
        self.state_repository = LoopStateRepository()

    def execute_loop(self, loop_instance, incident_id: str, input_payload: any):
        loop_identifier = loop_instance.__class__.__name__

        # 1. State Verification (Read before act)
        current_state = self.state_repository.retrieve_state(incident_id, loop_identifier)
        if current_state and current_state["status"] == "AWAITING_HUMAN":
            print(f"[{loop_identifier}] Execution suspended. Incident {incident_id} requires manual verification.")
            return None

        if current_state and current_state["status"] == "COMPLETED":
            print(f"[{loop_identifier}] Execution bypassed. Terminal state already reached for {incident_id}.")
            cached_data = current_state["data"]
            # Rehydrate into Pydantic model if returning ClassificationResult
            if loop_identifier == "L02_ClassificationLoop" and isinstance(cached_data, dict):
                return ClassificationResult(**cached_data)
            return cached_data

        # 2. Execution Phase
        print(f"[{loop_identifier}] Initializing execution for {incident_id}...")
        self.state_repository.persist_state(incident_id, loop_identifier, "RUNNING", {})

        try:
            result = loop_instance.execute(input_payload)
            
            # 3. Halt Condition Evaluation
            requires_hitl = getattr(result, "requires_hitl", False)
            if requires_hitl:
                self.state_repository.persist_state(
                    incident_id, 
                    loop_identifier, 
                    "AWAITING_HUMAN", 
                    result.model_dump() if hasattr(result, "model_dump") else result
                )
                print(f"[{loop_identifier}] Bounded-Autonomy threshold breached. Halting loop.")
                return result

            self.state_repository.persist_state(
                incident_id, 
                loop_identifier, 
                "COMPLETED", 
                result.model_dump() if hasattr(result, "model_dump") else result
            )
            return result

        except Exception as e:
            self.state_repository.persist_state(incident_id, loop_identifier, "FAILED", {"error": str(e)})
            print(f"[{loop_identifier}] Execution fault: {str(e)}")
            raise e