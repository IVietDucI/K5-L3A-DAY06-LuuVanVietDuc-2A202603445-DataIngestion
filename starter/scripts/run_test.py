"""Evaluate the held-out test set using existing pgvector data."""

import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from dotenv import load_dotenv

STARTER = Path(__file__).resolve().parents[1]
ROOT = STARTER.parent
sys.path.insert(0, str(STARTER))

from src.embeddings import MyEmbedder
from src.evaluation import evaluate_query, summarize
from src.store import PgVectorStore


def main() -> None:
    load_dotenv(STARTER / ".env", override=True)

    model_name = os.environ["EMBEDDING_MODEL"]
    database_url = os.environ["DATABASE_URL"]

    dev_dir = ROOT / "results/dev/20261113T112611135714Z"
    preparation = ROOT / "results/preparation"
    benchmark_path = ROOT / "benchmark/thinkpython_questions.json"

    dev_config = json.loads((dev_dir / "run_config.json").read_text(encoding="utf-8"))
    current_config = json.loads(
        (preparation / "strategies.json").read_text(encoding="utf-8")
    )

    benchmark_sha = hashlib.sha256(benchmark_path.read_bytes()).hexdigest()

    manifest = json.loads((ROOT / "data/manifest.json").read_text(encoding="utf-8"))
    source_sha = hashlib.sha256(
        (ROOT / manifest["source_path_or_url"]).read_bytes()
    ).hexdigest()

    if benchmark_sha != dev_config["benchmark_sha256"]:
        raise ValueError("Benchmark changed since the development run")

    if source_sha != dev_config["source_sha256"]:
        raise ValueError("Source PDF changed since the development run")

    if current_config != dev_config["strategies"]:
        raise ValueError("Strategy configuration changed since dev")

    if model_name != dev_config["model"]:
        raise ValueError("Embedding model differs from the dev run")

    # Verify that the database still contains the prepared corpus.
    chunk_hashes = {}

    with psycopg.connect(database_url) as conn:
        for strategy in ("A", "B", "C"):
            path = preparation / f"chunks_{strategy}.jsonl"
            chunk_hashes[strategy] = hashlib.sha256(path.read_bytes()).hexdigest()

            expected = {}
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue

                chunk = json.loads(line)
                metadata = dict(chunk["metadata"])
                metadata.update(
                    {
                        "document_id": chunk["document_id"],
                        "source": chunk["source"],
                        "page": chunk["page"],
                    }
                )

                if metadata["source_sha256"] != source_sha:
                    raise ValueError("Prepared chunk has a different source")

                expected[chunk["chunk_id"]] = (
                    chunk["text"],
                    metadata,
                )

            rows = conn.execute(
                """
                SELECT chunk_id, text, metadata, vector_dims(embedding)
                FROM day06_eg2_chunks
                WHERE strategy = %s
                """,
                (strategy,),
            ).fetchall()

            actual = {row[0]: (row[1], row[2]) for row in rows}

            if actual != expected:
                raise ValueError(
                    f"Database content differs from preparation: {strategy}"
                )

            if any(row[3] != 768 for row in rows):
                raise ValueError("Database contains wrong vector dimensions")

            print(
                f"[{strategy}] Existing database verified: {len(rows)} chunks",
                flush=True,
            )

    if chunk_hashes["B"] != chunk_hashes["C"]:
        raise ValueError("B and C chunks must be identical")

    # Freeze the selection before evaluating any test query.
    decision = {
        "selected_strategy": "C",
        "reason": (
            "B/C tied on development retrieval metrics. "
            "C additionally enforced explicit chapter scope and "
            "improved Q04 evidence rank from 3 to 2."
        ),
        "model": model_name,
        "dimensions": 768,
        "benchmark_sha256": benchmark_sha,
        "source_sha256": source_sha,
        "chunk_hashes": chunk_hashes,
        "dev_run": dev_dir.name,
        "dev_summary_sha256": hashlib.sha256(
            (dev_dir / "summary.json").read_bytes()
        ).hexdigest(),
        "embedding_code_sha256": hashlib.sha256(
            (STARTER / "src/embeddings.py").read_bytes()
        ).hexdigest(),
        "strategies": current_config,
    }

    selection_path = ROOT / "results/selection_C.json"

    if selection_path.exists():
        frozen = json.loads(selection_path.read_text(encoding="utf-8"))
        if frozen["decision"] != decision:
            raise ValueError("Current setup differs from frozen selection")
    else:
        with selection_path.open("x", encoding="utf-8") as file:
            json.dump(
                {
                    "frozen_at": datetime.now(timezone.utc).isoformat(),
                    "decision": decision,
                },
                file,
                ensure_ascii=False,
                indent=2,
            )

    print("Selection frozen: C", flush=True)

    questions = [
        question
        for question in json.loads(benchmark_path.read_text(encoding="utf-8"))
        if question["split"] == "test"
    ]

    if len(questions) != 5:
        raise ValueError("Expected exactly five test questions")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = ROOT / "results/test" / run_id
    output.mkdir(parents=True)

    logging.basicConfig(
        filename=output / "run.log",
        level=logging.INFO,
        encoding="utf-8",
        force=True,
    )

    def save_json(name, value):
        (output / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    save_json(
        "run_config.json",
        {
            "split": "test",
            "selection": decision,
            "document_vectors": "Reused from existing pgvector table",
        },
    )

    start = time.perf_counter()
    embedder = MyEmbedder(model_name)
    load_seconds = time.perf_counter() - start

    store = PgVectorStore(database_url, embedder.dimensions)

    start = time.perf_counter()
    query_vectors = {}

    for question in questions:
        query_vectors[question["id"]] = embedder.embed_query(question["question"])
        print(f"Test query ready: {question['id']}", flush=True)

    query_seconds = time.perf_counter() - start
    traces = []

    with (output / "traces.jsonl").open("w", encoding="utf-8") as file:
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

                if applied_filter and any(
                    not all(
                        hit["metadata"].get(key) == value
                        for key, value in applied_filter.items()
                    )
                    for hit in hits
                ):
                    raise RuntimeError("Returned hit violates applied filter")

                trace = evaluate_query(question, hits)
                trace.update(
                    {
                        "strategy": strategy,
                        "applied_filter": applied_filter,
                        "search_seconds": search_seconds,
                        "metadata_review": [
                            {
                                "chunk_id": hit["chunk_id"],
                                "source_correct": None,
                                "page_correct": None,
                                "chapter_correct": None,
                                "reason": "",
                            }
                            for hit in hits
                        ],
                    }
                )

                traces.append(trace)
                file.write(json.dumps(trace, ensure_ascii=False) + "\n")
                file.flush()

    summary = summarize(traces)
    save_json("summary.json", summary)
    save_json("manual_test_review.json", traces)
    save_json(
        "resources.json",
        {
            "model_load_seconds": load_seconds,
            "shared_test_query_embedding_seconds": query_seconds,
            "document_embedding_seconds": 0,
            "document_vectors_reused": True,
            "note": (
                "No document re-embedding. Five query vectors are shared "
                "across A/B/C. No generation API calls."
            ),
        },
    )

    print("\n=== TEST RESULTS ===")
    for key, values in summary.items():
        print(
            f"{key}: "
            f"Hit@1={values['hit_at_1_count']}/5 | "
            f"Evidence Hit@3={values['evidence_hit_at_3_count']}/5"
        )

    print("\nSelected strategy before test: C")
    print("Human grounding and metadata review remain unscored.")
    print("Results:", output)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logging.exception("Test run failed")
        raise
