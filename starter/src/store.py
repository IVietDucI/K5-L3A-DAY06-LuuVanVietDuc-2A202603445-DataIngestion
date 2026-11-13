"""TODO: store and search vectors using PostgreSQL + pgvector."""

from typing import Any
from .models import Chunk
import math
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        if not database_url:
            raise ValueError("DATABASE_URL is required")

        if dimensions != 768:
            raise ValueError("This EmbeddingGemma 2 table requires 768 dimensions")

        self.database_url = database_url
        self.dimensions = dimensions

    def create_schema(self) -> None:
        with psycopg.connect(self.database_url) as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

            conn.execute("""
                CREATE TABLE IF NOT EXISTS day06_eg2_chunks (
                    strategy TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    page INTEGER NOT NULL CHECK (page >= 1),
                    text TEXT NOT NULL,
                    metadata JSONB NOT NULL,
                    embedding VECTOR(768) NOT NULL,
                    PRIMARY KEY (strategy, chunk_id)
                )
            """)

    def upsert(
        self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]
    ) -> None:
        """Write a COMPLETE snapshot of one strategy.

        Repeated snapshots do not duplicate chunks.
        Chunks absent from the new snapshot are removed.
        Do not call this method once per embedding batch.
        """
        if not strategy:
            raise ValueError("Strategy is required")

        if not chunks:
            raise ValueError("Refusing an empty strategy snapshot")

        if len(chunks) != len(vectors):
            raise ValueError("Chunk/vector counts differ")

        ids = [chunk.chunk_id for chunk in chunks]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate chunk IDs in the input snapshot")

        rows = []

        for chunk, vector in zip(chunks, vectors):
            if len(vector) != self.dimensions:
                raise ValueError(f"Wrong dimensions: {chunk.chunk_id}")

            if not all(math.isfinite(value) for value in vector):
                raise ValueError(f"Invalid vector: {chunk.chunk_id}")

            if not any(value != 0 for value in vector):
                raise ValueError("Zero vectors cannot be used for cosine search")

            if not chunk.text.strip() or chunk.page < 1:
                raise ValueError(f"Invalid chunk: {chunk.chunk_id}")

            if type(chunk.metadata.get("chapter")) is not int:
                raise ValueError("Each chunk requires an integer chapter")

            metadata = dict(chunk.metadata)
            metadata.update(
                {
                    "document_id": chunk.document_id,
                    "source": chunk.source,
                    "page": chunk.page,
                }
            )

            vector_text = "[" + ",".join(str(float(value)) for value in vector) + "]"

            rows.append(
                (
                    strategy,
                    chunk.chunk_id,
                    chunk.document_id,
                    chunk.source,
                    chunk.page,
                    chunk.text,
                    Jsonb(metadata),
                    vector_text,
                )
            )

        # Inserts, updates and obsolete-chunk removal are one transaction.
        with psycopg.connect(self.database_url) as conn:
            # Serialize writers to this small lab table during snapshot updates.
            conn.execute("LOCK TABLE day06_eg2_chunks IN SHARE ROW EXCLUSIVE MODE")

            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO day06_eg2_chunks (
                        strategy, chunk_id, document_id, source,
                        page, text, metadata, embedding
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                    ON CONFLICT (strategy, chunk_id)
                    DO UPDATE SET
                        document_id = EXCLUDED.document_id,
                        source = EXCLUDED.source,
                        page = EXCLUDED.page,
                        text = EXCLUDED.text,
                        metadata = EXCLUDED.metadata,
                        embedding = EXCLUDED.embedding
                """,
                    rows,
                )

            conn.execute(
                """
                DELETE FROM day06_eg2_chunks
                WHERE strategy = %s
                  AND NOT (chunk_id = ANY(%s::text[]))
            """,
                (strategy, ids),
            )

    def search(
        self,
        strategy: str,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if top_k < 1:
            raise ValueError("top_k must be positive")

        if len(query_vector) != self.dimensions:
            raise ValueError("Wrong query vector dimensions")

        if not all(math.isfinite(value) for value in query_vector):
            raise ValueError("Query vector contains NaN or infinity")

        if not any(value != 0 for value in query_vector):
            raise ValueError("Query vector must not be zero")

        filters = dict(filters or {})
        allowed_filters = {"chapter", "chapter_title", "document_id", "source", "page"}

        unknown = set(filters) - allowed_filters
        if unknown:
            raise ValueError(f"Unsupported filters: {sorted(unknown)}")

        for field in ("chapter", "page"):
            if field in filters and type(filters[field]) is not int:
                raise ValueError(f"{field} filter must be an integer")

        vector_text = "[" + ",".join(str(float(value)) for value in query_vector) + "]"

        with psycopg.connect(
            self.database_url,
            row_factory=dict_row,
        ) as conn:
            hits = conn.execute(
                """
                SELECT
                    chunk_id,
                    text,
                    metadata,
                    1 - (embedding <=> %s::vector) AS score
                FROM day06_eg2_chunks
                WHERE strategy = %s
                  AND metadata @> %s::jsonb
                ORDER BY
                    embedding <=> %s::vector,
                    chunk_id
                LIMIT %s
            """,
                (
                    vector_text,
                    strategy,
                    Jsonb(filters),
                    vector_text,
                    top_k,
                ),
            ).fetchall()

        return hits
