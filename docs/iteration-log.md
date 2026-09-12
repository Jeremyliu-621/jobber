# Iteration log

## 2026-09-11 - Resume source and packet readiness

- Observation: the newly supplied resume was a LaTeX source inside a ZIP, not a
  rendered PDF.
- Change: moved the source and archive into `candidate/resumes/`, registered
  `swe-current`, and synchronized current candidate evidence.
- Safety result: the planner now fails the quality gate when a registered
  source has no rendered PDF.
- Validation: 21 tests, Ruff, and mypy pass after the hardening changes.
- Follow-up: install or provide a LaTeX compiler when an employer upload needs a
  PDF.

## 2026-09-11 - Grounding and browser safety hardening

- Observation: a sentence could share enough ordinary words with a source to
  hide an invented metric, and a browser worker could run with a failed packet
  quality gate.
- Change: numeric claims must be present in retrieved source text, lexical
  grounding uses a higher support threshold, and the worker refuses packets
  without a passing quality report. Resume registration also rejects missing
  source or rendered files.
- Validation: targeted regression tests cover invented metrics, failed packet
  refusal, missing resume artifacts, and missing CLI files.
- Follow-up: add a controlled mock-form runner before testing employer portals.

## 2026-09-11 - Remote Browser Use API alignment

- Observation: the installed Browser Use 0.13.10 package returned a
  `BrowserSession` from `Browser(...)`; the older `new_context()` smoke code
  did not apply.
- Change: the adapter now uses the documented remote-session flags and always
  stops the Browser Use session in a `finally` block.
- Validation: a live Browserbase session navigated to `https://example.com/`
  over CDP and was released. No employer site was opened.

## Final verification - 2026-09-11

- 25 tests passed.
- Ruff and mypy passed across the repository.
- Candidate validation passed; 40 candidate sources indexed and one resume
  registered.
- Hermes connected over WSL stdio and discovered 11 tools.
- Browserbase created and released a session after Browser Use navigated to
  `https://example.com/` only.
- No raw Browserbase token was found outside the ignored `.env` file.
- No application was submitted.

## Operating guidance adopted

The current official OpenAI model guidance recommends explicit instructions for
initiative and follow-through, auditing instruction files such as `AGENTS.md`,
and calibrating testing and verification to the change. This loop encodes those
practices locally:

- [OpenAI model guidance](https://developers.openai.com/api/docs/guides/latest-model)

## 2026-09-12 - Live job and form test

- Observation: three current public postings were ingested from Lever and
  Ashby feeds: SoloPulse Software Engineer Intern/Co-op, Super.com Software
  Engineering Intern - Platform, and Notion Software Engineer Intern. The
  first Lever evaluation missed Python and C++ because Lever stores those
  requirements in structured `lists` fields.
- Hypothesis: retaining the structured Lever sections will make the score and
  evidence matrix reflect the actual posting, and recognizing U.S. city/state
  location formats will prevent an unsafe authorization pass.
- Change: Lever descriptions now include `lists` and additional sections;
  U.S. location detection recognizes common city/state formats; remote file
  uploads use Browserbase Session Uploads and the runner receives the remote
  path; browser policy prefers a required `_systemfield_resume` over an
  optional ATS autofill input.
- Result: SoloPulse now extracts required Python and C++ and escalates on
  unknown U.S. work authorization. Super.com scores 73.8 with unknown Canada
  authorization; Notion scores 66.6 with unknown U.S. authorization. The
  worker created no session for any of these plans because its gates correctly
  escalated or skipped them.
- Live bounded form result: Lever accepted the rendered resume and verified
  name, email, phone, LinkedIn, and GitHub fields. Ashby accepted the same
  verified fields and the rendered resume when the required system resume
  input was selected on both Notion and Super.com. Every session was released
  and no final submit control was clicked. The optional Ashby autofill widget
  showed a site-side fetch error when deliberately selected, confirming the
  field-selection rule.
- Resume result: MiKTeX rendered the supplied LaTeX resume to a one-page PDF;
  visual inspection and text extraction found the expected name, email,
  school, and Futurify entries. The PDF is registered as the rendered artifact
  for `swe-current`.
- Validation: focused tests, the full suite, Ruff, and mypy pass. No
  application has a submitted state.
- Next experiment: add a local mock-form runner and configure a model runner
  only after the user supplies missing work-authorization facts.

## 2026-09-12 - Hermes host check

- A fresh `hermes mcp test job-agent` retry and a basic `wsl.exe` echo were
  blocked by `Wsl/Service/CreateInstance/HCS_E_CONNECTION_TIMEOUT` from the
  host. The earlier Hermes MCP discovery passed with eleven tools before this
  host-level timeout. No project or MCP configuration was changed in response.

## 2026-09-12 - Browser live view and replay links

- Observation: Browserbase sessions were recorded, but the application exposed
  only a session ID, so a user could not easily watch an active worker or open
  the completed recording from the CLI/MCP boundary.
- Hypothesis: calling Browserbase's documented debug and replay endpoints
  through the provider will provide both capabilities while preserving the
  provider abstraction and the server-side credential boundary.
- Change: added provider-neutral live view and replay models; implemented the
  Browserbase debug, replay metadata, and HLS playlist calls; recorded live and
  replay events from the worker; added `application browser-links` and the MCP
  `get_browser_session_links` tool; documented the Browserbase Session
  Inspector URL as the durable replay entry point.
- Safety result: the worker still releases sessions and never submits forms.
-  Event payloads store tab IDs and an inspector link, not live debugger access
  URLs, signed HLS URLs, or API keys. A completed session reports live view as
  unavailable while replay metadata remains queryable. The links command keeps
  the inspector link available even when recording finalization is delayed.
- Validation: 30 tests passed; Ruff and mypy passed. A real bounded Browserbase
  smoke session returned a live debugger URL, exposed one replay page after
  release, and was released successfully. No job page was opened and no
  application was submitted.

## 2026-09-12 - SimplifyJobs discovery integration

- Observation: Swelist is a CLI whose documented agent interface
  emits human-formatted stdout, while the app already owns a deterministic
  `JobSource` boundary.
- Hypothesis: reading the public SimplifyJobs JSON feeds used by Swelist will
  provide a stable, richer discovery adapter without coupling job ingestion to
  terminal formatting.
- Change: added `SimplifyJobsSource` with internship/new-grad, timeframe, and
  location filters; exposed it through `job-agent job discover-simplifyjobs` and
  the Hermes MCP `discover_simplifyjobs` tool; preserved upstream rows and
  posting IDs in normalized jobs; kept the old Swelist names as compatibility
  aliases; documented the missing-description limitation.
- Safety result: discovery remains read-only with respect to employers; no
  application or submission path is invoked.
- Validation: focused parser/filter tests, 33 full pytest tests, Ruff, and mypy
  pass; live Toronto feed ingestion was checked through the app boundary and
  remained idempotent after the canonical rename.
