from datetime import date

from sovereign_cortex.project_summary import summarize_project
from sovereign_cortex.vault import MarkdownDocument


def _task(task_id: str, title: str, status: str, dependencies=None, due=None):
    metadata = {
        "id": task_id,
        "title": title,
        "status": status,
        "dependencies": dependencies or [],
    }
    if due:
        metadata["due"] = due
    return MarkdownDocument(
        relative_path=f"tasks/{task_id}.md",
        metadata=metadata,
        body=f"# {title}\n",
        raw="",
    )


def test_project_summary_reports_dependency_problem_counts():
    report = summarize_project(
        [
            _task("blocked", "Blocked Task", "planned", dependencies=["active", "missing-task"]),
            _task("active", "Active Dependency", "todo"),
            _task("done", "Done Task", "done"),
        ],
        workspace_name="demo-project",
        today=date(2026, 6, 6),
    )

    assert "Dependency problems: missing: 1, active: 1" in report


def test_project_summary_reports_no_dependency_problems_when_dependencies_are_done():
    report = summarize_project(
        [
            _task("launch", "Launch", "planned", dependencies=["research"]),
            _task("research", "Research", "done"),
        ],
        workspace_name="demo-project",
        today=date(2026, 6, 6),
    )

    assert "Dependency problems: missing: 0, active: 0" in report
