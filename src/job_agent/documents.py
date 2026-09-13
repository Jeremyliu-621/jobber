"""Local document-folder inventory for a personal Jobber workspace."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .workspace import effective_config

SUPPORTED_EXTENSIONS = frozenset(
    {".pdf", ".doc", ".docx", ".md", ".txt", ".tex", ".yaml", ".yml", ".json", ".rtf"}
)


@dataclass(frozen=True)
class DocumentRecord:
    name: str
    path: str
    extension: str
    size_bytes: int
    content_hash: str
    modified_at: str


def document_root(root: Path | None = None) -> Path:
    return effective_config(root).documents_path.expanduser().resolve()


def inventory(root: Path | None = None) -> list[DocumentRecord]:
    """Inventory supported files and write a local, non-secret manifest."""

    base = document_root(root)
    base.mkdir(parents=True, exist_ok=True)
    records = []
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.suffix.casefold() not in SUPPORTED_EXTENSIONS:
            continue
        if path.relative_to(base).as_posix() == "README.md":
            continue
        stat = path.stat()
        records.append(
            DocumentRecord(
                name=path.name,
                path=path.relative_to(base).as_posix(),
                extension=path.suffix.casefold().lstrip("."),
                size_bytes=stat.st_size,
                content_hash=_sha256(path),
                modified_at=datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(),
            )
        )
    manifest = _manifest_path(root)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest.with_suffix(".tmp")
    temporary.write_text(
        json.dumps([asdict(record) for record in records], indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(manifest)
    return records


def import_document(source: Path, root: Path | None = None) -> DocumentRecord:
    """Copy one user-selected file into the local inbox and inventory it."""

    source = source.expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"Document does not exist: {source}")
    if source.suffix.casefold() not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"Unsupported document type {source.suffix or '<none>'}; use: {supported}")
    inbox = document_root(root) / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    destination = inbox / source.name
    if destination.resolve() != source:
        if destination.exists() and _sha256(destination) != _sha256(source):
            destination = _available_name(destination)
        if not destination.exists():
            shutil.copy2(source, destination)
    records = inventory(root)
    relative = destination.relative_to(document_root(root)).as_posix()
    return next(record for record in records if record.path == relative)


def _manifest_path(root: Path | None) -> Path:
    workspace = effective_config(root).workspace_path.expanduser().resolve()
    return workspace / "data" / "documents.json"


def _available_name(path: Path) -> Path:
    index = 2
    while True:
        candidate = path.with_name(f"{path.stem}-{index}{path.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
