"""
Spell Correction Service — AI-powered typo correction for search queries.

Uses OpenAI GPT-4o-mini for fast, cheap spell correction of fashion search queries.
Runs in parallel with marketplace API calls, adding no extra latency.

Cache: LRU in-memory (1000 entries) to avoid redundant API calls.
Timeout: 2s max — if OpenAI is slow, returns None gracefully.
"""

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SpellCorrection:
    """Result of spell correction."""
    original: str
    corrected: str
    was_corrected: bool


# System prompt — kept minimal for speed
SYSTEM_PROMPT = """You are a search query spell checker for a fashion shopping app.
Given a user's search query, correct any spelling mistakes and return ONLY the corrected query.
If the query has no mistakes, return it exactly as-is.
Rules:
- Fix typos (e.g., "bwon" → "brown", "snekers" → "sneakers")
- Keep the same words/meaning — do NOT add extra words
- Keep it lowercase
- Do NOT add quotes or punctuation
- Do NOT explain, just return the corrected query"""


def _get_openai_client():
    """Lazy-load OpenAI client to avoid import errors if not configured."""
    try:
        from openai import OpenAI
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set — spell correction disabled")
            return None
        return OpenAI(api_key=api_key)
    except ImportError:
        logger.warning("openai package not installed — spell correction disabled")
        return None


# Singleton client
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = _get_openai_client()
    return _client


@lru_cache(maxsize=1000)
def correct_query(query: str) -> Optional[SpellCorrection]:
    """
    Correct spelling in a search query using GPT-4o-mini.
    
    Args:
        query: Raw user search query (e.g., "bwon t shirt men")
    
    Returns:
        SpellCorrection with corrected query, or None if correction failed/unavailable
    """
    client = _get_client()
    if not client:
        return None
    
    query = query.strip()
    if not query or len(query) < 3:
        return SpellCorrection(original=query, corrected=query, was_corrected=False)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            max_tokens=60,
            temperature=0,
            timeout=2.0,
        )
        
        corrected = response.choices[0].message.content.strip().lower()
        
        # Sanity checks
        if not corrected:
            return None
        
        # If correction is wildly different length, it's probably wrong
        if len(corrected) > len(query) * 2 or len(corrected) < len(query) * 0.3:
            logger.warning(f"Spell correction rejected (length mismatch): '{query}' → '{corrected}'")
            return None
        
        was_corrected = corrected != query.lower()
        
        return SpellCorrection(
            original=query,
            corrected=corrected,
            was_corrected=was_corrected,
        )
    
    except Exception as e:
        logger.warning(f"Spell correction failed for '{query}': {e}")
        return None
