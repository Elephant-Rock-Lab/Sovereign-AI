from sovereign_cortex import cli
from sovereign_cortex.events import EventEnvelope, EventType, TaskResult


class DummyOrchestrator:
    def __init__(self, repo_root, workspace_name="demo-project"):
        self.repo_root = repo_root
        self.workspace_name = workspace_name

    def handle_command(self, text, *, auto_approve=False, today=None):
        assert text == "Move the website launch task to next Friday and explain the dependency impact"
        assert auto_approve is False
        event = EventEnvelope(
            event_type=EventType.COMMAND_RECEIVED,
            sender="test",
            recipient="test",
            workspace="demo-project",
            payload={"text": text},
        )
        return TaskResult(status="no_action", message="dummy command handled", events=[event])


class DummyRecordStore:
    calls = []

    def __init__(self, repo_root):
        self.repo_root = repo_root

    def append(self, events):
        self.__class__.calls.append(events)
        return []


def test_cli_accepts_natural_language_command(monkeypatch, capsys):
    DummyRecordStore.calls = []
    monkeypatch.setattr(cli, "LocalOrchestrator", DummyOrchestrator)
    monkeypatch.setattr(cli, "ActivityRecordStore", DummyRecordStore)

    cli.main(["Move the website launch task to next Friday and explain the dependency impact"])

    captured = capsys.readouterr()
    assert "Status: no_action" in captured.out
    assert "dummy command handled" in captured.out
    assert len(DummyRecordStore.calls) == 1
    assert DummyRecordStore.calls[0][0].event_type == EventType.COMMAND_RECEIVED


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
