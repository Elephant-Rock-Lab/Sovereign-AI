from __future__ import annotations

from datetime import date as Date
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .activity import ActivityRecordStore
from .events import CommandPayload, EventEnvelope, EventType, TaskResult
from .orchestrator import LocalOrchestrator
from .project_reports import handle_project_report
from .vault import Vault
from .workspace import WorkspaceRegistry


class CommandRequest(BaseModel):
    text: str = Field(min_length=1)
    workspace: str = "demo-project"
    date: Date | None = None


class CommandResponse(BaseModel):
    status: str
    message: str
    approval_id: str | None = None
    commit_hash: str | None = None
    events: list[dict[str, Any]]


def create_app(repo_root: Path | None = None) -> FastAPI:
    root = repo_root or Path(__file__).resolve().parents[2]
    app = FastAPI(title="Sovereign AI Local Control Plane", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/commands", response_model=CommandResponse)
    def run_command(request: CommandRequest) -> CommandResponse:
        today = request.date or Date.today()
        result = build_report_result(root, request.text, request.workspace, today)
        if result is None:
            result = LocalOrchestrator(root, request.workspace).handle_command(
                request.text,
                auto_approve=False,
                today=request.date,
            )
        ActivityRecordStore(root).append(result.events)
        return CommandResponse(
            status=result.status,
            message=result.message,
            approval_id=result.approval_id,
            commit_hash=result.commit_hash,
            events=[event.model_dump(mode="json") for event in result.events],
        )

    return app


def build_report_result(repo_root: Path, command: str, workspace_name: str, today: Date) -> TaskResult | None:
    workspace = WorkspaceRegistry(repo_root).get(workspace_name)
    message = handle_project_report(command, vault=Vault(workspace.vault_root), workspace_name=workspace_name, today=today)
    if message is None:
        return None

    command_event = EventEnvelope(
        event_type=EventType.COMMAND_RECEIVED,
        sender="user/api",
        recipient="agent/orchestrator",
        workspace=workspace_name,
        payload=CommandPayload(channel="api", text=command).model_dump(),
    )
    completed_event = EventEnvelope(
        event_type=EventType.TASK_COMPLETED,
        sender="agent/orchestrator",
        recipient="user/api",
        workspace=workspace_name,
        payload={"status": "no_action", "reason": "Read-only project report completed."},
    )
    completed_event.correlation_id = command_event.correlation_id
    return TaskResult(status="no_action", message=message, events=[command_event, completed_event])


app = create_app()
