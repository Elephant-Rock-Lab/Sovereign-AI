import shutil
from pathlib import Path

import pytest

from sovereign_cortex.orchestrator import LocalOrchestrator


def _copy_repo(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[1]
    target = tmp_path / "repo"
    ignore = shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__", "approval_requests")
    shutil.copytree(source, target, ignore=ignore)
    return target


def _raise_commit_error(self, paths, message):
    raise RuntimeError("commit unavailable")


def test_orchestrator_proposes_launch_patch():
    repo_root = Path(__file__).resolve().parents[1]
    result = LocalOrchestrator(repo_root).handle_command(
        "Move the website launch task to next Friday and explain the dependency impact",
        auto_approve=False,
    )
    assert result.status == "approval_saved"
    assert result.patches
    assert result.approval_id
    assert "Launch Website" in result.patches[0].after


def test_auto_approve_removes_created_file_when_commit_is_unavailable(tmp_path, monkeypatch):
    repo_root = _copy_repo(tmp_path)
    target = repo_root / "vault" / "demo-project" / "tasks" / "audit-check.md"
    monkeypatch.setattr("sovereign_cortex.orchestrator.GitAudit.commit_paths", _raise_commit_error)

    with pytest.raises(RuntimeError, match="commit unavailable"):
        LocalOrchestrator(repo_root).handle_command("Create task Audit Check", auto_approve=True)

    assert not target.exists()
