from datetime import date

from fastapi.testclient import TestClient

from sovereign_cortex.api import create_app
from sovereign_cortex.events import EventEnvelope, EventType, TaskResult


class DummyRecordStore:
    calls = []

    def __init__(self, repo_root):
        self.repo_root = repo_root

    def append(self, events):
        self.__class__.calls.append(events)
        return []


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


def test_health_endpoint():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_command_endpoint_calls_orchestrator_and_records_events(monkeypatch):
    DummyRecordStore.calls = []
    DummyOrchestrator.calls = []
    monkeypatch.setattr("sovereign_cortex.api.ActivityRecordStore", DummyRecordStore)
    monkeypatch.setattr("sovereign_cortex.api.LocalOrchestrator", DummyOrchestrator)
    client = TestClient(create_app())

    response = client.post(
        "/commands",
        json={
            "text": "Show dependency impact for launch",
            "workspace": "demo-project",
            "date": "2026-06-06",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "no_action"
    assert payload["message"] == "dummy command handled"
    assert DummyOrchestrator.calls == [("Show dependency impact for launch", False, date(2026, 6, 6), "demo-project")]
    assert len(DummyRecordStore.calls) == 1
    assert payload["events"][0]["event_type"] == "CommandReceived"


def test_command_endpoint_runs_project_report_command(monkeypatch, tmp_path):
    DummyRecordStore.calls = []
    monkeypatch.setattr("sovereign_cortex.api.ActivityRecordStore", DummyRecordStore)
    client = TestClient(create_app(tmp_path))

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

    response = client.post(
        "/commands",
        json={
            "text": "Project summary",
            "workspace": "demo-project",
            "date": "2026-06-06",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "no_action"
    assert "Project summary for demo-project:" in payload["message"]
    assert payload["approval_id"] is None
    assert payload["events"][0]["payload"]["channel"] == "api"
    assert len(DummyRecordStore.calls) == 1
