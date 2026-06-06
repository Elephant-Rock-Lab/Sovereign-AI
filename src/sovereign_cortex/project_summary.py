from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

from .vault import MarkdownDocument


DONE_STATUSES = {"done", "complete", "completed", "closed"}


def summarize_project(tasks: Iterable[MarkdownDocument], *, workspace_name: str, today: date) -> str:
    task_list = list(tasks)
    status_counts: dict[str, int] = {}
    scheduled = 0
    overdue = 0
    due_next_7_days = 0
    with_dependencies = 0
    declared_dependencies = 0
    missing_dependencies = 0
    active_dependencies = 0
    by_id = {str(task.metadata.get("id", "")): task for task in task_list if task.metadata.get("id")}

    for task in task_list:
        metadata = task.metadata
        status = str(metadata.get("status", "unspecified")).lower()
        status_counts[status] = status_counts.get(status, 0) + 1

        dependencies = metadata.get("dependencies") or []
        if dependencies:
            with_dependencies += 1
            declared_dependencies += len(dependencies)
            for dependency in dependencies:
                dependency_task = by_id.get(str(dependency))
                if dependency_task is None:
                    missing_dependencies += 1
                    continue
                dependency_status = str(dependency_task.metadata.get("status", "unspecified")).lower()
                if dependency_status not in DONE_STATUSES:
                    active_dependencies += 1

        raw_due = metadata.get("due")
        if raw_due:
            scheduled += 1
            if status in DONE_STATUSES:
                continue
            try:
                due = date.fromisoformat(str(raw_due))
            except ValueError:
                continue
            if due < today:
                overdue += 1
            elif due <= today + timedelta(days=7):
                due_next_7_days += 1

    status_parts = ", ".join(f"{key}: {status_counts[key]}" for key in sorted(status_counts)) or "none"
    return "\n".join(
        [
            f"Project summary for {workspace_name}:",
            f"- Total tasks: {len(task_list)}",
            f"- Status counts: {status_parts}",
            f"- Due dates: scheduled: {scheduled}, overdue: {overdue}, due_next_7_days: {due_next_7_days}",
            f"- Dependencies: with_dependencies: {with_dependencies}, declared_dependencies: {declared_dependencies}",
            f"- Dependency problems: missing: {missing_dependencies}, active: {active_dependencies}",
        ]
    )
