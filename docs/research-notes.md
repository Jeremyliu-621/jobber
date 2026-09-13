# Research Notes

Date: 2026-09-09

## Local Hermes audit

Hermes is installed in the WSL2 Ubuntu environment at `/home/jerem/.hermes/hermes-agent`, with the CLI at `/home/jerem/.local/bin/hermes`. The installed version is Hermes Agent `0.18.2` (`2026.7.7.2`), running Python `3.11.15`. Its gateway and dashboard are managed by user-level systemd services. Telegram is configured, the gateway is active, and nine scheduled jobs are present.

Hermes exposes a built-in browser toolset and has source-level providers for Browser Use, Browserbase, local Chromium/CDP, and other backends. The local installation currently has no direct Browser Use or Browserbase credentials and is not logged into the Nous Portal browser gateway. Phase 1 therefore must remain provider-independent.

Hermes has first-class MCP support. It discovers tools from local stdio or remote HTTP servers and supports per-server tool filtering. Two existing MCP servers, GitHub and `futurify_rfp_control`, connect successfully and enumerate tools. A local stdio MCP server is the intended future integration boundary for `jobber`.

During the audit, the Hermes gateway service definition was stale and was refreshed with `hermes gateway restart`. Five unpinned cron jobs had stopped because their recorded creation-time model differed from the current global model. Each was pinned to its recorded provider/model pair. The MCP reconnect warnings were transient startup/reconnect events; both servers passed connection and tool-discovery tests after the restart.

## Hermes findings

The official Hermes documentation describes MCP as the extension mechanism for external databases, APIs, filesystems, browser stacks, and internal services. It also documents the Tool Gateway, where Browser Use can be supplied through a Nous subscription, but that path requires Portal access and is not currently enabled on this machine.

Sources:

- [Hermes documentation](https://hermes-agent.nousresearch.com/docs/)
- [Hermes MCP integration](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp/)
- [Hermes browser automation](https://hermes-agent.nousresearch.com/docs/user-guide/features/browser/)
- [Hermes source repository](https://github.com/NousResearch/hermes-agent)

## Browser Use and Browserbase

Browser Use's current cloud API creates browser sessions through `https://api.browser-use.com/api/v3/sessions`. A session can be idle or task-backed, can stay alive for follow-up work, and can load a persistent `profileId`. Browser Use also exposes a browser-session API that returns a `cdpUrl` and `liveUrl`. Profiles persist cookies, local storage, and login state and must be stopped so state is saved.

Browserbase's current Sessions API is `POST https://api.browserbase.com/v1/sessions`, authenticated with `X-BB-API-Key`. A created session returns a `connectUrl` for CDP automation. Browserbase Contexts persist cookies, authentication, and application data across sessions. Persistence is opt-in through the session's browser context settings, and the documentation recommends one Context per site/login and avoiding simultaneous sessions on one Context.

The official Browserbase Browser Use integration creates a Browserbase session and passes its CDP URL to Browser Use's `Browser` class. This validates the repository's preferred `Browser Use → CDP → Browserbase` boundary. The provider abstraction should carry session IDs, CDP URLs, live-view URLs, profile/context IDs, and close/persist semantics without exposing those details to the planner.

Sources:

- [Browser Use create session API](https://docs.browser-use.com/cloud/api-v3/sessions/create-session)
- [Browser Use browser session API](https://docs.browser-use.com/cloud/api-v3/browsers/create-browser-session)
- [Browser Use profiles](https://docs.browser-use.com/cloud/guides/authentication)
- [Browserbase sessions API](https://docs.browserbase.com/reference/api/create-a-session)
- [Browserbase Contexts](https://docs.browserbase.com/platform/browser/core-features/contexts)
- [Browserbase Browser Use integration](https://docs.browserbase.com/integrations/browseruse/python)

The installed open-source Browser Use package is 0.13.10. Its current Python
API aliases `Browser` to `BrowserSession` and exposes direct session methods
such as `start()`, `navigate_to()`, `get_current_page_title()`, and `stop()`.
Remote CDP sessions should be constructed with `is_local=False`, and browser
sessions should always be stopped after use. A live read-only smoke check
created a Browserbase session, navigated to `https://example.com/`, and
released the session successfully on 2026-09-11.

Source:

- [Browser Use remote browser documentation](https://docs.browser-use.com/open-source/customize/browser/remote)
- [Browser Use browser parameters](https://docs.browser-use.com/open-source/customize/browser/all-parameters)

For remote file inputs, Browserbase documents the Session Uploads API followed
by `DOM.setFileInputFiles` with the session-local path
`/tmp/.uploads/<filename>`. The Browserbase provider now uploads the selected
rendered resume through that API before Browser Use starts, so a local Windows
path is never handed to the remote browser as if it were a remote file.

Source:

- [Browserbase file uploads](https://docs.browserbase.com/platform/browser/files/uploads)
- [Browserbase Create Session Uploads API](https://docs.browserbase.com/reference/api/create-session-uploads)

Browserbase's current observability APIs support the requested browser replay
workflow. `GET /v1/sessions/{id}/debug` returns live debugger URLs for a running
session. After completion, `GET /v1/sessions/{id}/replays` lists recorded tabs
and `GET /v1/sessions/{id}/replays/{pageId}` returns an HLS playlist. The
application keeps the API key server-side and uses the durable Session Inspector
URL as the user-facing replay entry point.

Sources:

- [Browserbase Session Live URLs](https://docs.browserbase.com/reference/api/session-live-urls)
- [Browserbase Session Live View](https://docs.browserbase.com/platform/browser/observability/session-live-view)
- [Browserbase Session Replay](https://docs.browserbase.com/platform/browser/observability/session-replay)
- [Browserbase getting started](https://docs.browserbase.com/welcome/getting-started)

## Browserbase alternatives

Steel is an open-source browser API with managed and self-hosted deployment options. Its documented capabilities include CDP-based control, sessions, persistent profiles, proxies, CAPTCHA support, replays, and observability. Steel is a reasonable future provider implementation because it exposes the same broad lifecycle shape as Browserbase, but it should remain a later adapter until browser reliability requirements justify it.

Sources:

- [Steel documentation](https://docs.steel.dev/)
- [Steel open-source repository](https://github.com/steel-dev/steel-browser)

## Public ATS feeds

Greenhouse's Job Board API exposes published jobs as unauthenticated JSON GET requests. `content=true` includes descriptions, departments, and offices; individual job responses can include application questions, compliance fields, demographic questions, and pay ranges. This is the first deterministic discovery adapter to implement.

Lever's public Postings API exposes published postings and supports fields such as description, location, workplace type, salary information, and public application URLs. Lever also documents a public XML postings feed. Authenticated Lever Data API endpoints are not required for public discovery.

Ashby exposes a public job board endpoint at `https://api.ashbyhq.com/posting-api/job-board/{JOB_BOARD_NAME}`. It returns published jobs, locations, job URLs, application URLs, listing status, and optional compensation data. The job-board name comes from the company's hosted job-board URL.

Workday documents a Recruiting REST metadata API with a tenant-specific server and `/jobPostings` endpoint. There is no single public, tenant-independent feed contract to use as a universal adapter, so Workday should begin as targeted ingestion with explicit tenant configuration.

Sources:

- [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html)
- [Lever Developer documentation](https://hire.lever.co/developer/documentation)
- [Lever public postings feed use case](https://hire.lever.co/developer/usecases)
- [Ashby public job posting API](https://developers.ashbyhq.com/docs/public-job-posting-api)
- [Workday job postings metadata API](https://developer.workday.com/documentation/pyd1580334491723/)

## Swelist integration

Swelist is a Python CLI distributed on PyPI. Its current public project page
documents internship/new-grad role filters, timeframe filters, location
filters, and an agent integration based on parsing human-readable stdout. The
published package does not expose a typed Python discovery client. Its source
fetches JSON listings from the SimplifyJobs internship and new-grad GitHub
repositories, with fields such as company, title, locations, URL, posting
timestamps, category, and sponsorship metadata.

Sources:

- [Swelist on PyPI](https://pypi.org/project/swelist/)
- [Swelist source repository](https://github.com/chenyuan99/swelist)
- [SimplifyJobs Summer 2027 internship feed](https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json)
- [SimplifyJobs new-grad feed](https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json)

Architecture decision: `job_agent.discovery.SimplifyJobsSource` reads the
public JSON feed directly, applies the same role/timeframe/location semantics,
and stores the complete upstream row in `raw_payload`. This is more stable than
parsing Rich-formatted CLI output and keeps the discovery layer deterministic.
`SwelistSource` remains a compatibility alias, and existing persisted `swelist`
source labels are intentionally retained. The feed is metadata-oriented and
does not consistently include full job descriptions, so SimplifyJobs results
are suitable for initial triage and can be enriched from the linked ATS posting
before a high-value application is prepared. No API key or login is required.

## Architecture updates

- Hermes integration is recorded as a local MCP server rather than a Hermes-specific native plugin.
- Browser profiles/contexts are site-scoped identities and require conservative locking.
- Browserbase is wired through `BrowserbaseProvider`; a live create/release health check succeeded on 2026-09-09. Context IDs are sent under `browserSettings.context` with `persist=true`.
- The optional `BrowserUseRunner` attaches Browser Use's `Browser` to Browserbase's `connectUrl`, registers guarded candidate and human-escalation tools, and uses `ChatBrowserUse` by default when `BROWSER_USE_API_KEY` is configured. Packet preparation and safety checks remain usable without a model key or Browser Use installation.
- Greenhouse, Lever, and Ashby are the first deterministic discovery sources. Workday remains a later tenant-specific adapter.
- The local `job-agent-mcp` server is registered in Hermes over stdio and currently exposes fifteen domain tools, including the model-backed `run_application` entry point.

## Productization and hosted execution research

The current repository remains a local single-user vertical slice. It has no
workspace or tenant identity, authenticated API, object storage, queue, hosted
document pipeline, or deployment image. The local web server is intentionally
read-only and uses `Path.cwd()`, SQLite WAL, and filesystem-backed candidate
sources. These are local-mode defaults, not a public-service boundary.

For a multi-user product, the preferred connection model is a local companion:
the user authenticates Codex or Claude locally, chooses a document root, and
pairs an outbound companion connection with a hosted workspace. This keeps CLI
credentials and local documents on the user’s machine. A hosted worker can be a
later opt-in mode using explicit API-key or enterprise credentials and an
ephemeral sandbox. The product should not request uploaded Codex or Claude
credential cache files.

OpenAI documents ChatGPT sign-in and API-key paths for Codex CLI, warns that
cached login material can contain access tokens, and warns against exposing
Codex execution in untrusted or public environments. Claude Code documents
non-interactive `claude -p`/Agent SDK execution, local credential handling, and
the limitations of its subscription setup token. Codex app-server exposes a
useful local protocol, but its WebSocket transport is currently experimental
and unsupported for production use. These facts support a local companion
boundary instead of a public hosted app-server socket.

Cloud Run is a plausible first hosted runtime: stateless HTTP services for the
API, Jobs for bounded batch work, and worker pools or a managed queue for
background processing. Supabase Auth/Postgres/Storage is a plausible early
data plane because JWT authentication and RLS can protect both rows and
workspace-scoped files. The deployment alternative is a containerized API
with independent managed Postgres and S3-compatible storage.

The proposed durable model is `workspace_id` on every row, immutable document
versions, private object storage, source spans for extracted claims, an
idempotent task queue, and isolated workers for parsing, model execution, and
browser sessions. A vector database remains deferred until retrieval tests
demonstrate a need.

See [`docs/deployment-brainstorm.md`](deployment-brainstorm.md) for the staged
architecture, provider boundary, isolation rules, and first implementation
slice.

Sources:

- [OpenAI Codex authentication](https://learn.chatgpt.com/docs/auth)
- [OpenAI Codex CLI](https://learn.chatgpt.com/docs/codex/cli)
- [Codex app-server](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md)
- [Claude Code authentication](https://code.claude.com/docs/en/team)
- [Claude Code programmatic execution](https://code.claude.com/docs/en/headless)
- [Claude Agent SDK hosting](https://code.claude.com/docs/en/agent-sdk/hosting)
- [Claude Agent SDK secure deployment](https://code.claude.com/docs/en/agent-sdk/secure-deployment)
- [Cloud Run overview](https://docs.cloud.google.com/run/docs/overview/what-is-cloud-run)
- [Cloud Run Jobs](https://cloud.google.com/run/docs/create-jobs)
- [Supabase Auth architecture](https://supabase.com/docs/guides/auth/architecture)
- [Supabase Storage access control](https://supabase.com/docs/guides/storage/security/access-control)
