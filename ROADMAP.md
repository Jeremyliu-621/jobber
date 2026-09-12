# Roadmap

## Current implementation status — 2026-09-12

Implemented in the repository:

- Phase 0: Hermes audit, current Browserbase/Browser Use/ATS research, and stack decision.
- Phase 1: candidate profile, Markdown index, SQLite migrations, CLI, and tests.
- Phase 2: deterministic Greenhouse/Lever/Ashby ingestion, eligibility, fit, importance, and tier scoring.
- Phase 3: reviewable application packets, resume inventory, grounding/style gates, and feedback records.
- Phase 4 foundation: Browserbase provider, CDP worker boundary, Browser Use adapter, event logging, and safety tests.
- Phase 4 hardening: rendered-resume readiness checks, failed-quality refusal,
  conservative metric grounding, stale candidate-source cleanup, and remote
  Browser Use API alignment, remote session file uploads, and ATS form-field
  selection guidance.
- Phase 6: local stdio MCP server registered with Hermes.
- Phase 7 foundation: SimplifyJobs-backed internship/new-grad discovery with
  timeframe and location filters; Swelist remains a compatibility alias.
- Phase 8 foundation: human-answer capture and edit-rate reporting.

The current local resume source is registered as `swe-current` with a rendered
PDF compiled from the supplied LaTeX source and visually checked. Live
read-only form tests have filled verified fields and uploaded the PDF on Lever
and Ashby pages, then released every Browserbase session before submission.

The next executable slice is a controlled mock-form runner with the optional
Browser Use model runner. Real employer-site worker runs still require
user-supplied work-authorization facts, an LLM runner configuration, and
explicit human review before any submission action.

## Phase 0 — Research and environment audit

Before implementation:

- inspect existing Hermes installation;
- inspect Hermes config and skills;
- identify Telegram integration status;
- verify current Browser Use API;
- verify current Browserbase API;
- verify CDP connection pattern;
- investigate Browserbase persistent profile/context behavior;
- inspect relevant open-source projects for architecture ideas;
- research current public ATS job-feed APIs;
- document findings in `docs/research-notes.md`.

Deliverable:

```text
docs/research-notes.md
docs/decisions/0001-initial-stack.md
```

---

## Phase 1 — Candidate brain + core schemas

Build:

- Pydantic domain models;
- `candidate/profile.yaml` schema;
- candidate Markdown conventions;
- candidate source index;
- SQLite DB + migrations;
- simple CLI.

CLI examples:

```bash
job-agent candidate validate
job-agent candidate search "leadership"
job-agent db status
```

Tests:

- missing facts never default silently;
- stable candidate source IDs;
- Markdown/frontmatter indexing;
- structured fact lookup.

No browser automation yet.

---

## Phase 2 — Job evaluation

Build:

- URL/JD ingestion;
- normalized job model;
- eligibility extraction;
- hard eligibility checker;
- criterion extraction;
- evidence matrix;
- fit score;
- importance score;
- tier classification.

CLI:

```bash
job-agent evaluate <url>
```

Output:

```text
Company:
Role:
Eligibility:
Fit:
Importance:
Tier:
Required criteria:
Evidence:
Gaps:
Recommended next action:
```

This phase should already be useful manually.

---

## Phase 3 — Application preparation

Build:

- resume inventory;
- base resume selection;
- evidence-backed resume tailoring;
- free-response answer retrieval;
- answer generation;
- provenance extraction;
- grounding gate;
- style gate;
- slop critic.

CLI:

```bash
job-agent prepare <job-id>
```

Generate an application packet containing:

```text
evaluation
selected resume
resume changes
likely questions
draft answers
quality reports
```

Still no autonomous browser required.

---

## Phase 4 — Browser prototype

Implement:

- BrowserProvider abstraction;
- Browserbase provider;
- Browser Use worker;
- mock application test site;
- candidate tools;
- application event logging;
- pause/escalate mechanism.

Test against controlled forms first.

Target:

- reliable completion;
- zero unsupported candidate claims;
- graceful escalation.

---

## Phase 5 — Real application flows

Manual live tests now cover Lever and Ashby application pages. They fill only
verified facts, upload the rendered resume through Browserbase Session Uploads,
and stop before submission. The worker still escalates the three tested jobs
because work authorization is unknown or the role is below threshold.

Test representative:

- Greenhouse;
- Lever;
- Ashby;
- Workday;
- custom portal.

Do not write ATS-specific selector frameworks unless a tiny deterministic helper is objectively better.

Record failure types.

Fix general browser-agent/tooling problems before adding one-off site hacks.

---

## Phase 6 — Hermes integration

Expose high-level actions to Hermes.

Desired UX:

```text
apply <url>
evaluate <url>
show application <id>
answer <id> <response>
approve <id>
```

Connect Telegram if not already configured.

Tier A results should be presented as preparation packets, not autonomous applications.

---

## Phase 7 — Discovery

Add deterministic job sources. Greenhouse, Lever, Ashby, and SimplifyJobs are
now available; SimplifyJobs reads the public feeds behind Swelist directly and
is exposed through both the CLI and Hermes MCP.

Build:

- scheduled ingestion;
- deduplication;
- new-job detection;
- eligibility filtering;
- cheap first-pass ranking;
- deeper evaluation for promising jobs;
- Telegram notifications.

Example:

```text
NEW — Company / Role
Fit: 88
Importance: 92
Tier A
Why: ...
```

---

## Phase 8 — Learning loop

Capture:

- user-edited answers;
- rejected drafts;
- user tier overrides;
- user skip/apply decisions;
- resume choices.

Build reports:

```text
edit rate by answer category
tier override rate
false-positive jobs
false-negative jobs
application success by source/tier
```

Update style retrieval and policies from explicit, inspectable data.

Do not silently mutate hard candidate facts.

---

## Phase 9 — Controlled auto-submit

Only after enough evidence.

Potential allowlist conditions:

```text
Tier C
eligibility = pass
all hard facts known
no RED questions
grounding gate = pass
style gate = pass
no unsupported claims
application type has strong historical reliability
```

Keep a global kill switch.

Keep per-company/site policies.

---

## Non-goals for early phases

Do not build:

- full React dashboard;
- Kubernetes;
- Redis;
- distributed task system;
- vector database;
- custom browser farm;
- fine-tuned writing model;
- ATS-specific mega-framework;
- automated LinkedIn spam;
- autonomous assessments/interviews.

Build the smallest useful personal system first.
