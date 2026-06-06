from datetime import date

from sovereign_cortex import cli
from sovereign_cortex.events import EventType
from sovereign_cortex.next_action import recommend_next_action
from sovereign_cortex.vault import MarkdownDocument


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


def _task(task_id: str, title: str, status: str, dependencies=None, due=None):
    metadata = {
        "id": task_id,
        "title": title,
        "status": status,
        "dependencies": dependencies or [],
    }
    if due:
        metadata["due"] = due
    return MarkdownDocument(
        relative_path=f"tasks/{task_id}.md",
        metadata=metadata,
        body=f"# {title}\n",
        raw="",
    )


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
    assert "unblocked overdue task due 2026-06-05" in captured.out
    assert "Approval ID" not in captured.out
    assert len(DummyRecordStore.calls) == 1
    assert [event.event_type for event in DummyRecordStore.calls[0]] == [
        EventType.COMMAND_RECEIVED,
        EventType.TASK_COMPLETED,
    ]


def test_next_action_skips_tasks_with_active_dependencies():
    report = recommend_next_action(
        [
            _task("blocked", "Blocked Task", "planned", dependencies=["dependency"], due="2026-06-01"),
            _task("dependency", "Dependency", "todo", due="2026-06-02"),
            _task("ready", "Ready Task", "planned", due="2026-06-03"),
        ],
        workspace_name="demo-project",
        today=date(2026, 6, 6),
    )

    assert "Task: Ready Task" in report
    assert "Path: tasks/ready.md" in report
    assert "unblocked" in report


def test_next_action_reports_when_all_active_tasks_are_blocked():
    report = recommend_next_action(
        [
            _task("blocked", "Blocked Task", "planned", dependencies=["dependency"], due="2026-06-01"),
            _task("dependency", "Dependency", "todo", due="2026-06-02"),
        ],
        workspace_name="demo-project",
        today=date(2026, 6, 6),
    )

    assert "No unblocked active tasks found." in report


def test_cli_next_action_detection_does_not_intercept_update_commands():
    result = cli.build_next_action_result(
        cli.Path(__file__).resolve().parents[1],
        "Mark next action done",
        "demo-project",
        cli.date.fromisoformat("2026-06-06"),
    )

    assert result is None
