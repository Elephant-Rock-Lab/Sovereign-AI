from __future__ import annotations

from datetime import date as Date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .activity import ActivityRecordStore
from .approvals import ApprovalConflictError, ApprovalRequest, ApprovalStatus, ApprovalStore
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


class RejectApprovalRequest(BaseModel):
    reason: str | None = None


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

    @app.get("/approvals", response_model=list[ApprovalRequest])
    def list_approvals(status: ApprovalStatus = "pending") -> list[ApprovalRequest]:
        return ApprovalStore(root).list(status)

    @app.get("/approvals/{approval_id}", response_model=ApprovalRequest)
    def get_approval(approval_id: str) -> ApprovalRequest:
        try:
            return ApprovalStore(root).get(approval_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/approvals/{approval_id}/approve", response_model=ApprovalRequest)
    def approve_approval(approval_id: str) -> ApprovalRequest:
        try:
            return ApprovalStore(root).approve(approval_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ApprovalConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/approvals/{approval_id}/reject", response_model=ApprovalRequest)
    def reject_approval(approval_id: str, request: RejectApprovalRequest) -> ApprovalRequest:
        try:
            return ApprovalStore(root).reject(approval_id, request.reason)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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
