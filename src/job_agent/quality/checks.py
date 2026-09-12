"""Conservative deterministic checks used before any browser filling."""

from __future__ import annotations

import re
from collections.abc import Iterable

from job_agent.db import CandidateSource
from job_agent.models import QualityReport

SLOP_PATTERNS = {
    "generic enthusiasm": r"\bthrilled|incredibly passionate|excited to apply\b",
    "empty adjectives": r"\binnovative and cutting-edge|diverse skill set|aligns perfectly\b",
    "homepage restatement": r"\bmission|world-class|industry-leading\b",
    "corporate filler": r"\bleverage(?:d)?|synerg(?:y|ize)|robust solution\b",
}


def inspect_answer(
    text: str,
    sources: Iterable[CandidateSource],
    *,
    require_company_specific: bool = False,
    company: str | None = None,
) -> QualityReport:
    """Check a draft against retrieved candidate sources.

    This is intentionally conservative: unsupported sentences fail the gate and
    are surfaced for a human instead of being silently rewritten.
    """

    source_list = list(sources)
    source_text = " ".join(f"{source.title} {source.content}" for source in source_list).casefold()
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text.strip())
        if sentence.strip()
    ]
    unsupported: list[str] = []
    for sentence in sentences:
        tokens = _meaningful_tokens(sentence)
        if tokens and not _sentence_supported(tokens, source_text):
            unsupported.append(sentence)

    slop_flags = [
        name for name, pattern in SLOP_PATTERNS.items() if re.search(pattern, text.casefold())
    ]
    notes: list[str] = []
    if require_company_specific and company and company.casefold() not in text.casefold():
        notes.append("Company-specific answers must name the company or a verified company detail.")
    if not source_list:
        notes.append("No approved candidate sources were retrieved for this answer.")
    if not text.strip():
        notes.append("Answer is empty.")
    if unsupported:
        notes.append("Every factual sentence must be supported by an approved candidate source.")

    grounding_score = 1.0 if not sentences else max(0.0, 1 - len(unsupported) / len(sentences))
    style_score = max(0.0, 1 - min(len(slop_flags), 4) * 0.2)
    company_ok = not require_company_specific or bool(
        company and company.casefold() in text.casefold()
    )
    passed = (
        bool(text.strip())
        and not unsupported
        and not slop_flags
        and company_ok
        and bool(source_list)
    )
    return QualityReport(
        passed=passed,
        grounding_score=grounding_score,
        style_score=style_score,
        unsupported_claims=unsupported,
        slop_flags=slop_flags,
        notes=notes,
    )


def _meaningful_tokens(text: str) -> set[str]:
    stop_words = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "i",
        "in",
        "is",
        "it",
        "my",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "with",
        "we",
        "you",
        "your",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9+.#-]*", text.casefold())
        if token not in stop_words and len(token) > 2
    }


def _sentence_supported(tokens: set[str], source_text: str) -> bool:
    if not source_text:
        return False
    # Numbers and percentages are high-risk candidate claims. A sentence that
    # borrows several ordinary words from a source must still fail if it adds a
    # new metric.
    # Compare numeric tokens from the sentence directly against the retrieved
    # source text. This keeps invented scale and impact claims from hiding
    # behind otherwise similar wording.
    sentence_numbers = re.findall(r"\b\d+(?:[,.]\d+)*%?\b", " ".join(tokens))
    if sentence_numbers:
        return all(number in source_text for number in sentence_numbers)
    supported = sum(1 for token in tokens if token in source_text)
    return supported / len(tokens) >= 0.6
