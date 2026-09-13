"""Local workspace discovery and per-user configuration."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict


class WorkspaceConfigurationError(RuntimeError):
    """Raised when the local workspace configuration cannot be loaded."""


class WorkspaceConfig(BaseModel):
    """Non-secret settings stored for one local Jobber installation."""

    model_config = ConfigDict(extra="forbid")

    version: int = 1
    workspace_root: str
    documents_root: str = "documents"
    agent_provider: Literal["auto", "codex", "claude"] = "auto"

    @property
    def workspace_path(self) -> Path:
        return Path(self.workspace_root).expanduser()

    @property
    def documents_path(self) -> Path:
        path = Path(self.documents_root).expanduser()
        return path if path.is_absolute() else self.workspace_path / path


def config_directory() -> Path:
    """Return the platform-appropriate directory for non-secret user config."""

    override = os.getenv("JOBBER_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        return Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Jobber"
    xdg = os.getenv("XDG_CONFIG_HOME")
    return (Path(xdg) if xdg else Path.home() / ".config") / "jobber"


def config_path() -> Path:
    return config_directory() / "config.json"


def load_user_config() -> WorkspaceConfig | None:
    """Load the user config, returning ``None`` before the first ``init``."""

    path = config_path()
    if not path.exists():
        return None
    try:
        return WorkspaceConfig.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise WorkspaceConfigurationError(f"Invalid Jobber config: {path}") from error


def save_user_config(config: WorkspaceConfig) -> Path:
    """Atomically save non-secret workspace preferences."""

    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(config.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def default_workspace_root() -> Path:
    return Path.home() / "Jobber"


def resolve_workspace_root(explicit: Path | None = None) -> Path:
    """Resolve a workspace with explicit and environment overrides first."""

    if explicit:
        return explicit.expanduser().resolve()
    environment_root = os.getenv("JOBBER_WORKSPACE")
    if environment_root:
        return Path(environment_root).expanduser().resolve()
    configured = load_user_config()
    if configured:
        return configured.workspace_path.expanduser().resolve()
    current = Path.cwd()
    if (current / "pyproject.toml").exists() and (current / "candidate").exists():
        return current.resolve()
    return current.resolve()


def effective_config(root: Path | None = None) -> WorkspaceConfig:
    """Return config for a root without requiring a config file to exist."""

    workspace = resolve_workspace_root(root)
    configured = load_user_config()
    if configured and configured.workspace_path.expanduser().resolve() == workspace:
        return configured
    return WorkspaceConfig(workspace_root=str(workspace))


def initialize_workspace(root: Path | None = None, *, select: bool = True) -> tuple[Path, ...]:
    """Create a safe blank workspace without overwriting user files."""

    workspace = (root or default_workspace_root()).expanduser().resolve()
    directories = (
        workspace / "candidate" / "experiences",
        workspace / "candidate" / "projects",
        workspace / "candidate" / "stories",
        workspace / "candidate" / "answers",
        workspace / "candidate" / "companies",
        workspace / "candidate" / "resumes",
        workspace / "documents" / "inbox",
        workspace / "documents" / "organized",
        workspace / "data",
    )
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    files = {
        workspace / "candidate" / "profile.yaml": (
            "# Fill only with facts you have verified. Unknown values stay blank.\n"
            "identity:\n"
            "  legal_name:\n"
            "  preferred_name:\n"
            "  email:\n"
            "  phone:\n"
            "education: []\n"
            "work_authorization:\n"
            "  canada:\n"
            "    authorized:\n"
            "    sponsorship_required:\n"
            "    notes:\n"
            "  usa:\n"
            "    authorized:\n"
            "    sponsorship_required:\n"
            "    notes:\n"
            "links:\n"
            "  github:\n"
            "  linkedin:\n"
            "  portfolio:\n"
            "preferences:\n"
            "  target_roles: []\n"
            "  locations: []\n"
            "  target_companies: []\n"
            "  referral_companies: []\n"
            "  excitement_keywords: []\n"
            "  remote:\n"
        ),
        workspace / "candidate" / "preferences.yaml": "{}\n",
        workspace / "candidate" / "style.md": "# Writing style\n\nAdd your preferences here.\n",
        workspace / "documents" / "README.md": (
            "# Documents\n\n"
            "Drop files into `inbox/`, then run `job-agent documents list`.\n"
        ),
    }
    created: list[Path] = []
    for path, content in files.items():
        if path.exists():
            continue
        path.write_text(content, encoding="utf-8")
        created.append(path)
    if select:
        save_user_config(WorkspaceConfig(workspace_root=str(workspace)))
    return tuple(created)


def update_config(
    *,
    workspace_root: Path | None = None,
    documents_root: Path | None = None,
    agent_provider: Literal["auto", "codex", "claude"] | None = None,
) -> WorkspaceConfig:
    """Update one or more non-secret local preferences."""

    current = load_user_config()
    root = workspace_root or (current.workspace_path if current else resolve_workspace_root())
    base = current or WorkspaceConfig(workspace_root=str(root))
    updates: dict[str, str] = {}
    if workspace_root:
        updates["workspace_root"] = str(workspace_root.expanduser().resolve())
    if documents_root:
        updates["documents_root"] = str(documents_root.expanduser().resolve())
    if agent_provider:
        updates["agent_provider"] = agent_provider
    updated = base.model_copy(update=updates)
    save_user_config(updated)
    return updated
