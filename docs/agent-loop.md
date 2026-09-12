# Autonomous engineering loop

This repository is improved through short, reviewable loops. The target is a
more reliable application preparation system, measured by grounded results and
useful human review, not by the number of files changed.

## Loop

1. Read `AGENTS.md`, the relevant specification, and the latest entry in
   `docs/iteration-log.md`.
2. Establish a baseline with the smallest relevant test or command. Record the
   observed failure, missing behavior, or uncertainty.
3. Form one concrete hypothesis about the cause. Prefer a reversible change in
   one module.
4. Implement the smallest change that tests the hypothesis. Keep candidate
   facts and product policy separate from generated prose.
5. Add a meaningful regression test when the behavior is safety critical or
   likely to regress. Avoid tests that only mirror implementation details.
6. Run focused validation first, then the full suite and static checks when the
   change affects shared behavior.
7. Inspect the resulting diff and runtime output. Check that no secret,
   unsupported candidate claim, or submission action was introduced.
8. Record the result, evidence, and next useful experiment in the iteration
   log.

## Application-system invariants

- Final submission is disabled. A browser run may prepare a form and stop for
  review, but it must never click a final submit control.
- Unknown candidate facts remain unknown and cause escalation where needed.
- Only approved candidate sources support application claims.
- A browser packet needs a real local resume artifact and a rendered PDF before
  it can pass the quality gate.
- External job discovery is deterministic and read-only until a user chooses to
  prepare an application.
- Changes to hard candidate facts require explicit user supplied evidence.

## Completion criteria

An iteration is complete when the observed issue has a clear result, the
relevant tests pass, the safety boundary remains intact, and the next action is
known. If the same external blocker repeats across three loops, record it as a
blocker rather than hiding it behind a weaker check.
