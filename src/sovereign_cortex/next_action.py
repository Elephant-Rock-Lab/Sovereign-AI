from __future__ import annotations

from datetime import date
from typing import Iterable

from .project_summary import DONE_STATUSES
from .vault import MarkdownDocument


def recommend_next_action(tasks: Iterable[MarkdownDocument], *, workspace_name: str, today: date) -> str:
    task_list = list(tasks)
    by_id = {str(task.metadata.get("id", "")): task for task in task_list if task.metadata.get("id")}
    candidates = []
    blocked_count = 0

    for task in task_list:
        metadata = task.metadata
        status = str(metadata.get("status", "unspecified")).lower()
        if status in DONE_STATUSES:
            continue
        if not dependencies_ready(task, by_id):
            blocked_count += 1
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
        if blocked_count:
            return f"Next action for {workspace_name}:\n- No unblocked active tasks found."
        return f"Next action for {workspace_name}:\n- No active tasks found."

    _, due, _, task = sorted(candidates)[0]
    metadata = task.metadata
    title = str(metadata.get("title", task.relative_path))
    raw_due = metadata.get("due")
    if raw_due:
        if due < today:
            reason = f"unblocked overdue task due {raw_due}"
        else:
            reason = f"unblocked task with nearest due date {raw_due}"
    else:
        reason = "unblocked unscheduled task selected by title order"

    return "\n".join(
        [
            f"Next action for {workspace_name}:",
            f"- Task: {title}",
            f"- Path: {task.relative_path}",
            f"- Reason: {reason}.",
        ]
    )


def dependencies_ready(task: MarkdownDocument, by_id: dict[str, MarkdownDocument]) -> bool:
    dependencies = task.metadata.get("dependencies") or []
    if not isinstance(dependencies, list):
        dependencies = [dependencies]
    for dependency in dependencies:
        dependency_task = by_id.get(str(dependency))
        if dependency_task is None:
            return False
        status = str(dependency_task.metadata.get("status", "unspecified")).lower()
        if status not in DONE_STATUSES:
            return False
    return True
