from pathlib import Path

import pytest

from sovereign_cortex.workspace import WorkspaceRegistry


def test_workspace_registry_loads_default_demo_config():
    repo_root = Path(__file__).resolve().parents[1]

    workspace = WorkspaceRegistry(repo_root).get("demo-project")

    assert workspace.name == "demo-project"
    assert workspace.vault_root == (repo_root / "vault" / "demo-project").resolve()


def test_workspace_registry_loads_custom_config(tmp_path):
    custom_vault = tmp_path / "vaults" / "custom"
    custom_vault.mkdir(parents=True)
    (tmp_path / "workspaces.yaml").write_text(
        "workspaces:\n  custom:\n    vault_root: vaults/custom\n",
        encoding="utf-8",
    )

    workspace = WorkspaceRegistry(tmp_path).get("custom")

    assert workspace.name == "custom"
    assert workspace.vault_root == custom_vault.resolve()


def test_workspace_registry_reports_missing_vault(tmp_path):
    (tmp_path / "workspaces.yaml").write_text(
        "workspaces:\n  missing:\n    vault_root: vaults/missing\n",
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError):
        WorkspaceRegistry(tmp_path).get("missing")


def test_workspace_registry_rejects_repo_escape(tmp_path):
    outside = "." + "." + "/outside"
    (tmp_path / "workspaces.yaml").write_text(
        f"workspaces:\n  unsafe:\n    vault_root: {outside}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="escapes repository"):
        WorkspaceRegistry(tmp_path).get("unsafe")
