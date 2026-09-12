# Browser Agent Design

## Principle

Do not model an application as a fixed sequence of selectors.

Model it as:

> **A goal-directed agent operating a real browser while constrained by candidate truth and application policy.**

---

## Preferred stack

```text
Browser Use
    │
    │ CDP
    ▼
Browserbase
```

Research current APIs before implementing because these projects evolve quickly.

Browserbase is infrastructure.
Browser Use is browser intelligence.

## Implemented boundary

`job_agent.browser.BrowserbaseProvider` creates and releases Browserbase
Sessions through the current REST API. `ControlledBrowserWorker` owns the
session lifecycle, writes application events, and refuses to start when
eligibility is uncertain, a resume is missing, the quality gate has failed, or
the application is below the configured tier threshold. A registered source
also needs a real local rendered PDF before browser preparation can pass.
`BrowserUseRunner` is an optional adapter that attaches Browser Use to the
returned CDP URL and always releases the Browser Use session.
Before the runner starts, `BrowserbaseProvider` uploads the selected rendered
resume through the Browserbase Session Uploads API and passes the resulting
session-local path to Browser Use. ATS pages with multiple file inputs should
target the required application resume field instead of an optional resume
autofill widget.

While a worker session is running, it fetches Browserbase Live View URLs and
records only their availability and tab IDs in the application event log.
Debugger URLs are access links and are returned only on demand. After release,
the worker records replay metadata when available. `application browser-links
APPLICATION_ID` and the MCP `get_browser_session_links` tool return the active
debugger URL or the Browserbase Session Inspector URL for the completed
recording. HLS playlist retrieval stays behind the provider so the Browserbase
API key never reaches a client.

The runner result can move an application to `ready_to_submit`, but no code
path clicks or submits a final application button. The MCP and CLI approval
operations record human review and keep submission disabled.

---

## Browser worker input

Example:

```python
ApplicationTask(
    application_id="...",
    job_id="...",
    url="...",
    tier="B",
    resume_id="swe_backend",
    submission_policy="stop_before_submit",
)
```

---

## Browser agent system rules

The browser agent should receive a short, strict policy.

Example:

```text
You are completing a job application for the candidate.

You may use candidate tools to obtain verified information.

Rules:
1. Never fabricate candidate facts.
2. If a factual answer is unknown, use ask_user().
3. Never guess work authorization.
4. Never guess demographic/EEO answers.
5. Use approved candidate stories/answers when possible.
6. You may rewrite for clarity but may not create unsupported achievements.
7. Use the requested resume file exactly.
8. If the website explicitly blocks automation or requires a human verification step, escalate.
9. Follow the application's normal flow.
10. Stop before final submission unless the application's current policy explicitly allows auto-submit.
```

---

## Agent tools

### Candidate

```text
get_candidate_fact(path)
search_candidate_knowledge(query, types=None, top_k=5)
get_approved_answers(query, top_k=5)
get_style_examples(question_type, top_k=5)
```

### Files

```text
get_resume_path(resume_id)
get_cover_letter_path(application_id)
```

### Application state

```text
record_question(...)
record_answer(...)
record_event(...)
set_application_state(...)
```

The shipped MCP server exposes `get_candidate_fact`,
`search_candidate_knowledge`, `answer_application_question`, and
`get_application_status` for these operations. It also exposes
`record_feedback` for explicit human edits and rejections. All browser worker
events are stored in SQLite; secrets and raw credentials are excluded from
event payloads.

### Human escalation

```text
ask_user(
    application_id,
    question,
    context,
    allowed_options=None
)
```

The worker should pause safely while waiting for an answer rather than restarting the browser flow from scratch when possible.

---

## Browser provider abstraction

```python
@dataclass
class BrowserSessionInfo:
    session_id: str
    cdp_url: str
    live_view_url: str | None
    profile_id: str | None

class BrowserProvider(Protocol):
    async def create_session(
        self,
        profile_id: str | None = None,
    ) -> BrowserSessionInfo: ...

    async def close_session(self, session_id: str) -> None: ...

    async def get_live_view(self, session_id: str) -> BrowserLiveView: ...

    async def list_replays(self, session_id: str) -> tuple[BrowserReplayPage, ...]: ...

    async def get_replay_playlist(self, session_id: str, page_id: str) -> str: ...
```

First implementation: Browserbase.

Second possible implementation: Steel.

---

## Profiles/contexts

Maintain reusable browser identity carefully.

Examples:

```text
candidate-general
google
workday:<tenant>
portal:<company>
```

Do not assume a single shared profile is safe for all parallel sessions.

Build a small locking mechanism:

```text
profile_id -> max active sessions
```

Default conservative value: 1 for authenticated contexts until tested.

---

## Deterministic helpers are allowed

Use deterministic browser code for stable primitives such as:

- file uploads;
- downloads;
- screenshots;
- DOM extraction;
- CDP inspection;
- reading current URL;
- opening/closing tabs;
- detecting browser crashes;
- retrieving live-view links.

Do not encode each ATS application's semantic flow as deterministic selectors.

---

## Failure handling

Classify failures.

```text
NAVIGATION_FAILURE
AUTH_REQUIRED
MFA_REQUIRED
CAPTCHA_OR_HUMAN_VERIFICATION
UNKNOWN_PERSONAL_FACT
UNSUPPORTED_QUESTION
FILE_UPLOAD_FAILURE
SITE_BLOCKED_AUTOMATION
BROWSER_CRASH
AGENT_STUCK
SUBMISSION_ERROR
```

For each failure:

1. record event;
2. capture enough state for debugging;
3. decide retry vs escalation;
4. prevent infinite loops.

Set maximum action counts / time budgets per application.

---

## Browser agent evaluation

Create a local test suite using mock job forms.

Include:

- basic single-page form;
- multi-step form;
- custom select;
- React-style combobox;
- iframe;
- file upload;
- conditional question;
- validation error;
- unknown candidate fact;
- final submit confirmation.

Measure:

```text
completion rate
incorrect fields
hallucinated facts
human escalations
actions per application
time per application
token/model cost
```

Do not test first against only live employer sites.
