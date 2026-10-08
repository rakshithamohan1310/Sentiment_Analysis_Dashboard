"""
YouTube adapter – collects video comments via the YouTube Data API v3 (httpx).

Quota management:
  - YouTube Data API v3 has a 10,000 units/day default quota.
  - search.list costs 100 units; commentThreads.list costs 1 unit per page.
  - We track consumed units and stop when remaining units < YOUTUBE_QUOTA_BUFFER (env var).
  - Quota state is in-memory per run (not persisted); restart resets it.

Privacy:
  - Author display names are NEVER stored. Only SHA-256(salt + channelId) is kept.
  - No private messages or account data is collected.

Missing credentials:
  - If YOUTUBE_API_KEY is absent, is_available() returns False.
  - No scraping fallback ever.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional
from urllib.parse import urlencode

import httpx
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

_YT_BASE = "https://www.googleapis.com/youtube/v3"

# YouTube Data API v3 quota costs
_QUOTA_SEARCH = 100       # per search.list call
_QUOTA_COMMENTS = 1       # per commentThreads.list page request

# Transient HTTP status codes that should trigger retry
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class QuotaExhaustedError(Exception):
    """Raised when YouTube quota buffer threshold is reached."""


class YouTubeCollector(ReviewCollector):
    """
    Searches YouTube for videos matching keywords, then fetches commentThreads
    for each video. Stops gracefully when quota buffer is low.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._quota_used: int = 0

    @property
    def source_name(self) -> str:
        return "youtube"

    def is_available(self) -> bool:
        if not self._settings.youtube_configured:
            logger.info(
                "[youtube] YOUTUBE_API_KEY not configured. Adapter skipped."
            )
            return False
        return True

    @property
    def _quota_remaining(self) -> int:
        # Default daily quota is 10,000 units; buffer is configurable
        return 10_000 - self._quota_used

    def _check_quota(self, cost: int) -> None:
        if self._quota_remaining - cost < self._settings.youtube_quota_buffer:
            raise QuotaExhaustedError(
                f"YouTube quota buffer reached. Used: {self._quota_used}, "
                f"Remaining: {self._quota_remaining}, Buffer: {self._settings.youtube_quota_buffer}"
            )

    async def collect(self, config: CollectorConfig) -> AsyncIterator[RawRecord]:
        if not self.is_available():
            return

        salt = self._settings.author_hash_salt
        keywords = config.keywords or []
        max_records = config.max_records or self._settings.default_max_records
        collected = 0

        logger.info(
            "[youtube] Starting collection: %d keywords, max=%d", len(keywords), max_records
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            for keyword in keywords:
                if collected >= max_records:
                    break

                try:
                    video_ids = await self._search_videos(client, keyword, max_results=10)
                except QuotaExhaustedError:
                    logger.warning("[youtube] Quota buffer reached during video search. Stopping.")
                    break
                except Exception as exc:  # noqa: BLE001
                    logger.error("[youtube] Error searching keyword=%r: %s", keyword, exc)
                    continue

                for video_id in video_ids:
                    if collected >= max_records:
                        break

                    try:
                        async for record in self._collect_comments(
                            client, video_id, keyword, salt, config, max_records - collected
                        ):
                            yield record
                            collected += 1
                            if collected >= max_records:
                                break
                    except QuotaExhaustedError:
                        logger.warning(
                            "[youtube] Quota buffer reached during comment fetch. Stopping."
                        )
                        return
                    except Exception as exc:  # noqa: BLE001
                        logger.error(
                            "[youtube] Error fetching comments for video %s: %s", video_id, exc
                        )
                        continue

        logger.info(
            "[youtube] Collected %d records. Total quota used: %d units.",
            collected,
            self._quota_used,
        )

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(4),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _search_videos(
        self, client: httpx.AsyncClient, keyword: str, max_results: int = 10
    ) -> list[str]:
        """Search for video IDs matching a keyword. Returns list of videoIds."""
        self._check_quota(_QUOTA_SEARCH)

        params = {
            "part": "id",
            "q": keyword,
            "type": "video",
            "maxResults": min(max_results, 50),
            "relevanceLanguage": "en",
            "key": self._settings.youtube_api_key,
        }
        url = f"{_YT_BASE}/search?{urlencode(params)}"
        response = await client.get(url)

        if response.status_code in _RETRYABLE_STATUS:
            raise httpx.TransportError(f"HTTP {response.status_code}")
        response.raise_for_status()

        self._quota_used += _QUOTA_SEARCH
        data = response.json()
        video_ids = [
            item["id"]["videoId"]
            for item in data.get("items", [])
            if item.get("id", {}).get("videoId")
        ]
        logger.debug("[youtube] keyword=%r → %d videos found", keyword, len(video_ids))
        return video_ids

    async def _collect_comments(
        self,
        client: httpx.AsyncClient,
        video_id: str,
        keyword: str,
        salt: str,
        config: CollectorConfig,
        limit: int,
    ) -> AsyncIterator[RawRecord]:
        """Fetch commentThreads for a video, page by page."""
        page_token: Optional[str] = None
        fetched = 0

        while fetched < limit:
            try:
                data, page_token = await self._fetch_comment_page(
                    client, video_id, page_token
                )
            except QuotaExhaustedError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.error("[youtube] Comment page fetch failed for video %s: %s", video_id, exc)
                break

            for item in data.get("items", []):
                if fetched >= limit:
                    break
                try:
                    record = self._item_to_record(item, video_id, keyword, salt, config)
                    if record is None:
                        continue
                    yield record
                    fetched += 1
                except Exception as exc:  # noqa: BLE001
                    logger.error("[youtube] Skipping comment item: %s", exc)
                    continue

            if not page_token:
                break

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(4),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _fetch_comment_page(
        self,
        client: httpx.AsyncClient,
        video_id: str,
        page_token: Optional[str],
    ) -> tuple[dict, Optional[str]]:
        """Fetch one page of comment threads for a video."""
        self._check_quota(_QUOTA_COMMENTS)

        params: dict[str, Any] = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": 100,
            "order": "relevance",
            "textFormat": "plainText",
            "key": self._settings.youtube_api_key,
        }
        if page_token:
            params["pageToken"] = page_token

        url = f"{_YT_BASE}/commentThreads?{urlencode(params)}"
        response = await client.get(url)

        if response.status_code == 403:
            data = response.json()
            reason = data.get("error", {}).get("errors", [{}])[0].get("reason", "")
            if reason == "commentsDisabled":
                logger.debug("[youtube] Comments disabled for video %s", video_id)
                return {}, None
            if reason == "quotaExceeded":
                raise QuotaExhaustedError("YouTube API quota exceeded (403 quotaExceeded)")

        if response.status_code in _RETRYABLE_STATUS:
            raise httpx.TransportError(f"HTTP {response.status_code}")
        response.raise_for_status()

        self._quota_used += _QUOTA_COMMENTS
        data = response.json()
        next_page = data.get("nextPageToken")
        return data, next_page

    def _item_to_record(
        self,
        item: dict,
        video_id: str,
        keyword: str,
        salt: str,
        config: CollectorConfig,
    ) -> Optional[RawRecord]:
        """Convert a YouTube commentThread item to a RawRecord."""
        top = item.get("snippet", {}).get("topLevelComment", {})
        snippet = top.get("snippet", {})

        comment_id = top.get("id") or item.get("id")
        if not comment_id:
            return None

        text = snippet.get("textDisplay") or snippet.get("textOriginal") or ""
        if not text.strip():
            return None

        published_str = snippet.get("publishedAt")
        published_at: Optional[datetime] = None
        if published_str:
            try:
                published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        if config.date_from and published_at and published_at < config.date_from:
            return None
        if config.date_to and published_at and published_at > config.date_to:
            return None

        # Author channel ID — never the display name
        author_channel_id = snippet.get("authorChannelId", {}).get("value") or ""
        author_hash = hash_author_id(author_channel_id, salt) if author_channel_id else None

        like_count = snippet.get("likeCount", 0)
        reply_count = item.get("snippet", {}).get("totalReplyCount", 0)

        return RawRecord(
            source="youtube",
            source_record_id=f"comment_{comment_id}",
            source_url=f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}",
            published_at=published_at,
            author_id_hash=author_hash,
            title=None,
            text=truncate_text(text),
            rating=None,
            language=None,
            metadata={
                "video_id": video_id,
                "keyword": keyword,
                "like_count": like_count,
                "reply_count": reply_count,
                "post_type": "comment",
            },
            raw_payload={
                "comment_id": comment_id,
                "video_id": video_id,
                "text": text[:5000],
                "published_at": published_str,
                "like_count": like_count,
                "reply_count": reply_count,
            },
        )
