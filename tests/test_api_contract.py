from fastapi.testclient import TestClient

from sovereign_cortex.api import create_app


def _write_workspace(tmp_path):
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


def test_health_contract_uses_http_client():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_commands_contract_serializes_report_response(tmp_path):
    _write_workspace(tmp_path)
    client = TestClient(create_app(tmp_path))

    response = client.post(
        "/commands",
        json={"text": "Project summary", "date": "2026-06-06"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"status", "message", "approval_id", "commit_hash", "events"}
    assert payload["status"] == "no_action"
    assert payload["approval_id"] is None
    assert payload["commit_hash"] is None
    assert "Project summary for demo-project:" in payload["message"]
    assert payload["events"][0]["event_type"] == "CommandReceived"
    assert payload["events"][0]["payload"]["channel"] == "api"
