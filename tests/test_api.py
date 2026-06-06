from datetime import date

from sovereign_cortex.api import CommandRequest, build_report_result, create_app
from sovereign_cortex.events import EventEnvelope, EventType, TaskResult


class DummyOrchestrator:
    calls = []

    def __init__(self, repo_root, workspace_name="demo-project"):
        self.repo_root = repo_root
        self.workspace_name = workspace_name

    def handle_command(self, text, *, auto_approve=False, today=None):
        self.__class__.calls.append((text, auto_approve, today, self.workspace_name))
        event = EventEnvelope(
            event_type=EventType.COMMAND_RECEIVED,
            sender="test/api",
            recipient="agent/orchestrator",
            workspace=self.workspace_name,
            payload={"text": text},
        )
        return TaskResult(status="no_action", message="dummy command handled", events=[event])


def test_app_exposes_expected_routes():
    app = create_app()
    paths = {route.path for route in app.routes}

    assert "/health" in paths
    assert "/commands" in paths


def test_command_request_parses_date():
    request = CommandRequest(text="Show dependency impact for launch", date="2026-06-06")

    assert request.date == date(2026, 6, 6)


def test_project_report_result_builds_api_events(tmp_path):
    vault = tmp_path / "vault" / "demo-project" / "tasks"
    vault.mkdir(parents=True)
    (tmp_path / "workspaces.yaml").write_text(
        "workspaces:\n  demo-project:\n    vault_root: vault/demo-project\n",
        encoding="utf-8",
    )
    (vault / "launch.md").write_text(
        "---\ntitle: Launch\nstatus: planned\ndue: 2026-06-05\ndependencies: []\n---\n# Launch\n",
        encoding="utf-8",
    )

    result = build_report_result(tmp_path, "Project summary", "demo-project", date(2026, 6, 6))

    assert result is not None
    assert result.status == "no_action"
    assert "Project summary for demo-project:" in result.message
    assert result.approval_id is None
    assert result.events[0].event_type == EventType.COMMAND_RECEIVED
    assert result.events[0].payload["channel"] == "api"
