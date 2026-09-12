# Initial stack and integration decisions

Date: 2026-09-09

## Decision

Build the first useful version as a single Python package with Pydantic domain models, the standard-library SQLite driver, SQL migrations, YAML structured facts, Markdown candidate knowledge, and a Typer CLI.

Integrate with the installed Hermes Agent through a local stdio MCP server. Keep the application service independent from Hermes so the CLI, tests, and later Telegram workflow use the same domain operations.

Keep browser execution behind a provider interface. The first real provider can use Browserbase to create a session and return its CDP connection URL, with Browser Use attaching to that URL. Browserbase Contexts are modeled as site-specific browser identities, with one active session per authenticated context by default.

Start discovery with public Greenhouse, Lever, and Ashby job feeds. Treat Workday as a tenant-specific adapter that requires additional investigation rather than assuming a single global public endpoint.

## Rationale

Hermes already supports local stdio and remote HTTP MCP servers, automatic tool discovery, and per-server tool filtering. A local MCP boundary matches the architecture's narrow domain-tool goal without coupling business logic to Hermes internals.

Current Browser Use documentation exposes cloud browser sessions and persistent profiles, while Browserbase exposes sessions, CDP connection URLs, and encrypted persistent Contexts. The official Browserbase integration documentation shows Browser Use consuming a Browserbase-created CDP URL. This preserves the repository's “agentic applying, deterministic discovery” split.

SQLite through Python's built-in driver keeps the first phase boring and portable. Pydantic validates the domain boundary, while migrations create the full application schema before later phases need it.

## Consequences

- The Windows checkout remains the source tree, while Hermes runs in WSL2. The later MCP command must be executable from WSL and point at the checkout through `/mnt/c/...`.
- The local runtime stores Browserbase credentials only in an ignored `.env`; the provider is optional for evaluation and packet preparation.
- Candidate facts remain usable without an LLM or browser provider.
- The database stores candidate-source content for deterministic search and provenance. It is an index of user-owned files, not a replacement for those files.
- Hermes is registered against the Windows virtual environment through `cmd.exe`, because the existing Hermes gateway runs in WSL2.

## Sources

- [Hermes Agent documentation](https://hermes-agent.nousresearch.com/docs/)
- [Hermes Agent MCP documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp/)
- [Hermes Agent source repository](https://github.com/NousResearch/hermes-agent)
- [Browser Use create-browser-session API](https://docs.browser-use.com/cloud/api-v3/browsers/create-browser-session)
- [Browser Use profiles](https://docs.browser-use.com/cloud/guides/authentication)
- [Browserbase sessions API](https://docs.browserbase.com/reference/api/create-a-session)
- [Browserbase Contexts](https://docs.browserbase.com/platform/browser/core-features/contexts)
- [Browserbase Browser Use integration](https://docs.browserbase.com/integrations/browseruse/python)
- [Steel documentation](https://docs.steel.dev/)
- [Steel open-source repository](https://github.com/steel-dev/steel-browser)
- [Greenhouse Job Board API](https://docs.greenhouse.io/job-board.html)
- [Lever Developer documentation](https://hire.lever.co/developer/documentation)
- [Ashby public job posting API](https://developers.ashbyhq.com/docs/public-job-posting-api)
- [Workday job postings metadata API](https://developer.workday.com/documentation/pyd1580334491723/)
