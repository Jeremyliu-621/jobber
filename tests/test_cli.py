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


def test_init_cli_selects_workspace_without_overwriting_existing_files(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("JOBBER_CONFIG_DIR", str(tmp_path / "config"))
    root = tmp_path / "workspace"
    root.mkdir()
    existing = root / "candidate" / "profile.yaml"
    existing.parent.mkdir(parents=True)
    existing.write_text("identity:\n  email: person@example.com\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["init", str(root)])

    assert result.exit_code == 0
    assert "Created" in result.stdout
    assert "person@example.com" in existing.read_text(encoding="utf-8")


def test_documents_import_cli_uses_selected_workspace(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBBER_CONFIG_DIR", str(tmp_path / "config"))
    root = tmp_path / "workspace"
    source = tmp_path / "notes.md"
    source.write_text("hello", encoding="utf-8")
    assert CliRunner().invoke(app, ["init", str(root)]).exit_code == 0

    result = CliRunner().invoke(app, ["documents", "import", str(source)])

    assert result.exit_code == 0
    assert "inbox/notes.md" in result.stdout
