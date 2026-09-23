# loops/l09_version_control.py
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Tuple
from core.opencode_service import OpenCodeService

class L09_VersionControlLoop:
    def __init__(self):
        self.model = os.getenv("FRONTIER_MODEL", OpenCodeService.get_configured_model("model"))
        self.pr_artifacts_dir = Path("artifacts/pull_requests")
        self.pr_artifacts_dir.mkdir(parents=True, exist_ok=True)

    def _exec_git(self, args: list[str]) -> Tuple[bool, str]:
        """Runs a Git subprocess deterministically, capturing stdout and stderr."""
        try:
            res = subprocess.run(
                ["git"] + args,
                capture_output=True,
                text=True,
                check=True
            )
            return True, res.stdout.strip()
        except subprocess.CalledProcessError as e:
            return False, e.stderr.strip()

    def _ensure_clean_working_branch(self, branch_name: str) -> None:
        """Ensures the working tree switches to an isolated branch safely."""
        _, current_branch = self._exec_git(["rev-parse", "--abbrev-ref", "HEAD"])
        branch_exists, _ = self._exec_git(["rev-parse", "--verify", branch_name])
        
        if branch_exists:
            if current_branch == branch_name:
                self._exec_git(["checkout", "main"])
            self._exec_git(["branch", "-D", branch_name])

        success, err = self._exec_git(["checkout", "-b", branch_name])
        if not success:
            raise RuntimeError(f"Failed to switch to isolated branch {branch_name}: {err}")

    def execute(self, payload: dict) -> Dict[str, Any]:
        # Unpack the single dictionary payload
        incident_id = payload.get("incident_id")
        patch_result = payload.get("patch_result", {})
        rca_result = payload.get("rca_result", {})
        test_output = payload.get("test_output", "")

        print(f"\n[L09] Initiating Version Control & PR Synthesis for {incident_id}...")
        
        target_file = patch_result.get("target_file")
        if not target_file or not Path(target_file).exists():
            raise FileNotFoundError(f"Target file {target_file} not found on disk.")

        branch_name = f"synapse/fix-{incident_id.lower().replace('_', '-')}"
        self._ensure_clean_working_branch(branch_name)

        print(f"  📁 Staging target file: {target_file}")
        self._exec_git(["add", target_file])

        _, raw_diff = self._exec_git(["diff", "--cached", target_file])
        diff_line_count = len(raw_diff.splitlines())
        if diff_line_count > 150:
            raise ValueError(f"Diff too large ({diff_line_count} lines)! Safety limit exceeded.")

        print("  🤖 Generating structured Pull Request body and Conventional Commit message...")
        system_prompt = """
        You are a Staff Software Engineer preparing an automated production PR.
        Format your response into EXACTLY two sections separated by '---':
        
        COMMIT_TITLE: <conventional commit format, e.g., fix(service): description>
        ---
        ## Context & Problem
        <Brief problem statement>
        
        ## Root Cause Analysis
        <Summary of defect>
        
        ## Validation & Verification Proof
        <Summary of passing sandbox tests>
        
        ## Risk & Rollback Strategy
        <Safe rollback instructions>
        """

        user_prompt = f"""
        Incident ID: {incident_id}
        Target File: {target_file}
        Root Cause: {rca_result.get('root_cause')}
        Evidence: {rca_result.get('evidence_summary')}
        Sandbox Verification Output:
        {test_output}

        Git Unified Diff:
        {raw_diff}
        """

        raw_synthesis = OpenCodeService.send(
            model_id=self.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1200
        )

        parts = raw_synthesis.split("---")
        commit_msg = parts[0].replace("COMMIT_TITLE:", "").strip()
        pr_markdown = parts[1].strip() if len(parts) > 1 else raw_synthesis.strip()

        print(f"  📝 Committing: {commit_msg}")
        commit_success, commit_out = self._exec_git(["commit", "-m", commit_msg])
        if not commit_success:
            print(f"  ⚠️ Commit warning: {commit_out}")

        pr_file = self.pr_artifacts_dir / f"PR_{incident_id.upper()}.md"
        pr_content = f"# PR: {commit_msg}\n\n**Branch:** `{branch_name}`\n**Target:** `main`\n\n{pr_markdown}"
        pr_file.write_text(pr_content, encoding="utf-8")
        print(f"  ✅ PR documentation generated at: {pr_file}")

        return {
            "branch_name": branch_name,
            "commit_message": commit_msg,
            "pr_artifact_path": str(pr_file),
            "diff_lines": diff_line_count,
            "status": "READY_FOR_PEER_REVIEW"
        }