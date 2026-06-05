from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .events import ProposedPatch


@dataclass(frozen=True)
class MarkdownDocument:
    relative_path: str
    metadata: dict[str, Any]
    body: str
    raw: str


def parse_markdown(raw: str, relative_path: str) -> MarkdownDocument:
    if raw.startswith("---\n"):
        end = raw.find("\n---\n", 4)
        if end != -1:
            frontmatter = raw[4:end]
            body = raw[end + 5 :]
            metadata = yaml.safe_load(frontmatter) or {}
            if not isinstance(metadata, dict):
                metadata = {}
            return MarkdownDocument(relative_path, metadata, body, raw)
    return MarkdownDocument(relative_path, {}, raw, raw)


def render_markdown(metadata: dict[str, Any], body: str) -> str:
    fm = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{fm}\n---\n{body.lstrip()}"


class Vault:
    def __init__(self, root: Path):
        self.root = root

    def read(self, relative_path: str) -> MarkdownDocument:
        path = self._resolve(relative_path)
        raw = path.read_text(encoding="utf-8")
        return parse_markdown(raw, relative_path)

    def write(self, relative_path: str, content: str) -> None:
        path = self._resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def list_task_docs(self) -> list[MarkdownDocument]:
        tasks_dir = self.root / "tasks"
        if not tasks_dir.exists():
            return []
        docs: list[MarkdownDocument] = []
        for path in sorted(tasks_dir.glob("*.md")):
            rel = str(path.relative_to(self.root))
            docs.append(self.read(rel))
        return docs

    def apply_patch(self, patch: ProposedPatch) -> None:
        if patch.operation.value not in {"update_file", "create_file"}:
            raise ValueError(f"Unsupported operation: {patch.operation}")
        self.write(patch.relative_path, patch.after)

    def _resolve(self, relative_path: str) -> Path:
        path = (self.root / relative_path).resolve()
        root = self.root.resolve()
        if root not in path.parents and path != root:
            raise ValueError(f"Path escapes vault: {relative_path}")
        return path
