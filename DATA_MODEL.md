# Data Model

Use SQLite initially with migrations.

## Core entities

### jobs

```text
id
source
source_job_id
company
title
location
url
apply_url
description_text
posted_at
first_seen_at
last_seen_at
status
dedupe_hash
raw_payload_json
```

### job_criteria

```text
id
job_id
name
category        # required/preferred/contextual
weight
source_text
```

### criterion_evidence

```text
id
criterion_id
candidate_source_id
strength
notes
```

### job_evaluations

```text
id
job_id
eligibility_status
fit_score
importance_score
tier
summary
created_at
model_id
version
```

### applications

```text
id
job_id
status
tier
resume_id
browser_provider
browser_session_id
created_at
started_at
submitted_at
last_updated_at
```

Suggested statuses:

```text
discovered
evaluated
skipped
tier_a_manual
queued
preparing
needs_user
ready_for_review
ready_to_submit
submitted
failed
withdrawn
rejected
interview
offer
```

### application_questions

```text
id
application_id
question_text
normalized_question
question_type
required
max_length
source_page
created_at
```

### application_answers

```text
id
question_id
generated_text
final_text
status
grounding_score
style_score
human_edit_distance
created_at
approved_at
```

### answer_claims

Tracks provenance for factual claims.

```text
id
answer_id
claim_text
candidate_source_id
support_type
confidence
```

`candidate_source_id` should point to a known candidate fact, project, story, experience, or approved answer.

### candidate_sources

Metadata index over user-owned knowledge.

```text
id
path
type
title
approved
content_hash
last_indexed_at
```

### resumes

```text
id
name
base_type
source_path
rendered_path
version
created_at
```

### application_events

Append-only event log.

```text
id
application_id
event_type
payload_json
created_at
```

Examples:

```text
browser_started
question_detected
answer_generated
answer_rejected
user_asked
user_answered
resume_uploaded
page_advanced
ready_to_submit
submitted
browser_error
```

### user_feedback

Captures learning signal.

```text
id
application_id
artifact_type
artifact_id
original_text
edited_text
feedback_type
created_at
```

---

## Pydantic domain models

Start with explicit models such as:

```python
class Job(BaseModel): ...
class JobCriterion(BaseModel): ...
class EligibilityResult(BaseModel): ...
class FitEvaluation(BaseModel): ...
class ImportanceEvaluation(BaseModel): ...
class Evidence(BaseModel): ...
class ResumeChoice(BaseModel): ...
class ApplicationPlan(BaseModel): ...
class ApplicationQuestion(BaseModel): ...
class CandidateClaim(BaseModel): ...
class QualityReport(BaseModel): ...
```

Use structured model output whenever an LLM produces machine-consumed results.

---

## Candidate source IDs

Every candidate fact/story/project should have a stable ID.

Examples:

```text
fact.education.uoft.program
fact.work_authorization.canada
project.paper_cuts
experience.futurify
story.paper_cuts_leadership
answer.why_ai.v1
```

This enables provenance like:

```json
{
  "claim": "Built a multiplayer drawing-based game",
  "source_id": "project.paper_cuts"
}
```

---

## No vector database in V1

Index Markdown files with:

- paths;
- frontmatter;
- tags;
- basic full-text search;
- optional SQLite FTS5.

Only add embeddings if real retrieval failures demonstrate a need.
