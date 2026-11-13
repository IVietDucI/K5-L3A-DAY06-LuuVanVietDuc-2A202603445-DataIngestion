"""Page-bounded windows and heading/sentence-aware grouping.
PDF extraction lacks reliable paragraph marks. B uses existing blank lines,
numbered headings and sentence endings as heuristic boundaries, not semantic AI.
Offsets refer to normalized page text; end is exclusive.
"""

import hashlib
import json
import re
from .models import Chunk, DocumentPage


def _chunk(page: DocumentPage, start: int, end: int, method: str) -> Chunk | None:
    while start < end and page.text[start].isspace():
        start += 1
    while end > start and page.text[end - 1].isspace():
        end -= 1
    if start == end:
        return None
    metadata = dict(page.metadata)
    metadata.update({"char_start": start, "char_end": end, "chunk_method": method})
    payload = json.dumps(
        [page.document_id, page.source, page.page, page.text[start:end], metadata],
        sort_keys=True,
        ensure_ascii=False,
    )
    stable_id = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return Chunk(
        stable_id,
        page.document_id,
        page.source,
        page.page,
        page.text[start:end],
        metadata,
    )


def fixed_size(page: DocumentPage, size: int, overlap: int) -> list[Chunk]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("Require size > 0 and 0 <= overlap < size")
    chunks = []
    start = 0
    while start < len(page.text):
        end = min(start + size, len(page.text))
        chunk = _chunk(page, start, end, f"fixed-v1-{size}-{overlap}")
        if chunk:
            chunks.append(chunk)
        if end == len(page.text):
            break
        start += size - overlap
    return chunks


def by_paragraph(page: DocumentPage, max_size: int) -> list[Chunk]:
    if max_size <= 0:
        raise ValueError("max_size must be positive")
    text = page.text
    # Blank lines, section headings, sentence ends. Includes every character.
    cuts = {len(text)}
    for match in re.finditer(
        r"\n\s*\n|\n(?=\d+(?:\.\d+)+\s)|(?<=[.!?])\s+(?=[A-Z])", text
    ):
        cuts.add(match.end())
    boundaries = sorted(cuts)
    chunks = []
    start = 0
    while start < len(text):
        limit = min(start + max_size, len(text))
        candidates = [c for c in boundaries if start + max_size * 0.4 <= c <= limit]
        end = max(candidates) if candidates else limit
        if not candidates and limit < len(text):
            # Oversized block: split at a word boundary if possible.
            word_break = text.rfind(" ", start, limit + 1)
            if word_break > start:
                end = word_break
        if end <= start:
            end = limit
        chunk = _chunk(page, start, end, f"heading-sentence-v1-{max_size}")
        if chunk:
            chunks.append(chunk)
        start = end
    return chunks
