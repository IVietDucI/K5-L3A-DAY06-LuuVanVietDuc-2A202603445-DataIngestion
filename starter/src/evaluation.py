"""TODO: evaluate retrieved evidence and preserve per-query traces."""

from typing import Any
import unicodedata


def evaluate_query(
    question: dict[str, Any], hits: list[dict[str, Any]]
) -> dict[str, Any]:
    def canonical(text):
        # Ignore whitespace differences caused by PDF line wrapping.
        return "".join(unicodedata.normalize("NFC", text).split()).casefold()

    golds = [question] + question.get("alternative_gold", [])
    checked = []

    for hit in hits[:3]:
        metadata = hit["metadata"]
        is_hit = False

        for gold in golds:
            evidence = canonical(gold["evidence_quote"])
            if not evidence:
                raise ValueError("Gold evidence must not be empty")

            if (
                metadata.get("document_id") == gold["gold_source_id"]
                and metadata.get("page") == gold["gold_page"]
                and evidence in canonical(hit["text"])
            ):
                is_hit = True

        checked.append(
            {
                **hit,
                "automatic_evidence_match": is_hit,
            }
        )

    return {
        "id": question["id"],
        "split": question["split"],
        "question": question["question"],
        "expected_answer": question["expected_answer"],
        "gold_source_id": question["gold_source_id"],
        "gold_page": question["gold_page"],
        "evidence_quote": question["evidence_quote"],
        "alternative_gold": question.get("alternative_gold", []),
        "requested_filter": question.get("filter"),
        "hit_at_1": bool(checked and checked[0]["automatic_evidence_match"]),
        "evidence_hit_at_3": any(hit["automatic_evidence_match"] for hit in checked),
        "hits": checked,
        "human_grounding_0_2": None,
        "human_reason": "",
    }


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    groups = {}

    for trace in traces:
        key = f"{trace['strategy']}/{trace['split']}"
        groups.setdefault(key, []).append(trace)

    result = {}

    for key, rows in groups.items():
        total = len(rows)
        hit1 = sum(row["hit_at_1"] for row in rows)
        hit3 = sum(row["evidence_hit_at_3"] for row in rows)

        result[key] = {
            "questions": total,
            "hit_at_1_count": hit1,
            "hit_at_1": hit1 / total,
            "evidence_hit_at_3_count": hit3,
            "evidence_hit_at_3": hit3 / total,
        }

    return result
