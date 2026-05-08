from __future__ import annotations

import abc
import hashlib
from dataclasses import dataclass


class AbstractEmbeddingsClient(abc.ABC):
    @abc.abstractmethod
    def embed_text(self, *, text: str) -> list[float]:  # pragma: no cover
        raise NotImplementedError


@dataclass(frozen=True)
class DeterministicEmbeddingsClient(AbstractEmbeddingsClient):
    """
    Deterministic, dependency-free embeddings suitable for development/tests.

    This is not semantically meaningful like real embeddings, but it enables the full
    pgvector pipeline (storage + ANN index + distance queries) end-to-end.
    """

    dim: int = 64

    def embed_text(self, *, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        # Expand to dim floats by re-hashing with a counter.
        out: list[float] = []
        counter = 0
        while len(out) < self.dim:
            h = hashlib.sha256(digest + counter.to_bytes(2, "big")).digest()
            for b in h:
                out.append((b / 255.0) * 2.0 - 1.0)
                if len(out) >= self.dim:
                    break
            counter += 1
        return out

