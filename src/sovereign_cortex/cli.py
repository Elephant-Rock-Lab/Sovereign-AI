from __future__ import annotations

import argparse
import difflib
import sys
from datetime import date
from pathlib import Path

from .approvals import ApprovalConflictError, ApprovalStore
from .orchestrator import LocalOrchestrator


def main(argv: list[str] | None = None) -> None:
    args_list = list(sys.argv[1:] if argv is None else argv)
    repo_root = Path(__file__).resolve().parents[2]

    if args_list and args_list[0] == "approvals":
        args = build_approvals_parser().parse_args(args_list[1:])
        handle_approvals(repo_root, args)
        return

    parser = build_command_parser()
    args = parser.parse_args(args_list)

    if not args.command:
        parser.error("command is required unless using the 'approvals' subcommand")

    today = date.fromisoformat(args.date) if args.date else None
    orchestrator = LocalOrchestrator(repo_root, args.workspace)
    result = orchestrator.handle_command(args.command, auto_approve=args.auto_approve, today=today)

    print(f"Status: {result.status}")
    print(result.message)

    if result.approval_id:
        print(f"Approval ID: {result.approval_id}")

    for patch in result.patches:
        print_patch(patch.before, patch.after, patch.relative_path, patch.summary)

    if result.status == "approval_saved" and not args.auto_approve:
        print(f"\nApprove with: cortex approvals approve {result.approval_id}")
        print(f"Reject with:  cortex approvals reject {result.approval_id}")

    if result.commit_hash:
        print(f"\nGit commit: {result.commit_hash}")

    print("\nEvents:")
    for event in result.events:
        print(f"- {event.event_type.value}: {event.sender} → {event.recipient}")


def build_command_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Sovereign AI MVP local control plane.")
    parser.add_argument("command", nargs="?", help="Natural-language project command")
    parser.add_argument("--workspace", default="demo-project", help="Workspace name under vault/")
    parser.add_argument("--auto-approve", action="store_true", help="Apply approved policy patches without saving an approval request")
    parser.add_argument("--date", help="Override today's date as YYYY-MM-DD for deterministic demos")
    return parser


def build_approvals_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage persisted approval requests")
    subparsers = parser.add_subparsers(dest="approval_command", required=True)

    list_parser = subparsers.add_parser("list", help="List approval requests")
    list_parser.add_argument("--status", choices=("pending", "approved", "rejected"), default="pending")

    show_parser = subparsers.add_parser("show", help="Show one approval request")
    show_parser.add_argument("approval_id")

    diff_parser = subparsers.add_parser("diff", help="Show only the stored approval diff")
    diff_parser.add_argument("approval_id")

    approve_parser = subparsers.add_parser("approve", help="Approve and apply a pending request")
    approve_parser.add_argument("approval_id")

    reject_parser = subparsers.add_parser("reject", help="Reject a pending request without writing files")
    reject_parser.add_argument("approval_id")
    reject_parser.add_argument("--reason", default="Rejected by user.")

    prune_parser = subparsers.add_parser("prune", help="Archive old resolved approval requests")
    prune_parser.add_argument("--older-than-days", type=int, required=True)

    return parser


def handle_approvals(repo_root: Path, args: argparse.Namespace) -> None:
    store = ApprovalStore(repo_root)

    if args.approval_command == "list":
        requests = store.list(args.status)
        if not requests:
            print(f"No {args.status} approval requests.")
            return
        for request in requests:
            print(f"{request.approval_id} [{request.status}] {request.workspace}: {request.patch.summary}")
        return

    if args.approval_command == "show":
        request = get_request_or_exit(store, args.approval_id)
        print(f"Approval ID: {request.approval_id}")
        print(f"Status: {request.status}")
        print(f"Workspace: {request.workspace}")
        print(f"Created: {request.created_at.isoformat()}")
        print(f"Command: {request.command_text}")
        print(f"Policy: {request.policy_decision.reason}")
        if request.commit_hash:
            print(f"Git commit: {request.commit_hash}")
        if request.rejection_reason:
            print(f"Rejection reason: {request.rejection_reason}")
        print_patch(request.patch.before, request.patch.after, request.patch.relative_path, request.patch.summary)
        return

    if args.approval_command == "diff":
        request = get_request_or_exit(store, args.approval_id)
        print_patch(request.patch.before, request.patch.after, request.patch.relative_path, request.patch.summary)
        return

    if args.approval_command == "approve":
        try:
            request = store.approve(args.approval_id)
        except (ApprovalConflictError, FileNotFoundError, ValueError) as exc:
            fail_expected(str(exc))
        print(f"Approved: {request.approval_id}")
        if request.commit_hash:
            print(f"Git commit: {request.commit_hash}")
        else:
            print("No Git commit was created because there were no file changes.")
        return

    if args.approval_command == "reject":
        try:
            request = store.reject(args.approval_id, args.reason)
        except (FileNotFoundError, ValueError) as exc:
            fail_expected(str(exc))
        print(f"Rejected: {request.approval_id}")
        print(f"Reason: {request.rejection_reason}")
        return

    if args.approval_command == "prune":
        try:
            pruned = store.prune(args.older_than_days)
        except ValueError as exc:
            fail_expected(str(exc))
        print(f"Pruned {len(pruned)} approval request(s).")
        for request in pruned:
            print(f"{request.approval_id} [{request.status}] {request.workspace}: {request.patch.summary}")
        return

    raise ValueError(f"Unsupported approvals command: {args.approval_command}")


def get_request_or_exit(store: ApprovalStore, approval_id: str):
    try:
        return store.get(approval_id)
    except FileNotFoundError as exc:
        fail_expected(str(exc))


def fail_expected(message: str) -> None:
    print(f"Error: {message}")
    raise SystemExit(1) from None


def print_patch(before_text: str | None, after_text: str, relative_path: str, summary: str) -> None:
    print("\n--- Proposed Patch ---")
    print(f"File: {relative_path}")
    print(f"Summary: {summary}")
    before = (before_text or "").splitlines(keepends=True)
    after = after_text.splitlines(keepends=True)
    print("".join(difflib.unified_diff(before, after, fromfile="before", tofile="after")))


if __name__ == "__main__":
    main()
