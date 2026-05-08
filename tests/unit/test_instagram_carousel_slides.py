from __future__ import annotations

import pytest

from eventflow.domain.exceptions import InvariantViolation
from eventflow.entrypoints.api.schemas import ShareInstagramCarouselRequest
from eventflow.service_layer.handlers import _resolve_instagram_carousel_slide_indices


def test_default_slides_one_and_two_when_present():
    assert _resolve_instagram_carousel_slide_indices(requested=None, num_slides=10) == [1, 2]


def test_default_single_slide_carousel():
    assert _resolve_instagram_carousel_slide_indices(requested=None, num_slides=1) == [1]


def test_requested_deduped_sorted():
    assert _resolve_instagram_carousel_slide_indices(requested=[7, 3, 7], num_slides=10) == [3, 7]


def test_requested_single():
    assert _resolve_instagram_carousel_slide_indices(requested=[5], num_slides=10) == [5]


def test_out_of_range_raises():
    with pytest.raises(InvariantViolation, match="out of range"):
        _resolve_instagram_carousel_slide_indices(requested=[4], num_slides=3)


def test_more_than_two_indices_raises():
    with pytest.raises(InvariantViolation, match="At most"):
        _resolve_instagram_carousel_slide_indices(requested=[1, 2, 3], num_slides=10)


def test_share_instagram_carousel_request_empty_list_becomes_none():
    m = ShareInstagramCarouselRequest(url="https://www.instagram.com/p/abc/", carousel_slide_indices=[])
    assert m.carousel_slide_indices is None


def test_share_instagram_carousel_request_rejects_three_indices():
    with pytest.raises(ValueError, match="At most 2"):
        ShareInstagramCarouselRequest(
            url="https://www.instagram.com/p/abc/",
            carousel_slide_indices=[1, 2, 3],
        )
