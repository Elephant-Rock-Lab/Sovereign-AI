from datetime import datetime, timedelta, timezone

from sovereign_cortex.events import PatchOperation, ProposedPatch
from sovereign_cortex.policy import CapabilityToken, PolicyEngine


def test_policy_rejects_workspace_escape():
    token = CapabilityToken(
        workspace="demo-project",
        can_read=("tasks",),
        can_write=("tasks",),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=1),
    )
    patch = ProposedPatch(
        operation=PatchOperation.UPDATE_FILE,
        relative_path="../secrets.md",
        before="",
        after="x",
        summary="bad",
    )
    decision = PolicyEngine().evaluate_patch(patch, token)
    assert not decision.allowed


def test_policy_allows_scoped_task_patch_with_approval():
    token = CapabilityToken(
        workspace="demo-project",
        can_read=("tasks",),
        can_write=("tasks",),
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=1),
    )
    patch = ProposedPatch(
        operation=PatchOperation.UPDATE_FILE,
        relative_path="tasks/launch-website.md",
        before="old",
        after="new",
        summary="ok",
    )
    decision = PolicyEngine().evaluate_patch(patch, token)
    assert decision.allowed
    assert decision.approval_required
