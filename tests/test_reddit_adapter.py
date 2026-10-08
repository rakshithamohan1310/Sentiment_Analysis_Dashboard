"""
Unit tests for the Reddit adapter.
All PRAW/network calls are mocked — no real API calls made.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.collectors.base import CollectorConfig
from backend.collectors.reddit.adapter import RedditCollector


# ── Helpers to build fake PRAW objects ───────────────────────────────────────

def _fake_submission(
    post_id: str = "abc123",
    title: str = "Test EV post",
    selftext: str = "Great battery life!",
    subreddit: str = "electricvehicles",
    score: int = 42,
    upvote_ratio: float = 0.95,
    created_utc: float = 1_700_000_000.0,
    author: str = "testuser",
    num_comments: int = 5,
    permalink: str = "/r/electricvehicles/comments/abc123/test_ev_post/",
    is_self: bool = True,
) -> MagicMock:
    sub = MagicMock()
    sub.id = post_id
    sub.title = title
    sub.selftext = selftext
    sub.score = score
    sub.upvote_ratio = upvote_ratio
    sub.created_utc = created_utc
    sub.num_comments = num_comments
    sub.permalink = permalink
    sub.url = f"https://www.reddit.com{permalink}"
    sub.is_self = is_self
    sub.link_flair_text = None
    sub.subreddit.display_name = subreddit
    sub.author = MagicMock()
    sub.author.name = author

    # Stub out comments so _fetch_top_comments works
    sub.comments = MagicMock()
    sub.comments.replace_more = MagicMock()
    sub.comments.list.return_value = []
    return sub


def _fake_comment(
    comment_id: str = "cmt001",
    body: str = "Very helpful comment about charging",
    subreddit: str = "electricvehicles",
    score: int = 10,
    created_utc: float = 1_700_010_000.0,
    author: str = "commenter1",
    post_id: str = "abc123",
    permalink: str = "/r/electricvehicles/comments/abc123/test_ev_post/cmt001",
) -> MagicMock:
    import praw.models  # imported here so mock doesn't need it at module level

    cmt = MagicMock(spec=praw.models.Comment)
    cmt.id = comment_id
    cmt.body = body
    cmt.score = score
    cmt.created_utc = created_utc
    cmt.permalink = permalink
    cmt.parent_id = f"t3_{post_id}"  # top-level comment
    cmt.subreddit.display_name = subreddit
    cmt.author = MagicMock()
    cmt.author.name = author
    return cmt


# ── Credential checks ─────────────────────────────────────────────────────────

def test_reddit_unavailable_when_no_credentials():
    with patch("backend.collectors.reddit.adapter.get_settings") as mock_settings:
        mock_settings.return_value.reddit_configured = False
        collector = RedditCollector()
        assert collector.is_available() is False


def test_reddit_available_when_credentials_present():
    with patch("backend.collectors.reddit.adapter.get_settings") as mock_settings:
        mock_settings.return_value.reddit_configured = True
        mock_settings.return_value.reddit_client_id = "fake_id"
        mock_settings.return_value.reddit_client_secret = "fake_secret"
        mock_settings.return_value.reddit_user_agent = "TestAgent/1.0"
        collector = RedditCollector()
        assert collector.is_available() is True


@pytest.mark.asyncio
async def test_reddit_collect_yields_nothing_when_no_credentials():
    """collect() must yield nothing (not crash) when credentials are missing."""
    with patch("backend.collectors.reddit.adapter.get_settings") as mock_settings:
        mock_settings.return_value.reddit_configured = False
        mock_settings.return_value.author_hash_salt = "test_salt"
        mock_settings.return_value.default_max_records = 10
        collector = RedditCollector()
        config = CollectorConfig(keywords=["battery"], max_records=10)
        records = [r async for r in collector.collect(config)]
        assert records == []


# ── Normal collection ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reddit_collects_post():
    """A mocked PRAW response yields one post record."""
    submission = _fake_submission()

    with (
        patch("backend.collectors.reddit.adapter.get_settings") as mock_settings,
        patch("backend.collectors.reddit.adapter._make_praw_reddit") as mock_praw,
        patch("asyncio.to_thread") as mock_thread,
    ):
        settings = MagicMock()
        settings.reddit_configured = True
        settings.author_hash_salt = "test_salt"
        settings.default_max_records = 10
        mock_settings.return_value = settings

        mock_praw.return_value = MagicMock()

        # to_thread: first call → search results, second call → comment list
        mock_thread.side_effect = [
            [submission],      # _fetch_posts
            [],                # _fetch_top_comments
        ]

        collector = RedditCollector()
        collector._reddit = mock_praw.return_value
        config = CollectorConfig(keywords=["battery"], subreddits=["electricvehicles"], max_records=10)
        records = [r async for r in collector.collect(config)]

    assert len(records) >= 1
    post = records[0]
    assert post.source == "reddit"
    assert post.source_record_id == "post_abc123"
    assert post.title == "Test EV post"
    assert post.metadata["subreddit"] == "electricvehicles"
    assert post.metadata["post_type"] == "submission"


@pytest.mark.asyncio
async def test_reddit_collects_top_level_comment():
    """Top-level comments are collected as separate records."""
    submission = _fake_submission()
    comment = _fake_comment()

    with (
        patch("backend.collectors.reddit.adapter.get_settings") as mock_settings,
        patch("backend.collectors.reddit.adapter._make_praw_reddit") as mock_praw,
        patch("asyncio.to_thread") as mock_thread,
    ):
        settings = MagicMock()
        settings.reddit_configured = True
        settings.author_hash_salt = "test_salt"
        settings.default_max_records = 10
        mock_settings.return_value = settings

        mock_thread.side_effect = [
            [submission],   # _fetch_posts
            [comment],      # _fetch_top_comments
        ]

        collector = RedditCollector()
        collector._reddit = mock_praw.return_value
        config = CollectorConfig(keywords=["battery"], subreddits=["electricvehicles"], max_records=10)
        records = [r async for r in collector.collect(config)]

    record_ids = [r.source_record_id for r in records]
    assert "comment_cmt001" in record_ids

    cmt_record = next(r for r in records if r.source_record_id == "comment_cmt001")
    assert cmt_record.title is None
    assert cmt_record.text == "Very helpful comment about charging"
    assert cmt_record.metadata["post_type"] == "comment"


@pytest.mark.asyncio
async def test_reddit_author_hashed():
    """Author username is never stored, only its hash."""
    submission = _fake_submission(author="real_username_should_not_appear")

    with (
        patch("backend.collectors.reddit.adapter.get_settings") as mock_settings,
        patch("backend.collectors.reddit.adapter._make_praw_reddit") as mock_praw,
        patch("asyncio.to_thread") as mock_thread,
    ):
        settings = MagicMock()
        settings.reddit_configured = True
        settings.author_hash_salt = "test_salt"
        settings.default_max_records = 10
        mock_settings.return_value = settings

        mock_thread.side_effect = [[submission], []]
        collector = RedditCollector()
        collector._reddit = mock_praw.return_value
        config = CollectorConfig(keywords=["battery"], subreddits=["electricvehicles"], max_records=10)
        records = [r async for r in collector.collect(config)]

    assert len(records) >= 1
    assert records[0].author_id_hash != "real_username_should_not_appear"
    assert len(records[0].author_id_hash) == 64  # SHA-256 hex


@pytest.mark.asyncio
async def test_reddit_search_error_does_not_crash():
    """An API error for one keyword should log and continue, not abort."""
    with (
        patch("backend.collectors.reddit.adapter.get_settings") as mock_settings,
        patch("backend.collectors.reddit.adapter._make_praw_reddit") as mock_praw,
        patch("asyncio.to_thread") as mock_thread,
    ):
        settings = MagicMock()
        settings.reddit_configured = True
        settings.author_hash_salt = "test_salt"
        settings.default_max_records = 10
        mock_settings.return_value = settings

        # First keyword raises, second succeeds
        good_sub = _fake_submission(post_id="good001", title="Good post")
        mock_thread.side_effect = [
            ConnectionError("Network error"),  # keyword 1 fetch_posts fails
            [good_sub],                        # keyword 2 fetch_posts succeeds
            [],                               # keyword 2 fetch_top_comments
        ]

        collector = RedditCollector()
        collector._reddit = mock_praw.return_value
        config = CollectorConfig(
            keywords=["bad_keyword", "good_keyword"],
            subreddits=["electricvehicles"],
            max_records=10,
        )
        records = [r async for r in collector.collect(config)]

    # Should have collected the good keyword's result despite the first error
    assert any(r.source_record_id == "post_good001" for r in records)
