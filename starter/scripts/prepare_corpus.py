"""Offline corpus/chunk preparation. No API, embeddings, or database calls."""

import hashlib
import json
import logging
import statistics
import sys
from dataclasses import asdict
from pathlib import Path

STARTER = Path(__file__).resolve().parents[1]
ROOT = STARTER.parent
sys.path.insert(0, str(STARTER))
from src.ingestion import load_pdf
from src.chunking import fixed_size, by_paragraph


def write_json(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_jsonl(path, rows):
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
        newline="\r\n",
    )


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_chunks(pages, chunks, max_size):
    by_page = {p.page: p for p in pages}
    if len({c.chunk_id for c in chunks}) != len(chunks):
        raise ValueError("Duplicate chunk IDs")
    for page in pages:
        coverage = bytearray(len(page.text))
        for c in [c for c in chunks if c.page == page.page]:
            start, end = c.metadata["char_start"], c.metadata["char_end"]
            if c.text != by_page[c.page].text[start:end] or len(c.text) > max_size:
                raise ValueError("Chunk offset/size mismatch")
            if c.metadata.get("chapter") != page.metadata["chapter"]:
                raise ValueError("Chapter metadata mismatch")
            coverage[start:end] = b"\x01" * (end - start)
        if any(
            not coverage[i] and not char.isspace() for i, char in enumerate(page.text)
        ):
            raise ValueError(f"Lost source content on page {page.page}")


def main():
    out = ROOT / "results/preparation"
    out.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        handlers=[
            logging.FileHandler(out / "ingestion.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
        force=True,
    )
    manifest = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
    source = ROOT / manifest["source_path_or_url"]
    if sha(source) != manifest["sha256"]:
        raise ValueError("PDF differs from manifest snapshot")
    benchmark = ROOT / "benchmark/thinkpython_questions.json"
    benchmark_sha = sha(benchmark)
    selections = {p["page"]: p for p in manifest["pages"]}
    if len(selections) != len(manifest["pages"]):
        raise ValueError("Repeated selected page in manifest")
    all_pages = load_pdf(source, manifest["source_id"], manifest["source_path_or_url"])
    pages = [p for p in all_pages if p.page in selections]
    if len(pages) != len(selections) or len(pages) < 30:
        raise ValueError("Selected corpus must contain at least 30 physical pages")
    for page in pages:
        if not page.text:
            raise ValueError(f"Selected page {page.page} has no text")
        info = selections[page.page]
        chars = len(" ".join(page.text.split()))
        if chars != info["normalized_char_count"]:
            raise ValueError(
                f"Extraction differs from manifest on page {page.page}: {chars}"
            )
        page.metadata = {
            "chapter": info["chapter"],
            "chapter_title": info["chapter_title"],
            "page_id": info["page_id"],
            "printed_page": info["printed_page"],
            "source_sha256": manifest["sha256"],
        }
    a = [c for p in pages for c in fixed_size(p, 500, 50)]
    b = [c for p in pages for c in by_paragraph(p, 1000)]
    strategies = {"A": a, "B": b, "C": b}
    validate_chunks(pages, a, 500)
    validate_chunks(pages, b, 1000)
    write_jsonl(out / "pages.jsonl", [asdict(p) for p in pages])
    stats = {}
    for strategy, chunks in strategies.items():
        write_jsonl(out / f"chunks_{strategy}.jsonl", [asdict(c) for c in chunks])
        lengths = [len(c.text) for c in chunks]
        stats[strategy] = {
            "chunks": len(chunks),
            "min_chars": min(lengths),
            "max_chars": max(lengths),
            "mean_chars": round(statistics.mean(lengths), 2),
            "total_chars": sum(lengths),
        }
    # Same ten source positions fixed before retrieval results, not selected by score.
    samples = []
    for page in sorted(pages, key=lambda p: p.page)[:10]:
        position = len(page.text) // 2
        while position < len(page.text) - 1 and page.text[position].isspace():
            position += 1
        for strategy, chunks in strategies.items():
            covering = [
                c
                for c in chunks
                if c.page == page.page
                and c.metadata["char_start"] <= position < c.metadata["char_end"]
            ]
            chosen = min(covering, key=lambda c: c.metadata["char_start"])
            samples.append(
                {
                    "strategy": strategy,
                    "page": page.page,
                    "source_position": position,
                    "chunk_id": chosen.chunk_id,
                    "text": chosen.text,
                    "coherence_score_0_2": None,
                    "reason": "",
                }
            )
    # Do not overwrite an existing human annotation file on rerun.
    if not (out / "coherence_samples.json").exists():
        write_json(out / "coherence_samples.json", samples)
    config = {
        "A": {
            "method": "fixed",
            "size_chars": 500,
            "overlap_chars": 50,
            "filter": False,
        },
        "B": {
            "method": "heading_sentence_heuristic",
            "max_chars": 1000,
            "filter": False,
        },
        "C": {"same_chunks_as": "B", "filter": "Explicit query filter only"},
        "embedding_model": "google/embeddinggemma-2",
        "dimensions": 768,
        "distance": "cosine",
        "vector_store": "PostgreSQL/pgvector",
        "benchmark_sha256": benchmark_sha,
        "source_sha256": manifest["sha256"],
    }
    write_json(out / "strategies.json", config)
    write_json(
        out / "summary.json",
        {
            "selected_pages": len(pages),
            "statistics": stats,
            "benchmark_sha256": benchmark_sha,
            "bc_chunks_identical": sha(out / "chunks_B.jsonl")
            == sha(out / "chunks_C.jsonl"),
        },
    )
    if sha(benchmark) != benchmark_sha:
        raise RuntimeError("Benchmark changed during preparation")
    print(f"Corpus OK | selected pages: {len(pages)}")
    for strategy, values in stats.items():
        print(
            f'{strategy}: {values["chunks"]} chunks | max chars: {values["max_chars"]}'
        )
    print("B/C chunks identical: True")
    print("Content coverage and metadata: OK")
    print("Coherence samples: 10 source positions x 3 strategies (unscored)")
    print("Benchmark unchanged:", benchmark_sha)
    print("Preparation OK | no embedding or retrieval has run")


if __name__ == "__main__":
    main()
