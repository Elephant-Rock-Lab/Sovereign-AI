from __future__ import annotations

from datetime import date
from typing import Iterable

from .project_summary import DONE_STATUSES
from .vault import MarkdownDocument


def summarize_risk(tasks: Iterable[MarkdownDocument], *, workspace_name: str, today: date) -> str:
    task_list = list(tasks)
    overdue = 0
    with_dependencies = 0
    declared_dependencies = 0
    unowned = 0

    for task in task_list:
        metadata = task.metadata
        status = str(metadata.get("status", "unspecified")).lower()

        owner = str(metadata.get("owner", "")).strip()
        if not owner:
            unowned += 1

        dependencies = metadata.get("dependencies") or []
        if dependencies:
            with_dependencies += 1
            declared_dependencies += len(dependencies)

        if status in DONE_STATUSES:
            continue

        raw_due = metadata.get("due")
        if raw_due:
            try:
                due = date.fromisoformat(str(raw_due))
            except ValueError:
                continue
            if due < today:
                overdue += 1

    return "\n".join(
        [
            f"Project risk report for {workspace_name}:",
            f"- Active overdue tasks: {overdue}",
            f"- Tasks with dependencies: {with_dependencies}",
            f"- Declared dependencies: {declared_dependencies}",
            f"- Unowned tasks: {unowned}",
        ]
    )
