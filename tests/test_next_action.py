from sovereign_cortex import cli
from sovereign_cortex.events import EventType


class DummyRecordStore:
    calls = []

    def __init__(self, repo_root):
        self.repo_root = repo_root

    def append(self, events):
        self.__class__.calls.append(events)
        return []


class FailingOrchestrator:
    def __init__(self, repo_root, workspace_name="demo-project"):
        pass

    def handle_command(self, text, *, auto_approve=False, today=None):
        raise AssertionError("Next action report should be handled before update planning")


def test_cli_next_action_report_is_read_only(monkeypatch, capsys):
    DummyRecordStore.calls = []
    monkeypatch.setattr(cli, "LocalOrchestrator", FailingOrchestrator)
    monkeypatch.setattr(cli, "ActivityRecordStore", DummyRecordStore)

    cli.main(["--date", "2026-06-06", "Next action"])

    captured = capsys.readouterr()
    assert "Status: no_action" in captured.out
    assert "Next action for demo-project:" in captured.out
    assert "Task: Launch Website" in captured.out
    assert "Path: tasks/launch-website.md" in captured.out
    assert "active overdue task due 2026-06-05" in captured.out
    assert "Approval ID" not in captured.out
    assert len(DummyRecordStore.calls) == 1
    assert [event.event_type for event in DummyRecordStore.calls[0]] == [
        EventType.COMMAND_RECEIVED,
        EventType.TASK_COMPLETED,
    ]


def test_cli_next_action_detection_does_not_intercept_update_commands():
    result = cli.build_next_action_result(
        cli.Path(__file__).resolve().parents[1],
        "Mark next action done",
        "demo-project",
        cli.date.fromisoformat("2026-06-06"),
    )

    assert result is None
