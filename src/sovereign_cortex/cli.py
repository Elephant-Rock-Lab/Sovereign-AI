from __future__ import annotations

import argparse
import difflib
from datetime import date
from pathlib import Path

from .orchestrator import LocalOrchestrator


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Sovereign Cortex MVP-0 local loop.")
    parser.add_argument("command", help="Natural-language project command")
    parser.add_argument("--workspace", default="demo-project", help="Workspace name under vault/")
    parser.add_argument("--auto-approve", action="store_true", help="Apply approved policy patches without prompting")
    parser.add_argument("--date", help="Override today's date as YYYY-MM-DD for deterministic demos")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    today = date.fromisoformat(args.date) if args.date else None
    orchestrator = LocalOrchestrator(repo_root, args.workspace)
    result = orchestrator.handle_command(args.command, auto_approve=args.auto_approve, today=today)

    print(f"Status: {result.status}")
    print(result.message)

    for patch in result.patches:
        print("\n--- Proposed Patch ---")
        print(f"File: {patch.relative_path}")
        print(f"Summary: {patch.summary}")
        before = (patch.before or "").splitlines(keepends=True)
        after = patch.after.splitlines(keepends=True)
        print("".join(difflib.unified_diff(before, after, fromfile="before", tofile="after")))

    if result.status == "proposed" and not args.auto_approve:
        print("\nRe-run with --auto-approve to apply this patch, or wire this prompt to a human approval UI later.")

    if result.commit_hash:
        print(f"\nGit commit: {result.commit_hash}")

    print("\nEvents:")
    for event in result.events:
        print(f"- {event.event_type.value}: {event.sender} → {event.recipient}")


if __name__ == "__main__":
    main()
