from pathlib import Path

from typer.testing import CliRunner

from job_agent.cli import app


def test_candidate_validate_cli(tmp_path: Path) -> None:
    profile = tmp_path / "profile.yaml"
    profile.write_text("identity:\n  email: person@example.com\n", encoding="utf-8")

    result = CliRunner().invoke(
        app,
        ["candidate", "validate", "--profile", str(profile)],
    )

    assert result.exit_code == 0
    assert "VALID" in result.stdout
    assert "1 known facts" in result.stdout


def test_resume_add_cli_rejects_missing_source(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "resume",
            "add",
            "missing",
            "Missing resume",
            str(tmp_path / "missing.pdf"),
        ],
    )

    assert result.exit_code == 1
    assert "does not exist" in result.output
