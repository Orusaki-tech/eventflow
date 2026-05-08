from __future__ import annotations

import base64
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from eventflow.entrypoints.fastapi_app import create_app
from eventflow.entrypoints import dependencies
from eventflow.service_layer.unit_of_work import FakeUnitOfWork


def test_capture_and_confirm_flow_in_memory():
    app = create_app()

    fixed_user = uuid4()
    uow = FakeUnitOfWork()
    app.dependency_overrides[dependencies.get_uow] = lambda: uow
    app.dependency_overrides[dependencies.get_current_user_id] = lambda: fixed_user

    client = TestClient(app)

    img = base64.b64encode(b"fake-image-bytes").decode("ascii")
    r1 = client.post("/api/v1/capture/image", json={"image_base64": img})
    assert r1.status_code == 201
    draft_id = UUID(r1.json()["draft_id"])

    r2 = client.post(f"/api/v1/events/confirm/{draft_id}")
    assert r2.status_code == 201
    UUID(r2.json()["event_id"])

