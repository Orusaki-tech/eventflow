from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status

from eventflow.adapters.embeddings_client import DeterministicEmbeddingsClient
from eventflow.domain import commands
from eventflow.entrypoints.api.schemas import CommunityEventResponse, CommunityEventUpsertRequest
from eventflow.entrypoints.dependencies import get_current_user_id, get_session, get_uow
from eventflow.service_layer import messagebus, views


router = APIRouter(tags=["Discovery"])


def _vector_literal(vec: list[float]) -> str:
    # pgvector accepts '[1,2,3]' syntax.
    return "[" + ",".join(f"{x:.6f}" for x in vec) + "]"


@router.get("/discovery/feed", status_code=status.HTTP_200_OK)
async def discovery_feed(
    limit: int = Query(default=50, ge=1, le=200),
    session=Depends(get_session),
):
    if session is None:
        return []
    return views.list_community_events(session=session, limit=limit)


@router.get("/discovery/search", status_code=status.HTTP_200_OK)
async def discovery_search(
    q: str = Query(min_length=1, max_length=2000),
    limit: int = Query(default=20, ge=1, le=50),
    session=Depends(get_session),
):
    if session is None:
        return []
    embedder = DeterministicEmbeddingsClient(dim=64)
    qvec = _vector_literal(embedder.embed_text(text=q))
    return views.search_community_events(session=session, query_vector=qvec, limit=limit)


@router.post("/discovery/community-events", status_code=status.HTTP_201_CREATED, response_model=CommunityEventResponse)
async def upsert_community_event(
    body: CommunityEventUpsertRequest,
    user_id=Depends(get_current_user_id),
    uow=Depends(get_uow),
):
    result = messagebus.handle(
        commands.UpsertCommunityEvent(
            user_id=user_id,
            source=body.source,
            title=body.title,
            start_time=body.start_time,
            venue=body.venue,
            description=body.description,
        ),
        uow,
    )
    return result

