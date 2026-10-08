"""
Unit tests for the YouTube adapter.
All HTTP calls are mocked via respx — no real network calls.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from backend.collectors.base import CollectorConfig
from backend.collectors.youtube.adapter import YouTubeCollector


# ── Helpers ───────────────────────────────────────────────────────────────────

def _search_response(video_ids: list[str]) -> dict:
    return {
        "items": [
            {"id": {"videoId": vid, "kind": "youtube#video"}, "kind": "youtube#searchResult"}
            for vid in video_ids
        ]
    }


def _comment_response(
    comments: list[dict],
    next_page_token: str | None = None,
) -> dict:
    items = []
    for c in comments:
        items.append({
            "id": c.get("thread_id", "thread_001"),
            "snippet": {
                "totalReplyCount": 0,
                "topLevelComment": {
                    "id": c["id"],
                    "snippet": {
                        "textDisplay": c["text"],
                        "textOriginal": c["text"],
                        "publishedAt": c.get("published_at", "2023-06-01T10:00:00Z"),
                        "likeCount": c.get("likes", 5),
                        "authorChannelId": {"value": c.get("channel_id", "UC_test_channel")},
                    },
                },
            },
        })
    result = {"items": items}
    if next_page_token:
        result["nextPageToken"] = next_page_token
    return result


# ── Credential checks ─────────────────────────────────────────────────────────

def test_youtube_unavailable_when_no_key():
    with patch("backend.collectors.youtube.adapter.get_settings") as mock_settings:
        mock_settings.return_value.youtube_configured = False
        collector = YouTubeCollector()
        assert collector.is_available() is False


def test_youtube_available_when_key_present():
    with patch("backend.collectors.youtube.adapter.get_settings") as mock_settings:
        mock_settings.return_value.youtube_configured = True
        mock_settings.return_value.youtube_api_key = "FAKE_KEY"
        collector = YouTubeCollector()
        assert collector.is_available() is True


@pytest.mark.asyncio
async def test_youtube_collect_yields_nothing_without_key():
    """collect() must yield nothing (not crash) when API key is missing."""
    with patch("backend.collectors.youtube.adapter.get_settings") as mock_settings:
        mock_settings.return_value.youtube_configured = False
        mock_settings.return_value.author_hash_salt = "test_salt"
        mock_settings.return_value.default_max_records = 10
        collector = YouTubeCollector()
        config = CollectorConfig(keywords=["battery"], max_records=10)
        records = [r async for r in collector.collect(config)]
        assert records == []


# ── Normal collection ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
@respx.mock
async def test_youtube_collects_comment():
    """A mocked YouTube API response yields one comment record."""
    settings = MagicMock()
    settings.youtube_configured = True
    settings.youtube_api_key = "FAKE_KEY"
    settings.author_hash_salt = "test_salt"
    settings.default_max_records = 10
    settings.youtube_quota_buffer = 500

    respx.get(url__contains="youtube.googleapis.com/youtube/v3/search").mock(
        return_value=httpx.Response(200, json=_search_response(["vid_abc123"]))
    )
    respx.get(url__contains="youtube.googleapis.com/youtube/v3/commentThreads").mock(
        return_value=httpx.Response(
            200,
            json=_comment_response([
                {
                    "id": "cmt_001",
                    "thread_id": "thread_001",
                    "text": "Great battery life in winter!",
                    "published_at": "2023-06-01T10:00:00Z",
                    "channel_id": "UC_test_channel_001",
                }
            ]),
        )
    )

    with patch("backend.collectors.youtube.adapter.get_settings", return_value=settings):
        collector = YouTubeCollector()
        config = CollectorConfig(keywords=["EV battery"], max_records=10)
        records = [r async for r in collector.collect(config)]

    assert len(records) == 1
    r = records[0]
    assert r.source == "youtube"
    assert r.source_record_id == "comment_cmt_001"
    assert r.text == "Great battery life in winter!"
    assert r.metadata["video_id"] == "vid_abc123"
    assert r.metadata["keyword"] == "EV battery"


@pytest.mark.asyncio
@respx.mock
async def test_youtube_author_hashed():
    """Channel ID is hashed, not stored raw."""
    settings = MagicMock()
    settings.youtube_configured = True
    settings.youtube_api_key = "FAKE_KEY"
    settings.author_hash_salt = "test_salt"
    settings.default_max_records = 10
    settings.youtube_quota_buffer = 500

    respx.get(url__contains="search").mock(
        return_value=httpx.Response(200, json=_search_response(["vid_xyz"]))
    )
    respx.get(url__contains="commentThreads").mock(
        return_value=httpx.Response(
            200,
            json=_comment_response([
                {"id": "cmt_hash_test", "thread_id": "t_hash", "text": "Comment text",
                 "channel_id": "UC_REAL_CHANNEL_ID"}
            ]),
        )
    )

    with patch("backend.collectors.youtube.adapter.get_settings", return_value=settings):
        collector = YouTubeCollector()
        config = CollectorConfig(keywords=["charging"], max_records=10)
        records = [r async for r in collector.collect(config)]

    assert len(records) == 1
    assert records[0].author_id_hash != "UC_REAL_CHANNEL_ID"
    assert len(records[0].author_id_hash) == 64


@pytest.mark.asyncio
@respx.mock
async def test_youtube_search_error_continues():
    """A search failure for one keyword should not stop other keywords."""
    settings = MagicMock()
    settings.youtube_configured = True
    settings.youtube_api_key = "FAKE_KEY"
    settings.author_hash_salt = "test_salt"
    settings.default_max_records = 10
    settings.youtube_quota_buffer = 500

    call_count = 0

    def search_side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(500, json={"error": "internal"})
        return httpx.Response(200, json=_search_response(["vid_good"]))

    respx.get(url__contains="search").mock(side_effect=search_side_effect)
    respx.get(url__contains="commentThreads").mock(
        return_value=httpx.Response(
            200,
            json=_comment_response([
                {"id": "cmt_good", "thread_id": "t_good", "text": "Good comment"}
            ]),
        )
    )

    with patch("backend.collectors.youtube.adapter.get_settings", return_value=settings):
        collector = YouTubeCollector()
        config = CollectorConfig(keywords=["bad_keyword", "good_keyword"], max_records=10)
        records = [r async for r in collector.collect(config)]

    assert any(r.source_record_id == "comment_cmt_good" for r in records)


@pytest.mark.asyncio
@respx.mock
async def test_youtube_stops_on_quota_exhaustion():
    """When quota buffer is reached, collection stops gracefully."""
    settings = MagicMock()
    settings.youtube_configured = True
    settings.youtube_api_key = "FAKE_KEY"
    settings.author_hash_salt = "test_salt"
    settings.default_max_records = 100
    settings.youtube_quota_buffer = 500

    respx.get(url__contains="search").mock(
        return_value=httpx.Response(
            403,
            json={
                "error": {
                    "errors": [{"reason": "quotaExceeded"}],
                    "message": "Quota exceeded",
                }
            },
        )
    )

    with patch("backend.collectors.youtube.adapter.get_settings", return_value=settings):
        collector = YouTubeCollector()
        # Manually set quota near limit so buffer check triggers
        collector._quota_used = 9_600  # only 400 left, buffer is 500
        config = CollectorConfig(keywords=["battery"], max_records=10)
        records = [r async for r in collector.collect(config)]

    # Should have yielded nothing and not crashed
    assert records == []


@pytest.mark.asyncio
@respx.mock
async def test_youtube_comments_disabled_skipped():
    """Videos with comments disabled should be skipped, not error."""
    settings = MagicMock()
    settings.youtube_configured = True
    settings.youtube_api_key = "FAKE_KEY"
    settings.author_hash_salt = "test_salt"
    settings.default_max_records = 10
    settings.youtube_quota_buffer = 500

    respx.get(url__contains="search").mock(
        return_value=httpx.Response(200, json=_search_response(["vid_no_comments"]))
    )
    respx.get(url__contains="commentThreads").mock(
        return_value=httpx.Response(
            403,
            json={"error": {"errors": [{"reason": "commentsDisabled"}]}},
        )
    )

    with patch("backend.collectors.youtube.adapter.get_settings", return_value=settings):
        collector = YouTubeCollector()
        config = CollectorConfig(keywords=["charging"], max_records=10)
        records = [r async for r in collector.collect(config)]

    assert records == []
