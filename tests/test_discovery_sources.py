import pytest

from job_agent.discovery.models import RawJob, normalize_job
from job_agent.discovery.sources import (
    AshbySource,
    GreenhouseSource,
    LeverSource,
    SimplifyJobsSource,
    SwelistSource,
    html_to_text,
)


def test_greenhouse_parser_normalizes_html_and_urls() -> None:
    jobs = GreenhouseSource("example").parse_payload(
        {
            "jobs": [
                {
                    "id": 42,
                    "title": "Software Engineer Intern",
                    "location": {"name": "Toronto, Canada"},
                    "absolute_url": "https://boards.greenhouse.io/example/jobs/42",
                    "content": "<p>Required: <b>Python</b>.</p>",
                    "updated_at": "2026-09-01T10:00:00Z",
                }
            ]
        }
    )

    assert jobs[0].company == "example"
    assert jobs[0].location == "Toronto, Canada"
    assert jobs[0].description_text == "Required: Python."
    assert str(jobs[0].url).startswith("https://boards.greenhouse.io")


def test_lever_and_ashby_parsers_use_public_payload_shapes() -> None:
    lever = LeverSource("acme").parse_payload(
        [
            {
                "id": "lever-1",
                "text": "Backend Engineer",
                "categories": {"location": "Remote - Canada"},
                "hostedUrl": "https://jobs.lever.co/acme/lever-1",
                "descriptionPlain": "Build APIs with Go.",
            }
        ]
    )
    ashby = AshbySource("acme").parse_payload(
        {
            "jobs": [
                {
                    "jobUrl": "https://jobs.ashbyhq.com/acme/ashby-1",
                    "title": "Frontend Engineer",
                    "location": "Toronto",
                    "descriptionHtml": "<p>React and TypeScript.</p>",
                }
            ]
        }
    )

    assert lever[0].location == "Remote - Canada"
    assert ashby[0].description_text == "React and TypeScript."
    assert html_to_text("<div>A &amp; B</div>") == "A & B"


def test_lever_source_includes_structured_lists_in_description() -> None:
    jobs = LeverSource("solopulseco").parse_payload(
        [
            {
                "id": "123",
                "text": "Software Engineer Intern",
                "hostedUrl": "https://jobs.lever.co/acme/123",
                "categories": {"location": "Toronto, ON"},
                "descriptionPlain": "Build useful software.",
                "lists": [
                    {
                        "text": "Qualifications",
                        "content": "<li>Proficiency in Python and C++</li>",
                    }
                ],
            }
        ]
    )

    assert "Qualifications" in jobs[0].description_text
    assert "Python and C++" in jobs[0].description_text


def test_normalized_job_id_is_stable() -> None:
    raw = RawJob(
        source="greenhouse",
        source_job_id="42",
        company="Acme",
        title="Engineer",
        url="https://example.com/jobs/42",
    )
    assert normalize_job(raw).id == normalize_job(raw).id


def test_normalized_job_id_sanitizes_url_source_ids() -> None:
    raw = RawJob(
        source="ashby",
        source_job_id="https://jobs.ashbyhq.com/acme/posting/123",
        company="Acme",
        title="Engineer",
        url="https://jobs.ashbyhq.com/acme/posting/123",
    )

    job = normalize_job(raw)

    assert "/" not in job.id
    assert "://" not in job.id


def test_simplifyjobs_parser_applies_timeframe_and_location_filters() -> None:
    import time

    now = time.time()
    jobs = SimplifyJobsSource(
        role="internship", timeframe="lastweek", location="Toronto"
    ).parse_payload(
        [
            {
                "id": "swelist-current",
                "company_name": "Acme",
                "title": "Software Engineering Intern",
                "locations": ["Toronto, ON, Canada"],
                "url": "https://example.com/jobs/swelist-current",
                "date_posted": now - 60 * 60,
                "category": "Software Engineering",
            },
            {
                "id": "swelist-old",
                "company_name": "Old Co",
                "title": "Software Engineering Intern",
                "locations": ["Toronto, ON, Canada"],
                "url": "https://example.com/jobs/swelist-old",
                "date_posted": now - 8 * 24 * 60 * 60,
            },
            {
                "id": "swelist-other-location",
                "company_name": "Elsewhere",
                "title": "Software Engineering Intern",
                "locations": ["New York, NY"],
                "url": "https://example.com/jobs/swelist-other-location",
                "date_posted": now - 60 * 60,
            },
        ]
    )

    assert len(jobs) == 1
    assert jobs[0].source == "swelist"
    assert jobs[0].source_job_id == "swelist-current"
    assert jobs[0].location == "Toronto, ON, Canada"
    assert jobs[0].raw_payload["category"] == "Software Engineering"
    assert jobs[0].raw_payload["discovery_source"] == "simplifyjobs"


def test_simplifyjobs_source_rejects_unknown_filters() -> None:
    with pytest.raises(ValueError, match="role"):
        SimplifyJobsSource(role="fulltime")
    with pytest.raises(ValueError, match="timeframe"):
        SimplifyJobsSource(timeframe="today")


def test_swelist_source_name_remains_a_compatibility_alias() -> None:
    assert SwelistSource is SimplifyJobsSource
