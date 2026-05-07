"""WeChat Work Webhook notifier module."""

from __future__ import annotations

import asyncio
import time
import httpx
import logging

from config import get_settings

logger = logging.getLogger(__name__)

# Enterprise WeChat Webhook rate limit: 20 requests per minute
WECHAT_RATE_LIMIT = 20
WECHAT_RATE_WINDOW = 60  # seconds
WECHAT_RETRY_COUNT = 2
WECHAT_RETRY_DELAY = 5  # seconds

_request_timestamps: list[float] = []


def _check_rate_limit() -> bool:
    """Return True if under rate limit, False if exceeded."""
    now = time.monotonic()
    # Drop timestamps older than the window
    _request_timestamps[:] = [t for t in _request_timestamps if now - t < WECHAT_RATE_WINDOW]
    if len(_request_timestamps) >= WECHAT_RATE_LIMIT:
        return False
    _request_timestamps.append(now)
    return True


async def send_wechat_markdown(title: str, content: str) -> bool:
    """Send a markdown message via WeChat Work webhook.

    Args:
        title: The message title (shown as bold heading).
        content: The markdown content body.

    Returns:
        True if message was sent successfully, False otherwise.
    """
    settings = get_settings()
    webhook_url = settings.WECHAT_WEBHOOK_URL

    if not webhook_url:
        logger.warning("WECHAT_WEBHOOK_URL not configured, skipping notification")
        return False

    if not _check_rate_limit():
        logger.warning("WeChat rate limit exceeded (%d req/%ds), skipping", WECHAT_RATE_LIMIT, WECHAT_RATE_WINDOW)
        return False

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": f"**{title}**\n{content}"
        }
    }

    for attempt in range(1 + WECHAT_RETRY_COUNT):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=10.0)) as client:
                resp = await client.post(webhook_url, json=payload)
                if resp.status_code == 200:
                    result = resp.json()
                    if result.get("errcode") == 0:
                        logger.info("WeChat notification sent: %s", title)
                        return True
                    else:
                        logger.error("WeChat API error: %s", result.get("errmsg"))
                        return False
                else:
                    logger.error("WeChat HTTP %s: %s", resp.status_code, resp.text)
        except httpx.ConnectError as e:
            logger.error("Failed to connect to WeChat webhook: %s", e)
        except httpx.ReadTimeout as e:
            logger.error("WeChat webhook read timeout: %s", e)
        except Exception as e:
            logger.error("Unexpected error sending WeChat notification: %s", e)

        if attempt < WECHAT_RETRY_COUNT:
            logger.info("Retrying WeChat notification in %ds (attempt %d/%d)...", WECHAT_RETRY_DELAY, attempt + 1, WECHAT_RETRY_COUNT)
            await asyncio.sleep(WECHAT_RETRY_DELAY)

    return False