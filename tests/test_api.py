from datetime import date

from sovereign_cortex.api import CommandRequest, build_report_result, create_app
from sovereign_cortex.events import EventType


def _endpoint(app, path: str):
    for route in app.routes:
        if route.path == path:
            return route.endpoint
    raise AssertionError(f"Route not found: {path}")


def _write_demo_workspace(tmp_path):
    vault = tmp_path / "vault" / "demo-project" / "tasks"
    vault.mkdir(parents=True)
    (tmp_path / "workspaces.yaml").write_text(
        "workspaces:\n  demo-project:\n    vault_root: vault/demo-project\n",
        encoding="utf-8",
    )
    (vault / "launch.md").write_text(
        "---\nid: launch\ntitle: Launch\nstatus: planned\ndue: 2026-06-05\ndependencies: []\n---\n# Launch\n",
        encoding="utf-8",
    )


def test_app_exposes_expected_routes():
    app = create_app()
    paths = {route.path for route in app.routes}

    assert "/health" in paths
    assert "/commands" in paths


def test_health_endpoint_returns_ok():
    app = create_app()
    health = _endpoint(app, "/health")

    assert health() == {"status": "ok"}


def test_command_endpoint_runs_read_only_report_and_records_events(tmp_path):
    _write_demo_workspace(tmp_path)
    app = create_app(tmp_path)
    run_command = _endpoint(app, "/commands")

    response = run_command(CommandRequest(text="Project summary", date=date(2026, 6, 6)))

    assert response.status == "no_action"
    assert response.approval_id is None
    assert "Project summary for demo-project:" in response.message
    assert response.events[0]["event_type"] == "CommandReceived"
    records = list((tmp_path / "approval_requests" / "records").glob("*.jsonl"))
    assert records


def test_project_report_result_builds_api_events(tmp_path):
    _write_demo_workspace(tmp_path)

    result = build_report_result(tmp_path, "Project summary", "demo-project", date(2026, 6, 6))

    assert result is not None
    assert result.status == "no_action"
    assert "Project summary for demo-project:" in result.message
    assert result.approval_id is None
    assert result.events[0].event_type == EventType.COMMAND_RECEIVED
    assert result.events[0].payload["channel"] == "api"
