"""
Lexical retrieval: BM25 over section chunks.

Why BM25 and not embeddings: the corpus is four documents and ~40 sections.
Support questions here hinge on exact terms (chargeback, purchaser, 2FA,
Season Pass) that a term-weighted index nails deterministically, offline, with
zero cost and zero network. Embeddings are the right call once the corpus grows
past what one lexical index can disambiguate (see STACK.md); at this size they
add latency and a key requirement without moving the metric.

Improvements over the baseline scorer:
  - IDF weighting: "the" no longer counts as much as "chargeback".
  - Length normalisation so long sections do not dominate.
  - Light stemming (plural / -ing / -ed) so "refunds" matches "refund".
  - Heading terms are indexed with the body, so a query about "deletion" finds
    the "Deletion grace period" section even if the body says "deleted".
  - Relevance gate: a query whose content terms barely overlap the corpus
    returns nothing, which lets the agent refuse instead of guessing.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from .chunking import Chunk, build_chunks
from .redaction import redact_restricted

K1 = 1.5
B = 0.75
# Worked examples that carried personal data are training material, not policy.
# They stay searchable (the pipeline must still recognise a ticket question and
# refuse) but rank below the policy sections that actually state the rule.
RESTRICTED_PENALTY = 0.5
MAX_PER_DOC = 2

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for", "from",
    "has", "have", "how", "i", "if", "in", "is", "it", "its", "of", "on", "or", "that",
    "the", "their", "them", "they", "this", "to", "was", "we", "what", "when", "which",
    "who", "with", "did", "any", "now", "our", "us", "player", "players", "support",
    "tell", "them", "about", "should", "would", "need", "needs", "want", "wants",
    "many", "much", "long", "right", "still",
}

_VERSION = re.compile(r"\d+\.\d+\.\d+")


def _stem(tok: str) -> str:
    for suffix in ("ing", "ies", "ed", "es", "s"):
        if len(tok) > 4 and tok.endswith(suffix):
            return tok[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return tok


def tokenize(text: str) -> list[str]:
    text = text.lower()
    versions = _VERSION.findall(text)
    tokens = [_stem(t) for t in re.findall(r"[a-z0-9]+", text) if t not in STOPWORDS]
    return tokens + versions


@dataclass
class Hit:
    chunk: Chunk
    score: float

    def as_dict(self) -> dict:
        return {"doc": self.chunk.doc, "heading": self.chunk.heading,
                "text": self.chunk.text, "score": round(self.score, 4)}


class BM25Index:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.tf = [Counter(tokenize(c.search_text)) for c in chunks]
        self.lengths = [sum(tf.values()) for tf in self.tf]
        self.avg_len = sum(self.lengths) / max(len(self.lengths), 1)
        df = Counter()
        for tf in self.tf:
            df.update(tf.keys())
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - d + 0.5) / (d + 0.5)) for t, d in df.items()}

    def _score(self, q_terms: list[str], i: int) -> float:
        tf, length = self.tf[i], self.lengths[i]
        score = 0.0
        for term in q_terms:
            if term not in tf:
                continue
            f = tf[term]
            score += self.idf[term] * f * (K1 + 1) / (f + K1 * (1 - B + B * length / self.avg_len))
        return score

    def search(self, query: str, k: int = 4, max_per_doc: int = MAX_PER_DOC) -> list[Hit]:
        q_terms = tokenize(query)
        if not q_terms:
            return []
        hits = [Hit(c, self._score(q_terms, i) * (RESTRICTED_PENALTY if c.restricted else 1.0))
                for i, c in enumerate(self.chunks)]
        hits.sort(key=lambda h: h.score, reverse=True)
        # Diversify: cap chunks per document so a multi-hop question that needs
        # two documents is not buried under four sections of the same one.
        picked, per_doc = [], Counter()
        for h in hits:
            if h.score <= 0 or len(picked) == k:
                break
            if per_doc[h.chunk.doc] >= max_per_doc:
                continue
            picked.append(h)
            per_doc[h.chunk.doc] += 1
        return picked

    def coverage(self, query: str, hits: list[Hit]) -> float:
        """Fraction of informative query terms present in the retrieved text."""
        q_terms = set(tokenize(query))
        if not q_terms:
            return 0.0
        found = set()
        for h in hits:
            found |= set(tokenize(h.chunk.search_text))
        # Terms the corpus has never seen are maximally informative: they get
        # the top IDF, and they are by definition not covered.
        unknown = max(self.idf.values(), default=1.0)
        weight = {t: self.idf.get(t, unknown) for t in q_terms}
        return sum(w for t, w in weight.items() if t in found) / sum(weight.values())


_INDEX: BM25Index | None = None


def get_index() -> BM25Index:
    global _INDEX
    if _INDEX is None:
        chunks = build_chunks()
        for c in chunks:
            redacted = redact_restricted(c.text)
            c.restricted = redacted != c.text
            c.text = redacted
        _INDEX = BM25Index(chunks)
    return _INDEX


def retrieve(question: str, k: int = 4, min_score: float = 0.0) -> list[Hit]:
    return [h for h in get_index().search(question, k) if h.score >= min_score]
