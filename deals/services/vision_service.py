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
    
    ANALYSIS_PROMPT = """Analyze this product screenshot and extract the following information in JSON format:

{
    "product_name": "Full product name",
    "brand": "Brand name",
    "price": 123.45,
    "currency": "USD",
    "source": "Website name (e.g., Amazon, eBay, Best Buy)",
    "condition": "new/used/refurbished",
    "features": ["feature1", "feature2"],
    "raw_text": "Any other relevant text visible"
}

If any field cannot be determined, use null. For price, extract only the number without currency symbols."""

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
            
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
            else:
                json_str = content
            
            data = json.loads(json_str.strip())
            
            return ImageAnalysis(
                product_name=data.get("product_name"),
                brand=data.get("brand"),
                price=data.get("price"),
                currency=data.get("currency", "USD"),
                source=data.get("source"),
                condition=data.get("condition"),
                features=data.get("features", []),
                raw_text=data.get("raw_text", ""),
                confidence=0.9,
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Vision API response: {e}")
            return ImageAnalysis(
                product_name=None,
                brand=None,
                price=None,
                currency="USD",
                source=None,
                condition=None,
                features=[],
                raw_text=content if 'content' in dir() else "",
                confidence=0.0,
            )
    
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
