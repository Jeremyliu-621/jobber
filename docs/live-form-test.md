# Live form test — 2026-09-12

These tests used isolated Browserbase sessions against public application pages.
They filled verified candidate fields and uploaded the registered rendered
resume. No final submit control was clicked, and each session was released.

| ATS | Role | Application URL | Result |
| --- | --- | --- | --- |
| Lever | SoloPulse — Software Engineer Intern/Co-op, Fall 2026 | https://jobs.lever.co/solopulseco/00fbde18-a387-4c9f-97d4-77059aec7b56/apply | Resume, name, email, phone, LinkedIn, and GitHub accepted; stopped before submission |
| Ashby | Notion — Software Engineer Intern, Summer 2027 | https://jobs.ashbyhq.com/notion/3fba1c39-c5cb-47d7-9ad2-1cec4d7e9d0c/application | Required `_systemfield_resume` accepted the resume and verified fields; stopped before submission |
| Ashby | Super.com — Software Engineering Intern, Platform, 12 months | https://jobs.ashbyhq.com/super.com/29751d58-eacc-4b5a-8e9d-e59cb7a595c7/application | Required form reached and accepted verified name, email, phone, and resume; stopped before submission |

The optional Ashby “Autofill from resume” widget produced “Oops! Failed to
fetch” when deliberately selected. The required application resume input worked,
so the browser policy now prefers the required input when both are present.

The planner still escalates these live jobs before worker execution because
work authorization is unknown for the relevant country, or because the
importance tier is below the configured threshold. This prevents a live worker
from starting without a user-supplied hard fact.
