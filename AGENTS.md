# AGENTS.md — Personal SWE Job Application Agent

## Mission

Build a personal SWE job-application system that optimizes for **expected interviews per hour**, not applications per hour.

The system should:

1. Discover and ingest SWE internship / new-grad jobs.
2. Decide whether each job is worth applying to.
3. Classify jobs by application importance.
4. Prepare high-value applications for the user to complete manually.
5. Autonomously complete lower-priority applications with a browser agent.
6. Never invent facts about the user.
7. Learn from the user's edits and application decisions over time.

This is a **personal career operating system**, not a mass-spam bot.

---

## Important local environment note

**Hermes is already installed on this computer.**

Before installing Hermes, cloning another Hermes repo, or creating a substitute orchestration layer:

- inspect the existing installation;
- determine how it is configured;
- find its available CLI, config, skills, MCP, browser, Telegram, scheduling, and tool interfaces;
- reuse it where appropriate.

Do not create a parallel agent framework unless the current Hermes installation genuinely cannot support the needed functionality.

---

## Research rule

When you encounter something you do not understand, something whose API/version may have changed, or a design choice that depends on current software behavior:

**Do deep web research before implementing it.**

Examples:

- current Hermes browser/tool interfaces;
- Browser Use APIs;
- Browserbase session/context APIs;
- Browserbase + Browser Use CDP integration;
- current Stagehand/Steel alternatives;
- Obsidian MCP / Local REST integration;
- ATS public job feeds;
- Workday / Greenhouse / Lever / Ashby application behavior;
- LLM structured-output APIs;
- current model/tool support.

Prefer:

1. official documentation;
2. current GitHub repositories;
3. first-party examples;
4. recent technical writeups.

Do not rely on stale blog posts or remembered APIs when implementation details matter.

If research changes an assumption in these specs, update the docs in this repo and proceed with the better design.

---

## Core architecture

Use this mental model:

```text
                         USER
                          │
                  Telegram / CLI
                          │
                          ▼
                       HERMES
                conversational control
                          │
                          ▼
                 OUR APPLICATION SERVICE
                       Python
                          │
          ┌───────────────┼────────────────┐
          │               │                │
          ▼               ▼                ▼
   Candidate Brain   Application DB    Job Discovery
          │               │                │
   Markdown/YAML       SQLite WAL       ATS feeds
          │
          ▼
   Application Planner
          │
          ├─ eligibility
          ├─ fit + importance scoring
          ├─ evidence matrix
          ├─ resume selection
          ├─ answer retrieval/generation
          └─ quality gates
                          │
                          ▼
                   Browser Worker
                          │
                     Browser Use
                          │ CDP
                          ▼
                     Browserbase
                          │
                          ▼
             Greenhouse / Lever / Ashby /
                Workday / custom portals
```

---

## Architectural principles

### 1. Own intelligence, rent infrastructure

We should own:

- candidate knowledge representation;
- truth/grounding rules;
- job evaluation;
- application tiers;
- resume selection/tailoring;
- answer generation;
- quality control;
- learning from edits;
- application state.

We should initially rent/reuse:

- cloud browser infrastructure;
- browser session persistence;
- CAPTCHA/browser fleet infrastructure;
- agent runtime;
- messaging.

Browserbase should be treated as replaceable infrastructure behind a small provider abstraction.

---

### 2. Agentic applying, deterministic discovery

**Discovery is a data problem.**
Use APIs, feeds, repositories, and lightweight scraping whenever possible.

**Applying is an agent problem.**
Do not build a giant ATS-specific selector tree.

The browser agent should receive goals and candidate tools, then understand and operate the current webpage.

Deterministic Playwright/CDP helpers are fine as primitives, but not as the application logic.

---

### 3. Facts are deterministic; stories are retrievable

Hard facts must come from structured data.

Examples:

- name;
- email;
- phone;
- school;
- degree;
- graduation date;
- work authorization;
- locations;
- links;
- GPA if supplied;
- legal/application declarations.

Never infer these from prose.

Soft knowledge can come from Markdown/Obsidian:

- projects;
- experiences;
- stories;
- accomplishments;
- past answers;
- writing preferences;
- company notes.

---

### 4. No hallucinated candidate claims

Generation may:

- select;
- summarize;
- reorder;
- shorten;
- expand;
- connect facts;
- adapt wording.

Generation may not:

- invent technologies;
- invent metrics;
- upgrade responsibilities;
- change dates;
- manufacture impact;
- guess work authorization;
- guess demographic answers;
- claim enthusiasm or motivations unsupported by user context.

Every factual claim about the candidate should be traceable to a stored source.

---

### 5. Human effort goes where expected value is highest

Applications have three tiers.

#### Tier A — manual application by user

Examples include:

- companies the user is genuinely excited about;
- major career-step opportunities;
- unusually strong fits;
- top-tier companies such as Stripe, Ramp, Shopify, Google;
- companies where the user has a referral/recruiter connection;
- smaller companies with exceptional learning/upside.

The agent prepares everything but does not replace the user's application process.

#### Tier B — agent applies, optional review

Solid companies and good roles where the user would gladly interview but does not want to spend much time on the application.

#### Tier C — autonomous application

Good-enough opportunities with low-risk, well-understood forms.

Initial system should still stop before final submission until quality is proven.

---

## Initial safety/autonomy policy

V1 may autonomously:

- discover;
- score;
- classify;
- prepare;
- open pages;
- navigate;
- fill known factual fields;
- upload known files;
- draft answers;
- save application state.

V1 must escalate:

- unknown personal facts;
- ambiguous work authorization;
- demographic/EEO questions unless explicit policy exists;
- salary/legal declarations if not explicitly known;
- novel answers that fail quality/grounding thresholds;
- final submission.

Do **not** enable blanket auto-submit in V1.

---

## Engineering style

- Prefer small modules with typed interfaces.
- Use Pydantic models for domain objects.
- Use SQLite initially.
- Use migrations from day one.
- Keep the browser provider swappable.
- Keep the LLM provider swappable.
- Avoid unnecessary microservices.
- Avoid adding Redis/Postgres/vector DB until there is an actual need.
- Avoid dashboards initially; Telegram/CLI + logs are sufficient.
- Add tests around business logic and truth/grounding rules before UI work.

## Autonomous engineering loop

For sustained work, follow `docs/agent-loop.md` and append outcomes to
`docs/iteration-log.md`. Begin each loop by reading the relevant instructions,
reproducing the issue, and stating a concrete hypothesis. Make the smallest
reversible change, add a meaningful regression test for safety-critical
behavior, run the appropriate validation, inspect the diff, and record the
result. Continue through routine implementation and testing without pausing
for trivial confirmation. Keep final submission disabled throughout.

---

## First action

Before coding:

1. inspect the current machine;
2. locate Hermes;
3. inspect Hermes configuration and installed skills;
4. verify Python/Node tooling;
5. research the current APIs for Browser Use and Browserbase;
6. create `docs/research-notes.md` with findings and links;
7. update implementation assumptions if needed;
8. then begin Phase 1 from `ROADMAP.md`.

Do not spend the first day building browser automation.

Start with the candidate brain, schemas, DB, planner, and tests.
