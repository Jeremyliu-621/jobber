# Personal SWE Application Agent

A personal AI system for discovering, evaluating, preparing, and eventually completing SWE job applications.

The objective is not to maximize the number of applications sent.

The objective is:

> **Maximize expected interviews and career upside per unit of human attention.**

## What makes this different

Most auto-apply products optimize:

```text
jobs found
→ forms filled
→ applications submitted
```

This system optimizes:

```text
jobs found
→ eligibility
→ opportunity quality
→ fit
→ candidate evidence
→ application importance
→ tailored materials
→ quality-controlled application
→ submission
→ learning loop
```

## Product behavior

A job should end in one of four outcomes:

```text
SKIP
TIER A — user applies manually
TIER B — agent prepares/applies with review
TIER C — agent can eventually submit autonomously
```

Tier A is not equivalent to "famous company." It means **high expected career value or personal importance**.

## V1 experience

Example:

```text
USER:
apply https://jobs.example.com/123

SYSTEM:
Stripe — Software Engineer Intern

Fit: 94/100
Importance: 97/100
Tier: A — manual application recommended

Why:
- exceptional career upside
- strong backend/AI fit
- user has explicitly high interest in Stripe

Strong evidence:
- Python backend work
- AWS
- PostgreSQL
- AI agent work

Potential gaps:
- no strong distributed systems evidence

Recommended resume:
swe-backend.pdf

I prepared:
- application rubric
- resume recommendation
- two answer drafts
- possible referral targets

Open application?
```

For a Tier C role:

```text
SYSTEM:
Acme SaaS — SWE Intern
Fit: 79/100
Importance: 66/100
Tier: C

Application prepared.
All candidate claims grounded.
No novel personal questions.
Ready for review/submission.
```

## Stack

Initial preferred stack:

| Layer | Technology |
|---|---|
| High-level orchestration | Hermes |
| Mobile interface | Telegram through Hermes |
| Backend | Python |
| Domain models | Pydantic |
| State | SQLite WAL |
| Browser intelligence | Browser Use |
| Cloud browser fleet | Browserbase |
| Browser protocol | CDP |
| Human-readable brain | Markdown / Obsidian |
| Hard candidate facts | YAML |
| Resume source | structured Markdown/YAML |
| Resume rendering | Typst or another reproducible template system |
| Job discovery | ATS APIs + feeds + targeted scraping |
| Later semantic retrieval | optional embeddings |

## Repo target

```text
job-agent/
├── AGENTS.md
├── README.md
├── docs/
│   ├── research-notes.md
│   └── decisions/
├── candidate/
│   ├── profile.yaml
│   ├── preferences.yaml
│   ├── style.md
│   ├── experiences/
│   ├── projects/
│   ├── stories/
│   ├── answers/
│   └── resumes/
├── src/
│   └── job_agent/
│       ├── models/
│       ├── db/
│       ├── discovery/
│       ├── planner/
│       ├── candidate/
│       ├── quality/
│       ├── browser/
│       ├── llm/
│       └── interfaces/
├── tests/
├── scripts/
└── data/
```

See the other specification files for details.

## Phase 1 quickstart

Create the isolated environment and install the package with its development
tools:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

The initial candidate brain is intentionally empty. Unknown facts remain
`null` or empty until supplied by the user.

## Local setup for another user

Each person can use a separate local workspace without a hosted account or
shared database. From a checkout of this repository, run the installer for the
platform:

```powershell
.\scripts\install.ps1
```

```bash
bash ./scripts/install.sh
```

The installer creates a workspace under `~/Jobber` (or `$HOME/Jobber`), selects
it in per-user config, and leaves the starter profile blank. To choose another
folder, pass it as the first argument to either installer. The user can also
run `job-agent init PATH` directly.

Add documents to `documents/inbox` or import them explicitly:

```powershell
.\.venv\Scripts\job-agent.exe documents import C:\path\to\resume.pdf
.\.venv\Scripts\job-agent.exe documents list
```

The document inventory stays local, records file hashes and metadata, and does
not upload content. Supported files can later be organized or sent to a local
agent task by explicit user action.

Local Codex and Claude connections use the CLI already installed and
authenticated on the user's machine:

```powershell
.\.venv\Scripts\job-agent.exe agent check
.\.venv\Scripts\job-agent.exe config provider codex
.\.venv\Scripts\job-agent.exe agent run "Summarize the approved project notes"
```

The adapter invokes `codex exec --ephemeral --json` or Claude Code's
non-interactive `--bare -p` mode without a shell and without reading or storing
provider credential files. Browser tasks still require the existing local
Browserbase and Browser Use configuration.

```powershell
.\.venv\Scripts\job-agent.exe candidate validate
.\.venv\Scripts\job-agent.exe candidate fact education.0.institution
.\.venv\Scripts\job-agent.exe candidate search "leadership"
.\.venv\Scripts\job-agent.exe db status
.\.venv\Scripts\python.exe -m pytest
```

Open the local research desk:

```powershell
.\.venv\Scripts\job-agent.exe web
```

Then open `http://127.0.0.1:8765`. The frontend is read-only and uses the same
SQLite state as the CLI and Hermes MCP server. Open any opportunity to see its
current browser state; active sessions show live view, and recorded tabs can be
played as replays when Browserbase has finalized them.

### Local Browserbase configuration

Browserbase credentials stay in the ignored local `.env` file. Copy the example
and fill in the values from the Browserbase dashboard:

```powershell
Copy-Item .env.example .env
\.venv\Scripts\job-agent.exe config check
```

The configuration check only prints a masked key marker and never prints the
secret itself. Browser sessions are not created by this check.

## Implemented workflow

The current vertical slice supports deterministic ATS discovery, job scoring,
reviewable application packets, Browserbase session lifecycle, and Hermes MCP
control:

```powershell
# Discover a public board
.\.venv\Scripts\job-agent.exe job discover greenhouse BOARD_TOKEN

# Fetch current SimplifyJobs internship postings for Toronto
.\.venv\Scripts\job-agent.exe job discover-simplifyjobs --role internship --timeframe lastweek --location Toronto
# `discover-swelist` remains available as a compatibility alias

# Inspect and evaluate stored jobs
.\.venv\Scripts\job-agent.exe job list
.\.venv\Scripts\job-agent.exe job extract-opportunities
.\.venv\Scripts\job-agent.exe job evaluate JOB_ID

# Register an approved resume and prepare a packet
.\.venv\Scripts\job-agent.exe resume add swe-backend "Backend resume" candidate/resumes/backend.pdf --base-type python+sql
.\.venv\Scripts\job-agent.exe application prepare JOB_ID

# Record a human answer and inspect learning signals
.\.venv\Scripts\job-agent.exe application answer APPLICATION_ID "Why this company?" "User-provided answer"
.\.venv\Scripts\job-agent.exe learning feedback answer ANSWER_ID "Draft" "Human edit" minor_edit
.\.venv\Scripts\job-agent.exe learning report

# Inspect a running session or open its completed replay in Browserbase
.\.venv\Scripts\job-agent.exe application browser-links APPLICATION_ID

# Run the model-backed browser agent from an interactive terminal
.\.venv\Scripts\job-agent.exe application run APPLICATION_ID
```

The SimplifyJobs integration reads the same public JSON feeds used by the
`swelist` CLI and stores the results in this app's jobs database. It keeps
the feed's source metadata and stable posting IDs, while avoiding a dependency
on Swelist's human-formatted terminal output. Swelist postings are useful for
discovery and triage; many entries do not include a job description, so a
deeper evaluation may need the linked ATS page or a company-board adapter.

Each normalized job also receives a source-grounded opportunity document before
it reaches the frontend. The extractor preserves headings, paragraphs, and
lists from source HTML in a versioned SQLite record; the flattened description
field remains only for search and compatibility. Use `job extract-opportunities`
to backfill or rebuild these documents after an extractor update.

The local stdio MCP entry point is `job-agent-mcp`. Hermes is configured to
launch it through the Windows virtual environment and has tools for discovery,
evaluation, packet preparation, candidate retrieval, application state,
opportunity extraction, candidate retrieval, application state, human answers,
approvals, feedback capture, and learning reports. Approval records remain
non-submitting; the browser worker always stops before the final submit action.

`application browser-links` and the MCP `get_browser_session_links` tool keep
the Browserbase API key on the server side. They return a live debugger URL when
the session is active, the Browserbase Session Inspector URL for replay, and
recorded tab metadata. Live debugger URLs are not persisted in the event log.
The provider also exposes the HLS playlist method for a future embedded player
without making signed playlist URLs permanent.

To enable the optional Browser Use runner after supplying the model provider
configuration, install the browser extra:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,browser]"
```

Set `BROWSER_USE_API_KEY` in `.env` to enable the default `ChatBrowserUse`
model-backed runner. `BROWSER_USE_MODEL` defaults to `bu-2-0`. The agent can
reason over different form layouts and use the registered candidate and human
escalation tools; final application submission remains disabled.

Candidate Markdown files use YAML frontmatter with stable IDs. For example:

```markdown
---
id: story.example
type: story
topics: [leadership]
approved: true
source: user-authored
---

User-authored evidence goes here.
```
