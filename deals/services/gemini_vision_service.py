"""
Gemini Vision Service

Analyzes clothing/fashion images using Google Gemini to:
1. Break down the image (type, color, brand, style, material, pattern)
2. Generate precise search queries for marketplace APIs

Primary image analysis service — replaces BLIP for accuracy.
Cost: ~$0.0025 per image (Gemini 2.5 Flash).
"""

import json
import base64
import logging
from typing import Optional, Dict, Any

from django.conf import settings

logger = logging.getLogger(__name__)


class GeminiVisionService:
    """Analyze fashion images using Google Gemini."""

    MODEL = "gemini-2.5-flash"

    PROMPT = """Identify the main clothing item. Return JSON:
{"items":[{"category":"","type":"","color":"","brand":null,"material":"","pattern":"","style":""}],
"search_queries":["brand+type+color query","type+color query"],
"overall_style":"brief description"}

Rules: 2 search queries, concise (3-5 words), shopping-site style. Brand in first query if visible. JSON only."""

    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google import genai
            api_key = getattr(settings, "GEMINI_API_KEY", "")
            if not api_key:
                raise ValueError("GEMINI_API_KEY not configured")
            self._client = genai.Client(api_key=api_key)
        return self._client

    def analyze_image(self, image_base64: str) -> Optional[Dict[str, Any]]:
        """
        Analyze a fashion image and return structured data + search queries.

        Args:
            image_base64: Base64-encoded image string

        Returns:
            Dict with 'items', 'search_queries', 'overall_style'
            or None on failure
        """
        try:
            client = self._get_client()
            from google.genai import types

            # Decode base64 to bytes
            image_bytes = base64.b64decode(image_base64)

            response = client.models.generate_content(
                model=self.MODEL,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=self.PROMPT),
                            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                        ],
                    ),
                ],
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=256,
                    response_mime_type="application/json",
                ),
            )

            # Parse JSON response
            text = response.text.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()

            result = json.loads(text)

            search_queries = result.get("search_queries", [])
            if not search_queries and result.get("items"):
                # Fallback: build queries from item data
                item = result["items"][0]
                brand = item.get("brand") or ""
                color = item.get("color", "")
                item_type = item.get("type", item.get("category", ""))
                queries = []
                if brand:
                    queries.append(f"{brand} {color} {item_type}".strip())
                queries.append(f"{color} {item_type}".strip())
                queries.append(item.get("category", item_type))
                result["search_queries"] = [q for q in queries if q]

            logger.info(
                f"Gemini identified: {result.get('search_queries', [])} "
                f"({len(result.get('items', []))} items)"
            )
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Gemini returned invalid JSON: {e}")
            return None
        except Exception as e:
            logger.exception(f"Gemini vision analysis failed: {e}")
            return None


# Singleton instance
gemini_vision = GeminiVisionService()
