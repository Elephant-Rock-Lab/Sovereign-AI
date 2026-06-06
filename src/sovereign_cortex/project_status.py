from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any

from .vault import MarkdownDocument, Vault


def project_status_report(vault: Vault, workspace_name: str, today: date) -> str:
    tasks = vault.list_task_docs()
    if not tasks:
        return f"Project status for {workspace_name}: no tasks found."

    counts = Counter(str(task.metadata.get("status", "unspecified")) for task in tasks)
    by_status = ", ".join(f"{status}={count}" for status, count in sorted(counts.items()))

    overdue: list[str] = []
    upcoming: list[str] = []
    for task in tasks:
        due = parse_due(task.metadata.get("due"))
        if due is None:
            continue
        title = task_title(task)
        if due < today:
            overdue.append(f"{title} due {due.isoformat()}")
        elif due <= today + timedelta(days=7):
            upcoming.append(f"{title} due {due.isoformat()}")

    lines = [
        f"Project status for {workspace_name}",
        f"Total tasks: {len(tasks)}",
        f"By status: {by_status}",
        f"Overdue: {format_items(overdue)}",
        f"Upcoming: {format_items(upcoming)}",
        f"Dependency issues: {format_items(dependency_issues(tasks))}",
    ]
    return "\n".join(lines)


def dependency_issues(tasks: list[MarkdownDocument]) -> list[str]:
    by_id = {str(task.metadata.get("id", "")): task for task in tasks if task.metadata.get("id")}
    issues: list[str] = []
    for task in tasks:
        dependencies = task.metadata.get("dependencies") or []
        if not isinstance(dependencies, list):
            dependencies = [dependencies]
        for dependency in dependencies:
            dependency_id = str(dependency)
            dependency_task = by_id.get(dependency_id)
            if dependency_task is None:
                issues.append(f"{task_title(task)} depends on missing {dependency_id}")
                continue
            status = str(dependency_task.metadata.get("status", "unspecified"))
            if status != "done":
                issues.append(f"{task_title(task)} depends on {dependency_id} ({status})")
    return issues


def parse_due(value: Any) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def task_title(task: MarkdownDocument) -> str:
    return str(task.metadata.get("title") or task.metadata.get("id") or task.relative_path)


def format_items(items: list[str]) -> str:
    return "; ".join(items) if items else "none"
