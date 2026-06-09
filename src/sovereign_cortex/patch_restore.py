from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .events import ProposedPatch


@dataclass(frozen=True)
class PatchTargetSnapshot:
    path: Path
    existed: bool
    content: str | None


@contextmanager
def restore_patch_target_on_error(vault_root: Path, patch: ProposedPatch) -> Iterator[None]:
    snapshot = _snapshot_patch_target(vault_root, patch)
    try:
        yield
    except Exception:
        _restore_patch_target(snapshot)
        raise


def _snapshot_patch_target(vault_root: Path, patch: ProposedPatch) -> PatchTargetSnapshot:
    path = _resolve(vault_root, patch.relative_path)
    existed = path.exists()
    content = path.read_text(encoding="utf-8") if existed else None
    return PatchTargetSnapshot(path=path, existed=existed, content=content)


def _restore_patch_target(snapshot: PatchTargetSnapshot) -> None:
    if snapshot.existed:
        snapshot.path.parent.mkdir(parents=True, exist_ok=True)
        snapshot.path.write_text(snapshot.content or "", encoding="utf-8")
    elif snapshot.path.exists():
        snapshot.path.unlink()


def _resolve(vault_root: Path, relative_path: str) -> Path:
    path = (vault_root / relative_path).resolve()
    root = vault_root.resolve()
    if root not in path.parents and path != root:
        raise ValueError(f"Patch path escapes the workspace: {relative_path}")
    return path
