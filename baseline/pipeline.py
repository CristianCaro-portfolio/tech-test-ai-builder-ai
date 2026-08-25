"""
Naive RAG baseline for the Hollow Crown support assistant.

Left behind by a previous contractor. It works. It is not good.
It runs offline with no API key so you always have a comparison point.

Public contract used by eval/run_eval.py -- keep it if you rewrite this:

    answer(question: str) -> {
        "answer": str,
        "chunks": [ {"doc": str, "text": str, "score": float}, ... ],
        "tokens_in": int,
        "tokens_out": int,
    }
"""

import math
import os
import re
from collections import Counter

CORPUS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "corpus")

CHUNK_SIZE = 400   # characters
CHUNK_OVERLAP = 0
TOP_K = 1


def _load_docs():
    docs = {}
    for name in sorted(os.listdir(CORPUS_DIR)):
        if name.endswith(".md"):
            with open(os.path.join(CORPUS_DIR, name), encoding="utf-8") as fh:
                docs[name] = fh.read()
    return docs


def _chunk(text):
    """Fixed-width character slicing. Knows nothing about sentences, tables or headings."""
    step = CHUNK_SIZE - CHUNK_OVERLAP
    return [text[i:i + CHUNK_SIZE] for i in range(0, len(text), step)]


def _tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


def _vector(text):
    return Counter(_tokenize(text))


def _cosine(a, b):
    """Raw term-frequency cosine. No IDF, so 'the' counts as much as 'chargeback'."""
    shared = set(a) & set(b)
    if not shared:
        return 0.0
    num = sum(a[t] * b[t] for t in shared)
    den = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return num / den if den else 0.0


_INDEX = None


def _index():
    global _INDEX
    if _INDEX is None:
        _INDEX = []
        for doc, text in _load_docs().items():
            for piece in _chunk(text):
                _INDEX.append({"doc": doc, "text": piece, "vec": _vector(piece)})
    return _INDEX


def retrieve(question, k=TOP_K):
    qv = _vector(question)
    scored = [
        {"doc": c["doc"], "text": c["text"], "score": _cosine(qv, c["vec"])}
        for c in _index()
    ]
    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[:k]


def answer(question):
    """
    Extractive 'answer': hands back the winning chunk verbatim.

    No LLM call, no synthesis, no refusal path, no redaction. Whatever is in the
    chunk goes out -- including anything the data policy says should not.
    """
    chunks = retrieve(question)
    text = "\n\n".join(c["text"] for c in chunks)
    return {
        "answer": text,
        "chunks": chunks,
        "tokens_in": len(_tokenize(question)) + len(_tokenize(text)),
        "tokens_out": len(_tokenize(text)),
    }
