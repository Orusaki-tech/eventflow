from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from eventflow.adapters.repository import DevicePushToken, FakeDevicePushTokenRepository


def test_fake_push_token_repo_upsert_and_disable():
    user_id = uuid4()
    repo = FakeDevicePushTokenRepository()
    now = datetime.now(timezone.utc)

    tok = DevicePushToken(user_id=user_id, expo_push_token="ExponentPushToken[abc]", created_at=now, last_seen_at=now)
    saved = repo.upsert(tok)
    assert saved.id is not None
    assert len(repo.list_active(user_id=user_id)) == 1

    repo.disable(token_id=saved.id, disabled_at=now)
    assert len(repo.list_active(user_id=user_id)) == 0

