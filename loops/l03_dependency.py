# pulsecheck/loops/l03_dependency.py
from typing import Set, Dict, List, Any
from core.contracts import IncidentSchema

class L03_DependencyMappingLoop:
    def __init__(self):
        # Simulated architecture topology map
        self.topology_graph = {
            "ORD-001": ["CUSTOMER-ACC-042", "PAY-001", "FUL-001", "INVENTORY-RESERVATION-99"],
            "PAY-001": ["BILLING-WEBHOOK-DISPATCH", "PAYMENT-GATEWAY-STRIPE"],
            "FUL-001": ["3PL-SHIPMENT-QUEUE", "WAREHOUSE-DISPATCH-EAST"],
            "CUSTOMER-ACC-042": ["SLA-MONITOR-TIER1", "ORD-001"] # Cycle intentionally present
        }
        self.max_depth = 5
        self.max_nodes = 200

    def execute(self, incident: IncidentSchema) -> Dict[str, Any]:
        print(f"[L03] Mapping blast radius for root entity: {incident.affected_service} (Ref: {incident.correlation_id})")
        
        visited_nodes: Set[str] = set()
        edges: List[Dict[str, str]] = []
        cycle_detected = False
        queue = [(incident.affected_service if incident.affected_service in self.topology_graph else "ORD-001", 0)]

        while queue:
            current_node, depth = queue.pop(0)

            if depth >= self.max_depth or len(visited_nodes) >= self.max_nodes:
                break

            if current_node in visited_nodes:
                cycle_detected = True
                continue

            visited_nodes.add(current_node)
            neighbors = self.topology_graph.get(current_node, [])

            for neighbor in neighbors:
                edges.append({"from": current_node, "to": neighbor})
                if neighbor not in visited_nodes:
                    queue.append((neighbor, depth + 1))

        result = {
            "blast_radius_count": len(visited_nodes),
            "nodes": list(visited_nodes),
            "edges": edges,
            "cycle_detected": cycle_detected,
            "requires_hitl": len(visited_nodes) > 50
        }

        print(f"[L03] Traversal complete. {len(visited_nodes)} affected nodes identified. Cycle detected: {cycle_detected}")
        
        if result["requires_hitl"]:
            print(f"[L03] HITL Gate Triggered: Blast radius exceeds safety threshold of 50 nodes.")
            
        return result