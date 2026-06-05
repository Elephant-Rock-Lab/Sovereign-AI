from __future__ import annotations

import subprocess
from pathlib import Path


class GitAudit:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root

    def ensure_repo(self) -> None:
        if not (self.repo_root / ".git").exists():
            self._run(["git", "init"])
            self._run(["git", "config", "user.email", "sovereign-cortex@local"])
            self._run(["git", "config", "user.name", "Sovereign Cortex"])

    def commit_paths(self, paths: list[str], message: str) -> str | None:
        self.ensure_repo()
        for path in paths:
            self._run(["git", "add", path])
        status = self._run(["git", "status", "--porcelain"], capture=True)
        if not status.strip():
            return None
        self._run(["git", "commit", "-m", message])
        return self._run(["git", "rev-parse", "--short", "HEAD"], capture=True).strip()

    def _run(self, args: list[str], capture: bool = False) -> str:
        result = subprocess.run(
            args,
            cwd=self.repo_root,
            check=True,
            text=True,
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        return result.stdout if capture else ""
