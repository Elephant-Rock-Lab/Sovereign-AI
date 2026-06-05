from pathlib import Path

from sovereign_cortex.orchestrator import LocalOrchestrator


def test_orchestrator_proposes_launch_patch():
    repo_root = Path(__file__).resolve().parents[1]
    result = LocalOrchestrator(repo_root).handle_command(
        "Move the website launch task to next Friday and explain the dependency impact",
        auto_approve=False,
    )
    assert result.status == "approval_saved"
    assert result.patches
    assert result.approval_id
    assert "Launch Website" in result.patches[0].after
