"""
Structure-aware chunking for the markdown corpus.

The baseline slices every document into fixed 400-character windows, which cuts
sentences, tables and headings in half. Here a chunk is a markdown section:
everything under one `## heading` (tables and lists stay intact). Each chunk is
prefixed with the document title and the section heading so that a section such
as "2. Deletion grace period" is searchable by the topic it belongs to.

Sections longer than MAX_CHARS are split on paragraph boundaries, with the
heading repeated on every piece so no piece loses its context.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

CORPUS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "corpus")

MAX_CHARS = 1200


@dataclass
class Chunk:
    doc: str
    heading: str
    text: str
    restricted: bool = False

    @property
    def search_text(self) -> str:
        return f"{self.heading}\n{self.text}"


def load_docs(corpus_dir: str = CORPUS_DIR) -> dict[str, str]:
    docs = {}
    for name in sorted(os.listdir(corpus_dir)):
        if name.endswith(".md"):
            with open(os.path.join(corpus_dir, name), encoding="utf-8") as fh:
                docs[name] = fh.read()
    return docs


def _split_long(text: str) -> list[str]:
    if len(text) <= MAX_CHARS:
        return [text]
    pieces, current = [], ""
    for para in re.split(r"\n{2,}", text):
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) > MAX_CHARS and current:
            pieces.append(current)
            current = para
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def _explode_tables(section_text: str) -> list[str]:
    """
    Split a section that contains a markdown table into: the prose around the
    table (one piece) and one piece per table row, each prefixed with the header
    row. A row such as "Crown Tokens | 7 days | ..." then competes for retrieval
    on its own terms instead of being diluted by the ten rows around it.
    """
    lines = section_text.splitlines()
    prose, rows, header = [], [], None
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if header is None:
                header = cells
            elif all(set(c) <= set("-: ") for c in cells):
                continue  # separator row
            else:
                rows.append("; ".join(f"{h}: {c}" for h, c in zip(header, cells)))
        else:
            prose.append(line)
    if not rows:
        return [section_text]
    pieces = []
    prose_text = "\n".join(prose).strip()
    if prose_text:
        pieces.append(prose_text)
    pieces.extend(rows)
    return pieces


def chunk_document(doc: str, text: str) -> list[Chunk]:
    lines = text.splitlines()
    title = ""
    for line in lines:
        if line.startswith("# "):
            title = line[2:].strip()
            break

    sections: list[tuple[str, list[str]]] = []
    heading, body = "", []
    for line in lines:
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            if body and "".join(body).strip():
                sections.append((heading, body))
            heading, body = line[3:].strip(), []
        else:
            body.append(line)
    if body and "".join(body).strip():
        sections.append((heading, body))

    chunks = []
    for heading, body in sections:
        section_text = "\n".join(body).strip()
        if not section_text:
            continue
        label = f"{title} > {heading}" if heading else title
        for piece in _explode_tables(section_text):
            for sub in _split_long(piece):
                chunks.append(Chunk(doc=doc, heading=label, text=sub))
    return chunks


def build_chunks(corpus_dir: str = CORPUS_DIR) -> list[Chunk]:
    chunks = []
    for doc, text in load_docs(corpus_dir).items():
        chunks.extend(chunk_document(doc, text))
    return chunks
