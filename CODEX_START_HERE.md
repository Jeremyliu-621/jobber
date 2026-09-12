# Codex — Start Here

You are taking over implementation of this project.

Read, in order:

1. `AGENTS.md`
2. `README.md`
3. `ARCHITECTURE.md`
4. `DATA_MODEL.md`
5. `QUALITY_AND_SAFETY.md`
6. `BROWSER_AGENT.md`
7. `ROADMAP.md`

## Immediate task

Perform **Phase 0 and Phase 1**.

Do not jump straight into browser automation.

### Phase 0

Inspect this machine and determine:

- where Hermes is installed;
- how Hermes is invoked;
- its version;
- its current configuration;
- available skills/tools;
- whether Telegram is configured;
- whether Browser Use integration already exists;
- whether Browserbase support already exists;
- what can be reused directly.

Then perform deep web research using current first-party sources for anything unclear or version-sensitive.

At minimum research:

- Hermes current docs/source;
- Browser Use current docs/source;
- Browserbase current docs;
- Browser Use + Browserbase integration over CDP;
- Browserbase persistent contexts/profiles;
- current open-source Browserbase alternatives such as Steel;
- current ATS public job-posting APIs.

Create:

```text
docs/research-notes.md
```

with:

- source links;
- important API facts;
- version information where relevant;
- implications for our architecture;
- any corrections to the provided specs.

If a provided assumption is wrong, update the spec instead of blindly implementing it.

### Phase 1

Create the Python project and implement:

- Pydantic domain models;
- SQLite database;
- migrations;
- candidate profile schema;
- Markdown/frontmatter candidate indexing;
- simple candidate search;
- candidate fact retrieval;
- CLI;
- tests.

Create sensible placeholder candidate files but **do not invent personal data**.

Unknown facts must remain empty/null and fail safely.

## Technology preferences

Prefer:

- modern Python;
- `uv` if appropriate;
- Pydantic;
- SQLAlchemy or a similarly boring DB layer;
- Alembic or equivalent migrations;
- Typer for CLI if appropriate;
- pytest;
- Ruff;
- mypy/pyright if useful.

These are preferences, not hard constraints. Research and choose better alternatives if justified.

## Implementation behavior

Work autonomously.

Do not ask trivial architecture questions that are already answered in the specs.

When something is unknown:

```text
inspect local system
→ inspect source/docs
→ deep research
→ make a documented decision
→ implement
```

Only stop for user input when the missing information is genuinely personal or changes product intent.

## Definition of done for first pass

The project should support something like:

```bash
job-agent candidate validate
job-agent candidate fact education.0.institution
job-agent candidate search "leadership"
job-agent db status
pytest
```

and have enough structure that Phase 2 can be implemented without rewriting Phase 1.

At the end, summarize:

- what you discovered about the local Hermes install;
- architecture changes made;
- files created;
- tests run;
- what Phase 2 should implement next.
