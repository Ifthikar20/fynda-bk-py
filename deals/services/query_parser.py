"""
Query Parser Service

Parses natural language queries to extract:
- Product name/type
- Budget constraints
- Requirements/features
"""

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ParsedQuery:
    """Structured representation of a parsed search query."""
    original: str
    product: str
    budget: Optional[float]
    requirements: List[str]
    
    def to_dict(self):
        return {
            "original": self.original,
            "parsed": {
                "product": self.product,
                "budget": self.budget,
                "requirements": self.requirements,
            }
        }


class QueryParser:
    """
    Parses natural language product queries.
    
    Example:
        "I am looking for a sony camera and my budget is $1200 that comes with a lens"
        -> product: "sony camera"
        -> budget: 1200.00
        -> requirements: ["lens"]
    """
    
    # Patterns for budget extraction
    BUDGET_PATTERNS = [
        r'\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',  # $1200 or $1,200.00
        r'budget\s+(?:is\s+)?(?:of\s+)?\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',  # budget is $1200
        r'under\s+\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',  # under $1200
        r'(?:less\s+than|below)\s+\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',  # less than $1200
        r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:dollars?|usd)',  # 1200 dollars
    ]
    
    # Patterns for requirement extraction
    REQUIREMENT_PATTERNS = [
        r'(?:with|includes?|comes?\s+with|has|featuring)\s+(?:a\s+)?(.+?)(?:\s+and\s+|\s*,\s*|$)',
        r'(?:that\s+)?(?:comes?\s+with|includes?|has)\s+(?:a\s+)?(.+?)(?:\.|,|$)',
    ]
    
    # Words to remove when extracting product name
    FILTER_WORDS = {
        'i', 'am', 'looking', 'for', 'a', 'an', 'the', 'want', 'need',
        'buy', 'purchase', 'find', 'me', 'and', 'my', 'budget', 'is',
        'that', 'comes', 'with', 'which', 'has', 'includes', 'including',
        'under', 'below', 'less', 'than', 'around', 'about', 'approximately',
        'please', 'can', 'you', 'show', 'get', 'search', 'looking',
    }
    
    def parse(self, query: str) -> ParsedQuery:
        """Parse a natural language query into structured components."""
        original = query.strip()
        query_lower = query.lower()
        
        budget = self._extract_budget(query_lower)
        requirements = self._extract_requirements(query_lower)
        product = self._extract_product(query_lower, budget, requirements)
        
        return ParsedQuery(
            original=original,
            product=product,
            budget=budget,
            requirements=requirements,
        )
    
    def _extract_budget(self, query: str) -> Optional[float]:
        """Extract budget/price constraint from query."""
        for pattern in self.BUDGET_PATTERNS:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                # Remove commas and convert to float
                budget_str = match.group(1).replace(',', '')
                try:
                    return float(budget_str)
                except ValueError:
                    continue
        return None
    
    def _extract_requirements(self, query: str) -> List[str]:
        """Extract product requirements/features from query."""
        requirements = []
        
        for pattern in self.REQUIREMENT_PATTERNS:
            matches = re.findall(pattern, query, re.IGNORECASE)
            for match in matches:
                # Clean up the requirement
                req = match.strip().lower()
                # Remove common filler words
                req = re.sub(r'^(a|an|the)\s+', '', req)
                # Take just the key item (first noun phrase)
                req = req.split()[0] if req else ''
                if req and req not in self.FILTER_WORDS and len(req) > 2:
                    requirements.append(req)
        
        return list(set(requirements))  # Remove duplicates
    
    def _extract_product(self, query: str, budget: Optional[float], requirements: List[str]) -> str:
        """Extract the main product being searched for."""
        # Remove budget mentions
        cleaned = query
        for pattern in self.BUDGET_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Remove requirement phrases
        for pattern in self.REQUIREMENT_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Remove common phrases
        cleaned = re.sub(r'i\s+am\s+looking\s+for', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'i\s+want\s+to\s+buy', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'my\s+budget\s+is', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'and\s+my\s+budget', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'that\s+comes\s+with', '', cleaned, flags=re.IGNORECASE)
        
        # Split into words and filter
        words = cleaned.split()
        product_words = []
        
        for word in words:
            # Clean punctuation
            word = re.sub(r'[^\w\s-]', '', word).strip()
            if word and word.lower() not in self.FILTER_WORDS:
                product_words.append(word)
        
        return ' '.join(product_words).strip()


# Singleton instance for easy import
query_parser = QueryParser()
