from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from .events import PatchOperation, ProposedPatch
from .git_audit import GitAudit
from .policy import PolicyDecision
from .vault import Vault
from .workspace import WorkspaceRegistry

ApprovalStatus = Literal["pending", "approved", "rejected"]


class ApprovalConflictError(RuntimeError):
    """Raised when an approval request no longer matches current workspace state."""


class PolicyDecisionSnapshot(BaseModel):
    allowed: bool
    approval_required: bool
    reason: str

    @classmethod
    def from_decision(cls, decision: PolicyDecision) -> "PolicyDecisionSnapshot":
        return cls(
            allowed=decision.allowed,
            approval_required=decision.approval_required,
            reason=decision.reason,
        )


class ApprovalRequest(BaseModel):
    approval_id: str = Field(default_factory=lambda: str(uuid4()))
    status: ApprovalStatus = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime | None = None
    workspace: str
    command_text: str
    correlation_id: str
    patch: ProposedPatch
    policy_decision: PolicyDecisionSnapshot
    commit_hash: str | None = None
    rejection_reason: str | None = None


class ApprovalStore:
    """Filesystem-backed approval queue for durable patch decisions.

    Approval artifacts are JSON files stored under:

        approval_requests/pending/*.json
        approval_requests/approved/*.json
        approval_requests/rejected/*.json
    """

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.root = repo_root / "approval_requests"
        self.pending_dir = self.root / "pending"
        self.approved_dir = self.root / "approved"
        self.rejected_dir = self.root / "rejected"
        self._ensure_dirs()

    def create(
        self,
        *,
        workspace: str,
        command_text: str,
        correlation_id: str,
        patch: ProposedPatch,
        policy_decision: PolicyDecision,
    ) -> ApprovalRequest:
        request = ApprovalRequest(
            workspace=workspace,
            command_text=command_text,
            correlation_id=correlation_id,
            patch=patch,
            policy_decision=PolicyDecisionSnapshot.from_decision(policy_decision),
        )
        self._write(request, self.pending_dir)
        return request

    def list(self, status: ApprovalStatus = "pending") -> list[ApprovalRequest]:
        directory = self._dir_for_status(status)
        requests = [self._read(path) for path in sorted(directory.glob("*.json"))]
        return sorted(requests, key=lambda item: item.created_at)

    def get(self, approval_id: str) -> ApprovalRequest:
        path = self._find_path(approval_id)
        if path is None:
            raise FileNotFoundError(f"Approval request not found: {approval_id}")
        return self._read(path)

    def approve(self, approval_id: str) -> ApprovalRequest:
        request = self.get(approval_id)
        if request.status != "pending":
            raise ValueError(f"Approval request is already {request.status}: {approval_id}")
        if not request.policy_decision.allowed:
            raise ValueError(f"Cannot approve policy-rejected request: {approval_id}")

        registry = WorkspaceRegistry(self.repo_root)
        workspace = registry.get(request.workspace)
        vault = Vault(workspace.vault_root)
        self._ensure_patch_is_current(request, workspace.vault_root)
        vault.apply_patch(request.patch)

        git = GitAudit(self.repo_root)
        commit_hash = git.commit_paths(
            [f"vault/{request.workspace}/{request.patch.relative_path}"],
            f"Approve Cortex patch: {request.patch.summary}",
        )

        updated = request.model_copy(
            update={
                "status": "approved",
                "updated_at": datetime.now(timezone.utc),
                "commit_hash": commit_hash,
            }
        )
        self._move(request, updated)
        return updated

    def reject(self, approval_id: str, reason: str | None = None) -> ApprovalRequest:
        request = self.get(approval_id)
        if request.status != "pending":
            raise ValueError(f"Approval request is already {request.status}: {approval_id}")
        updated = request.model_copy(
            update={
                "status": "rejected",
                "updated_at": datetime.now(timezone.utc),
                "rejection_reason": reason or "Rejected by user.",
            }
        )
        self._move(request, updated)
        return updated

    def _ensure_patch_is_current(self, request: ApprovalRequest, vault_root: Path) -> None:
        target = self._resolve_vault_path(vault_root, request.patch.relative_path)

        if request.patch.operation == PatchOperation.CREATE_FILE:
            if target.exists():
                raise ApprovalConflictError(
                    f"Cannot approve {request.approval_id}: target file already exists: {request.patch.relative_path}"
                )
            return

        if request.patch.operation == PatchOperation.UPDATE_FILE:
            if not target.exists():
                raise ApprovalConflictError(
                    f"Cannot approve {request.approval_id}: target file is missing: {request.patch.relative_path}"
                )
            current = target.read_text(encoding="utf-8")
            expected = request.patch.before
            if expected is None:
                raise ApprovalConflictError(
                    f"Cannot approve {request.approval_id}: update patch has no baseline content."
                )
            if current != expected:
                raise ApprovalConflictError(
                    f"Cannot approve {request.approval_id}: target file changed after approval was requested: "
                    f"{request.patch.relative_path}"
                )
            return

        raise ApprovalConflictError(f"Unsupported patch operation: {request.patch.operation}")

    @staticmethod
    def _resolve_vault_path(vault_root: Path, relative_path: str) -> Path:
        path = (vault_root / relative_path).resolve()
        root = vault_root.resolve()
        if root not in path.parents and path != root:
            raise ApprovalConflictError(f"Patch path escapes the workspace: {relative_path}")
        return path

    def _ensure_dirs(self) -> None:
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        self.approved_dir.mkdir(parents=True, exist_ok=True)
        self.rejected_dir.mkdir(parents=True, exist_ok=True)

    def _dir_for_status(self, status: ApprovalStatus) -> Path:
        match status:
            case "pending":
                return self.pending_dir
            case "approved":
                return self.approved_dir
            case "rejected":
                return self.rejected_dir
        raise ValueError(f"Unsupported approval status: {status}")

    def _path_for(self, request: ApprovalRequest) -> Path:
        return self._dir_for_status(request.status) / f"{request.approval_id}.json"

    def _write(self, request: ApprovalRequest, directory: Path | None = None) -> None:
        directory = directory or self._dir_for_status(request.status)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{request.approval_id}.json"
        path.write_text(request.model_dump_json(indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def _read(path: Path) -> ApprovalRequest:
        return ApprovalRequest.model_validate_json(path.read_text(encoding="utf-8"))

    def _find_path(self, approval_id: str) -> Path | None:
        for directory in (self.pending_dir, self.approved_dir, self.rejected_dir):
            path = directory / f"{approval_id}.json"
            if path.exists():
                return path
        return None

    def _move(self, old: ApprovalRequest, new: ApprovalRequest) -> None:
        old_path = self._path_for(old)
        new_path = self._path_for(new)
        self._write(new)
        if old_path.exists() and old_path != new_path:
            old_path.unlink()
        elif old_path.exists():
            # Ensure replacement is atomic enough for the local MVP case.
            shutil.move(str(new_path), str(old_path))
