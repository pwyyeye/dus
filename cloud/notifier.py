"""WeChat Work Webhook notifier module."""

from __future__ import annotations

import httpx
import logging

from config import get_settings

logger = logging.getLogger(__name__)


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

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": f"**{title}**\n{content}"
        }
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=10.0)) as client:
            resp = await client.post(webhook_url, json=payload)
            if resp.status_code == 200:
                result = resp.json()
                if result.get("errcode") == 0:
                    logger.info(f"WeChat notification sent: {title}")
                    return True
                else:
                    logger.error(f"WeChat API error: {result.get('errmsg')}")
                    return False
            else:
                logger.error(f"WeChat HTTP {resp.status_code}: {resp.text}")
                return False
    except httpx.ConnectError as e:
        logger.error(f"Failed to connect to WeChat webhook: {e}")
        return False
    except httpx.ReadTimeout as e:
        logger.error(f"WeChat webhook read timeout: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending WeChat notification: {e}")
        return False