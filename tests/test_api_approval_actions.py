from fastapi import HTTPException
import pytest

from sovereign_cortex.api import RejectApprovalRequest, create_app
from sovereign_cortex.approvals import ApprovalStore
from sovereign_cortex.events import PatchOperation, ProposedPatch
from sovereign_cortex.policy import PolicyDecision


def _endpoint(app, path: str):
    for route in app.routes:
        if route.path == path:
            return route.endpoint
    raise AssertionError(f"Route not found: {path}")


def _write_workspace(tmp_path):
    vault = tmp_path / "vault" / "demo-project" / "tasks"
    vault.mkdir(parents=True)
    (tmp_path / "workspaces.yaml").write_text(
        "workspaces:\n  demo-project:\n    vault_root: vault/demo-project\n",
        encoding="utf-8",
    )
    task = vault / "launch.md"
    task.write_text(
        "---\nid: launch\ntitle: Launch\nstatus: planned\n---\n# Launch\n",
        encoding="utf-8",
    )
    return task


def _create_request(tmp_path, *, before: str, after: str):
    return ApprovalStore(tmp_path).create(
        workspace="demo-project",
        command_text="Update launch task",
        correlation_id="api-action-test",
        patch=ProposedPatch(
            operation=PatchOperation.UPDATE_FILE,
            relative_path="tasks/launch.md",
            before=before,
            after=after,
            summary="Update launch task",
            risk="medium",
            requires_human_approval=True,
        ),
        policy_decision=PolicyDecision(
            allowed=True,
            approval_required=True,
            reason="Medium-risk patch requires approval.",
        ),
    )


def test_approval_action_routes_are_registered():
    app = create_app()
    paths = {route.path for route in app.routes}

    assert "/approvals/{approval_id}/approve" in paths
    assert "/approvals/{approval_id}/reject" in paths


def test_approval_approve_route_applies_patch_and_moves_request(tmp_path):
    task = _write_workspace(tmp_path)
    before = task.read_text(encoding="utf-8")
    after = before.replace("status: planned", "status: active")
    request = _create_request(tmp_path, before=before, after=after)
    approve = _endpoint(create_app(tmp_path), "/approvals/{approval_id}/approve")

    response = approve(request.approval_id)

    assert response.status == "approved"
    assert response.commit_hash
    assert task.read_text(encoding="utf-8") == after
    assert (tmp_path / "approval_requests" / "approved" / f"{request.approval_id}.json").exists()
    assert not (tmp_path / "approval_requests" / "pending" / f"{request.approval_id}.json").exists()


def test_approval_approve_route_returns_409_for_conflict(tmp_path):
    task = _write_workspace(tmp_path)
    request = _create_request(tmp_path, before="older content", after="new content")
    approve = _endpoint(create_app(tmp_path), "/approvals/{approval_id}/approve")

    with pytest.raises(HTTPException) as error:
        approve(request.approval_id)

    assert error.value.status_code == 409
    assert task.exists()
    assert (tmp_path / "approval_requests" / "pending" / f"{request.approval_id}.json").exists()


def test_approval_reject_route_moves_request_without_writing(tmp_path):
    task = _write_workspace(tmp_path)
    before = task.read_text(encoding="utf-8")
    request = _create_request(tmp_path, before=before, after=before + "\nextra\n")
    reject = _endpoint(create_app(tmp_path), "/approvals/{approval_id}/reject")

    response = reject(request.approval_id, RejectApprovalRequest(reason="Not now."))

    assert response.status == "rejected"
    assert response.rejection_reason == "Not now."
    assert task.read_text(encoding="utf-8") == before
    assert (tmp_path / "approval_requests" / "rejected" / f"{request.approval_id}.json").exists()
    assert not (tmp_path / "approval_requests" / "pending" / f"{request.approval_id}.json").exists()
