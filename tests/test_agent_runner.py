from pathlib import Path
from types import SimpleNamespace

from job_agent.agent_runner import AgentTask, LocalCliRunner, _extract_final_text


def test_local_provider_commands_are_shell_free_and_ephemeral(tmp_path: Path) -> None:
    runner = LocalCliRunner()
    codex = runner.command(
        AgentTask(provider="codex", prompt="organize these notes", cwd=tmp_path),
        "codex",
    )
    claude = runner.command(
        AgentTask(provider="claude", prompt="organize these notes", cwd=tmp_path),
        "claude",
    )

    assert codex == ["codex", "exec", "--ephemeral", "--json", "organize these notes"]
    assert claude == [
        "claude",
        "--bare",
        "-p",
        "organize these notes",
        "--output-format",
        "json",
        "--no-session-persistence",
    ]


def test_local_runner_returns_final_message_without_logging_stderr(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        "job_agent.agent_runner.shutil.which",
        lambda name: f"/bin/{name}",
    )
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout='{"result":"organized"}', stderr="secret")

    monkeypatch.setattr("job_agent.agent_runner.subprocess.run", fake_run)
    result = LocalCliRunner().run(
        AgentTask(provider="claude", prompt="organize", cwd=tmp_path)
    )

    assert result.success is True
    assert result.text == "organized"
    assert result.error is None
    assert calls[0][1]["shell"] is False
    assert calls[0][1]["cwd"] == tmp_path.resolve()


def test_codex_jsonl_parser_uses_last_agent_message() -> None:
    stdout = "\n".join(
        [
            '{"type":"item.completed","item":{"type":"agent_message","text":"first"}}',
            '{"type":"item.completed","item":{"type":"agent_message","text":"last"}}',
        ]
    )

    assert _extract_final_text("codex", stdout) == "last"
