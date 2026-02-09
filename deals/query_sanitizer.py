"""
Query Sanitization — shared by web and mobile search views.

Strips dangerous characters, enforces length limits, and normalises
whitespace so every search query hitting the affiliate APIs is clean.
"""

import re
import html


# ── Limits ────────────────────────────────────────────────
MAX_QUERY_LENGTH = 200  # characters — longer than this is suspicious
MIN_QUERY_LENGTH = 2
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50


def sanitize_query(raw: str) -> str:
    """
    Sanitise a user search query.

    1. Strip leading/trailing whitespace
    2. HTML-unescape (in case `&amp;` etc. sneak in from the frontend)
    3. Remove HTML tags
    4. Remove control characters and null bytes
    5. Collapse multiple spaces
    6. Truncate to MAX_QUERY_LENGTH
    """
    if not raw:
        return ""

    q = raw.strip()

    # HTML unescape (&amp; → &, &#39; → ', etc.)
    q = html.unescape(q)

    # Strip any HTML tags
    q = re.sub(r"<[^>]+>", "", q)

    # Remove null bytes, control chars (keep printable + newline/tab)
    q = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", q)

    # Collapse whitespace (tabs, multiple spaces, newlines -> single space)
    q = re.sub(r"\s+", " ", q).strip()

    # Truncate
    q = q[:MAX_QUERY_LENGTH]

    return q


def validate_query(query: str) -> str | None:
    """
    Validate a sanitised query.  Returns an error string or None if valid.
    """
    if not query:
        return "Missing required parameter 'q' (search query)"

    if len(query) < MIN_QUERY_LENGTH:
        return f"Query must be at least {MIN_QUERY_LENGTH} characters long"

    if len(query) > MAX_QUERY_LENGTH:
        return f"Query must be at most {MAX_QUERY_LENGTH} characters long"

    # Reject queries that are only special characters
    if not re.search(r"[a-zA-Z0-9]", query):
        return "Query must contain at least one letter or number"

    return None  # valid


def get_pagination_params(request) -> tuple[int, int]:
    """
    Extract and clamp page/limit from query params.

    Supports:
        ?page=2&limit=20    (page-based)
        ?offset=40&limit=20 (offset-based, takes priority over page)

    Returns (offset, limit).
    """
    try:
        limit = int(request.query_params.get("limit", DEFAULT_PAGE_SIZE))
    except (ValueError, TypeError):
        limit = DEFAULT_PAGE_SIZE
    limit = max(1, min(limit, MAX_PAGE_SIZE))

    # offset takes priority
    offset_raw = request.query_params.get("offset")
    if offset_raw is not None:
        try:
            offset = max(0, int(offset_raw))
        except (ValueError, TypeError):
            offset = 0
    else:
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (ValueError, TypeError):
            page = 1
        offset = (page - 1) * limit

    return offset, limit
