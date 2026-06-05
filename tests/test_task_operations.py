import shutil
from datetime import date
from pathlib import Path

from sovereign_cortex.events import PatchOperation
from sovereign_cortex.orchestrator import LocalOrchestrator


def _copy_repo(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[1]
    target = tmp_path / "repo"
    ignore = shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__", "approval_requests")
    shutil.copytree(source, target, ignore=ignore)
    return target


def test_create_task_saves_create_file_approval(tmp_path):
    repo_root = _copy_repo(tmp_path)
    result = LocalOrchestrator(repo_root).handle_command(
        "Create task Write launch copy due 2026-06-12 owner Fatima",
        auto_approve=False,
    )

    assert result.status == "approval_saved"
    assert result.approval_id
    assert result.patches[0].operation == PatchOperation.CREATE_FILE
    assert result.patches[0].relative_path == "tasks/write-launch-copy.md"
    assert "title: Write launch copy" in result.patches[0].after
    assert "owner: Fatima" in result.patches[0].after


def test_mark_task_done_saves_update_approval(tmp_path):
    repo_root = _copy_repo(tmp_path)
    result = LocalOrchestrator(repo_root).handle_command(
        "Mark launch done",
        auto_approve=False,
    )

    assert result.status == "approval_saved"
    assert result.patches[0].operation == PatchOperation.UPDATE_FILE
    assert result.patches[0].relative_path == "tasks/launch-website.md"
    assert "status: done" in result.patches[0].after


def test_change_owner_saves_update_approval(tmp_path):
    repo_root = _copy_repo(tmp_path)
    result = LocalOrchestrator(repo_root).handle_command(
        "Change owner of launch to Omar",
        auto_approve=False,
    )

    assert result.status == "approval_saved"
    assert result.patches[0].relative_path == "tasks/launch-website.md"
    assert "owner: Omar" in result.patches[0].after


def test_shift_due_date_saves_update_approval(tmp_path):
    repo_root = _copy_repo(tmp_path)
    result = LocalOrchestrator(repo_root).handle_command(
        "Shift launch due date by 3 days",
        auto_approve=False,
        today=date(2026, 6, 5),
    )

    assert result.status == "approval_saved"
    assert result.patches[0].relative_path == "tasks/launch-website.md"
    assert "due: '2026-06-08'" in result.patches[0].after or "due: 2026-06-08" in result.patches[0].after


def test_dependency_impact_is_read_only(tmp_path):
    repo_root = _copy_repo(tmp_path)
    result = LocalOrchestrator(repo_root).handle_command(
        "Show dependency impact for launch",
        auto_approve=False,
    )

    assert result.status == "no_action"
    assert not result.approval_id
    assert not result.patches
    assert "Dependency impact for Launch Website" in result.message
    assert "competitor-research" in result.message


def test_existing_launch_next_friday_behavior_remains_supported(tmp_path):
    repo_root = _copy_repo(tmp_path)
    result = LocalOrchestrator(repo_root).handle_command(
        "Move the website launch task to next Friday and explain the dependency impact",
        auto_approve=False,
        today=date(2026, 6, 5),
    )

    assert result.status == "approval_saved"
    assert result.patches
    assert "Launch Website" in result.patches[0].after
    assert "2026-06-12" in result.patches[0].after
