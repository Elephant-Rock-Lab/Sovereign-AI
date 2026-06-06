from __future__ import annotations

import re
from datetime import date

from .next_action import recommend_next_action
from .project_risk import summarize_risk
from .project_summary import summarize_project
from .vault import Vault


def handle_project_report(command: str, *, vault: Vault, workspace_name: str, today: date) -> str | None:
    stripped = command.strip()
    if re.fullmatch(
        r"(?:show\s+)?(?:the\s+)?(?:project|workspace)\s+(?:summary|status)|summary\s+of\s+(?:the\s+)?project|summarize\s+(?:the\s+)?project",
        stripped,
        flags=re.I,
    ):
        return summarize_project(vault.list_task_docs(), workspace_name=workspace_name, today=today)

    if re.fullmatch(
        r"(?:show\s+)?(?:the\s+)?(?:project|workspace)\s+(?:risk|risks|risk\s+report)|risk\s+(?:report|summary)\s+(?:for\s+)?(?:the\s+)?(?:project|workspace)",
        stripped,
        flags=re.I,
    ):
        return summarize_risk(vault.list_task_docs(), workspace_name=workspace_name, today=today)

    if re.fullmatch(
        r"(?:show\s+)?(?:the\s+)?(?:next\s+action|recommended\s+next\s+action)|(?:what\s+is\s+)?(?:the\s+)?next\s+action|next\s+action\s+(?:for\s+)?(?:the\s+)?(?:project|workspace)",
        stripped,
        flags=re.I,
    ):
        return recommend_next_action(vault.list_task_docs(), workspace_name=workspace_name, today=today)

    return None
