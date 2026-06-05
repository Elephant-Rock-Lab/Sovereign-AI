import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sovereign_cortex.approvals import ApprovalConflictError, ApprovalStore
from sovereign_cortex.events import PatchOperation, ProposedPatch
from sovereign_cortex.orchestrator import LocalOrchestrator
from sovereign_cortex.policy import PolicyDecision


def _copy_repo(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[1]
    target = tmp_path / "repo"
    ignore = shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__", "approval_requests")
    shutil.copytree(source, target, ignore=ignore)
    return target


def _rewrite_request(path: Path, request) -> None:
    path.write_text(request.model_dump_json(indent=2) + "\n", encoding="utf-8")


def test_orchestrator_saves_pending_approval(tmp_path):
    repo_root = _copy_repo(tmp_path)
    result = LocalOrchestrator(repo_root).handle_command(
        "Move the website launch task to next Friday and explain the dependency impact",
        auto_approve=False,
    )

    assert result.status == "approval_saved"
    assert result.approval_id
    approval_path = repo_root / "approval_requests" / "pending" / f"{result.approval_id}.json"
    assert approval_path.exists()

    request = ApprovalStore(repo_root).get(result.approval_id)
    assert request.status == "pending"
    assert request.patch.relative_path == "tasks/launch-website.md"
    assert request.policy_decision.allowed


def test_approval_reject_moves_request_without_writing(tmp_path):
    repo_root = _copy_repo(tmp_path)
    result = LocalOrchestrator(repo_root).handle_command(
        "Move the website launch task to next Friday and explain the dependency impact",
        auto_approve=False,
    )
    task_path = repo_root / "vault" / "demo-project" / "tasks" / "launch-website.md"
    before = task_path.read_text(encoding="utf-8")

    rejected = ApprovalStore(repo_root).reject(result.approval_id, "Not now.")

    assert rejected.status == "rejected"
    assert (repo_root / "approval_requests" / "rejected" / f"{result.approval_id}.json").exists()
    assert not (repo_root / "approval_requests" / "pending" / f"{result.approval_id}.json").exists()
    assert task_path.read_text(encoding="utf-8") == before


def test_approval_approve_applies_patch_and_moves_request(tmp_path):
    repo_root = _copy_repo(tmp_path)
    result = LocalOrchestrator(repo_root).handle_command(
        "Move the website launch task to next Friday and explain the dependency impact",
        auto_approve=False,
    )

    approved = ApprovalStore(repo_root).approve(result.approval_id)

    assert approved.status == "approved"
    assert (repo_root / "approval_requests" / "approved" / f"{result.approval_id}.json").exists()
    assert not (repo_root / "approval_requests" / "pending" / f"{result.approval_id}.json").exists()
    task_text = (repo_root / "vault" / "demo-project" / "tasks" / "launch-website.md").read_text(encoding="utf-8")
    assert "due: '" in task_text or "due: 20" in task_text
    assert "Cortex Notes" in task_text


def test_approval_rejects_stale_update_and_keeps_request_pending(tmp_path):
    repo_root = _copy_repo(tmp_path)
    result = LocalOrchestrator(repo_root).handle_command(
        "Move the website launch task to next Friday and explain the dependency impact",
        auto_approve=False,
    )
    task_path = repo_root / "vault" / "demo-project" / "tasks" / "launch-website.md"
    changed = task_path.read_text(encoding="utf-8") + "\nManual edit after approval request.\n"
    task_path.write_text(changed, encoding="utf-8")

    with pytest.raises(ApprovalConflictError):
        ApprovalStore(repo_root).approve(result.approval_id)

    assert (repo_root / "approval_requests" / "pending" / f"{result.approval_id}.json").exists()
    assert not (repo_root / "approval_requests" / "approved" / f"{result.approval_id}.json").exists()
    assert task_path.read_text(encoding="utf-8") == changed


def test_approval_rejects_stale_create_and_keeps_request_pending(tmp_path):
    repo_root = _copy_repo(tmp_path)
    target = repo_root / "vault" / "demo-project" / "tasks" / "new-task.md"
    target.write_text("already exists\n", encoding="utf-8")

    store = ApprovalStore(repo_root)
    request = store.create(
        workspace="demo-project",
        command_text="Create a new task",
        correlation_id="test-correlation",
        patch=ProposedPatch(
            operation=PatchOperation.CREATE_FILE,
            relative_path="tasks/new-task.md",
            before=None,
            after="new content\n",
            summary="Create new task.",
        ),
        policy_decision=PolicyDecision(allowed=True, approval_required=True, reason="ok"),
    )

    with pytest.raises(ApprovalConflictError):
        store.approve(request.approval_id)

    assert (repo_root / "approval_requests" / "pending" / f"{request.approval_id}.json").exists()
    assert target.read_text(encoding="utf-8") == "already exists\n"


def test_approval_cannot_approve_already_rejected_request(tmp_path):
    repo_root = _copy_repo(tmp_path)
    result = LocalOrchestrator(repo_root).handle_command("Create task Rejected Once", auto_approve=False)
    store = ApprovalStore(repo_root)
    store.reject(result.approval_id, "No.")

    with pytest.raises(ValueError, match="already rejected"):
        store.approve(result.approval_id)


def test_prune_archives_old_resolved_requests_and_keeps_pending(tmp_path):
    repo_root = _copy_repo(tmp_path)
    orchestrator = LocalOrchestrator(repo_root)
    store = ApprovalStore(repo_root)
    old_time = datetime.now(timezone.utc) - timedelta(days=3)

    pending_result = orchestrator.handle_command("Create task Pending Prune Safety", auto_approve=False)
    pending_path = repo_root / "approval_requests" / "pending" / f"{pending_result.approval_id}.json"
    pending_request = store.get(pending_result.approval_id).model_copy(update={"created_at": old_time})
    _rewrite_request(pending_path, pending_request)

    approved_result = orchestrator.handle_command("Create task Approved Prune Safety", auto_approve=False)
    approved = store.approve(approved_result.approval_id).model_copy(update={"updated_at": old_time})
    approved_path = repo_root / "approval_requests" / "approved" / f"{approved.approval_id}.json"
    _rewrite_request(approved_path, approved)

    rejected_result = orchestrator.handle_command("Create task Rejected Prune Safety", auto_approve=False)
    rejected = store.reject(rejected_result.approval_id, "No.").model_copy(update={"updated_at": old_time})
    rejected_path = repo_root / "approval_requests" / "rejected" / f"{rejected.approval_id}.json"
    _rewrite_request(rejected_path, rejected)

    pruned = store.prune(older_than_days=1)

    assert {request.approval_id for request in pruned} == {approved.approval_id, rejected.approval_id}
    assert pending_path.exists()
    assert not approved_path.exists()
    assert not rejected_path.exists()
    assert (repo_root / "approval_requests" / "pruned" / "approved" / f"{approved.approval_id}.json").exists()
    assert (repo_root / "approval_requests" / "pruned" / "rejected" / f"{rejected.approval_id}.json").exists()
