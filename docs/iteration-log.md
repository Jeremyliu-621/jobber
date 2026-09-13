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

## 2026-09-12 - Browser Use resume upload retry

- Observation: the first upload probe reached Browserbase but found no file
  target because Browser Use's selector map had not been populated yet.
- Hypothesis: the normal agent state request must run before selecting an upload
  element; the ATS field itself is available once that state is ready.
- Change: repeated the fresh Browserbase run with Browser Use's state request,
  cross-origin iframe inspection, and the required Ashby `_systemfield_resume`
  target. The remote PDF was attached through Browser Use's native upload event.
- Result: the form held `Jeremy_Liu_Resume.pdf` with MIME type
  `application/pdf` and size 169,105 bytes. The session completed with a replay;
  no submit control was clicked.
- Limitation: the repository has no configured LLM key, so this experiment
  exercised the Browser Use upload action path directly rather than a full
  model decision loop. The model-backed runner still uses this same handler.

## 2026-09-12 - Minimal research desk frontend

- Observation: the first frontend pass exposed too much explanatory UI for a
  product whose primary task is scanning and triaging job records.
- Hypothesis: a single dense index with only Jobs, Apps, search, filters, and
  progressive job detail will better match the requested research-tool feel.
- Change: replaced the multi-section dashboard with a black-and-white,
  Times New Roman interface built from straight rules and tables; retained the
  read-only SQLite-backed web adapter and local `job-agent web` command.
- Safety result: the frontend exposes read-only dashboard/detail endpoints;
  final application submission remains human-only.
- Validation: 35 full pytest tests, Ruff, mypy, Node syntax checking, live API
  health, browser navigation, search filtering, Apps view, and job detail all
  passed.
- Next experiment: connect a deliberate user action to discovery refresh only
  after deciding whether the web surface should remain read-only.

## 2026-09-12 - Hermes Telegram job-agent bridge repair

- Observation: Hermes Telegram connected successfully, but the long-running
  gateway repeatedly parked the `job-agent` MCP after `FileNotFoundError:
  cmd.exe`; an interactive `hermes mcp test job-agent` still passed.
- Hypothesis: the gateway service could not resolve the bare Windows launcher
  name from its WSL service environment, while the project MCP executable and
  database were healthy.
- Change: updated Hermes' local `job-agent` MCP launcher to the explicit
  `/mnt/c/Windows/System32/cmd.exe` path, preserved its existing `/c` command
  and project executable, and restarted both the user gateway and dashboard
  services so their cached configurations were reloaded.
- Result: both services are active; Telegram reconnects in polling mode and
  registers its command menu; the gateway registers all 18 project MCP tools;
  Hermes' MCP test connects through the explicit launcher and discovers all 14
  callable project tools. Both service-owned watchdog processes remain alive
  through a stability window with no new launch failures.
- Limitation: no Telegram message was sent, so inbound message handling was
  not externally exercised in this check. No application submission occurred.

## 2026-09-12 - Narrow Hermes scope to Jobber

- Observation: the default Hermes gateway had nine active personal routines
  and an enabled RFP MCP server alongside the Jobber tools.
- Hypothesis: pausing the routines and disabling the RFP MCP will keep Catbot
  focused on Jobber while preserving the underlying definitions for later
  reactivation.
- Change: paused all nine scheduled routines, set the RFP MCP to
  `enabled: false`, and restarted the Hermes gateway and dashboard services.
- Result: Hermes reports no scheduled jobs; the RFP MCP is disabled; GitHub
  remains enabled for Jobber development; the Jobber MCP probe connects and
  discovers 15 callable tools; Telegram and the gateway remain active.
- Safety result: no external message was sent, no scheduled routine was run,
  and no application was submitted.

## 2026-09-12 - Single-size j-blog frontend pass

- Observation: the research-desk frontend still used a large display heading
  and several smaller utility sizes, which made it feel more like a dashboard
  than the user's restrained serif reference.
- Hypothesis: one 16px type size, with hierarchy expressed through weight,
  spacing, case, and rules, will make the interface quieter and more legible.
- Change: verified the user's j-blog reference and removed the size jumps from
  the frontend; narrowed the desktop column and kept Times New Roman, black and
  white, centered content, and straight rules.
- Safety result: this was a visual-only change; the frontend remains read-only
  and final application submission remains human-only.
- Validation: 35 full pytest tests, Ruff, mypy, Node syntax checking, and a
  live browser reload all passed.

## 2026-09-12 - j-blog research index overhaul

- Design read: a personal, read-only job research index for one operator;
  visual variance 5, motion 1, information density 6, asset dependence 1,
  and product-brand fidelity 5.
- Preserve: the Jobs and Apps routes, live SQLite data, search and filters,
  progressive job detail, keyboard-accessible actions, and human-only submit
  boundary.
- Remove: dashboard chrome, oversized headings, table headers, cards, badges,
  decorative status treatment, and explanatory copy that did not help triage.
- Change: rebuilt the frontend around the reference's centered personal index
  grammar: quiet masthead, plain underlined navigation, stacked entries,
  single-size Times New Roman typography, thin rules, and a detail document
  opened only for the selected job.
- Originality result: reused abstract layout principles only; no source images,
  source copy, logos, or source code were shipped.
- Validation: focused web tests, Node syntax checking, API health, live Jobs and
  Apps navigation, entry detail, and final browser rendering all passed. The
  unrelated full-suite Browser Use failures remain documented in the task
  update and were not changed.

## 2026-09-12 - Model-backed browser tools and human escalation

- Observation: Browser Use could attach to a remote session, but the runner had
  no custom action for unknown candidate facts or live human input. The model
  key and model selection were also not represented in local configuration.
- Hypothesis: registering Browser Use custom actions around the existing worker
  boundary will preserve model-driven form understanding while making unknown
  answers explicit and auditable.
- Research: current Browser Use documentation supports `Tools` custom actions,
  `ActionResult(is_done=True, success=False)` for stopping a task, and
  `ChatBrowserUse(model=..., api_key=...)` for the model client. See the official
  [custom tools](https://docs.browser-use.com/open-source/customize/tools/add),
  [response format](https://docs.browser-use.com/open-source/customize/tools/response),
  and [agent configuration](https://docs.browser-use.com/open-source/customize/agent/basics)
  documentation.
- Change: added `ask_user`, verified fact lookup, and approved knowledge search
  actions to `BrowserUseRunner`; added a callback-based human escalation
  contract; recorded questions and answers in SQLite without logging answer
  text; added retrieval of previously supplied answers for later runs;
  added `BROWSER_USE_API_KEY`/model configuration and the interactive
  `application run` command.
- Safety result: unknown answers return `needs_user`; final submission remains
  disabled; answer and browser errors are not written into event payloads.
- Validation: full pytest, Ruff, and mypy pass. No model-backed live run was
  started because the local `.env` has no `BROWSER_USE_API_KEY`.
- Next experiment: run the model-backed worker against the controlled mock form
  with an interactive human callback before another employer-site test.

## 2026-09-12 - Per-opportunity browser replay

- Observation: the three saved applications had no attached Browserbase
  session, and the existing live/replay metadata was available only through
  service and CLI interfaces.
- Hypothesis: exposing the session state inside each opportunity keeps the
  research index truthful while making a future filled tab immediately
  inspectable.
- Change: attached the latest application record to job payloads, added
  read-only browser-links and HLS playlist proxy routes, and added a detail
  viewer with live-session embedding and replay playback. Browserbase keys
  remain server-side; final submission remains disabled.
- Result: opportunities without a stored session show `no replay`; active
  sessions can show `live`, and released sessions can show recorded tabs.
- Validation: web tests, replay proxy test, Ruff, Node syntax checking, and
  API/browser smoke checks.

## 2026-09-12 - Move opportunity formatting upstream

- Observation: the frontend was parsing one flattened `description_text` at
  render time. The Ashby payload still contained source HTML headings and
  lists, but that structure was not represented in the application domain.
- Hypothesis: a versioned opportunity extraction step at ingest, evaluation,
  and preparation will make formatting durable, source-grounded, and
  independently improvable by the agent.
- Change: added `OpportunityDocument` and `OpportunitySection` models, an HTML
  and plain-text extractor, SQLite persistence, CLI and MCP extraction entry
  points, and a backfill for all 231 stored jobs. The frontend now renders only
  persisted opportunity sections; it has no description parser or heading
  guesses.
- Safety result: sections retain their source text, no candidate facts are
  generated, and the flattened job description remains available for search
  and compatibility.
- Validation: 42 tests, Ruff, mypy, Node syntax checking, real-record API
  inspection, and live browser rendering all pass.

## 2026-09-12 - Hosted productization brainstorm

- Observation: the current repository is a healthy local single-user slice,
  but its SQLite database, `Path.cwd()` configuration, filesystem candidate
  brain, stdio MCP server, and local web adapter do not provide user identity,
  tenant isolation, cloud document storage, or durable background execution.
- Hypothesis: a local companion should own each user’s Codex/Claude CLI session
  and selected document folders, while a hosted control plane owns workspace
  metadata, provenance, queues, approvals, and optional cloud workers.
- Research: current OpenAI docs warn that Codex cached login material contains
  sensitive tokens and should not be exposed in untrusted/public environments;
  Claude documents `claude -p`, the Agent SDK, sandboxed hosting, and the
  limitations of subscription setup tokens. Cloud Run provides stateless
  services, jobs, and worker pools; Supabase provides JWT/RLS patterns for
  workspace-scoped rows and files.
- Change: added `docs/deployment-brainstorm.md` and appended current research
  notes. No production deployment, credential migration, hosted worker, or
  application submission was performed.
- Validation: `.venv\\Scripts\\python.exe -m pytest -q` passed with 39 tests;
  `.venv\\Scripts\\python.exe -m ruff check src tests` passed. The default
  system Python lacks the project import path and Ruff, so those commands are
  not valid repository baselines without the project environment.
- Next experiment: introduce `WorkspaceContext`, storage interfaces, and an
  `AgentRunner`/companion protocol behind local test fakes before selecting a
  hosted database or queue implementation.

## 2026-09-12 - Application filters

- Observation: the Apps view listed every application without a local triage
  control.
- Hypothesis: compact search, tier, and state filters will make the existing
  list useful without changing its research-index layout.
- Change: added live application search, data-driven state options, tier
  filtering, a responsive result count, and a clear action. Job filters and
  application data remain unchanged.
- Validation: browser smoke checks covered search, tier, state, and clear;
  Node syntax checking, 42 tests, Ruff, mypy, and `git diff --check` pass.

## 2026-09-12 - Local friend setup

- Observation: the personal workflow was end to end, but a second user still
  had to understand the repository layout, edit paths manually, and rely on
  the hosted Browser Use model path.
- Hypothesis: a local workspace initializer, document inbox, and shell-free
  adapters for the user’s installed Codex or Claude CLI are enough to make the
  current tool repeatable for friends without adding a hosted control plane.
- Research: current Codex docs document `codex exec --json` and ephemeral runs;
  Claude documents `claude -p`, JSON output, and bare mode for scripted calls.
  The adapters intentionally keep these calls local and do not read or store
  credential files.
- Change: added per-user workspace config under the platform config directory;
  `job-agent init`, workspace/provider selection, local document-folder
  inventory/import commands, hashed document manifests, local Codex/Claude
  runner commands, and PowerShell/bash installers. Starter profile values are
  blank and existing files are never overwritten.
- Safety result: document import copies only supported files into the local
  inbox; provider execution uses `shell=False`; stderr is not returned in run
  results; Browserbase final submission remains disabled.
- Validation: `.venv\\Scripts\\python.exe -m pytest -q` passed with 51 tests;
  `.venv\\Scripts\\python.exe -m ruff check src tests` passed; mypy passed on
  41 source files; CLI help, workspace initialization, provider detection, and
  empty document inventory smoke checks passed. Real model execution was
  intentionally not invoked.
- Next experiment: run a local provider against a disposable fixture workspace,
  then add a narrow document-organizer task with an explicit write boundary.

## 2026-09-12 - Guard failed browser runs

- Observation: the Super.com run opened a Browserbase session, but Browser Use
  rejected all six model requests because the account could not use the LLM
  Gateway. The runner returned an empty history summary, and the worker marked
  the application `ready_to_submit` even though no form fields were filled.
- Change: recorded the user-provided Canada authorization fact, configured the
  Browser Use key locally, corrected the application to `failed`, and added a
  guard that rejects Browser Use histories without a final result.
- Replay result: the session produced one recorded tab; Jobber loaded the
  replay control and played the HLS replay successfully. No submission occurred.
- Validation: 52 tests, Ruff, mypy, Node syntax checking, and `git diff --check`
  pass.
