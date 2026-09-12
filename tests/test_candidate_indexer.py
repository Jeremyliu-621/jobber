from pathlib import Path

from job_agent.candidate import CandidateIndexer
from job_agent.db import CandidateSourceRepository


def test_markdown_frontmatter_is_indexed(database, tmp_path: Path) -> None:
    candidate_root = tmp_path / "candidate"
    stories = candidate_root / "stories"
    stories.mkdir(parents=True)
    (candidate_root / "profile.yaml").write_text("identity:\n  email: null\n", encoding="utf-8")
    (stories / "leadership.md").write_text(
        "\n---\n"
        "id: story.leadership\n"
        "type: story\n"
        "topics:\n"
        "  - leadership\n"
        "  - teamwork\n"
        "approved: true\n"
        "source: user-authored\n"
        "---\n\n"
        "Coordinated a small project team through an ambiguous deadline.\n",
        encoding="utf-8",
    )

    count = CandidateIndexer(
        candidate_root=candidate_root,
        project_root=tmp_path,
        database=database,
    ).index()
    results = CandidateSourceRepository(database).search("ambiguous deadline")

    assert count == 1
    assert len(results) == 1
    assert results[0].id == "story.leadership"
    assert results[0].approved is True
    assert results[0].topics == ("leadership", "teamwork")


def test_structured_profile_fact_is_indexed(database, tmp_path: Path) -> None:
    candidate_root = tmp_path / "candidate"
    candidate_root.mkdir()
    (candidate_root / "profile.yaml").write_text(
        "identity:\n  email: person@example.com\n", encoding="utf-8"
    )

    CandidateIndexer(
        candidate_root=candidate_root,
        project_root=tmp_path,
        database=database,
    ).index()
    result = CandidateSourceRepository(database).get("fact.identity.email")

    assert result is not None
    assert result.path == "candidate/profile.yaml#identity.email"
    assert result.content == "person@example.com"


def test_reindex_removes_deleted_markdown_sources(database, tmp_path: Path) -> None:
    candidate_root = tmp_path / "candidate"
    stories = candidate_root / "stories"
    stories.mkdir(parents=True)
    (candidate_root / "profile.yaml").write_text("{}\n", encoding="utf-8")
    story = stories / "old.md"
    story.write_text(
        """---
id: story.old
type: story
approved: true
source: user-authored
---
An old story.
""",
        encoding="utf-8",
    )
    indexer = CandidateIndexer(
        candidate_root=candidate_root, project_root=tmp_path, database=database
    )

    indexer.index()
    story.unlink()
    indexer.index()

    assert CandidateSourceRepository(database).get("story.old") is None
