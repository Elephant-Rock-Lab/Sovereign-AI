from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .policy import CapabilityToken


@dataclass(frozen=True)
class Workspace:
    name: str
    root: Path
    vault_root: Path
    memory_root: Path

    def issue_default_token(self) -> CapabilityToken:
        return CapabilityToken(
            workspace=self.name,
            can_read=("tasks", "notes", "memory"),
            can_write=("tasks", "notes", "memory"),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
            max_risk_without_approval="low",
        )


class WorkspaceRegistry:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root

    def get(self, workspace_name: str) -> Workspace:
        vault_root = self.repo_root / "vault" / workspace_name
        if not vault_root.exists():
            raise FileNotFoundError(f"Workspace vault not found: {vault_root}")
        memory_root = vault_root / "memory"
        memory_root.mkdir(exist_ok=True)
        return Workspace(
            name=workspace_name,
            root=self.repo_root,
            vault_root=vault_root,
            memory_root=memory_root,
        )
