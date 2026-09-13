from pathlib import Path

from job_agent.candidate import load_profile
from job_agent.workspace import (
    WorkspaceConfig,
    config_path,
    initialize_workspace,
    load_user_config,
    update_config,
)


def test_initialize_workspace_creates_blank_safe_profile_and_selects_it(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("JOBBER_CONFIG_DIR", str(tmp_path / "config"))
    root = tmp_path / "workspace"

    created = initialize_workspace(root)

    assert root / "candidate" / "profile.yaml" in created
    assert load_profile(root / "candidate" / "profile.yaml").identity.email is None
    assert (root / "documents" / "inbox").is_dir()
    assert (root / "documents" / "organized").is_dir()
    config = load_user_config()
    assert config is not None
    assert config.workspace_path == root
    assert config_path().is_file()


def test_update_config_keeps_provider_settings_non_secret(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBBER_CONFIG_DIR", str(tmp_path / "config"))
    root = tmp_path / "workspace"

    updated = update_config(
        workspace_root=root,
        documents_root=tmp_path / "my-documents",
        agent_provider="claude",
    )

    assert updated == WorkspaceConfig(
        workspace_root=str(root),
        documents_root=str(tmp_path / "my-documents"),
        agent_provider="claude",
    )
    assert "API_KEY" not in config_path().read_text(encoding="utf-8")
