from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .events import ProposedPatch


@dataclass(frozen=True)
class CapabilityToken:
    """A minimal local capability token for MVP-0.

    Later versions should sign this object and make it short-lived per task.
    """

    workspace: str
    can_read: tuple[str, ...]
    can_write: tuple[str, ...]
    expires_at: datetime
    max_risk_without_approval: str = "low"

    def is_valid(self) -> bool:
        return datetime.now(timezone.utc) < self.expires_at


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    approval_required: bool
    reason: str


class PolicyEngine:
    """Central authority for file write decisions in MVP-0."""

    def evaluate_patch(self, patch: ProposedPatch, token: CapabilityToken) -> PolicyDecision:
        if not token.is_valid():
            return PolicyDecision(False, True, "Capability token is expired.")

        if self._path_escapes_workspace(patch.relative_path):
            return PolicyDecision(False, True, "Patch path escapes the workspace.")

        if not self._matches_any_prefix(patch.relative_path, token.can_write):
            return PolicyDecision(False, True, "Patch target is outside the token write scope.")

        if patch.risk in {"medium", "high"}:
            return PolicyDecision(True, True, f"{patch.risk.title()}-risk patch requires approval.")

        if patch.requires_human_approval:
            return PolicyDecision(True, True, "Patch is configured to require human approval.")

        return PolicyDecision(True, False, "Patch allowed under policy.")

    @staticmethod
    def _path_escapes_workspace(relative_path: str) -> bool:
        p = Path(relative_path)
        return p.is_absolute() or ".." in p.parts

    @staticmethod
    def _matches_any_prefix(relative_path: str, prefixes: tuple[str, ...]) -> bool:
        normalized = relative_path.strip("/")
        for prefix in prefixes:
            p = prefix.strip("/")
            if normalized == p or normalized.startswith(p + "/"):
                return True
        return False
