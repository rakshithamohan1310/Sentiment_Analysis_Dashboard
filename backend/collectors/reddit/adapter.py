"""
Reddit adapter – collects posts and top-level comments via the official Reddit API (PRAW).

Privacy:
  - Author usernames are never stored. Only the SHA-256(salt + username) hash is kept.
  - Deleted/removed authors ("[deleted]", "[removed]") produce a None hash.
  - No private messages, DMs, or non-public content is collected.

Rate limits:
  - PRAW respects Reddit's OAuth2 rate limits automatically (60 req/min for script apps).
  - Tenacity provides exponential backoff on transient HTTP/network errors.
  - Sleep between items is handled by PRAW's built-in rate-limiter.

Missing credentials:
  - If REDDIT_CLIENT_ID or REDDIT_CLIENT_SECRET are absent, is_available() returns False
    and collect() yields nothing. No crash, no scraping fallback.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import AsyncIterator, Optional
import asyncio

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from backend.collectors.base import (
    CollectorConfig,
    RawRecord,
    ReviewCollector,
    hash_author_id,
    truncate_text,
)
from backend.config.settings import get_settings

logger = logging.getLogger(__name__)

# Maximum comment depth to traverse (0 = top-level only per spec)
_TOP_LEVEL_ONLY = True

# Transient exceptions that should trigger retry
_TRANSIENT_EXCEPTIONS = (ConnectionError, TimeoutError, OSError)


def _make_praw_reddit():
    """Create a read-only PRAW Reddit instance. Returns None if creds missing."""
    try:
        import praw  # type: ignore
    except ImportError:
        logger.error("[reddit] praw package not installed. Cannot collect Reddit data.")
        return None

    settings = get_settings()
    if not settings.reddit_configured:
        return None

    return praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.reddit_user_agent,
        # Read-only mode — no username/password needed
    )


class RedditCollector(ReviewCollector):
    """
    Collects Reddit posts and their top-level comments matching keyword searches
    in configured subreddits.

    Each post counts as one RawRecord; each top-level comment counts as a separate
    RawRecord with title=None (it's a comment, not a post title).
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._reddit = None  # lazy-init on first use

    @property
    def source_name(self) -> str:
        return "reddit"

    def is_available(self) -> bool:
        if not self._settings.reddit_configured:
            logger.info(
                "[reddit] Credentials not configured "
                "(REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET). Adapter skipped."
            )
            return False
        return True

    def _get_reddit(self):
        """Lazy-initialise the PRAW instance."""
        if self._reddit is None:
            self._reddit = _make_praw_reddit()
        return self._reddit

    async def collect(self, config: CollectorConfig) -> AsyncIterator[RawRecord]:
        if not self.is_available():
            return

        reddit = self._get_reddit()
        if reddit is None:
            logger.error("[reddit] Failed to initialise PRAW instance.")
            return

        salt = self._settings.author_hash_salt
        keywords = config.keywords or []
        subreddits = config.subreddits or ["all"]
        max_records = config.max_records or self._settings.default_max_records
        collected = 0

        logger.info(
            "[reddit] Starting collection: %d keywords, subreddits=%s, max=%d",
            len(keywords),
            subreddits,
            max_records,
        )

        for subreddit_name in subreddits:
            if collected >= max_records:
                break

            for keyword in keywords:
                if collected >= max_records:
                    break

                try:
                    posts = await asyncio.to_thread(
                        self._fetch_posts,
                        reddit,
                        subreddit_name,
                        keyword,
                        limit=min(100, max_records - collected),
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "[reddit] Error fetching posts for keyword=%r subreddit=%r: %s",
                        keyword,
                        subreddit_name,
                        exc,
                    )
                    continue

                for post in posts:
                    if collected >= max_records:
                        break

                    # Apply date filter
                    pub_dt = datetime.fromtimestamp(post.created_utc, tz=timezone.utc)
                    if config.date_from and pub_dt < config.date_from:
                        continue
                    if config.date_to and pub_dt > config.date_to:
                        continue

                    try:
                        post_record = self._post_to_record(post, salt, keyword)
                        yield post_record
                        collected += 1
                    except Exception as exc:  # noqa: BLE001
                        logger.error("[reddit] Skipping post %s: %s", post.id, exc)
                        continue

                    # Collect top-level comments
                    if collected >= max_records:
                        break
                    try:
                        async for comment_record in self._collect_comments(
                            post, salt, keyword, config, max_records - collected
                        ):
                            yield comment_record
                            collected += 1
                            if collected >= max_records:
                                break
                    except Exception as exc:  # noqa: BLE001
                        logger.error(
                            "[reddit] Error collecting comments for post %s: %s", post.id, exc
                        )
                        continue

        logger.info("[reddit] Collected %d records total.", collected)

    @retry(
        retry=retry_if_exception_type(_TRANSIENT_EXCEPTIONS),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(4),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _fetch_posts(self, reddit, subreddit_name: str, keyword: str, limit: int):
        """Synchronous PRAW call wrapped for retry. Returns list of submissions."""
        subreddit = reddit.subreddit(subreddit_name)
        results = list(subreddit.search(query=keyword, sort="new", limit=limit))
        logger.debug(
            "[reddit] Fetched %d posts for keyword=%r in r/%s",
            len(results),
            keyword,
            subreddit_name,
        )
        return results

    def _post_to_record(self, post, salt: str, keyword: str) -> RawRecord:
        author_name = None
        try:
            if post.author and post.author.name not in ("[deleted]", "[removed]", ""):
                author_name = post.author.name
        except Exception:
            pass

        return RawRecord(
            source="reddit",
            source_record_id=f"post_{post.id}",
            source_url=f"https://www.reddit.com{post.permalink}",
            published_at=datetime.fromtimestamp(post.created_utc, tz=timezone.utc),
            author_id_hash=hash_author_id(author_name, salt) if author_name else None,
            title=truncate_text(post.title, 1000) if post.title else None,
            text=truncate_text(post.selftext) if post.selftext else None,
            rating=None,
            language=None,
            metadata={
                "subreddit": post.subreddit.display_name,
                "score": post.score,
                "upvote_ratio": post.upvote_ratio,
                "num_comments": post.num_comments,
                "keyword": keyword,
                "post_type": "submission",
                "is_self": post.is_self,
                "flair": post.link_flair_text,
            },
            raw_payload={
                "id": post.id,
                "title": post.title,
                "selftext": post.selftext[:5000] if post.selftext else "",
                "subreddit": post.subreddit.display_name,
                "score": post.score,
                "created_utc": post.created_utc,
                "permalink": post.permalink,
                "url": post.url,
                "num_comments": post.num_comments,
                "upvote_ratio": post.upvote_ratio,
            },
        )

    async def _collect_comments(
        self, post, salt: str, keyword: str, config: CollectorConfig, limit: int
    ) -> AsyncIterator[RawRecord]:
        """Yield top-level comment records for a post."""
        try:
            comments = await asyncio.to_thread(self._fetch_top_comments, post, limit)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[reddit] Could not fetch comments for post %s: %s", post.id, exc)
            return

        for comment in comments:
            try:
                pub_dt = datetime.fromtimestamp(comment.created_utc, tz=timezone.utc)
                if config.date_from and pub_dt < config.date_from:
                    continue
                if config.date_to and pub_dt > config.date_to:
                    continue

                author_name = None
                try:
                    if (
                        comment.author
                        and comment.author.name not in ("[deleted]", "[removed]", "")
                    ):
                        author_name = comment.author.name
                except Exception:
                    pass

                yield RawRecord(
                    source="reddit",
                    source_record_id=f"comment_{comment.id}",
                    source_url=f"https://www.reddit.com{comment.permalink}",
                    published_at=pub_dt,
                    author_id_hash=hash_author_id(author_name, salt) if author_name else None,
                    title=None,
                    text=truncate_text(comment.body) if comment.body else None,
                    rating=None,
                    language=None,
                    metadata={
                        "subreddit": comment.subreddit.display_name,
                        "score": comment.score,
                        "keyword": keyword,
                        "post_type": "comment",
                        "parent_post_id": post.id,
                    },
                    raw_payload={
                        "id": comment.id,
                        "body": comment.body[:5000] if comment.body else "",
                        "subreddit": comment.subreddit.display_name,
                        "score": comment.score,
                        "created_utc": comment.created_utc,
                        "permalink": comment.permalink,
                        "parent_post_id": post.id,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("[reddit] Skipping comment %s: %s", comment.id, exc)
                continue

    @retry(
        retry=retry_if_exception_type(_TRANSIENT_EXCEPTIONS),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(3),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _fetch_top_comments(self, post, limit: int):
        """Fetch top-level comments only (not replies to comments)."""
        import praw.models  # type: ignore
        post.comments.replace_more(limit=0)
        top_comments = [
            c for c in post.comments.list()
            if isinstance(c, praw.models.Comment) and c.parent_id.startswith("t3_")
        ]
        return top_comments[:limit]
