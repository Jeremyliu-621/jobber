"""Extract source-grounded opportunity sections before presentation."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Literal

from job_agent.models import Job, OpportunityDocument, OpportunitySection

EXTRACTOR_VERSION = "structure-v1"

_HEADING_RE = re.compile(
    r"\b(Who We Are|About Us|About the Role|About this role|"
    r"What You'll Achieve|What You’ll Achieve|"
    r"What You'll Be Working On|What You’ll Be Working On|"
    r"What We’re Looking For|What We're Looking For|"
    r"What we’re looking for|What we are looking for|"
    r"Qualifications|Skills You’ll Need To Bring|Skills You'll Need To Bring|"
    r"Nice to Haves|Nice to Have|Our Technology|Our Tech|What We Offer|"
    r"Equal Opportunity & Accommodations|A Note on AI|Term)"
    r"\s*:?[ \t]*",
    re.IGNORECASE,
)

_LIST_KEYS = {
    "work",
    "requirements",
    "qualifications",
    "nice_to_have",
    "offer",
}

_LABELS = {
    "who we are": ("company", "company"),
    "about us": ("company", "company"),
    "about the role": ("role", "role"),
    "about this role": ("role", "role"),
    "what you'll achieve": ("work", "work"),
    "what you'll be working on": ("work", "work"),
    "what we're looking for": ("requirements", "requirements"),
    "what we’re looking for": ("requirements", "requirements"),
    "what we are looking for": ("requirements", "requirements"),
    "qualifications": ("qualifications", "qualifications"),
    "skills you'll need to bring": ("requirements", "requirements"),
    "skills you’ll need to bring": ("requirements", "requirements"),
    "nice to haves": ("nice_to_have", "nice to have"),
    "nice to have": ("nice_to_have", "nice to have"),
    "our technology": ("technology", "technology"),
    "our tech": ("technology", "technology"),
    "what we offer": ("offer", "offer"),
    "term": ("term", "term"),
    "equal opportunity & accommodations": ("details", "details"),
    "a note on ai": ("details", "details"),
}

_LIST_START_RE = re.compile(
    r"\s+(?=(?:Lead|Create|Own|Act|Guide|Review|Partner|Balance|Help|Write|"
    r"Build|Design|Develop|Use|Do|Work|Ship|Currently|Experience|Familiarity|"
    r"Strong|Proficiency|Candidates|Home Office|Friday|Learning|Fitness)\b)"
)


@dataclass(frozen=True)
class _Block:
    kind: Literal["heading", "paragraph", "list"]
    text: str


class _HTMLBlockParser(HTMLParser):
    """Keep headings and list items that the normal text adapter discards."""

    _heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}

    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[_Block] = []
        self._tag: str | None = None
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[no-untyped-def]
        tag = tag.casefold()
        if tag in self._heading_tags:
            self._flush()
            self._tag = tag
            self._buffer = []
        elif tag == "p":
            self._flush()
            self._tag = tag
            self._buffer = []
        elif tag == "li":
            self._flush()
            self._tag = tag
            self._buffer = []
        elif tag == "br" and self._tag is not None:
            self._buffer.append("\n")
        elif self._tag is None and tag in {"div", "section", "article"}:
            self._tag = "p"
            self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag == self._tag:
            self._flush()

    def handle_data(self, data: str) -> None:
        if data.strip() or self._tag is not None:
            self._buffer.append(data)

    def close(self) -> None:
        super().close()
        self._flush()

    def _flush(self) -> None:
        text = _clean(" ".join(self._buffer))
        if text and self._tag is not None:
            kind: Literal["heading", "paragraph", "list"]
            if self._tag in self._heading_tags:
                kind = "heading"
            elif self._tag == "li":
                kind = "list"
            else:
                kind = "paragraph"
            self.blocks.append(_Block(kind, text))
        self._tag = None
        self._buffer = []


def extract_opportunity(job: Job) -> OpportunityDocument:
    """Create a durable, source-grounded document for one normalized job."""

    source_material = _source_material(job)
    blocks = _html_blocks(source_material) if source_material else []
    if not blocks or not any(block.kind == "heading" for block in blocks):
        blocks = _plain_blocks(job.description_text)
    sections = _sections(blocks, split_paragraphs=not bool(source_material))
    if not sections:
        sections = [
            OpportunitySection(
                key="overview",
                label="overview",
                kind="paragraph",
                items=[job.description_text.strip() or "No description."],
                source_text=job.description_text.strip(),
            )
        ]
    material_for_hash = source_material or job.description_text
    material_hash = hashlib.sha256(material_for_hash.encode("utf-8")).hexdigest()
    return OpportunityDocument(
        job_id=job.id,
        source_hash=material_hash,
        extractor_version=EXTRACTOR_VERSION,
        sections=sections,
    )


def _source_material(job: Job) -> str:
    payload = job.raw_payload
    if not isinstance(payload, dict):
        return ""
    if job.source == "ashby":
        return str(payload.get("descriptionHtml") or "")
    if job.source == "greenhouse":
        return str(payload.get("content") or "")
    if job.source == "lever":
        return " ".join(
            str(payload.get(key) or "")
            for key in ("description", "additional", "descriptionPlain", "additionalPlain")
        ).strip()
    return ""


def _html_blocks(source_material: str) -> list[_Block]:
    parser = _HTMLBlockParser()
    try:
        parser.feed(source_material)
        parser.close()
    except Exception:
        return []
    return parser.blocks


def _plain_blocks(text: str) -> list[_Block]:
    cleaned = _clean(text)
    if not cleaned:
        return []
    matches = [match for match in _HEADING_RE.finditer(cleaned) if _is_heading(cleaned, match)]
    if not matches:
        return [_Block("paragraph", cleaned)]
    blocks: list[_Block] = []
    if matches[0].start() > 0:
        blocks.append(_Block("paragraph", cleaned[: matches[0].start()].strip()))
    for index, match in enumerate(matches):
        blocks.append(_Block("heading", match.group(1)))
        end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned)
        body = cleaned[match.end() : end].strip()
        if body:
            blocks.append(_Block("paragraph", body))
    return blocks


def _is_heading(text: str, match: re.Match[str]) -> bool:
    matched = match.group(0)
    if ":" in matched:
        return True
    key = _normalize_key(match.group(1))
    if key == "a note on ai":
        return True
    prefix = text[: match.start()].rstrip()
    return not prefix or prefix[-1] in ".!?"


def _sections(
    blocks: list[_Block],
    *,
    split_paragraphs: bool,
) -> list[OpportunitySection]:
    raw_sections: list[tuple[str, list[_Block]]] = []
    key = "overview"
    current: list[_Block] = []
    for block in blocks:
        if block.kind == "heading":
            if current:
                raw_sections.append((key, current))
            key = _canonical_key(block.text)
            current = []
        else:
            current.append(block)
    if current:
        raw_sections.append((key, current))

    merged_sections: list[tuple[str, list[_Block]]] = []
    for section_key, section_blocks in raw_sections:
        if merged_sections and merged_sections[-1][0] == section_key:
            merged_sections[-1][1].extend(section_blocks)
        else:
            merged_sections.append((section_key, section_blocks))

    sections: list[OpportunitySection] = []
    for key, section_blocks in merged_sections:
        items: list[str] = []
        has_list = False
        for block in section_blocks:
            has_list = has_list or block.kind == "list"
            units = (
                [block.text]
                if block.kind == "list" or (not split_paragraphs and key not in _LIST_KEYS)
                else _text_units(block.text, key)
            )
            for unit in units:
                if unit and _fingerprint(unit) not in {_fingerprint(item) for item in items}:
                    items.append(unit)
        if not items:
            continue
        kind: Literal["paragraph", "list"] = (
            "list" if has_list or key in _LIST_KEYS else "paragraph"
        )
        label = _LABELS.get(key, (key, key.replace("_", " ")))[1]
        sections.append(
            OpportunitySection(
                key=key,
                label=label,
                kind=kind,
                items=items,
                source_text=" ".join(items),
            )
        )
    return sections


def _text_units(text: str, key: str) -> list[str]:
    units = [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])|\n+", text)
        if part.strip()
    ]
    if key not in _LIST_KEYS:
        return units
    return [
        item.strip()
        for unit in units
        for item in _LIST_START_RE.split(unit)
        if item.strip()
    ]


def _canonical_key(raw: str) -> str:
    normalized = _normalize_key(raw)
    return _LABELS.get(normalized, (normalized, normalized))[0]


def _normalize_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold().replace("’", "'")).strip(" :")


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _fingerprint(value: str) -> str:
    return re.sub(r"\W+", " ", value.casefold()).strip()
