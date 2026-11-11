"""Wheel class comes from a recognized model, never from body style."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError

from backend.api.dependencies import get_session
from backend.api.domain_config import _load_yaml
from backend.main import app
from backend.models.review import ProcessingStatus, Review
from backend.models.review_aspect import ReviewAspect
from backend.processing.entity import EntityExtractor
from tests.conftest import make_raw_review


def _extractor() -> EntityExtractor:
    config = _load_yaml("ev")
    return EntityExtractor(config["gazetteer"], config["vehicle_categories"])


def test_ola_s1_pro_is_2w():
    result = _extractor().extract("Ola S1 Pro range dropped after a year")
    assert result.manufacturer == "Ola"
    assert result.vehicle_model == "S1_Pro"
    assert result.vehicle_category == "2W"
    assert result.vehicle_type is None


def test_nexon_ev_suv_keeps_body_style_and_4w():
    result = _extractor().extract("Tata Nexon EV SUV range is lower than claimed")
    assert result.manufacturer == "Tata"
    assert result.vehicle_model == "Nexon_EV"
    assert result.vehicle_category == "4W"
    assert result.vehicle_type == "SUV"


def test_bare_nexon_is_not_classified():
    result = _extractor().extract("Tata Nexon range fell in the city")
    assert result.manufacturer == "Tata"
    assert result.vehicle_model is None
    assert result.vehicle_category is None


def test_mahindra_model_chooses_the_class():
    extractor = _extractor()
    treo = extractor.extract("Mahindra Treo stopped charging")
    assert treo.manufacturer == "Mahindra"
    assert treo.vehicle_model == "Treo"
    assert treo.vehicle_category == "3W"
    xuv = extractor.extract("Mahindra XUV400 fast charging works")
    assert xuv.vehicle_model == "XUV400"
    assert xuv.vehicle_category == "4W"


def test_body_style_alone_does_not_assign_a_class():
    result = _extractor().extract("The SUV range dropped on the highway")
    assert result.manufacturer is None
    assert result.vehicle_model is None
    assert result.vehicle_type == "SUV"
    assert result.vehicle_category is None


def test_generic_terms_are_not_models():
    extractor = _extractor()
    for text in ("the auto range is poor", "a rickshaw blocked the charger", "the seal was broken"):
        result = extractor.extract(text)
        assert result.vehicle_model is None
        assert result.vehicle_category is None


def test_known_car_model_is_4w_and_brand_alone_is_null():
    extractor = _extractor()
    tesla = extractor.extract("Tesla Model 3 charging was fast")
    assert tesla.vehicle_model == "Model_3"
    assert tesla.vehicle_category == "4W"
    brand = extractor.extract("Hyundai is great")
    assert brand.manufacturer == "Hyundai"
    assert brand.vehicle_model is None
    assert brand.vehicle_category is None


def _override(session):
    async def _yield():
        yield session
    return _yield


@pytest.mark.asyncio
async def test_vehicle_category_filter_does_not_use_body_style(db_session):
    ola_raw = await make_raw_review(db_session, source="reddit", source_record_id="cat-ola", synthetic=False, ingestion_status="processed")
    nexon_raw = await make_raw_review(db_session, source="reddit", source_record_id="cat-nexon", synthetic=False, ingestion_status="processed")
    suv_raw = await make_raw_review(db_session, source="youtube", source_record_id="cat-suv", synthetic=False, ingestion_status="processed")
    rows = [
        Review(
            raw_review_id=ola_raw.id, source="reddit", source_record_id="cat-ola",
            published_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
            manufacturer="Ola", vehicle_model="S1_Pro", vehicle_category="2W",
            sentiment_label="negative", processing_status=ProcessingStatus.done.value,
            is_duplicate=False, synthetic=False, engagement_count=0,
        ),
        Review(
            raw_review_id=nexon_raw.id, source="reddit", source_record_id="cat-nexon",
            published_at=datetime(2024, 5, 1, tzinfo=timezone.utc),
            manufacturer="Tata", vehicle_model="Nexon_EV", vehicle_type="SUV", vehicle_category="4W",
            sentiment_label="negative", processing_status=ProcessingStatus.done.value,
            is_duplicate=False, synthetic=False, engagement_count=0,
        ),
        Review(
            raw_review_id=suv_raw.id, source="youtube", source_record_id="cat-suv",
            published_at=datetime(2024, 4, 1, tzinfo=timezone.utc),
            vehicle_type="SUV", vehicle_category=None,
            sentiment_label="neutral", processing_status=ProcessingStatus.done.value,
            is_duplicate=False, synthetic=False, engagement_count=0,
        ),
    ]
    db_session.add_all(rows)
    await db_session.flush()
    db_session.add(ReviewAspect(
        review_id=rows[0].review_id, category="range", aspect="range_loss",
        sentiment_label="negative", matched_text="range dropped",
    ))
    await db_session.flush()

    app.dependency_overrides[get_session] = _override(db_session)
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            two_w = await client.get("/api/reviews", params={"vehicle_category": "2W"})
            assert two_w.status_code == 200
            assert two_w.json()["total"] == 1
            assert two_w.json()["items"][0]["vehicle_category"] == "2W"
            assert two_w.json()["items"][0]["vehicle_model"] == "S1_Pro"

            four_w = await client.get("/api/sentiment/summary", params={"vehicle_category": "4W"})
            assert four_w.status_code == 200
            assert four_w.json()["overall"]["total"] == 1

            body = await client.get("/api/reviews", params={"vehicle_type": "SUV"})
            assert body.status_code == 200
            assert body.json()["total"] == 2

            combined = await client.get(
                "/api/reviews",
                params={"manufacturer": "Tata", "vehicle_category": "4W"},
            )
            assert combined.status_code == 200
            assert combined.json()["total"] == 1
            missed = await client.get(
                "/api/reviews",
                params={"manufacturer": "Tata", "vehicle_category": "2W"},
            )
            assert missed.status_code == 200
            assert missed.json()["total"] == 0

            invalid = await client.get("/api/sentiment/trend", params={"vehicle_category": "scooter"})
            assert invalid.status_code == 200
            assert invalid.json()["points"] == []

            aspects = await client.get("/api/aspects", params={"vehicle_category": "2w"})
            assert aspects.status_code == 200
            assert [row["aspect"] for row in aspects.json()["aspects"]] == ["range_loss"]

            detail = await client.get("/api/aspects/range_loss", params={"vehicle_category": "4W"})
            assert detail.status_code == 404
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_invalid_vehicle_category_is_rejected(db_session):
    raw = await make_raw_review(db_session, source="reddit", source_record_id="cat-bad", synthetic=False)
    db_session.add(Review(
        raw_review_id=raw.id, source="reddit", source_record_id="cat-bad",
        vehicle_category="SUV", processing_status=ProcessingStatus.done.value,
        is_duplicate=False, synthetic=False, engagement_count=0,
    ))
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()
