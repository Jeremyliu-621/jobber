# Architecture

## 1. Components

### Hermes

Hermes is already installed locally.

Use Hermes for:

- Telegram/mobile control;
- high-level commands;
- scheduled discovery tasks if appropriate;
- conversational interaction;
- invoking our application service;
- approval/escalation messages.

Do not make Hermes responsible for every browser click.

Expose a small number of domain tools to Hermes:

```text
find_jobs(...)
evaluate_job(url_or_id)
prepare_application(job_id)
apply_job(job_id)
get_application_status(id)
answer_application_question(id, answer)
approve_submission(id)
```

The first integration should expose these operations through a local stdio MCP
server. Hermes already supports MCP tool discovery and per-server tool
filtering, so the application service remains independent of Hermes while the
Telegram gateway can still invoke the same domain operations.

---

## 2. Application service

A Python package/service owns application logic.

Suggested modules:

```text
job_agent/
├── models/
├── db/
├── candidate/
├── discovery/
├── planner/
├── scoring/
├── quality/
├── resumes/
├── browser/
├── llm/
└── interfaces/
```

Avoid prematurely splitting this into multiple services.

---

## 3. Candidate brain

### Structured facts

`candidate/profile.yaml`

Used for anything where guessing is unacceptable.

Suggested schema:

```yaml
identity:
  legal_name:
  preferred_name:
  email:
  phone:

education:
  - institution:
    program:
    degree:
    start_date:
    graduation_date:
    location:
    gpa:

work_authorization:
  canada:
    authorized:
    sponsorship_required:
    notes:
  usa:
    authorized:
    sponsorship_required:
    notes:

links:
  github:
  linkedin:
  portfolio:

preferences:
  target_roles:
  locations:
  remote:
```

Do not populate unknown fields with guesses.

### Human knowledge

Markdown files:

```text
candidate/
├── experiences/
├── projects/
├── stories/
├── answers/
├── style.md
└── companies/
```

Recommended frontmatter:

```yaml
---
id: story-example
type: story
topics:
  - leadership
  - ambiguity
  - teamwork
approved: true
source: user-authored
---
```

---

## 4. Job discovery

Use deterministic ingestion where possible.

Create adapters:

```python
class JobSource(Protocol):
    async def fetch_jobs(self) -> list[RawJob]: ...
```

Potential sources:

- Greenhouse public boards;
- Lever postings;
- Ashby postings;
- Swelist's public SimplifyJobs internship and new-grad feeds;
- company career pages;
- maintained internship feeds/repos;
- user-submitted URLs;
- other job aggregators if permitted.

Normalize everything into a single `Job` object.

`SimplifyJobsSource` reads the public JSON feed behind the Swelist CLI rather
than parsing its human-oriented Rich output. This keeps discovery deterministic
and preserves the upstream posting metadata. `SwelistSource` remains a public
compatibility alias, and the persisted `swelist` source key is retained for
existing rows. These postings are useful for triage: the feed does not
consistently include full job descriptions, so linked ATS sources can provide
richer evaluation input later.

Do not use a browser agent to click through job boards if structured data is readily available.

---

## 5. Application planner

Planner flow:

```text
job
 ↓
normalize JD
 ↓
hard eligibility
 ↓
fit analysis
 ↓
importance score
 ↓
tier classification
 ↓
evidence matrix
 ↓
resume selection
 ↓
answer plan
 ↓
quality gates
 ↓
browser execution
```

### Hard eligibility

Examples:

- graduation window;
- work authorization;
- location;
- student status;
- degree constraints;
- required availability;
- years-of-experience constraints.

Possible result:

```python
EligibilityResult(
    status="pass" | "fail" | "uncertain",
    reasons=[...],
    missing_facts=[...],
)
```

If uncertain, ask the user rather than infer.

---

## 6. Fit scoring

Do not reduce fit to one LLM vibe score.

Produce structured criteria:

```python
class Criterion(BaseModel):
    name: str
    category: Literal["required", "preferred", "contextual"]
    weight: float
    evidence_ids: list[str]
    evidence_strength: float
```

Example:

```text
Python          required     strong
AWS             required     strong
PostgreSQL      required     strong
Docker          preferred    weak
Kubernetes      preferred    none
```

Then calculate an overall score with a documented formula.

The model may extract criteria and judge evidence, but the score inputs should be inspectable.

---

## 7. Importance scoring

Importance answers:

> How much human attention should this application receive?

Inputs may include:

- user excitement;
- career upside;
- role fit;
- learning opportunity;
- company quality;
- compensation/upside if known;
- location preference;
- referral/network opportunity;
- strategic fit with user's career goals.

Do not equate company fame with importance.

Suggested initial interpretation:

```text
90–100 -> Tier A
75–89  -> Tier B
60–74  -> Tier C
<60    -> skip
```

These thresholds should be configurable.

---

## 8. Browser architecture

Use an abstraction:

```python
class BrowserProvider(Protocol):
    async def create_session(self, profile_id: str | None = None) -> BrowserSessionInfo: ...
    async def close_session(self, session_id: str) -> None: ...
    async def get_cdp_url(self, session_id: str) -> str: ...
    async def get_live_view_url(self, session_id: str) -> str | None: ...
```

Initial implementation:

```text
BrowserbaseProvider
```

Later:

```text
SteelProvider
LocalChromeProvider
```

Browser Use should attach over CDP.

Do not allow Browserbase-specific assumptions to leak into planning/business logic.

---

## 9. Browser agent tools

The browser agent should not receive a giant candidate blob.

Expose narrow tools:

```text
get_candidate_fact(path)
search_candidate_knowledge(query)
get_resume(resume_id)
get_previous_answer(question)
ask_user(question, application_id)
record_generated_answer(...)
record_application_event(...)
```

Browser task prompt should emphasize:

- fill using verified facts;
- do not fabricate;
- escalate uncertainty;
- do not alter legal answers;
- do not submit without current policy allowing it.

---

## 10. Concurrency

Use a queue/worker model.

Do not open 1,000 tabs in one Chrome instance.

Prefer isolated application workers.

Conceptually:

```text
application queue
  ├─ worker 1 -> browser session
  ├─ worker 2 -> browser session
  ├─ worker 3 -> browser session
  └─ ...
```

Add per-profile/per-site locks when concurrent use of the same authenticated browser context could invalidate sessions.

Start with low concurrency. Scale only after measuring reliability.

---

## 11. Observability

Every browser/application run should record:

- job;
- browser provider;
- session id;
- start/end timestamps;
- final state;
- pages visited;
- questions encountered;
- answers used;
- candidate facts used;
- escalations;
- errors;
- whether human edits were required;
- submission state.

Never log secrets in plaintext.

Store enough information to reproduce why the system made a decision.
