from pathlib import Path

from job_agent.documents import import_document, inventory
from job_agent.workspace import initialize_workspace


def test_document_import_is_local_and_inventory_is_hashed(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBBER_CONFIG_DIR", str(tmp_path / "config"))
    root = tmp_path / "workspace"
    initialize_workspace(root)
    source = tmp_path / "resume.pdf"
    source.write_bytes(b"resume contents")

    imported = import_document(source, root)
    records = inventory(root)

    assert imported.path == "inbox/resume.pdf"
    assert (root / "documents" / imported.path).read_bytes() == source.read_bytes()
    assert records == [imported]
    assert len(imported.content_hash) == 64


def test_document_import_avoids_overwriting_a_different_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("JOBBER_CONFIG_DIR", str(tmp_path / "config"))
    root = tmp_path / "workspace"
    initialize_workspace(root)
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    first = first_dir / "notes.txt"
    second = second_dir / "notes.txt"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")

    first_record = import_document(first, root)
    second_record = import_document(second, root)

    assert first_record.path == "inbox/notes.txt"
    assert second_record.path == "inbox/notes-2.txt"
    assert (root / "documents" / second_record.path).read_text(encoding="utf-8") == "second"
