from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    COMMAND_RECEIVED = "CommandReceived"
    TASK_PLANNED = "TaskPlanned"
    POLICY_CHECKED = "PolicyChecked"
    PATCH_PROPOSED = "PatchProposed"
    APPROVAL_REQUESTED = "ApprovalRequested"
    PATCH_APPROVED = "PatchApproved"
    PATCH_REJECTED = "PatchRejected"
    PATCH_APPLIED = "PatchApplied"
    AUDIT_COMMITTED = "AuditCommitted"
    TASK_COMPLETED = "TaskCompleted"
    TASK_REJECTED = "TaskRejected"


class Priority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class EventEnvelope(BaseModel):
    """Canonical event wrapper for all Cortex messages.

    This is intentionally compatible with a future Solace/A2A event layer.
    """

    msg_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: EventType
    sender: str
    recipient: str
    workspace: str
    priority: Priority = Priority.NORMAL
    ttl_seconds: int = 3600
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    payload: dict[str, Any]


class CommandPayload(BaseModel):
    channel: Literal["cli", "telegram", "cherry", "api"] = "cli"
    text: str
    user_id: str = "local-user"


class PatchOperation(str, Enum):
    UPDATE_FILE = "update_file"
    CREATE_FILE = "create_file"


class ProposedPatch(BaseModel):
    operation: PatchOperation
    relative_path: str
    before: str | None
    after: str
    summary: str
    risk: Literal["low", "medium", "high"] = "low"
    requires_human_approval: bool = True


class TaskResult(BaseModel):
    status: Literal["proposed", "approval_saved", "applied", "rejected", "no_action"]
    message: str
    events: list[EventEnvelope] = Field(default_factory=list)
    patches: list[ProposedPatch] = Field(default_factory=list)
    commit_hash: str | None = None
    approval_id: str | None = None
