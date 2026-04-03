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

    PROMPT = """You are a fashion product identification expert. Analyze this image and extract detailed information about the clothing/fashion item(s) shown.

Return a JSON object with these fields:
{
  "items": [
    {
      "category": "dress/jacket/sneakers/bag/etc",
      "type": "midi dress/bomber jacket/running shoes/etc (be specific)",
      "color": "primary color(s)",
      "brand": "brand name if visible, otherwise null",
      "material": "denim/leather/cotton/silk/etc if identifiable",
      "pattern": "solid/striped/floral/plaid/etc",
      "style": "casual/formal/streetwear/modest/athletic/etc",
      "details": "notable details like buttons, zippers, embroidery, etc"
    }
  ],
  "search_queries": [
    "most specific search query using brand + type + color",
    "slightly broader query using type + color + material",
    "broadest useful query using category + style"
  ],
  "overall_style": "brief description of the overall look"
}

Rules:
- Generate 2-3 search queries ranked from most specific to broadest
- Search queries should be what someone would type into a shopping site
- If multiple items are visible, focus on the main/most prominent item
- If you can identify the brand, always include it in the first search query
- Keep search queries concise (3-6 words each)
- Return ONLY valid JSON, no markdown or explanation"""

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
                    temperature=0.1,
                    max_output_tokens=1024,
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
