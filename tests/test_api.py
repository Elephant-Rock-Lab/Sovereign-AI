import shutil
from pathlib import Path
from typing import Optional

from fastapi.testclient import TestClient

from sovereign_cortex.api import create_app


def _copy_repo(tmp_path: Path) -> Path:
    source = Path(__file__).resolve().parents[1]
    target = tmp_path / "repo"
    ignore = shutil.ignore_patterns(".git", ".pytest_cache", "__pycache__", "approval_requests")
    shutil.copytree(source, target, ignore=ignore)
    return target


def test_health_endpoint(tmp_path):
    repo_root = _copy_repo(tmp_path)
    client = TestClient(create_app(repo_root))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_command_endpoint_runs_read_only_command_and_records_events(tmp_path):
    repo_root = _copy_repo(tmp_path)
    client = TestClient(create_app(repo_root))

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
    assert "Dependency impact for Launch Website" in payload["message"]
    assert payload["approval_id"] is None
    assert [event["event_type"] for event in payload["events"]] == ["CommandReceived", "TaskCompleted"]
    activity_files = list((repo_root / "approval_requests" / "records").glob("*.jsonl"))
    assert activity_files


def test_command_endpoint_saves_approval_for_write_command(tmp_path):
    repo_root = _copy_repo(tmp_path)
    client = TestClient(create_app(repo_root))

    response = client.post(
        "/commands",
        json={
            "text": "Create task API Smoke due 2026-06-12",
            "workspace": "demo-project",
            "date": "2026-06-06",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "approval_saved"
    assert payload["approval_id"]
    approval_path = repo_root / "approval_requests" / "pending" / f"{payload['approval_id']}.json"
    assert approval_path.exists()
