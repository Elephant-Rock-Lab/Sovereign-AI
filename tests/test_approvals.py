import shutil
from pathlib import Path

from sovereign_cortex.approvals import ApprovalStore
from sovereign_cortex.orchestrator import LocalOrchestrator


def _copy_repo(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[1]
    target = tmp_path / "repo"
    ignore = shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__", "approval_requests")
    shutil.copytree(source, target, ignore=ignore)
    return target


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
