from __future__ import annotations

import re
from datetime import date, timedelta
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

        read_only = self._handle_read_only_task_query(text, vault)
        if read_only is not None:
            events.append(
                self._event(
                    EventType.TASK_COMPLETED,
                    "agent/orchestrator",
                    "user/cli",
                    {"status": "no_action", "reason": "Read-only task query completed."},
                    correlation_id=command_event.correlation_id,
                )
            )
            return TaskResult(status="no_action", message=read_only, events=events)

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
                message=(
                    "No supported project update detected. Try commands like: "
                    "'Create task Write launch copy due 2026-06-12', "
                    "'Mark launch done', or 'Show dependency impact for launch'."
                ),
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

        baseline_error = self._validate_patch_baseline(patch, workspace.vault_root)
        if baseline_error:
            events.append(
                self._event(
                    EventType.TASK_REJECTED,
                    "agent/orchestrator",
                    "user/cli",
                    {"status": "rejected", "reason": baseline_error},
                    correlation_id=command_event.correlation_id,
                )
            )
            return TaskResult(
                status="rejected",
                message=baseline_error,
                events=events,
                patches=[patch],
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

    def _handle_read_only_task_query(self, text: str, vault: Vault) -> str | None:
        match = re.search(r"(?:show\s+)?dependency impact for (?P<keyword>.+)$", text, flags=re.I)
        if not match:
            return None

        task = self._find_task(vault, keyword=match.group("keyword"))
        if task is None:
            return f"No task found for dependency impact query: {match.group('keyword').strip()}"

        title = task.metadata.get("title", task.relative_path)
        return f"Dependency impact for {title}: {self._dependency_impact(task.metadata)}"

    def _plan_task_update(self, text: str, vault: Vault, today: date) -> ProposedPatch | None:
        return (
            self._plan_create_task(text)
            or self._plan_mark_done(text, vault)
            or self._plan_owner_change(text, vault)
            or self._plan_due_shift(text, vault, today)
            or self._plan_launch_next_friday(text, vault, today)
        )

    def _plan_create_task(self, text: str) -> ProposedPatch | None:
        match = re.match(
            r"create task (?P<title>.+?)(?: due (?P<due>\d{4}-\d{2}-\d{2}))?(?: owner (?P<owner>.+))?$",
            text.strip(),
            flags=re.I,
        )
        if not match:
            return None

        title = match.group("title").strip()
        metadata: dict = {
            "id": self._slugify(title),
            "title": title,
            "status": "todo",
            "dependencies": [],
            "created_by": "sovereign-cortex-mvp",
        }
        if match.group("due"):
            metadata["due"] = match.group("due")
        if match.group("owner"):
            metadata["owner"] = match.group("owner").strip()

        body = f"# {title}\n\nCreated by Sovereign AI MVP-0.2.\n"
        after = render_markdown(metadata, body)
        return ProposedPatch(
            operation=PatchOperation.CREATE_FILE,
            relative_path=f"tasks/{metadata['id']}.md",
            before=None,
            after=after,
            summary=f"Create task '{title}'.",
            risk="low",
            requires_human_approval=True,
        )

    def _plan_mark_done(self, text: str, vault: Vault) -> ProposedPatch | None:
        match = re.match(r"(?:mark|complete) (?P<keyword>.+?)(?: as)? done$", text.strip(), flags=re.I)
        if not match:
            return None

        task = self._find_task(vault, keyword=match.group("keyword"))
        if task is None:
            return None

        metadata = dict(task.metadata)
        old_status = str(metadata.get("status", "unspecified"))
        metadata["status"] = "done"
        metadata["updated_by"] = "sovereign-cortex-mvp"
        metadata["last_change_reason"] = "User requested marking task done."
        after = render_markdown(metadata, task.body)
        return ProposedPatch(
            operation=PatchOperation.UPDATE_FILE,
            relative_path=task.relative_path,
            before=task.raw,
            after=after,
            summary=f"Mark '{metadata.get('title', 'task')}' done from {old_status}.",
            risk="low",
            requires_human_approval=True,
        )

    def _plan_owner_change(self, text: str, vault: Vault) -> ProposedPatch | None:
        match = re.match(
            r"(?:change owner of (?P<keyword_a>.+?) to (?P<owner_a>.+)|assign (?P<keyword_b>.+?) to (?P<owner_b>.+))$",
            text.strip(),
            flags=re.I,
        )
        if not match:
            return None

        keyword = match.group("keyword_a") or match.group("keyword_b")
        owner = (match.group("owner_a") or match.group("owner_b")).strip()
        task = self._find_task(vault, keyword=keyword)
        if task is None:
            return None

        metadata = dict(task.metadata)
        old_owner = str(metadata.get("owner", "unassigned"))
        metadata["owner"] = owner
        metadata["updated_by"] = "sovereign-cortex-mvp"
        metadata["last_change_reason"] = "User requested owner change."
        after = render_markdown(metadata, task.body)
        return ProposedPatch(
            operation=PatchOperation.UPDATE_FILE,
            relative_path=task.relative_path,
            before=task.raw,
            after=after,
            summary=f"Change '{metadata.get('title', 'task')}' owner from {old_owner} to {owner}.",
            risk="low",
            requires_human_approval=True,
        )

    def _plan_due_shift(self, text: str, vault: Vault, today: date) -> ProposedPatch | None:
        match = re.match(
            r"shift (?P<keyword>.+?) due date by (?P<amount>\d+) (?P<unit>day|days|week|weeks)$",
            text.strip(),
            flags=re.I,
        )
        if not match:
            return None

        task = self._find_task(vault, keyword=match.group("keyword"))
        if task is None:
            return None

        amount = int(match.group("amount"))
        if match.group("unit").lower().startswith("week"):
            amount *= 7

        metadata = dict(task.metadata)
        old_due = str(metadata.get("due", today.isoformat()))
        try:
            base_due = date.fromisoformat(old_due)
        except ValueError:
            base_due = today
        new_due = base_due + timedelta(days=amount)

        metadata["due"] = new_due.isoformat()
        metadata["updated_by"] = "sovereign-cortex-mvp"
        metadata["last_change_reason"] = f"User requested shifting due date by {amount} days."
        after = render_markdown(metadata, task.body)
        return ProposedPatch(
            operation=PatchOperation.UPDATE_FILE,
            relative_path=task.relative_path,
            before=task.raw,
            after=after,
            summary=f"Shift '{metadata.get('title', 'task')}' due date from {old_due} to {new_due.isoformat()}.",
            risk="low",
            requires_human_approval=True,
        )

    def _plan_launch_next_friday(self, text: str, vault: Vault, today: date) -> ProposedPatch | None:
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

    def _validate_patch_baseline(self, patch: ProposedPatch, vault_root: Path) -> str | None:
        target = self._resolve_vault_path(vault_root, patch.relative_path)

        if patch.operation == PatchOperation.CREATE_FILE:
            if target.exists():
                return f"Rejected by baseline check: target file already exists: {patch.relative_path}"
            return None

        if patch.operation == PatchOperation.UPDATE_FILE:
            if not target.exists():
                return f"Rejected by baseline check: target file is missing: {patch.relative_path}"
            if patch.before is None:
                return "Rejected by baseline check: update patch has no baseline content."
            current = target.read_text(encoding="utf-8")
            if current != patch.before:
                return f"Rejected by baseline check: target file changed before apply: {patch.relative_path}"
            return None

        return f"Rejected by baseline check: unsupported patch operation: {patch.operation}"

    @staticmethod
    def _resolve_vault_path(vault_root: Path, relative_path: str) -> Path:
        path = (vault_root / relative_path).resolve()
        root = vault_root.resolve()
        if root not in path.parents and path != root:
            raise ValueError(f"Patch path escapes the workspace: {relative_path}")
        return path

    @staticmethod
    def _find_task(vault: Vault, keyword: str):
        normalized_keyword = LocalOrchestrator._normalize_lookup(keyword)
        for doc in vault.list_task_docs():
            title = LocalOrchestrator._normalize_lookup(str(doc.metadata.get("title", "")))
            task_id = LocalOrchestrator._normalize_lookup(str(doc.metadata.get("id", "")))
            relative_path = LocalOrchestrator._normalize_lookup(doc.relative_path)
            if (
                normalized_keyword in title
                or normalized_keyword in task_id
                or normalized_keyword in relative_path
                or all(token in title or token in task_id for token in normalized_keyword.split())
            ):
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
            return "no declared dependencies were found."
        deps = ", ".join(str(d) for d in dependencies)
        return (
            f"this task depends on {deps}. "
            "Before applying schedule or completion changes, verify those upstream tasks remain complete or rescheduled."
        )

    @staticmethod
    def _normalize_lookup(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    @staticmethod
    def _slugify(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug or "new-task"

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
