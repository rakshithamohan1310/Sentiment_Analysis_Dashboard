"""Analytics endpoints honour the same optional review filters."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.dependencies import get_session
from backend.main import app
from backend.models.review import ProcessingStatus, Review
from backend.models.review_aspect import ReviewAspect
from tests.conftest import make_raw_review


def _override(session):
    async def _yield():
        yield session
    return _yield


async def _seed(session):
    reddit_raw = await make_raw_review(
        session,
        source="reddit",
        source_record_id="analytics-reddit-1",
        synthetic=False,
        ingestion_status="processed",
    )
    youtube_raw = await make_raw_review(
        session,
        source="youtube",
        source_record_id="analytics-youtube-1",
        synthetic=False,
        ingestion_status="processed",
    )
    reddit = Review(
        raw_review_id=reddit_raw.id,
        source="reddit",
        source_record_id="analytics-reddit-1",
        published_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        review_text="Battery health dropped after a year.",
        sentiment_label="negative",
        sentiment_confidence=0.8,
        vehicle_type="SUV",
        processing_status=ProcessingStatus.done.value,
        is_duplicate=False,
        synthetic=False,
        engagement_count=3,
    )
    youtube = Review(
        raw_review_id=youtube_raw.id,
        source="youtube",
        source_record_id="analytics-youtube-1",
        published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        review_text="Charging was fast.",
        sentiment_label="positive",
        sentiment_confidence=0.7,
        vehicle_type="Sedan",
        processing_status=ProcessingStatus.done.value,
        is_duplicate=False,
        synthetic=False,
        engagement_count=1,
    )
    session.add_all([reddit, youtube])
    await session.flush()
    session.add(ReviewAspect(
        review_id=reddit.review_id,
        category="battery",
        aspect="battery_health",
        sentiment_label="negative",
        confidence=0.8,
        matched_text="Battery health dropped",
    ))
    await session.flush()


@pytest.mark.asyncio
async def test_summary_trend_and_aspects_respect_existing_filters(db_session):
    await _seed(db_session)
    app.dependency_overrides[get_session] = _override(db_session)
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            summary = await client.get("/api/sentiment/summary")
            assert summary.status_code == 200
            assert summary.json()["overall"]["total"] == 2

            reddit_only = await client.get("/api/sentiment/summary", params={"source": "reddit"})
            assert reddit_only.status_code == 200
            body = reddit_only.json()
            assert body["overall"]["total"] == 1
            assert body["overall"]["negative_count"] == 1
            assert list(body["by_source"]) == ["reddit"]

            dated = await client.get(
                "/api/sentiment/trend",
                params={"date_from": "2024-05-01T00:00:00Z", "granularity": "month"},
            )
            assert dated.status_code == 200
            points = dated.json()["points"]
            assert len(points) == 1
            assert points[0]["period"] == "2024-06"
            assert points[0]["total"] == 1

            aspects = await client.get("/api/aspects", params={"source": "reddit", "sentiment": "negative"})
            assert aspects.status_code == 200
            names = [row["aspect"] for row in aspects.json()["aspects"]]
            assert names == ["battery_health"]

            hidden = await client.get("/api/aspects", params={"sentiment": "positive"})
            assert hidden.status_code == 200
            assert hidden.json()["aspects"] == []

            typed = await client.get("/api/reviews", params={"vehicle_type": "SUV"})
            assert typed.status_code == 200
            payload = typed.json()
            assert payload["total"] == 1
            assert payload["items"][0]["source"] == "reddit"
            assert payload["items"][0]["aspects"][0]["aspect"] == "battery_health"
    finally:
        app.dependency_overrides.clear()


def _review(raw, **kwargs) -> Review:
    values = dict(
        raw_review_id=raw.id,
        source=raw.source,
        source_record_id=raw.source_record_id,
        published_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        review_text="Stored review",
        sentiment_label="neutral",
        processing_status=ProcessingStatus.done.value,
        is_duplicate=False,
        synthetic=False,
        engagement_count=0,
    )
    values.update(kwargs)
    return Review(**values)


async def _seed_entities(session):
    specs = [
        ("reddit", "mfr-y", "Tesla", "Model_Y", "SUV", "negative", datetime(2024, 6, 1, tzinfo=timezone.utc), False),
        ("youtube", "mfr-3", "Tesla", "Model_3", "Sedan", "positive", datetime(2024, 3, 1, tzinfo=timezone.utc), False),
        ("reddit", "mfr-s", "Tesla", "Model_S", "Sedan", "neutral", datetime(2024, 1, 1, tzinfo=timezone.utc), False),
        ("reddit", "mfr-ioniq", "Hyundai", "Ioniq5", None, "positive", datetime(2024, 4, 1, tzinfo=timezone.utc), False),
        ("reddit", "mfr-unknown", None, None, None, "negative", datetime(2024, 5, 1, tzinfo=timezone.utc), False),
        ("reddit", "mfr-dup", "Tesla", "Model_Y", "SUV", "negative", datetime(2024, 6, 2, tzinfo=timezone.utc), True),
    ]
    rows = []
    for source, record_id, manufacturer, model, body, sentiment, published, duplicate in specs:
        raw = await make_raw_review(
            session,
            source=source,
            source_record_id=record_id,
            synthetic=False,
            ingestion_status="processed",
        )
        rows.append(_review(
            raw,
            published_at=published,
            manufacturer=manufacturer,
            vehicle_model=model,
            vehicle_type=body,
            sentiment_label=sentiment,
            is_duplicate=duplicate,
        ))
    session.add_all(rows)
    await session.flush()
    session.add(ReviewAspect(
        review_id=rows[0].review_id,
        category="battery",
        aspect="battery_health",
        sentiment_label="negative",
        confidence=0.8,
        matched_text="Battery health dropped",
    ))
    session.add(ReviewAspect(
        review_id=rows[3].review_id,
        category="charging",
        aspect="charging_speed",
        sentiment_label="positive",
        confidence=0.6,
        matched_text="Charging was fast",
    ))
    await session.flush()


@pytest.mark.asyncio
async def test_manufacturer_and_model_filters_across_analytics(db_session):
    await _seed_entities(db_session)
    app.dependency_overrides[get_session] = _override(db_session)
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            summary = await client.get("/api/sentiment/summary", params={"manufacturer": "Tesla"})
            assert summary.status_code == 200
            body = summary.json()["overall"]
            assert body["total"] == 3
            assert body["positive_count"] == 1
            assert body["neutral_count"] == 1
            assert body["negative_count"] == 1
            assert body["positive_pct"] == 33.33
            assert body["negative_pct"] == 33.33

            combined = await client.get(
                "/api/sentiment/summary",
                params={"manufacturer": "Tesla", "vehicle_model": "Model_3", "source": "youtube"},
            )
            assert combined.status_code == 200
            assert combined.json()["overall"]["total"] == 1
            assert combined.json()["overall"]["positive_count"] == 1

            mismatch = await client.get(
                "/api/sentiment/summary",
                params={"manufacturer": "Tesla", "vehicle_model": "Model_3", "source": "reddit"},
            )
            assert mismatch.status_code == 200
            assert mismatch.json()["overall"]["total"] == 0

            trend = await client.get(
                "/api/sentiment/trend",
                params={"vehicle_model": "Model_Y", "granularity": "month"},
            )
            assert trend.status_code == 200
            points = trend.json()["points"]
            assert len(points) == 1
            assert points[0]["period"] == "2024-06"
            assert points[0]["negative_count"] == 1

            spread = await client.get(
                "/api/sentiment/trend",
                params={"manufacturer": "Tesla", "granularity": "month"},
            )
            assert spread.status_code == 200
            periods = [(point["period"], point["total"]) for point in spread.json()["points"]]
            assert periods == [("2024-01", 1), ("2024-03", 1), ("2024-06", 1)]

            aspects = await client.get(
                "/api/aspects",
                params={"manufacturer": "Tesla", "vehicle_model": "Model_Y"},
            )
            assert aspects.status_code == 200
            assert [row["aspect"] for row in aspects.json()["aspects"]] == ["battery_health"]
            assert aspects.json()["aspects"][0]["mention_count"] == 1

            other = await client.get("/api/aspects", params={"manufacturer": "Hyundai"})
            assert other.status_code == 200
            assert [row["aspect"] for row in other.json()["aspects"]] == ["charging_speed"]

            unknown = await client.get("/api/sentiment/summary", params={"manufacturer": "NotABrand"})
            assert unknown.status_code == 200
            assert unknown.json()["overall"]["total"] == 0
            empty_aspects = await client.get("/api/aspects", params={"manufacturer": "NotABrand"})
            assert empty_aspects.status_code == 200
            assert empty_aspects.json()["aspects"] == []
            empty_trend = await client.get("/api/sentiment/trend", params={"vehicle_model": "NotAModel"})
            assert empty_trend.status_code == 200
            assert empty_trend.json()["points"] == []

            padded = await client.get("/api/sentiment/summary", params={"manufacturer": "  Tesla  "})
            assert padded.status_code == 200
            assert padded.json()["overall"]["total"] == 3
            blank = await client.get("/api/sentiment/summary", params={"manufacturer": "   "})
            assert blank.status_code == 200
            assert blank.json()["overall"]["total"] == 5

            too_long = await client.get("/api/reviews", params={"manufacturer": "x" * 200})
            assert too_long.status_code == 200
            assert too_long.json()["total"] == 0

            body_style = await client.get("/api/reviews", params={"vehicle_type": "SUV"})
            assert body_style.status_code == 200
            assert body_style.json()["total"] == 1
            category_word = await client.get("/api/reviews", params={"vehicle_type": "2W"})
            assert category_word.status_code == 200
            assert category_word.json()["total"] == 0

            page = await client.get(
                "/api/reviews",
                params={"manufacturer": "Tesla", "limit": 1, "offset": 1},
            )
            assert page.status_code == 200
            payload = page.json()
            assert payload["total"] == 3
            assert payload["limit"] == 1
            assert payload["offset"] == 1
            assert len(payload["items"]) == 1
            assert payload["items"][0]["vehicle_model"] == "Model_3"

            options = await client.get("/api/reviews/options")
            assert options.status_code == 200
            assert options.json()["manufacturers"] == ["Hyundai", "Tesla"]
            assert options.json()["vehicle_models"] == ["Ioniq5", "Model_3", "Model_S", "Model_Y"]

            narrowed = await client.get("/api/reviews/options", params={"manufacturer": "Tesla"})
            assert narrowed.status_code == 200
            assert narrowed.json()["manufacturers"] == ["Hyundai", "Tesla"]
            assert narrowed.json()["vehicle_models"] == ["Model_3", "Model_S", "Model_Y"]

            detail = await client.get("/api/aspects/battery_health", params={"manufacturer": "Hyundai"})
            assert detail.status_code == 404
            kept = await client.get("/api/aspects/battery_health", params={"manufacturer": "Tesla"})
            assert kept.status_code == 200
            assert kept.json()["summary"]["mention_count"] == 1
    finally:
        app.dependency_overrides.clear()
