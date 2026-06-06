from __future__ import annotations

from datetime import date
from typing import Iterable

from .project_summary import DONE_STATUSES
from .vault import MarkdownDocument


def recommend_next_action(tasks: Iterable[MarkdownDocument], *, workspace_name: str, today: date) -> str:
    candidates = []
    for task in tasks:
        metadata = task.metadata
        status = str(metadata.get("status", "unspecified")).lower()
        if status in DONE_STATUSES:
            continue

        raw_due = metadata.get("due")
        due = None
        if raw_due:
            try:
                due = date.fromisoformat(str(raw_due))
            except ValueError:
                due = None

        title = str(metadata.get("title", task.relative_path))
        candidates.append((due is None, due or date.max, title.lower(), task))

    if not candidates:
        return f"Next action for {workspace_name}:\n- No active tasks found."

    _, due, _, task = sorted(candidates)[0]
    metadata = task.metadata
    title = str(metadata.get("title", task.relative_path))
    raw_due = metadata.get("due")
    if raw_due:
        if due < today:
            reason = f"active overdue task due {raw_due}"
        else:
            reason = f"active task with nearest due date {raw_due}"
    else:
        reason = "active unscheduled task selected by title order"

    return "\n".join(
        [
            f"Next action for {workspace_name}:",
            f"- Task: {title}",
            f"- Path: {task.relative_path}",
            f"- Reason: {reason}.",
        ]
    )
