from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from eventflow.adapters.embeddings_client import DeterministicEmbeddingsClient
from eventflow.adapters.repository import CommunityEventEmbedding
from eventflow.adapters.orm import start_mappers
from eventflow.config import get_settings
from eventflow.service_layer.unit_of_work import SqlAlchemyUnitOfWork


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    if not settings.effective_db_url:
        raise RuntimeError("DB_URL is required for community_embeddings_worker")
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is required for community_embeddings_worker")

    start_mappers()
    engine = create_engine(settings.effective_db_url, future=True)
    session_factory = sessionmaker(bind=engine, future=True)
    uow = SqlAlchemyUnitOfWork(session_factory)

    embedder = DeterministicEmbeddingsClient(dim=64)

    r = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe("community_event.upserted")

    for msg in pubsub.listen():
        if msg.get("type") != "message":
            continue
        payload = json.loads(msg["data"])
        community_event_id = UUID(payload["community_event_id"])

        with uow:
            evt = uow.community_events.get(community_event_id=community_event_id)
            if evt is None:
                uow.commit()
                continue

            text = " ".join([evt.title, evt.venue, evt.description or ""]).strip()
            vec = embedder.embed_text(text=text)
            emb = CommunityEventEmbedding(
                community_event_id=evt.id,
                embedding=_vector_literal(vec),
                embedding_model="deterministic-64",
                embedded_at=datetime.now(timezone.utc),
            )
            uow.community_event_embeddings.upsert(emb)
            uow.commit()


if __name__ == "__main__":
    main()

