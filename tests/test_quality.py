from job_agent.db.repository import CandidateSource
from job_agent.quality import inspect_answer


def test_quality_gate_rejects_unsupported_claims_and_slop() -> None:
    source = CandidateSource(
        id="project.api",
        path="candidate/projects/api.md",
        source_type="project",
        title="API service",
        approved=True,
        source="user-authored",
        topics=("python",),
        content="Built a Python service.",
        content_hash="hash",
        last_indexed_at="now",
    )

    report = inspect_answer(
        "I am thrilled to apply. I built a Python service and managed 10,000 servers.",
        [source],
    )

    assert report.passed is False
    assert report.slop_flags
    assert report.unsupported_claims


def test_quality_gate_rejects_invented_metric_hidden_by_supported_words() -> None:
    source = CandidateSource(
        id="project.api",
        path="candidate/projects/api.md",
        source_type="project",
        title="API service",
        approved=True,
        source="user-authored",
        topics=("python",),
        content="Built a Python service.",
        content_hash="hash",
        last_indexed_at="now",
    )

    report = inspect_answer("I built a Python service and managed 10000 servers.", [source])

    assert report.passed is False
    assert report.unsupported_claims == [
        "I built a Python service and managed 10000 servers."
    ]
