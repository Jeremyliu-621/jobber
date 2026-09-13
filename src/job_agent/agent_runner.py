"""Safe local adapters for users' installed Codex and Claude CLIs."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AgentProvider = Literal["codex", "claude"]


class LocalAgentError(RuntimeError):
    """Raised when a local provider cannot be started safely."""


class AgentTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: AgentProvider
    prompt: str = Field(min_length=1)
    cwd: Path
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class AgentRunResult(BaseModel):
    provider: AgentProvider
    success: bool
    exit_code: int | None = None
    text: str = ""
    error: str | None = None


class LocalCliRunner:
    """Invoke a locally authenticated CLI without a shell or credential handling."""

    def executable(self, provider: AgentProvider) -> str | None:
        names = ("codex", "codex.exe", "codex.cmd") if provider == "codex" else (
            "claude",
            "claude.exe",
            "claude.cmd",
        )
        for name in names:
            found = shutil.which(name)
            if found:
                return found
        return None

    def command(self, task: AgentTask, executable: str) -> list[str]:
        if task.provider == "codex":
            return [executable, "exec", "--ephemeral", "--json", task.prompt]
        return [
            executable,
            "--bare",
            "-p",
            task.prompt,
            "--output-format",
            "json",
            "--no-session-persistence",
        ]

    def run(self, task: AgentTask) -> AgentRunResult:
        cwd = task.cwd.expanduser().resolve()
        if not cwd.is_dir():
            raise LocalAgentError(f"Agent workspace does not exist: {cwd}")
        executable = self.executable(task.provider)
        if executable is None:
            raise LocalAgentError(
                f"{task.provider} CLI was not found on PATH; install it and sign in locally first."
            )
        try:
            completed = subprocess.run(
                self.command(task, executable),
                cwd=cwd,
                text=True,
                capture_output=True,
                check=False,
                timeout=task.timeout_seconds,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            return AgentRunResult(
                provider=task.provider,
                success=False,
                error=f"{task.provider} CLI timed out after {task.timeout_seconds} seconds",
            )
        text = _extract_final_text(task.provider, completed.stdout)
        return AgentRunResult(
            provider=task.provider,
            success=completed.returncode == 0,
            exit_code=completed.returncode,
            text=text,
            error=(
                None
                if completed.returncode == 0
                else f"{task.provider} CLI exited with an error"
            ),
        )


def _extract_final_text(provider: AgentProvider, stdout: str) -> str:
    """Reduce provider JSON output to a useful final message without logging stderr."""

    if provider == "claude":
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            return stdout.strip()
        if isinstance(payload, dict) and isinstance(payload.get("result"), str):
            return payload["result"]
        return stdout.strip()

    messages: list[str] = []
    for line in stdout.splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = payload.get("item") if isinstance(payload, dict) else None
        if isinstance(item, dict) and item.get("type") == "agent_message":
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                messages.append(text)
    return messages[-1] if messages else stdout.strip()


def available_providers(runner: LocalCliRunner | None = None) -> dict[AgentProvider, bool]:
    active = runner or LocalCliRunner()
    providers: tuple[AgentProvider, AgentProvider] = ("codex", "claude")
    return {provider: active.executable(provider) is not None for provider in providers}
