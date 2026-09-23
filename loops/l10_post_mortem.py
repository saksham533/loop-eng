# loops/l10_post_mortem.py
import os
import sqlite3
from pathlib import Path
from typing import Dict, Any, List
from core.opencode_service import OpenCodeService

class L10_PostMortemLoop:
    def __init__(self, db_path: str = "pulsecheck_state.db"):
        self.model = os.getenv("FRONTIER_MODEL", OpenCodeService.get_configured_model("model"))
        self.db_path = db_path
        self.output_dir = Path("incident_reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _extract_timeline(self, incident_id: str) -> List[Dict[str, str]]:
        """Queries the state repository to extract the true chronological timeline."""
        if not Path(self.db_path).exists():
            return []

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT loop_identifier, status, updated_at 
                FROM pipeline_state 
                WHERE incident_id = ? 
                ORDER BY updated_at ASC
                """,
                (incident_id,)
            )
            rows = cursor.fetchall()
            return [{"loop": r[0], "status": r[1], "timestamp": r[2]} for r in rows]
        except Exception:
            return []
        finally:
            conn.close()

    def execute(self, aggregate_context: dict) -> Dict[str, Any]:
        incident_id = aggregate_context["incident_id"]
        print(f"\n[L10] Extracting chronological telemetry for Incident {incident_id}...")

        timeline = self._extract_timeline(incident_id)

        prompt = f"""
        You are a Principal Reliability Director authoring a formal, blameless Post-Mortem report.
        
        Incident Meta:
        - Identifier: {incident_id}
        - Severity: {aggregate_context.get('severity', 'HIGH')}
        - Classification: {aggregate_context.get('classification')}
        - Blast Radius: {aggregate_context.get('blast_radius')} nodes
        - Root Cause: {aggregate_context.get('root_cause')}
        - Remediation Applied: {aggregate_context.get('strategy')}
        - Target Source File: {aggregate_context.get('target_file')}
        
        True SQLite Audit Timeline:
        {timeline}

        Generate a complete, executive-ready Markdown post-mortem document.
        Structure:
        # Blameless Post-Mortem: {incident_id}
        
        ## 1. Executive Summary & Impact Metric
        (Quantify risk and affected nodes)

        ## 2. Chronological Incident Timeline
        (Generate a clear Markdown table mapping each loop, timestamp, and action taken)

        ## 3. Deep Root-Cause Analysis (5 Whys Framework)
        (Trace through why the transaction desynced)

        ## 4. Remediation & Verification Proof
        (Detail how the patch was verified)

        ## 5. Preventative Action Items
        (Identify long-term architectural improvements)

        Output pure Markdown only.
        """

        print("  🤖 Authoring complete blameless Post-Mortem artifact...")
        report_markdown = OpenCodeService.send(
            model_id=self.model,
            system_prompt="Generate a rigorous, professional engineering post-mortem. Output ONLY the markdown.",
            user_prompt=prompt,
            max_tokens=2000
        )

        clean_markdown = report_markdown.strip()
        if clean_markdown.startswith("```markdown"):
            clean_markdown = clean_markdown[11:]
        if clean_markdown.endswith("```"):
            clean_markdown = clean_markdown[:-3]

        report_file = self.output_dir / f"POST_MORTEM_{incident_id.upper()}.md"
        report_file.write_text(clean_markdown.strip(), encoding="utf-8")
        print(f"  ✅ Post-Mortem published to: {report_file}")

        return {
            "report_file": str(report_file),
            "timeline_events_recorded": len(timeline),
            "status": "PUBLISHED"
        }