from pathlib import Path

from sovereign_cortex.workspace import WorkspaceRegistry


def test_workspace_registry_loads_default_demo_config():
    repo_root = Path(__file__).resolve().parents[1]

    workspace = WorkspaceRegistry(repo_root).get("demo-project")

    assert workspace.name == "demo-project"
    assert workspace.vault_root == (repo_root / "vault" / "demo-project").resolve()
