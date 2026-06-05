from sovereign_cortex import cli
from sovereign_cortex.events import TaskResult


class DummyOrchestrator:
    def __init__(self, repo_root, workspace_name="demo-project"):
        self.repo_root = repo_root
        self.workspace_name = workspace_name

    def handle_command(self, text, *, auto_approve=False, today=None):
        assert text == "Move the website launch task to next Friday and explain the dependency impact"
        assert auto_approve is False
        return TaskResult(status="no_action", message="dummy command handled")


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
