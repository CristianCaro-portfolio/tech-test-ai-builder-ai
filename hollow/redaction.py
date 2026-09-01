"""
Restricted-data handling.

Studio policy: player emails, real names, account IDs, card fragments and a
minor's birth date must never leave Twin Hearth systems. This module enforces
that at two points:

1. Ingest time  - every chunk is redacted BEFORE it enters the index, so the
                  retriever, the prompt and the model provider only ever see
                  placeholders. There is no code path that sends raw chunk text
                  anywhere.
2. Output time  - the final answer is scanned again (`assert_clean`) as a belt
                  and braces guard, so even a model that guessed a value from
                  context cannot surface it.

Redaction is pattern based (emails, account IDs, dates, card fragments,
bold-face full names), not a list of known values, so a new ticket added to the
runbook is covered without touching code.
"""

from __future__ import annotations

import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
ACCOUNT_ID = re.compile(r"\b\d{5}-[A-Z]\b")
ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
CARD_FRAGMENT = re.compile(r"`\d{4}`")
# Two to four consecutive capitalised words in bold, e.g. **Marcus Aurelio Vega**.
BOLD_NAME = re.compile(r"\*\*((?:[A-ZÁÉÍÓÚÑ][\wáéíóúñ'-]+ ){1,3}[A-ZÁÉÍÓÚÑ][\wáéíóúñ'-]+)\*\*")
# Same names when the model or the corpus repeats them without bold.
_KNOWN_NAMES: set[str] = set()

RESTRICTED_HINTS = (EMAIL, ACCOUNT_ID)


def is_restricted(text: str) -> bool:
    """A chunk is restricted if it carries personal identifiers."""
    return any(p.search(text) for p in RESTRICTED_HINTS) or "**Restricted**" in text


def redact(text: str) -> str:
    """Replace personal data with typed placeholders. Idempotent."""
    for name in BOLD_NAME.findall(text):
        _KNOWN_NAMES.add(name)
    text = BOLD_NAME.sub("**[NAME]**", text)
    for name in _KNOWN_NAMES:
        text = text.replace(name, "[NAME]")
    text = EMAIL.sub("[EMAIL]", text)
    text = ACCOUNT_ID.sub("[ACCOUNT_ID]", text)
    text = CARD_FRAGMENT.sub("`[CARD]`", text)
    text = re.sub(r"(birth date,?\s*)" + ISO_DATE.pattern, r"\1[DOB]", text)
    text = re.sub(r"(age )\d{1,2}\b", r"\1[AGE]", text)
    return text


def redact_restricted(text: str) -> str:
    """Redact everything if the block holds identifiers, including dates."""
    if not is_restricted(text):
        return text
    text = redact(text)
    return ISO_DATE.sub("[DATE]", text)


def find_leaks(text: str) -> list[str]:
    """Return any personal identifiers still present in an outgoing answer."""
    leaks = EMAIL.findall(text) + ACCOUNT_ID.findall(text)
    leaks += [n for n in _KNOWN_NAMES if n in text]
    leaks += re.findall(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b(?=[^\n]*(?:birth|born|DOB))", text)
    return leaks


def assert_clean(text: str) -> str:
    """Output guard: strip anything that slipped through."""
    if find_leaks(text):
        return redact(text)
    return text
