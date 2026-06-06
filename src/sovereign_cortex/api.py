from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .activity import ActivityRecordStore
from .orchestrator import LocalOrchestrator


class CommandRequest(BaseModel):
    text: str = Field(min_length=1)
    workspace: str = "demo-project"
    auto_approve: bool = False
    date: date | None = None


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
        result = LocalOrchestrator(root, request.workspace).handle_command(
            request.text,
            auto_approve=request.auto_approve,
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


app = create_app()
