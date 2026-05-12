from __future__ import annotations

import re
import uuid

_MENTION_RE = re.compile(
    r"\[@?(.+?)\]\(mention://agent/([0-9a-fA-F-]+)\)"
)


def parse_mentions(content: str) -> list[tuple[str, uuid.UUID]]:
    """Parse @mention patterns from comment content.

    Returns:
        List of (display_name, agent_uuid) tuples found in content.
    """
    results = []
    for match in _MENTION_RE.finditer(content):
        display_name = match.group(1)
        agent_uuid_str = match.group(2)
        try:
            agent_uuid = uuid.UUID(agent_uuid_str)
            results.append((display_name, agent_uuid))
        except ValueError:
            continue
    return results


def has_mention_all(content: str) -> bool:
    """Check if content contains a [@All](mention://all/all) broadcast mention."""
    return bool(re.search(r"\[@?all\]\(mention://all/all\)", content, re.IGNORECASE))
