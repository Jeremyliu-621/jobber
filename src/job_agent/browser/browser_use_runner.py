"""Optional Browser Use adapter for a Browserbase CDP session."""

from __future__ import annotations

from typing import Any


class BrowserUseRunner:
    """Attach Browser Use to a provider-neutral CDP URL.

    Browser Use remains optional because evaluation and packet preparation do
    not require a model key. Install the browser extra and inject an LLM object
    when enabling this runner in a worker process.
    """

    def __init__(self, llm: Any) -> None:
        self.llm = llm

    async def run(
        self,
        *,
        task: str,
        cdp_url: str,
        max_steps: int,
        available_file_paths: list[str] | None = None,
    ) -> str:
        try:
            from browser_use import Agent, Browser  # type: ignore[import-not-found]
        except ImportError as error:  # pragma: no cover - optional runtime path
            raise RuntimeError(
                "Browser Use is not installed; install the browser extra before running a worker."
            ) from error

        browser_class: Any = Browser
        browser = browser_class(cdp_url=cdp_url, is_local=False, keep_alive=False)
        try:
            # Browser Use is an optional, dynamically imported dependency whose
            # public agent type varies across supported releases.
            agent: Any = Agent(
                task=task,
                llm=self.llm,
                browser=browser,
                available_file_paths=available_file_paths or [],
            )
            history = await agent.run(max_steps=max_steps)
            return _history_summary(history)
        finally:
            stop = getattr(browser, "stop", None)
            if stop:
                await stop()


def _history_summary(history: Any) -> str:
    """Return a bounded summary without persisting model traces or secrets."""

    if hasattr(history, "final_result"):
        result = history.final_result()
        return str(result)[:1000] if result else "Browser Use completed without a final result."
    return "Browser Use completed; inspect the Browserbase session for details."
