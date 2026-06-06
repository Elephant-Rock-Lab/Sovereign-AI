import pytest

from sovereign_cortex import cli
from sovereign_cortex.approvals import ApprovalRequest, PolicyDecisionSnapshot
from sovereign_cortex.events import EventEnvelope, EventType, PatchOperation, ProposedPatch, TaskResult


class DummyOrchestrator:
    def __init__(self, repo_root, workspace_name="demo-project"):
        self.repo_root = repo_root
        self.workspace_name = workspace_name

    def handle_command(self, text, *, auto_approve=False, today=None):
        assert text == "Move the website launch task to next Friday and explain the dependency impact"
        assert auto_approve is False
        event = EventEnvelope(
            event_type=EventType.COMMAND_RECEIVED,
            sender="test",
            recipient="test",
            workspace="demo-project",
            payload={"text": text},
        )
        return TaskResult(status="no_action", message="dummy command handled", events=[event])


class DummyRecordStore:
    calls = []

    def __init__(self, repo_root):
        self.repo_root = repo_root

    def append(self, events):
        self.__class__.calls.append(events)
        return []


class DummyApprovalStore:
    def __init__(self, repo_root):
        self.repo_root = repo_root

    def _request(self, approval_id="approval-1"):
        return ApprovalRequest(
            approval_id=approval_id,
            workspace="demo-project",
            command_text="Create task CLI Diff",
            correlation_id="cli-test",
            patch=ProposedPatch(
                operation=PatchOperation.CREATE_FILE,
                relative_path="tasks/cli-diff.md",
                before=None,
                after="---\ntitle: CLI Diff\n---\n# CLI Diff\n",
                summary="Create CLI diff task.",
            ),
            policy_decision=PolicyDecisionSnapshot(allowed=True, approval_required=True, reason="ok"),
        )

    def get(self, approval_id):
        if approval_id == "missing":
            raise FileNotFoundError("Approval request not found: missing")
        return self._request(approval_id)

    def approve(self, approval_id):
        return self._request(approval_id)

    def reject(self, approval_id, reason):
        return self._request(approval_id).model_copy(update={"rejection_reason": reason})

    def prune(self, older_than_days):
        assert older_than_days == 7
        return []


class DummyResolvedApprovalStore(DummyApprovalStore):
    def approve(self, approval_id):
        raise ValueError(f"Approval request is already rejected: {approval_id}")


def test_cli_accepts_natural_language_command(monkeypatch, capsys):
    DummyRecordStore.calls = []
    monkeypatch.setattr(cli, "LocalOrchestrator", DummyOrchestrator)
    monkeypatch.setattr(cli, "ActivityRecordStore", DummyRecordStore)

    cli.main(["Move the website launch task to next Friday and explain the dependency impact"])

    captured = capsys.readouterr()
    assert "Status: no_action" in captured.out
    assert "dummy command handled" in captured.out
    assert len(DummyRecordStore.calls) == 1
    assert DummyRecordStore.calls[0][0].event_type == EventType.COMMAND_RECEIVED


def test_cli_dispatches_approvals_subcommand(monkeypatch):
    calls = []

    def fake_handle_approvals(repo_root, args):
        calls.append((repo_root, args.approval_command, args.status))

    monkeypatch.setattr(cli, "handle_approvals", fake_handle_approvals)

    cli.main(["approvals", "list", "--status", "pending"])

    assert calls
    _, approval_command, status = calls[0]
    assert approval_command == "list"
    assert status == "pending"


def test_cli_approval_diff_prints_stored_patch(monkeypatch, capsys):
    monkeypatch.setattr(cli, "ApprovalStore", DummyApprovalStore)

    cli.main(["approvals", "diff", "approval-1"])

    captured = capsys.readouterr()
    assert "--- Proposed Patch ---" in captured.out
    assert "tasks/cli-diff.md" in captured.out
    assert "CLI Diff" in captured.out


def test_cli_prune_accepts_documented_older_than_alias(monkeypatch, capsys):
    monkeypatch.setattr(cli, "ApprovalStore", DummyApprovalStore)

    cli.main(["approvals", "prune", "--older-than", "7"])

    captured = capsys.readouterr()
    assert "Pruned 0 approval request(s)." in captured.out


def test_cli_missing_approval_exits_cleanly(monkeypatch, capsys):
    monkeypatch.setattr(cli, "ApprovalStore", DummyApprovalStore)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["approvals", "show", "missing"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "Error: Approval request not found: missing" in captured.out
    assert "Traceback" not in captured.err


def test_cli_already_resolved_approval_exits_cleanly(monkeypatch, capsys):
    monkeypatch.setattr(cli, "ApprovalStore", DummyResolvedApprovalStore)

    with pytest.raises(SystemExit) as exc_info:
        cli.main(["approvals", "approve", "approval-1"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 1
    assert "Error: Approval request is already rejected: approval-1" in captured.out
    assert "Traceback" not in captured.err


def test_cli_approval_approve_writes_activity_record(monkeypatch, capsys):
    DummyRecordStore.calls = []
    monkeypatch.setattr(cli, "ApprovalStore", DummyApprovalStore)
    monkeypatch.setattr(cli, "ActivityRecordStore", DummyRecordStore)

    cli.main(["approvals", "approve", "approval-1"])

    captured = capsys.readouterr()
    assert "Approved: approval-1" in captured.out
    assert len(DummyRecordStore.calls) == 1
    event = DummyRecordStore.calls[0][0]
    assert event.event_type == EventType.PATCH_APPROVED
    assert event.correlation_id == "cli-test"


def test_cli_approval_reject_writes_activity_record(monkeypatch, capsys):
    DummyRecordStore.calls = []
    monkeypatch.setattr(cli, "ApprovalStore", DummyApprovalStore)
    monkeypatch.setattr(cli, "ActivityRecordStore", DummyRecordStore)

    cli.main(["approvals", "reject", "approval-1", "--reason", "No."])

    captured = capsys.readouterr()
    assert "Rejected: approval-1" in captured.out
    assert len(DummyRecordStore.calls) == 1
    event = DummyRecordStore.calls[0][0]
    assert event.event_type == EventType.PATCH_REJECTED
    assert event.correlation_id == "cli-test"
