"""
NLP Service

Advanced natural language processing for query understanding.
Uses OpenAI API for intent extraction, falls back to regex if unavailable.
"""

import os
import re
import json
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExtractedIntent:
    """Structured intent extracted from natural language query."""
    product: str
    brand: Optional[str]
    category: Optional[str]
    budget_min: Optional[float]
    budget_max: Optional[float]
    requirements: List[str]
    condition: Optional[str]  # new, used, refurbished
    urgency: Optional[str]  # need now, researching
    confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "product": self.product,
            "brand": self.brand,
            "category": self.category,
            "budget_min": self.budget_min,
            "budget_max": self.budget_max,
            "requirements": self.requirements,
            "condition": self.condition,
            "urgency": self.urgency,
            "confidence": self.confidence,
        }


class NLPService:
    """
    Natural Language Processing service for query understanding.
    
    Uses OpenAI GPT-4o-mini for advanced intent extraction.
    Falls back to regex-based parsing if API is unavailable.
    """
    
    OPENAI_FUNCTION_SCHEMA = {
        "name": "parse_shopping_query",
        "description": "Extract shopping intent from a natural language query",
        "parameters": {
            "type": "object",
            "properties": {
                "product": {
                    "type": "string",
                    "description": "The main product being searched for (e.g., 'camera', 'laptop', 'headphones')"
                },
                "brand": {
                    "type": "string",
                    "description": "Brand preference if mentioned (e.g., 'Sony', 'Apple', 'Samsung')"
                },
                "category": {
                    "type": "string",
                    "description": "Product category (e.g., 'electronics', 'camera', 'audio')"
                },
                "budget_min": {
                    "type": "number",
                    "description": "Minimum budget in USD"
                },
                "budget_max": {
                    "type": "number",
                    "description": "Maximum budget in USD"
                },
                "requirements": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Required features or accessories (e.g., 'lens', 'warranty', '4K')"
                },
                "condition": {
                    "type": "string",
                    "enum": ["new", "used", "refurbished", "any"],
                    "description": "Preferred item condition"
                },
                "urgency": {
                    "type": "string",
                    "enum": ["urgent", "soon", "researching"],
                    "description": "How soon the user needs the item"
                }
            },
            "required": ["product"]
        }
    }
    
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
    
    def extract_intent(self, query: str) -> ExtractedIntent:
        """
        Extract shopping intent from natural language query.
        
        Args:
            query: Natural language search query
        
        Returns:
            ExtractedIntent with product, brand, budget, requirements, etc.
        """
        # Try OpenAI first if API key is available
        if self.client:
            try:
                return self._extract_with_openai(query)
            except Exception as e:
                logger.warning(f"OpenAI extraction failed: {e}, falling back to regex")
        
        # Fallback to regex-based extraction
        return self._extract_with_regex(query)
    
    def _extract_with_openai(self, query: str) -> ExtractedIntent:
        """Extract intent using OpenAI function calling."""
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a shopping assistant that extracts product search intent from queries."
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            tools=[{
                "type": "function",
                "function": self.OPENAI_FUNCTION_SCHEMA
            }],
            tool_choice={"type": "function", "function": {"name": "parse_shopping_query"}}
        )
        
        # Parse the function call response
        tool_call = response.choices[0].message.tool_calls[0]
        args = json.loads(tool_call.function.arguments)
        
        return ExtractedIntent(
            product=args.get("product", ""),
            brand=args.get("brand"),
            category=args.get("category"),
            budget_min=args.get("budget_min"),
            budget_max=args.get("budget_max"),
            requirements=args.get("requirements", []),
            condition=args.get("condition"),
            urgency=args.get("urgency"),
            confidence=0.95,  # High confidence with OpenAI
        )
    
    def _extract_with_regex(self, query: str) -> ExtractedIntent:
        """Fallback regex-based extraction."""
        query_lower = query.lower()
        
        # Extract brand (common electronics brands)
        brands = ['sony', 'canon', 'nikon', 'apple', 'samsung', 'lg', 'bose', 'dell', 'hp', 'lenovo']
        brand = None
        for b in brands:
            if b in query_lower:
                brand = b.title()
                break
        
        # Extract budget
        budget_max = None
        budget_patterns = [
            r'\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'budget\s+(?:is\s+)?(?:of\s+)?\$?\s*(\d+(?:,\d{3})*)',
            r'under\s+\$?\s*(\d+(?:,\d{3})*)',
        ]
        for pattern in budget_patterns:
            match = re.search(pattern, query_lower)
            if match:
                budget_max = float(match.group(1).replace(',', ''))
                break
        
        # Extract requirements
        requirements = []
        requirement_patterns = [
            r'(?:with|includes?|comes?\s+with|has)\s+(?:a\s+)?(\w+)',
        ]
        for pattern in requirement_patterns:
            matches = re.findall(pattern, query_lower)
            requirements.extend([m for m in matches if len(m) > 2])
        
        # Extract product (remove budget and filler words)
        product = query_lower
        for pattern in budget_patterns:
            product = re.sub(pattern, '', product)
        filler_words = ['i', 'am', 'looking', 'for', 'a', 'an', 'the', 'want', 'need', 'buy', 
                       'and', 'my', 'budget', 'is', 'that', 'comes', 'with', 'please']
        words = [w for w in product.split() if w not in filler_words and len(w) > 1]
        product = ' '.join(words).strip()
        
        # Detect category
        category = None
        if any(w in query_lower for w in ['camera', 'lens', 'mirrorless', 'dslr']):
            category = 'cameras'
        elif any(w in query_lower for w in ['laptop', 'computer', 'pc', 'macbook']):
            category = 'computers'
        elif any(w in query_lower for w in ['headphones', 'earbuds', 'speaker']):
            category = 'audio'
        
        return ExtractedIntent(
            product=product,
            brand=brand,
            category=category,
            budget_min=None,
            budget_max=budget_max,
            requirements=list(set(requirements)),
            condition=None,
            urgency=None,
            confidence=0.7,  # Lower confidence with regex
        )


# Singleton instance
nlp_service = NLPService()
