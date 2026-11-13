"""Choose a real embedding provider (API or local) and implement this contract."""

from typing import Protocol

import numpy as np
import torch
from sentence_transformers import SentenceTransformer


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class MyEmbedder:
    """TODO: implement a provider adapter; do not silently fall back to mock vectors."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.dimensions = 768

        print(
            f"Loading real embedding model: {self.model_name}",
            flush=True,
        )

        self.model = SentenceTransformer(
            self.model_name,
            device="cpu",
            config_kwargs={
                "vision_config": None,
                "audio_config": None,
            },
            model_kwargs={
                "torch_dtype": torch.float32,
            },
        )

        actual_dimensions = self.model.get_embedding_dimension()

        if actual_dimensions != self.dimensions:
            raise ValueError(
                f"Expected {self.dimensions} dimensions, " f"got {actual_dimensions}"
            )

        print(
            f"Model loaded | device=cpu | dimensions={self.dimensions}",
            flush=True,
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        if any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("Documents must be non-empty strings")

        vectors = self.model.encode(
            texts,
            prompt_name="Document",
            batch_size=8,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > 8,
        )

        vectors = np.asarray(vectors, dtype=np.float32)

        if vectors.shape != (len(texts), self.dimensions):
            raise ValueError(f"Unexpected document vector shape: {vectors.shape}")

        if not np.isfinite(vectors).all():
            raise ValueError("Document vectors contain NaN or infinity")

        norms = np.linalg.norm(vectors, axis=1)
        if not np.allclose(norms, 1.0, atol=1e-4):
            raise ValueError("Document vectors are not unit normalized")

        return vectors.tolist()

    def embed_query(self, question: str) -> list[float]:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Question must be a non-empty string")

        vectors = self.model.encode(
            [question],
            prompt_name="SearchQuery",
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        vectors = np.asarray(vectors, dtype=np.float32)

        if vectors.shape != (1, self.dimensions):
            raise ValueError(f"Unexpected query vector shape: {vectors.shape}")

        vector = vectors[0]

        if not np.isfinite(vector).all():
            raise ValueError("Query vector contains NaN or infinity")

        if not np.isclose(np.linalg.norm(vector), 1.0, atol=1e-4):
            raise ValueError("Query vector is not unit normalized")

        return vector.tolist()
