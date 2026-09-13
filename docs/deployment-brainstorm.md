# Deployment and scaling brainstorm

Date: 2026-09-12

## Current state

Jobber is a useful local single-user vertical slice. It has a Python service,
SQLite WAL, filesystem-backed candidate sources, a local read-only web surface,
Hermes over stdio MCP, Browser Use over CDP, and Browserbase session/replay
support. It does not yet have user accounts, workspace membership, tenant
isolation, object storage, a durable task queue, hosted document processing, or a
deployment image.

The current `Path.cwd()` and local candidate paths are good defaults for a
personal tool. They are the first seams to replace before exposing an API to
other people. The local frontend should remain a development and single-user
mode while a hosted control plane is introduced separately.

## Product shape

The cleanest product boundary is a multi-tenant document and agent workspace
with Jobber as its first domain capability:

```text
workspace
  ├─ documents and versions
  ├─ extracted facts, tags, links, and collections
  ├─ provider connections
  ├─ agent runs and approvals
  └─ Jobber jobs, evaluations, and application packets
```

That gives users a reason to bring their own documents even when they are not
running a job application. Resume, portfolio, transcript, project notes,
writing samples, and prior answers become source documents. Jobber consumes
approved facts and stories through the same provenance rules already in the
repository.

The first hosted product should organize and prepare work. External actions,
including a final job application submission, should remain behind an explicit
approval gate.

## Recommended connection model

### 1. Local companion, recommended first

Ship a small `jobber-agent` companion for Windows, macOS, and Linux. The user
installs Codex and/or Claude Code, signs in locally, chooses one or more local
workspace folders, and pairs the companion with the Jobber web account using a
one-time code.

The companion maintains an outbound encrypted connection to Jobber. Jobber
sends a typed task such as `index these selected files`, `extract candidate
facts`, or `prepare this application`. The companion runs the task locally,
streams progress and structured results back, and never sends credentials to
the web service. It should expose only an allowlisted workspace root and a
narrow capability set; it should never accept arbitrary shell commands from a
shared server worker.

This model solves the two hardest problems together:

- Codex and Claude credentials stay in the user’s own CLI environment.
- Documents can remain on the user’s machine unless the user explicitly opts
  into cloud storage or sends a particular document for processing.

The companion protocol should be versioned and provider-neutral. A minimal
interface is:

```text
pair / unpair
workspace capabilities
list selected files (metadata and hashes only)
read selected file
write derived artifact
run structured agent task
stream task event
request user approval
```

Use a short-lived pairing token, rotate the companion session token, show the
connected device in account settings, and provide an immediate revoke button.

### 2. Hosted worker, optional later

For users who want the service to run while their computer is off, provide an
isolated hosted worker. The user supplies an approved provider credential or
connects through a provider-specific OAuth flow; the worker receives a
short-lived scoped credential and runs in an ephemeral sandbox.

Treat this as a separate trust tier. It creates model cost, document privacy,
credential custody, provider terms, and sandboxing obligations. Store secrets
in a KMS-backed secret manager, inject them only into the worker process, and
redact them from logs, traces, prompts, and error reports.

Do not make uploading `~/.codex/auth.json` or Claude credential files part of
the setup flow. OpenAI documents that Codex cached login material can contain
access tokens and should be treated like a password. OpenAI also warns against
exposing Codex execution in untrusted or public environments. Anthropic
documents local credential locations and supports non-interactive `claude -p`
and Agent SDK execution, but its subscription setup token is intended for model
requests and does not establish Remote Control sessions. These details favor a
local companion for subscription logins and an explicit API-key or enterprise
connector for hosted execution.

### 3. Adapter boundary

Keep the existing LLM/browser abstractions and add a provider runner boundary:

```python
class AgentRunner(Protocol):
    async def run(self, task: AgentTask) -> AgentRunResult: ...

class LocalCodexRunner(AgentRunner): ...
class LocalClaudeRunner(AgentRunner): ...
class HostedModelRunner(AgentRunner): ...
```

The local adapters can start with one-shot structured calls. Codex CLI supports
repeatable `codex exec` workflows, and Claude Code supports non-interactive
`claude -p` plus the Agent SDK. For richer streaming and approvals, a local
companion can speak to the local Codex app-server or Claude Agent SDK directly.
Codex app-server’s current WebSocket transport is documented as experimental
and unsupported for production use, so the first companion should own that
connection locally rather than make the hosted API depend on a public app-
server socket.

The Jobber service should request capabilities and structured outputs, not
provider-specific prompts or raw CLI credentials. A user can switch providers
without rewriting the document or application domain.

## Document system

Make the original document immutable and treat every transformation as a
versioned derived artifact:

```text
upload or local discovery
  → MIME/size validation
  → malware scan
  → content hash and deduplication
  → text extraction / OCR
  → classification and metadata
  → chunked retrieval index
  → extracted facts with source spans
  → user review and approval
```

Suggested entities are `workspaces`, `workspace_members`, `documents`,
`document_versions`, `document_artifacts`, `document_tags`, `document_links`,
`processing_runs`, `provider_connections`, and `agent_runs`. Existing
`candidate_sources` can become a compatibility projection over approved
document artifacts instead of remaining the primary storage model.

For cloud storage, keep metadata and permissions in Postgres and originals in
private object storage. Use tenant-scoped object keys and short-lived signed
URLs. Supabase is a reasonable early choice because its Auth issues JWTs and
its database and Storage policies can enforce row and object access with RLS.
S3-compatible storage plus a separate auth provider is equally viable if we
want less coupling later.

Keep the original blob, extracted text, and generated answer separate. Every
candidate claim should retain a document version, source span, extractor run,
and approval state. Treat imported documents as untrusted content that may
contain prompt injection; retrieval must stay within the user’s workspace and
agent tools must not allow document text to rewrite policy.

Do not add a vector database at the first hosted milestone. Start with Postgres
full-text search and metadata filters. Add pgvector only after retrieval
evaluation shows a measurable gap.

## Hosted architecture

```text
browser / companion / optional Telegram adapter
                    │
             Authenticated API
                    │
      ┌─────────────┼─────────────┐
      ▼             ▼             ▼
  Postgres       Object store   Task queue
  + RLS          + signed URLs      │
                                    ▼
                         isolated task workers
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
                 parser     LLM/CLI     browser
                 worker      worker      worker
                                             │
                                          Browserbase
```

A practical first deployment is a containerized API on Cloud Run, managed
Postgres, private object storage, and a managed queue. Cloud Run services are
stateless HTTP endpoints with autoscaling; Cloud Run Jobs handle bounded
batch work, and worker pools support pull-based background work. Set explicit
maximum instances, per-workspace concurrency limits, task deadlines, retries,
and a global kill switch for browser actions. The same application can still
run locally with SQLite and a local filesystem adapter.

A simpler private alpha can use one Dockerized API and a managed Postgres plus
storage provider. Keep the queue and worker interfaces in the code from the
start so moving parsing or browser work to separate workers does not require a
domain rewrite.

## Multi-tenant rules

Every durable row should carry `workspace_id`; every request should resolve an
authenticated user and a workspace membership before entering the service.
Enforce access in both the application service and the database policy layer.
The following must be workspace-scoped:

- documents, extracted facts, resumes, jobs, applications, answers, and events;
- object storage keys and signed URLs;
- provider connections and companion devices;
- browser profiles, sessions, recordings, and replay links;
- quotas, usage meters, and audit records.

Never use a user-provided path as a server filesystem path. A hosted worker gets
one temporary workspace directory, an explicit file manifest, a non-root user,
resource limits, outbound network policy, and destruction on completion.

Do not run one shared Hermes/Telegram identity with all customers’ context.
Hermes can remain the local operator interface for the personal deployment.
For a public product, use web authentication and per-user workspace sessions;
add Telegram as an optional per-user integration after the core isolation
model is working.

## Delivery stages

### Stage 0 — local beta (current)

- Keep SQLite, Markdown/YAML, Browserbase, and the read-only frontend.
- Remove temporary inspection artifacts from release packaging.
- Keep final submission disabled.

### Stage 1 — private hosted alpha

- Add accounts, workspace membership, and a workspace context object.
- Add a Postgres repository while preserving SQLite for local mode.
- Add document upload, immutable versions, extraction status, and deletion.
- Add an authenticated API and move the frontend off the stdlib server.
- Add local companion pairing and a provider connection status screen.

### Stage 2 — reliable background work

- Add idempotent queue jobs for extraction, indexing, evaluation, and answer
  preparation.
- Add leases, retries, dead-letter handling, cancellation, and per-workspace
  budgets.
- Stream run events to the UI and preserve an auditable run timeline.

### Stage 3 — browser execution

- Add a dedicated browser worker with one isolated session per run.
- Store only safe metadata and user-authorized recordings.
- Add site/profile locks, concurrency quotas, human escalation, and replay.
- Keep the final-submit kill switch and approval gate in the service, not in the
  browser prompt.

### Stage 4 — hosted provider execution

- Add explicit API-key or enterprise provider connectors.
- Offer an ephemeral sandbox mode for users who opt into hosted execution.
- Meter model tokens, CPU, OCR, storage, browser time, and recording retention.
- Add regional storage choices, export/delete controls, incident auditing, and
  provider-specific terms review.

## First implementation slice

The next code should not be Kubernetes or a dashboard rewrite. It should be a
small set of seams that preserve the working local system:

1. Add `WorkspaceContext` and pass it through service/repository interfaces.
2. Add storage interfaces for candidate files, documents, and resume artifacts.
3. Add `AgentRunner` and `CompanionTransport` protocols with local test fakes.
4. Add migrations for workspace, document, provider connection, device, and
   run tables while keeping SQLite-compatible local tests.
5. Add a workspace-scoped document ingestion pipeline and provenance links.
6. Add a Dockerfile and a production ASGI API only after the boundaries above
   are tested.

This keeps Jobber’s expected-interviews-per-hour logic intact while making the
document and execution layers reusable for other personal workflows.

## References

- [OpenAI Codex authentication](https://learn.chatgpt.com/docs/auth)
- [OpenAI Codex CLI](https://learn.chatgpt.com/docs/codex/cli)
- [Codex app-server protocol](https://github.com/openai/codex/blob/main/codex-rs/app-server/README.md)
- [Claude Code authentication](https://code.claude.com/docs/en/team)
- [Claude Code programmatic execution](https://code.claude.com/docs/en/headless)
- [Claude Agent SDK hosting](https://code.claude.com/docs/en/agent-sdk/hosting)
- [Claude Agent SDK secure deployment](https://code.claude.com/docs/en/agent-sdk/secure-deployment)
- [Cloud Run overview](https://docs.cloud.google.com/run/docs/overview/what-is-cloud-run)
- [Cloud Run Jobs](https://cloud.google.com/run/docs/create-jobs)
- [Supabase Auth architecture](https://supabase.com/docs/guides/auth/architecture)
- [Supabase Storage access control](https://supabase.com/docs/guides/storage/security/access-control)
