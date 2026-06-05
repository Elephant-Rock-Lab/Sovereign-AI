from __future__ import annotations

from datetime import timezone
from pathlib import Path

from .events import EventEnvelope


class ActivityRecordStore:
    """Append EventEnvelope records to dated JSONL files."""

    def __init__(self, repo_root: Path):
        self.root = repo_root / "activity"

    def append(self, items: list[EventEnvelope]) -> list[Path]:
        paths: list[Path] = []
        self.root.mkdir(parents=True, exist_ok=True)
        for item in items:
            path = self._path_for(item)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(item.model_dump_json() + "\n")
            paths.append(path)
        return paths

    def _path_for(self, item: EventEnvelope) -> Path:
        day = item.timestamp.astimezone(timezone.utc).date().isoformat()
        return self.root / f"{day}.jsonl"
