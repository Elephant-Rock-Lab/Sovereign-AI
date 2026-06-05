import pytest

from sovereign_cortex import cli
from sovereign_cortex.approvals import ApprovalRequest, PolicyDecisionSnapshot
from sovereign_cortex.events import PatchOperation, ProposedPatch, TaskResult


class DummyOrchestrator:
    def __init__(self, repo_root, workspace_name="demo-project"):
        self.repo_root = repo_root
        self.workspace_name = workspace_name

    def handle_command(self, text, *, auto_approve=False, today=None):
        assert text == "Move the website launch task to next Friday and explain the dependency impact"
        assert auto_approve is False
        return TaskResult(status="no_action", message="dummy command handled")


class DummyApprovalStore:
    def __init__(self, repo_root):
        self.repo_root = repo_root

    def get(self, approval_id):
        if approval_id == "missing":
            raise FileNotFoundError("Approval request not found: missing")
        return ApprovalRequest(
            approval_id=approval_id,
            workspace="demo-project",
            command_text="Create task CLI Diff",
            correlation_id="cli-test",
            patch=ProposedPatch(
                operation=PatchOperation.CREATE_FILE,
                relative_path="tasks/cli-diff.md",
                before=None,
                after="---\ntitle: CLI Diff\n---\n# CLI Diff\n",
                summary="Create CLI diff task.",
            ),
            policy_decision=PolicyDecisionSnapshot(allowed=True, approval_required=True, reason="ok"),
        )


class DummyResolvedApprovalStore(DummyApprovalStore):
    def approve(self, approval_id):
        raise ValueError(f"Approval request is already rejected: {approval_id}")


def test_cli_accepts_natural_language_command(monkeypatch, capsys):
    monkeypatch.setattr(cli, "LocalOrchestrator", DummyOrchestrator)

    cli.main(["Move the website launch task to next Friday and explain the dependency impact"])

    captured = capsys.readouterr()
    assert "Status: no_action" in captured.out
    assert "dummy command handled" in captured.out


def test_cli_dispatches_approvals_subcommand(monkeypatch):
    calls = []

    def fake_handle_approvals(repo_root, args):
        calls.append((repo_root, args.approval_command, args.status))

    monkeypatch.setattr(cli, "handle_approvals", fake_handle_approvals)

    cli.main(["approvals", "list", "--status", "pending"])

    assert calls
    _, approval_command, status = calls[0]
    assert approval_command == "list"
    assert status == "pending"


def test_cli_approval_diff_prints_stored_patch(monkeypatch, capsys):
    monkeypatch.setattr(cli, "ApprovalStore", DummyApprovalStore)

    cli.main(["approvals", "diff", "approval-1"])

    captured = capsys.readouterr()
    assert "--- Proposed Patch ---" in captured.out
    assert "tasks/cli-diff.md" in captured.out
    assert "CLI Diff" in captured.out


def test_cli_missing_approval_exits_cleanly(monkeypatch, capsys):
    monkeypatch.setattr(cli, "ApprovalStore", DummyApprovalStore)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["approvals", "show", "missing"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "Error: Approval request not found: missing" in captured.out
    assert "Traceback" not in captured.err


def test_cli_already_resolved_approval_exits_cleanly(monkeypatch, capsys):
    monkeypatch.setattr(cli, "ApprovalStore", DummyResolvedApprovalStore)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["approvals", "approve", "approval-1"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "Error: Approval request is already rejected: approval-1" in captured.out
    assert "Traceback" not in captured.err
