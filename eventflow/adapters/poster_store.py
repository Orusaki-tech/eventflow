from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4


@dataclass(frozen=True)
class StoredPoster:
    poster_id: UUID
    content_type: str
    image_bytes: bytes


class PosterStore:
    """
    Durable poster storage using the local filesystem.

    Intended for Docker volume mounting in prod.
    """

    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir).expanduser().resolve()
        self._base.mkdir(parents=True, exist_ok=True)

    def _paths(self, poster_id: UUID) -> tuple[Path, Path]:
        # store bytes + content-type sidecar
        b = self._base / f"{poster_id}.bin"
        meta = self._base / f"{poster_id}.ct"
        return b, meta

    def put(self, *, content_type: str, image_bytes: bytes) -> UUID:
        poster_id = uuid4()
        b, meta = self._paths(poster_id)
        tmp_b = b.with_suffix(".bin.tmp")
        tmp_meta = meta.with_suffix(".ct.tmp")
        tmp_b.write_bytes(image_bytes)
        tmp_meta.write_text(content_type, encoding="utf-8")
        os.replace(tmp_b, b)
        os.replace(tmp_meta, meta)
        return poster_id

    def get(self, *, poster_id: UUID) -> StoredPoster | None:
        b, meta = self._paths(poster_id)
        if not b.exists() or not meta.exists():
            return None
        try:
            content_type = meta.read_text(encoding="utf-8").strip() or "application/octet-stream"
        except Exception:
            content_type = "application/octet-stream"
        try:
            image_bytes = b.read_bytes()
        except Exception:
            return None
        if not image_bytes:
            return None
        return StoredPoster(poster_id=poster_id, content_type=content_type, image_bytes=image_bytes)

