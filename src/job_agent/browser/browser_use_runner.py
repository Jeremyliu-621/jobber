"""Optional Browser Use adapter for a Browserbase CDP session."""

from __future__ import annotations

import inspect
import json
from typing import Any

from .base import (
    HumanEscalationHandler,
    HumanEscalationRequired,
    HumanQuestion,
)


class BrowserUseRunner:
    """Attach Browser Use to a provider-neutral CDP URL.

    Browser Use remains optional because evaluation and packet preparation do
    not require a model key. Install the browser extra and inject an LLM object
    when enabling this runner in a worker process.
    """

    def __init__(
        self,
        llm: Any,
        *,
        human_escalation: HumanEscalationHandler | None = None,
        candidate_fact_lookup: Any | None = None,
        candidate_knowledge_search: Any | None = None,
        application_answer_lookup: Any | None = None,
    ) -> None:
        self.llm = llm
        self.human_escalation = human_escalation
        self.candidate_fact_lookup = candidate_fact_lookup
        self.candidate_knowledge_search = candidate_knowledge_search
        self.application_answer_lookup = application_answer_lookup

    async def run(
        self,
        *,
        task: str,
        cdp_url: str,
        max_steps: int,
        available_file_paths: list[str] | None = None,
        application_id: str | None = None,
        human_escalation: HumanEscalationHandler | None = None,
    ) -> str:
        try:
            from browser_use import (  # type: ignore[import-not-found]
                ActionResult,
                Agent,
                Browser,
                Tools,
            )
        except ImportError as error:  # pragma: no cover - optional runtime path
            raise RuntimeError(
                "Browser Use is not installed; install the browser extra before running a worker."
            ) from error

        browser_class: Any = Browser
        browser = browser_class(cdp_url=cdp_url, is_local=False, keep_alive=False)
        pending_question: HumanQuestion | None = None
        tools: Any = Tools()
        answer_handler = human_escalation or self.human_escalation

        @tools.action(
            "Ask the candidate for a missing or ambiguous application answer. "
            "Use this instead of guessing any personal, legal, demographic, or factual answer."
        )
        async def ask_user(
            question: str,
            context: str = "",
            allowed_options: list[str] | None = None,
        ) -> Any:
            nonlocal pending_question
            human_question = HumanQuestion(
                application_id=application_id,
                question=question,
                context=context,
                allowed_options=tuple(allowed_options or ()),
            )
            if answer_handler is None:
                pending_question = human_question
                return ActionResult(
                    is_done=True,
                    success=False,
                    extracted_content=(
                        "No human answer is connected. Stop the application and report "
                        "the exact question for human review."
                    ),
                )
            answer = answer_handler(human_question)
            if inspect.isawaitable(answer):
                answer = await answer
            if answer is None or not str(answer).strip():
                pending_question = human_question
                return ActionResult(
                    is_done=True,
                    success=False,
                    extracted_content=(
                        "The human did not provide an answer. Stop and leave the form "
                        "unsubmitted."
                    ),
                )
            return ActionResult(
                extracted_content=f"Human answer (use exactly as provided): {answer}"
            )

        @tools.action(
            "Retrieve one verified structured candidate fact by its dotted path. "
            "Unknown facts must remain unknown."
        )
        async def get_candidate_fact(path: str) -> Any:
            if self.candidate_fact_lookup is None:
                return ActionResult(
                    error="Candidate fact lookup is unavailable; ask the human instead of guessing."
                )
            result = self.candidate_fact_lookup(path)
            if inspect.isawaitable(result):
                result = await result
            if result is None:
                return ActionResult(
                    extracted_content=(
                        f"No verified candidate fact exists at {path}. "
                        "Do not guess it; ask the human."
                    )
                )
            return ActionResult(extracted_content=_json_text(result))

        @tools.action(
            "Search approved candidate projects, experiences, stories, and answers "
            "for evidence relevant to an application question."
        )
        async def search_candidate_knowledge(query: str, top_k: int = 5) -> Any:
            if self.candidate_knowledge_search is None:
                return ActionResult(
                    error=(
                        "Candidate knowledge search is unavailable; ask the human "
                        "instead of inventing evidence."
                    )
                )
            result = self.candidate_knowledge_search(query, top_k)
            if inspect.isawaitable(result):
                result = await result
            return ActionResult(extracted_content=_json_text(result))

        @tools.action(
            "Retrieve answers the human already supplied for this application. "
            "Use an existing exact answer before asking the same question again."
        )
        async def get_previous_application_answers() -> Any:
            if self.application_answer_lookup is None or application_id is None:
                return ActionResult(extracted_content="No previous human answers are recorded.")
            result = self.application_answer_lookup(application_id)
            if inspect.isawaitable(result):
                result = await result
            return ActionResult(extracted_content=_json_text(result))

        try:
            # Browser Use is an optional, dynamically imported dependency whose
            # public agent type varies across supported releases.
            agent: Any = Agent(
                task=task,
                llm=self.llm,
                browser=browser,
                tools=tools,
                available_file_paths=available_file_paths or [],
            )
            history = await agent.run(max_steps=max_steps)
            if pending_question is not None:
                raise HumanEscalationRequired(pending_question)
            return _history_summary(history)
        finally:
            stop = getattr(browser, "stop", None)
            if stop:
                await stop()


def _history_summary(history: Any) -> str:
    """Return a bounded summary without persisting model traces or secrets."""

    if not hasattr(history, "final_result"):
        raise RuntimeError("Browser Use did not return a verifiable run history.")
    result = history.final_result()
    if not result:
        raise RuntimeError("Browser Use did not produce a final result.")
    return str(result)[:1000]


def _json_text(value: Any) -> str:
    """Serialize tool data without failing the agent on an unexpected object."""

    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)
