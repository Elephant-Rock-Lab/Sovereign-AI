from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path

from .approvals import ApprovalStore
from .events import (
    CommandPayload,
    EventEnvelope,
    EventType,
    PatchOperation,
    ProposedPatch,
    TaskResult,
)
from .git_audit import GitAudit
from .policy import PolicyEngine
from .vault import Vault, render_markdown
from .workspace import WorkspaceRegistry


class LocalOrchestrator:
    def __init__(self, repo_root: Path, workspace_name: str = "demo-project"):
        self.repo_root = repo_root
        self.workspace_name = workspace_name
        self.registry = WorkspaceRegistry(repo_root)
        self.policy = PolicyEngine()
        self.git = GitAudit(repo_root)
        self.approvals = ApprovalStore(repo_root)

    def handle_command(
        self,
        text: str,
        *,
        auto_approve: bool = False,
        today: date | None = None,
    ) -> TaskResult:
        today = today or date.today()
        workspace = self.registry.get(self.workspace_name)
        vault = Vault(workspace.vault_root)
        token = workspace.issue_default_token()
        events: list[EventEnvelope] = []

        command_event = self._event(
            EventType.COMMAND_RECEIVED,
            "user/cli",
            "agent/orchestrator",
            CommandPayload(text=text).model_dump(),
        )
        events.append(command_event)

        patch = self._plan_task_update(text, vault, today)
        if patch is None:
            events.append(
                self._event(
                    EventType.TASK_COMPLETED,
                    "agent/orchestrator",
                    "user/cli",
                    {"status": "no_action", "reason": "No supported project update detected."},
                    correlation_id=command_event.correlation_id,
                )
            )
            return TaskResult(
                status="no_action",
                message="No supported project update detected. Try: 'Move the website launch task to next Friday.'",
                events=events,
            )

        events.append(
            self._event(
                EventType.PATCH_PROPOSED,
                "agent/orchestrator",
                "policy/local",
                patch.model_dump(),
                correlation_id=command_event.correlation_id,
            )
        )

        decision = self.policy.evaluate_patch(patch, token)
        events.append(
            self._event(
                EventType.POLICY_CHECKED,
                "policy/local",
                "agent/orchestrator",
                {
                    "allowed": decision.allowed,
                    "approval_required": decision.approval_required,
                    "reason": decision.reason,
                },
                correlation_id=command_event.correlation_id,
            )
        )

        if not decision.allowed:
            return TaskResult(
                status="rejected",
                message=f"Rejected by policy: {decision.reason}",
                events=events,
                patches=[patch],
            )

        if decision.approval_required and not auto_approve:
            approval = self.approvals.create(
                workspace=self.workspace_name,
                command_text=text,
                correlation_id=command_event.correlation_id,
                patch=patch,
                policy_decision=decision,
            )
            events.append(
                self._event(
                    EventType.APPROVAL_REQUESTED,
                    "agent/orchestrator",
                    "approval/local",
                    {"approval_id": approval.approval_id, "relative_path": patch.relative_path},
                    correlation_id=command_event.correlation_id,
                )
            )
            return TaskResult(
                status="approval_saved",
                message=f"Patch proposed and saved for approval: {approval.approval_id}",
                events=events,
                patches=[patch],
                approval_id=approval.approval_id,
            )

        vault.apply_patch(patch)
        events.append(
            self._event(
                EventType.PATCH_APPLIED,
                "agent/orchestrator",
                "vault/demo-project",
                {"relative_path": patch.relative_path},
                correlation_id=command_event.correlation_id,
            )
        )

        commit_hash = self.git.commit_paths(
            [f"vault/{self.workspace_name}/{patch.relative_path}"],
            f"Apply Cortex patch: {patch.summary}",
        )
        events.append(
            self._event(
                EventType.AUDIT_COMMITTED,
                "git/local",
                "agent/orchestrator",
                {"commit_hash": commit_hash},
                correlation_id=command_event.correlation_id,
            )
        )
        events.append(
            self._event(
                EventType.TASK_COMPLETED,
                "agent/orchestrator",
                "user/cli",
                {"status": "applied", "summary": patch.summary},
                correlation_id=command_event.correlation_id,
            )
        )

        return TaskResult(
            status="applied",
            message=f"Applied patch: {patch.summary}",
            events=events,
            patches=[patch],
            commit_hash=commit_hash,
        )

    def _plan_task_update(self, text: str, vault: Vault, today: date) -> ProposedPatch | None:
        normalized = text.lower()
        if "launch" not in normalized or "next friday" not in normalized:
            return None

        task = self._find_task(vault, keyword="launch")
        if task is None:
            return None

        new_due = self._next_weekday(today, weekday=4)  # Friday, Monday=0
        metadata = dict(task.metadata)
        old_due = str(metadata.get("due", "unscheduled"))
        metadata["due"] = new_due.isoformat()
        metadata["updated_by"] = "sovereign-cortex-mvp"
        metadata["last_change_reason"] = "User requested moving launch task to next Friday."

        body = task.body
        dependency_note = self._dependency_impact(metadata)
        if "## Cortex Notes" not in body:
            body = body.rstrip() + "\n\n## Cortex Notes\n"
        body = re.sub(
            r"## Cortex Notes\n.*$",
            "## Cortex Notes\n" + dependency_note + "\n",
            body,
            flags=re.DOTALL,
        )

        after = render_markdown(metadata, body)
        return ProposedPatch(
            operation=PatchOperation.UPDATE_FILE,
            relative_path=task.relative_path,
            before=task.raw,
            after=after,
            summary=f"Move '{metadata.get('title', 'task')}' due date from {old_due} to {new_due.isoformat()}.",
            risk="low",
            requires_human_approval=True,
        )

    @staticmethod
    def _find_task(vault: Vault, keyword: str):
        for doc in vault.list_task_docs():
            title = str(doc.metadata.get("title", "")).lower()
            task_id = str(doc.metadata.get("id", "")).lower()
            if keyword in title or keyword in task_id:
                return doc
        return None

    @staticmethod
    def _next_weekday(today: date, weekday: int) -> date:
        days_ahead = weekday - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return today + timedelta(days=days_ahead)

    @staticmethod
    def _dependency_impact(metadata: dict) -> str:
        dependencies = metadata.get("dependencies") or []
        if not dependencies:
            return "- Dependency impact: no declared dependencies were found."
        deps = ", ".join(str(d) for d in dependencies)
        return (
            f"- Dependency impact: this task depends on {deps}. "
            "Before applying the new launch date, verify those upstream tasks remain complete or rescheduled."
        )

    def _event(
        self,
        event_type: EventType,
        sender: str,
        recipient: str,
        payload: dict,
        *,
        correlation_id: str | None = None,
    ) -> EventEnvelope:
        event = EventEnvelope(
            event_type=event_type,
            sender=sender,
            recipient=recipient,
            workspace=self.workspace_name,
            payload=payload,
        )
        if correlation_id:
            event.correlation_id = correlation_id
        return event
