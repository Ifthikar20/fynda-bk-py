"""
Vision Service

Image processing for product recognition and price extraction.
Uses OpenAI Vision API to analyze product screenshots.
"""

import os
import base64
import json
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ImageAnalysis:
    """Result of image analysis."""
    product_name: Optional[str]
    brand: Optional[str]
    price: Optional[float]
    currency: str
    source: Optional[str]  # e.g., "Amazon", "eBay", "Best Buy"
    condition: Optional[str]
    features: list
    raw_text: str
    confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_name": self.product_name,
            "brand": self.brand,
            "price": self.price,
            "currency": self.currency,
            "source": self.source,
            "condition": self.condition,
            "features": self.features,
            "raw_text": self.raw_text,
            "confidence": self.confidence,
        }


class VisionService:
    """
    Image analysis service using OpenAI Vision API.
    
    Extracts product information from screenshots:
    - Product name and brand
    - Price and currency
    - Source website
    - Product features
    """
    
    ANALYSIS_PROMPT = """Look at this image and identify the main product or fashion item shown. Respond ONLY with a JSON object (no extra text):

{
    "product_name": "Specific product description for searching (e.g., 'women's oversized denim jacket', 'men's white running shoes')",
    "brand": "Brand name if visible, or null",
    "price": null,
    "currency": "USD",
    "source": null,
    "condition": "new",
    "features": ["key feature 1", "key feature 2"],
    "raw_text": "Brief description of what you see"
}

IMPORTANT RULES:
- Focus on WHAT the product IS, not watermarks, credits, or background elements
- product_name should be a specific, searchable product description
- If you see clothing, describe the type, style, color, and any distinct features
- If you cannot identify a product, set product_name to null
- Respond with ONLY the JSON object, no other text"""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self._client = None
    
    @property
    def client(self):
        """Lazy-load OpenAI client."""
        if self._client is None and self.api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                logger.warning("OpenAI package not installed")
        return self._client
    
    def analyze_image(self, image_path: str = None, image_data: bytes = None, image_url: str = None) -> ImageAnalysis:
        """
        Analyze a product image/screenshot.
        
        Args:
            image_path: Path to image file
            image_data: Raw image bytes
            image_url: URL of image
        
        Returns:
            ImageAnalysis with extracted product information
        """
        if not self.client:
            raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY environment variable.")
        
        # Prepare image content
        if image_path:
            image_content = self._encode_image_file(image_path)
        elif image_data:
            image_content = self._encode_image_bytes(image_data)
        elif image_url:
            image_content = {"type": "image_url", "image_url": {"url": image_url}}
        else:
            raise ValueError("Must provide image_path, image_data, or image_url")
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": self.ANALYSIS_PROMPT},
                            image_content
                        ]
                    }
                ],
                max_tokens=1000
            )
            
            # Parse the JSON response
            content = response.choices[0].message.content
            logger.info(f"Vision API raw response (first 300 chars): {content[:300] if content else 'EMPTY'}")
            
            if not content or not content.strip():
                raise ValueError("Vision API returned empty response")
            
            # Extract JSON from response (handle markdown code blocks)
            json_str = content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                parts = content.split("```")
                if len(parts) >= 3:
                    json_str = parts[1]
            
            try:
                data = json.loads(json_str.strip())
            except json.JSONDecodeError:
                # Try to find any JSON object in the response
                import re
                json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    # Last resort: extract product name from text and create data
                    logger.warning(f"No JSON found in Vision response, extracting from text")
                    data = self._extract_from_text(content)
            
            return ImageAnalysis(
                product_name=data.get("product_name"),
                brand=data.get("brand"),
                price=data.get("price"),
                currency=data.get("currency", "USD"),
                source=data.get("source"),
                condition=data.get("condition"),
                features=data.get("features", []),
                raw_text=data.get("raw_text", content[:200] if content else ""),
                confidence=0.9 if data.get("product_name") else 0.3,
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Vision API response: {e}")
            logger.error(f"Raw content was: {content[:500] if content else 'NO CONTENT'}")
            # Try to salvage product name from text
            fallback = self._extract_from_text(content) if content else {}
            return ImageAnalysis(
                product_name=fallback.get("product_name"),
                brand=fallback.get("brand"),
                price=None,
                currency="USD",
                source=None,
                condition=None,
                features=[],
                raw_text=content[:200] if content else "",
                confidence=0.3 if fallback.get("product_name") else 0.0,
            )
    
    def _extract_from_text(self, text: str) -> Dict[str, Any]:
        """
        Fallback: extract product info from plain text Vision response.
        Uses a second, simpler API call asking just for the product name.
        """
        if not text:
            return {}
        
        # Try to find product-like terms in the text
        result = {}
        
        # If the text mentions a product, try a simpler follow-up call
        try:
            if self.client:
                simple_response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "user",
                            "content": f"From this text, extract just the product name and brand. Reply with ONLY a JSON object like {{\"product_name\": \"...\", \"brand\": \"...\"}}. If no product, reply {{}}.\n\nText: {text[:500]}"
                        }
                    ],
                    max_tokens=100
                )
                simple_content = simple_response.choices[0].message.content.strip()
                # Remove markdown fences if present
                if "```" in simple_content:
                    simple_content = simple_content.split("```")[1]
                    if simple_content.startswith("json"):
                        simple_content = simple_content[4:]
                    simple_content = simple_content.strip()
                result = json.loads(simple_content)
                logger.info(f"Text extraction fallback found: {result}")
        except Exception as e:
            logger.warning(f"Text extraction fallback failed: {e}")
        
        return result
    
    def _encode_image_file(self, image_path: str) -> Dict[str, Any]:
        """Encode image file to base64."""
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        
        with open(path, "rb") as f:
            image_data = f.read()
        
        return self._encode_image_bytes(image_data)
    
    def _encode_image_bytes(self, image_data: bytes) -> Dict[str, Any]:
        """Encode image bytes to base64 URL format."""
        base64_image = base64.b64encode(image_data).decode("utf-8")
        
        # Detect image type from magic bytes
        if image_data[:8] == b'\x89PNG\r\n\x1a\n':
            media_type = "image/png"
        elif image_data[:2] == b'\xff\xd8':
            media_type = "image/jpeg"
        elif image_data[:6] in (b'GIF87a', b'GIF89a'):
            media_type = "image/gif"
        elif image_data[:4] == b'RIFF' and image_data[8:12] == b'WEBP':
            media_type = "image/webp"
        else:
            media_type = "image/jpeg"  # Default
        
        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:{media_type};base64,{base64_image}"
            }
        }


# Singleton instance
vision_service = VisionService()
