from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

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
        self.repo_root = repo_root.resolve()
        self.registry_path = self.repo_root / "workspaces.yaml"

    def get(self, workspace_name: str) -> Workspace:
        vault_root = self._vault_root_for(workspace_name)
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

    def _vault_root_for(self, workspace_name: str) -> Path:
        config = self._load_config()
        workspaces = config.get("workspaces", {})
        if workspace_name in workspaces:
            workspace_config = workspaces[workspace_name] or {}
            if not isinstance(workspace_config, dict):
                raise ValueError(f"Workspace config must be a mapping: {workspace_name}")
            raw_vault_root = workspace_config.get("vault_root")
            if not raw_vault_root:
                raise ValueError(f"Workspace missing vault_root: {workspace_name}")
            return self._resolve_repo_path(str(raw_vault_root))

        # Preserve MVP-0 behavior when no explicit registry entry exists.
        return self._resolve_repo_path(f"vault/{workspace_name}")

    def _load_config(self) -> dict[str, Any]:
        if not self.registry_path.exists():
            return {}
        loaded = yaml.safe_load(self.registry_path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError("workspaces.yaml must contain a mapping")
        workspaces = loaded.get("workspaces", {})
        if not isinstance(workspaces, dict):
            raise ValueError("workspaces.yaml field 'workspaces' must be a mapping")
        return loaded

    def _resolve_repo_path(self, relative_path: str) -> Path:
        path = (self.repo_root / relative_path).resolve()
        if path != self.repo_root and self.repo_root not in path.parents:
            raise ValueError(f"Workspace path escapes repository: {relative_path}")
        return path
