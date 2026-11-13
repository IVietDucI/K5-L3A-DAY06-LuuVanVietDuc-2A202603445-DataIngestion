"""Suggested pipeline entry point; TODO: implement the orchestration."""

import hashlib
import json
import logging
import os
import platform
import time
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import psycopg
from dotenv import load_dotenv

from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .models import Chunk
from .store import PgVectorStore


def main() -> None:
    """TODO:

    1. Load the corpus and benchmark; validate at least 30 content pages.
    2. Build strategies A (fixed), B (paragraph) and C (B + metadata filter).
    3. Embed with the same model and store vectors/metadata per strategy.
    4. Run the same dev/test questions and save full top-3 traces.
    5. Report retrieval metrics and prepare samples for manual assessment.

    Follow the five dimensions in ../../BENCHMARK.md.
    """
    starter = Path(__file__).resolve().parents[1]
    root = starter.parent
    preparation = root / "results/preparation"

    load_dotenv(starter / ".env", override=True)

    model_name = os.getenv("EMBEDDING_MODEL", "")
    if model_name != "google/embeddinggemma-2":
        raise ValueError("Set EMBEDDING_MODEL=google/embeddinggemma-2 in starter/.env")

    database_url = os.environ["DATABASE_URL"]

    benchmark_path = root / "benchmark/thinkpython_questions.json"
    benchmark_sha = hashlib.sha256(benchmark_path.read_bytes()).hexdigest()

    recorded_sha = (
        (root / "benchmark/thinkpython_questions.sha256")
        .read_text(encoding="utf-8")
        .split()[0]
    )

    if benchmark_sha != recorded_sha:
        raise ValueError("Benchmark differs from its recorded SHA256")

    config = json.loads((preparation / "strategies.json").read_text(encoding="utf-8"))

    if config["benchmark_sha256"] != benchmark_sha:
        raise ValueError("Preparation belongs to a different benchmark")

    if config["embedding_model"] != model_name:
        raise ValueError("Update prepare_corpus.py model name and rerun preparation")

    manifest = json.loads((root / "data/manifest.json").read_text(encoding="utf-8"))
    source_path = root / manifest["source_path_or_url"]

    actual_source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()

    if (
        actual_source_sha != manifest["sha256"]
        or actual_source_sha != config["source_sha256"]
    ):
        raise ValueError("Corpus snapshot differs from preparation")

    all_questions = json.loads(benchmark_path.read_text(encoding="utf-8"))
    questions = [question for question in all_questions if question["split"] == "dev"]

    if len(questions) != 15:
        raise ValueError("Expected exactly 15 development questions")

    chunks_by_strategy = {}

    for strategy in ("A", "B", "C"):
        path = preparation / f"chunks_{strategy}.jsonl"
        chunks = [
            Chunk(**json.loads(line))
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

        if not chunks:
            raise ValueError(f"No chunks for strategy {strategy}")

        for chunk in chunks:
            if chunk.metadata.get("source_sha256") != actual_source_sha:
                raise ValueError("Chunk belongs to a different PDF")

        chunks_by_strategy[strategy] = chunks

    if (preparation / "chunks_B.jsonl").read_bytes() != (
        preparation / "chunks_C.jsonl"
    ).read_bytes():
        raise ValueError("B and C must have identical chunks")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = root / "results/dev" / run_id
    output.mkdir(parents=True)

    logging.basicConfig(
        filename=output / "run.log",
        level=logging.INFO,
        encoding="utf-8",
        force=True,
    )

    def save_json(filename, value):
        (output / filename).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    save_json(
        "run_config.json",
        {
            "model": model_name,
            "dimensions": 768,
            "device": "cpu",
            "split": "dev",
            "benchmark_sha256": benchmark_sha,
            "source_sha256": actual_source_sha,
            "strategies": config,
            "python": platform.python_version(),
            "packages": {
                package: version(package)
                for package in (
                    "torch",
                    "torchvision",
                    "sentence-transformers",
                    "transformers",
                    "pypdf",
                    "psycopg",
                    "Pillow",
                )
            },
        },
    )

    print("Output:", output, flush=True)

    start = time.perf_counter()
    embedder = MyEmbedder(model_name)
    model_load_seconds = time.perf_counter() - start

    store = PgVectorStore(database_url, embedder.dimensions)
    store.create_schema()

    resource_stats = {}
    b_vectors = None

    for strategy in ("A", "B", "C"):
        chunks = chunks_by_strategy[strategy]

        print(
            f"\n[{strategy}] Preparing {len(chunks)} real vectors",
            flush=True,
        )

        if strategy == "C":
            vectors = b_vectors
            embedding_seconds = 0.0
            reused_from = "B"
        else:
            start = time.perf_counter()
            vectors = embedder.embed_documents([chunk.text for chunk in chunks])
            embedding_seconds = time.perf_counter() - start
            reused_from = None

            if strategy == "B":
                b_vectors = vectors

        start = time.perf_counter()
        store.upsert(strategy, chunks, vectors)
        first_store_seconds = time.perf_counter() - start

        with psycopg.connect(database_url) as conn:
            first_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM day06_eg2_chunks
                WHERE strategy = %s
                """,
                (strategy,),
            ).fetchone()[0]

        # Re-ingest the same complete snapshot without re-embedding.
        store.upsert(strategy, chunks, vectors)

        with psycopg.connect(database_url) as conn:
            second_count = conn.execute(
                """
                SELECT COUNT(*)
                FROM day06_eg2_chunks
                WHERE strategy = %s
                """,
                (strategy,),
            ).fetchone()[0]

        if first_count != len(chunks) or second_count != len(chunks):
            raise RuntimeError(f"Idempotency check failed: {strategy}")

        resource_stats[strategy] = {
            "chunks": len(chunks),
            "document_embedding_seconds": embedding_seconds,
            "vectors_reused_from": reused_from,
            "first_store_seconds": first_store_seconds,
            "count_after_first_ingest": first_count,
            "count_after_second_ingest": second_count,
        }

        save_json(
            "resources.json",
            {
                "model_load_seconds": model_load_seconds,
                "strategies": resource_stats,
            },
        )

        print(
            f"[{strategy}] Store OK | " f"first={first_count} | second={second_count}",
            flush=True,
        )

    print("\nEmbedding 15 development queries...", flush=True)
    start = time.perf_counter()

    query_vectors = {}
    for question in questions:
        query_vectors[question["id"]] = embedder.embed_query(question["question"])
        print(f"Query ready: {question['id']}", flush=True)

    query_embedding_seconds = time.perf_counter() - start
    traces = []

    with (output / "traces.jsonl").open("w", encoding="utf-8") as trace_file:
        for strategy in ("A", "B", "C"):
            for question in questions:
                applied_filter = question.get("filter") if strategy == "C" else None

                start = time.perf_counter()
                hits = store.search(
                    strategy=strategy,
                    query_vector=query_vectors[question["id"]],
                    top_k=3,
                    filters=applied_filter,
                )
                search_seconds = time.perf_counter() - start

                trace = evaluate_query(question, hits)
                trace.update(
                    {
                        "strategy": strategy,
                        "applied_filter": applied_filter,
                        "search_seconds": search_seconds,
                    }
                )

                traces.append(trace)
                trace_file.write(json.dumps(trace, ensure_ascii=False) + "\n")
                trace_file.flush()

    summary = summarize(traces)
    save_json("summary.json", summary)
    save_json(
        "resources.json",
        {
            "model_load_seconds": model_load_seconds,
            "shared_dev_query_embedding_seconds": query_embedding_seconds,
            "strategies": resource_stats,
            "note": (
                "C reuses B document vectors. All strategies reuse the "
                "same query vectors. Model runs locally without API calls; "
                "local compute/electricity costs are not measured."
            ),
        },
    )

    print("\n=== DEVELOPMENT RESULTS ===")
    for key, values in summary.items():
        total = values["questions"]
        hit1 = values["hit_at_1_count"]
        hit3 = values["evidence_hit_at_3_count"]
        print(f"{key}: Hit@1={hit1}/{total} | " f"Evidence Hit@3={hit3}/{total}")

    print("\nDev run complete. Test questions have not been evaluated.")
    print("Results:", output)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("Pipeline failed")
        raise
