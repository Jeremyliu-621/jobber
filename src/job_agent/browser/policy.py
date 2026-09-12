"""Browser worker policy and task prompt construction."""

from __future__ import annotations

from job_agent.models import ApplicationPlan

APPLICATION_BROWSER_POLICY = """You are completing a job application for the candidate.

Rules:
1. Use only verified candidate facts returned by candidate tools.
2. Never fabricate technologies, dates, metrics, responsibilities, or motivation.
3. If a factual answer is unknown, stop and request the specific fact from the user.
4. Never guess work authorization, demographic/EEO answers, salary, or legal attestations.
5. Use the selected resume exactly and stop if it is unavailable.
   If a page has multiple file inputs, use the required application resume
   field (usually named or identified as `resume` or `_systemfield_resume`),
   and do not use an optional "Autofill from resume" widget unless no required
   resume field exists.
6. You may navigate and fill known fields, but never click a final submit button.
7. Escalate CAPTCHA, human verification, blocked automation, MFA, and ambiguous questions.
8. Record every question, answer, escalation, and page transition.
"""


def build_browser_task(plan: ApplicationPlan, *, apply_url: str) -> str:
    """Build a short goal for Browser Use without embedding the candidate profile."""

    return "\n".join(
        [
            APPLICATION_BROWSER_POLICY,
            "",
            f"Application ID: {plan.application_id}",
            f"Open this application URL: {apply_url}",
            f"Application tier: {plan.importance.tier}",
            f"Resume ID: {plan.resume.resume_id if plan.resume else 'NONE - stop before upload'}",
            "Prepare the application and stop before final submission.",
        ]
    )
