"""
Query Parser Service - Enhanced Version

Hybrid approach combining:
1. Fashion Gazetteers (hardcoded entity lists)
2. Fuzzy Matching (typo tolerance)
3. Regex Patterns (budget, requirements)

Inspired by Lyst's entity recognition approach but optimized for:
- Zero training data requirement
- Fast lookup performance
- Easy extensibility
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Set, Dict, Tuple

from .fashion_gazetteers import (
    BRANDS, BRAND_ALIASES,
    COLORS, COLOR_ALIASES,
    CATEGORIES, CATEGORY_NORMALIZATION,
    STYLES,
    MATERIALS,
    GENDER, GENDER_NORMALIZATION,
    OCCASIONS,
    get_brand_canonical,
    get_color_canonical,
    get_category_canonical,
    get_gender_canonical,
)
from .fuzzy_matcher import fuzzy_match, fuzzy_match_multi_word


@dataclass
class ParsedQuery:
    """
    Structured representation of a parsed fashion search query.
    
    Example:
        Input: "red nike sneakers under $100"
        Output:
            original: "red nike sneakers under $100"
            product: "sneakers"
            brand: "nike"
            color: "red"
            category: "sneakers"
            budget: 100.0
            ...
    """
    original: str
    product: str  # Legacy: combined product terms
    
    # Fashion entities (NEW)
    brand: Optional[str] = None
    color: Optional[str] = None
    category: Optional[str] = None
    style: Optional[str] = None
    material: Optional[str] = None
    gender: Optional[str] = None
    occasion: Optional[str] = None
    
    # Constraints
    budget: Optional[float] = None
    requirements: List[str] = field(default_factory=list)
    
    # Metadata
    recognized_entities: Dict[str, str] = field(default_factory=dict)
    confidence_score: float = 0.0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "original": self.original,
            "parsed": {
                "product": self.product,
                "brand": self.brand,
                "color": self.color,
                "category": self.category,
                "style": self.style,
                "material": self.material,
                "gender": self.gender,
                "occasion": self.occasion,
                "budget": self.budget,
                "requirements": self.requirements,
            },
            "entities": self.recognized_entities,
            "confidence": self.confidence_score,
        }
    
    def get_search_terms(self) -> str:
        """Get optimized search terms for Elasticsearch."""
        terms = []
        
        # Priority order: category, brand, color, style
        if self.category:
            terms.append(self.category)
        if self.brand:
            terms.append(self.brand)
        if self.color:
            terms.append(self.color)
        if self.style:
            terms.append(self.style)
        if self.material:
            terms.append(self.material)
        
        # Fallback to product if no entities found
        if not terms and self.product:
            terms.append(self.product)
        
        return " ".join(terms)
    
    def get_filters(self) -> Dict[str, any]:
        """Get structured filters for search."""
        filters = {}
        
        if self.brand:
            filters["brand"] = self.brand
        if self.color:
            filters["color"] = self.color
        if self.category:
            filters["category"] = self.category
        if self.gender:
            filters["gender"] = self.gender
        if self.budget:
            filters["max_price"] = self.budget
        
        return filters


class HybridQueryParser:
    """
    Enhanced query parser using hybrid entity recognition.
    
    Approach:
    1. Gazetteer Lookup - Fast O(1) lookup for known entities
    2. Fuzzy Matching - Handles typos with Levenshtein distance
    3. Regex Patterns - Extracts budgets and requirements
    
    Example:
        >>> parser = HybridQueryParser()
        >>> result = parser.parse("red nikee sneakers under $100")
        >>> result.brand
        'nike'  # Fuzzy matched from "nikee"
        >>> result.color
        'red'
        >>> result.category
        'sneakers'
        >>> result.budget
        100.0
    """
    
    # Budget patterns
    BUDGET_PATTERNS = [
        r'\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
        r'budget\s+(?:is\s+)?(?:of\s+)?\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
        r'under\s+\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
        r'(?:less\s+than|below)\s+\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
        r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:dollars?|usd)',
        r'max\s+(?:price\s+)?\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)',
    ]
    
    # Requirement patterns
    REQUIREMENT_PATTERNS = [
        r'(?:with|includes?|comes?\s+with|has|featuring)\s+(?:a\s+)?(.+?)(?:\s+and\s+|\s*,\s*|$)',
        r'(?:that\s+)?(?:comes?\s+with|includes?|has)\s+(?:a\s+)?(.+?)(?:\.|,|$)',
    ]
    
    # Noise words to filter
    NOISE_WORDS = {
        'i', 'am', 'looking', 'for', 'a', 'an', 'the', 'want', 'need',
        'buy', 'purchase', 'find', 'me', 'and', 'my', 'budget', 'is',
        'that', 'comes', 'with', 'which', 'has', 'includes', 'including',
        'under', 'below', 'less', 'than', 'around', 'about', 'approximately',
        'please', 'can', 'you', 'show', 'get', 'search', 'some', 'any',
        'where', 'to', 'of', 'in', 'on', 'at', 'from', 'like', 'similar',
    }
    
    def __init__(self, fuzzy_threshold: int = 2, enable_fuzzy: bool = True):
        """
        Initialize the parser.
        
        Args:
            fuzzy_threshold: Max edit distance for fuzzy matching (default: 2)
            enable_fuzzy: Whether to enable fuzzy matching (default: True)
        """
        self.fuzzy_threshold = fuzzy_threshold
        self.enable_fuzzy = enable_fuzzy
        
        # Prepare lowercase sets for faster lookup
        self._brands_lower = {b.lower() for b in BRANDS}
        self._colors_lower = {c.lower() for c in COLORS}
        self._categories_lower = {c.lower() for c in CATEGORIES}
        self._styles_lower = {s.lower() for s in STYLES}
        self._materials_lower = {m.lower() for m in MATERIALS}
        self._gender_lower = {g.lower() for g in GENDER}
        self._occasions_lower = {o.lower() for o in OCCASIONS}
    
    def parse(self, query: str) -> ParsedQuery:
        """
        Parse a natural language query into structured components.
        
        Args:
            query: Natural language search query
        
        Returns:
            ParsedQuery object with recognized entities
        """
        original = query.strip()
        query_lower = query.lower().strip()
        
        # Track recognized entities
        recognized = {}
        
        # Step 1: Extract budget (regex)
        budget = self._extract_budget(query_lower)
        
        # Step 2: Entity recognition (gazetteers + fuzzy)
        brand, brand_match = self._find_brand(query_lower)
        color, color_match = self._find_color(query_lower)
        category, category_match = self._find_category(query_lower)
        style, style_match = self._find_style(query_lower)
        material, material_match = self._find_material(query_lower)
        gender, gender_match = self._find_gender(query_lower)
        occasion, occasion_match = self._find_occasion(query_lower)
        
        # Track what we found
        if brand:
            recognized['brand'] = f"{brand_match} → {brand}"
        if color:
            recognized['color'] = f"{color_match} → {color}"
        if category:
            recognized['category'] = f"{category_match} → {category}"
        if style:
            recognized['style'] = style
        if material:
            recognized['material'] = material
        if gender:
            recognized['gender'] = gender
        if occasion:
            recognized['occasion'] = occasion
        
        # Step 3: Extract requirements (regex)
        requirements = self._extract_requirements(query_lower)
        
        # Step 4: Build product string (remaining terms)
        product = self._extract_product(
            query_lower,
            brand_match, color_match, category_match,
            style_match, material, gender_match, occasion
        )
        
        # Step 5: Calculate confidence
        confidence = self._calculate_confidence(
            brand, color, category, style, material, gender, occasion, budget
        )
        
        return ParsedQuery(
            original=original,
            product=product,
            brand=brand,
            color=color,
            category=category,
            style=style,
            material=material,
            gender=gender,
            occasion=occasion,
            budget=budget,
            requirements=requirements,
            recognized_entities=recognized,
            confidence_score=confidence,
        )
    
    def _find_brand(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """Find brand mention with fuzzy matching."""
        words = query.split()
        
        # Check 2-word combinations first (for "louis vuitton", "off white", etc.)
        for i in range(len(words) - 1):
            two_word = f"{words[i]} {words[i+1]}"
            if two_word in self._brands_lower:
                canonical = get_brand_canonical(two_word)
                return (canonical, two_word)
        
        # Check single words - exact match and aliases only
        for word in words:
            clean_word = ''.join(c for c in word if c.isalnum())
            
            # Skip noise words
            if clean_word in self.NOISE_WORDS:
                continue
            
            # Check aliases first
            if clean_word in BRAND_ALIASES:
                return (BRAND_ALIASES[clean_word], clean_word)
            
            # Exact match
            if clean_word in self._brands_lower:
                return (get_brand_canonical(clean_word), clean_word)
            
            # Fuzzy match - stricter: require length >= 5 and distance <= 1
            if self.enable_fuzzy and len(clean_word) >= 5:
                match = fuzzy_match(clean_word, BRANDS, max_distance=1)
                if match and self._is_valid_fuzzy_match(clean_word, match[0]):
                    return (get_brand_canonical(match[0]), clean_word)
        
        return (None, None)
    
    def _is_valid_fuzzy_match(self, query_word: str, matched: str) -> bool:
        """Validate fuzzy match to reduce false positives."""
        # Length ratio check - they should be similar length
        len_ratio = len(query_word) / len(matched)
        if len_ratio < 0.6 or len_ratio > 1.5:
            return False
        
        # First character should usually match
        if query_word[0].lower() != matched[0].lower():
            return False
        
        return True
    
    def _find_color(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """Find color mention."""
        words = query.split()
        
        # Check 2-word colors first (e.g., "light blue", "dark green")
        for i in range(len(words) - 1):
            two_word = f"{words[i]} {words[i+1]}"
            if two_word in self._colors_lower:
                return (get_color_canonical(two_word), two_word)
        
        # Single word colors
        for word in words:
            clean_word = ''.join(c for c in word if c.isalnum())
            
            if clean_word in COLOR_ALIASES:
                return (COLOR_ALIASES[clean_word], clean_word)
            
            if clean_word in self._colors_lower:
                return (get_color_canonical(clean_word), clean_word)
            
            # Fuzzy match for colors (lower threshold)
            if self.enable_fuzzy and len(clean_word) >= 4:
                match = fuzzy_match(clean_word, COLORS, max_distance=1)
                if match:
                    return (get_color_canonical(match[0]), clean_word)
        
        return (None, None)
    
    def _find_category(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """Find product category mention."""
        words = query.split()
        
        # Check 2-word categories first (e.g., "t-shirt", "tank top", "running shoes")
        for i in range(len(words) - 1):
            two_word = f"{words[i]} {words[i+1]}"
            if two_word in self._categories_lower:
                return (get_category_canonical(two_word), two_word)
        
        # Single word categories - prioritize exact matches
        for word in words:
            clean_word = ''.join(c for c in word if c.isalnum())
            
            # Skip noise and very short words
            if clean_word in self.NOISE_WORDS or len(clean_word) < 3:
                continue
            
            if clean_word in CATEGORY_NORMALIZATION:
                return (CATEGORY_NORMALIZATION[clean_word], clean_word)
            
            if clean_word in self._categories_lower:
                return (get_category_canonical(clean_word), clean_word)
        
        # No fuzzy matching for categories - too many false positives
        
        return (None, None)
    
    def _find_style(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """Find style descriptor."""
        words = query.split()
        
        # Check 2-word styles (e.g., "slim fit", "high waisted")
        for i in range(len(words) - 1):
            two_word = f"{words[i]} {words[i+1]}"
            if two_word in self._styles_lower:
                return (two_word, two_word)
        
        # Single word
        for word in words:
            clean_word = ''.join(c for c in word if c.isalnum())
            if clean_word in self._styles_lower:
                return (clean_word, clean_word)
        
        return (None, None)
    
    def _find_material(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """Find material mention."""
        words = query.split()
        
        for word in words:
            clean_word = ''.join(c for c in word if c.isalnum())
            if clean_word in self._materials_lower:
                return (clean_word, clean_word)
        
        return (None, None)
    
    def _find_gender(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """Find gender specification."""
        words = query.split()
        
        for word in words:
            clean_word = ''.join(c for c in word if c.isalnum())
            
            if clean_word in GENDER_NORMALIZATION:
                return (GENDER_NORMALIZATION[clean_word], clean_word)
            
            if clean_word in self._gender_lower:
                return (get_gender_canonical(clean_word), clean_word)
        
        return (None, None)
    
    def _find_occasion(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """Find occasion keyword."""
        words = query.split()
        
        # Check 2-word occasions
        for i in range(len(words) - 1):
            two_word = f"{words[i]} {words[i+1]}"
            if two_word in self._occasions_lower:
                return (two_word, two_word)
        
        for word in words:
            clean_word = ''.join(c for c in word if c.isalnum())
            if clean_word in self._occasions_lower:
                return (clean_word, clean_word)
        
        return (None, None)
    
    def _extract_budget(self, query: str) -> Optional[float]:
        """Extract budget/price constraint from query."""
        for pattern in self.BUDGET_PATTERNS:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
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
                req = match.strip().lower()
                req = re.sub(r'^(a|an|the)\s+', '', req)
                req = req.split()[0] if req else ''
                if req and req not in self.NOISE_WORDS and len(req) > 2:
                    requirements.append(req)
        
        return list(set(requirements))
    
    def _extract_product(
        self,
        query: str,
        brand_match: Optional[str],
        color_match: Optional[str],
        category_match: Optional[str],
        style_match: Optional[str],
        material_match: Optional[str],
        gender_match: Optional[str],
        occasion_match: Optional[str],
    ) -> str:
        """Extract remaining product terms after entity removal."""
        # Remove budget mentions
        cleaned = query
        for pattern in self.BUDGET_PATTERNS:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Remove recognized entities
        entities_to_remove = [
            brand_match, color_match, category_match,
            style_match, material_match, gender_match, occasion_match
        ]
        for entity in entities_to_remove:
            if entity:
                cleaned = re.sub(rf'\b{re.escape(entity)}\b', '', cleaned, flags=re.IGNORECASE)
        
        # Remove common phrases
        cleaned = re.sub(r'i\s+am\s+looking\s+for', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'i\s+want\s+to\s+buy', '', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'show\s+me', '', cleaned, flags=re.IGNORECASE)
        
        # Filter noise words
        words = cleaned.split()
        product_words = []
        for word in words:
            word = re.sub(r'[^\w\s-]', '', word).strip()
            if word and word.lower() not in self.NOISE_WORDS:
                product_words.append(word)
        
        return ' '.join(product_words).strip()
    
    def _calculate_confidence(
        self,
        brand: Optional[str],
        color: Optional[str],
        category: Optional[str],
        style: Optional[str],
        material: Optional[str],
        gender: Optional[str],
        occasion: Optional[str],
        budget: Optional[float],
    ) -> float:
        """
        Calculate confidence score based on entities recognized.
        
        Higher score = more structured query understanding.
        """
        score = 0.0
        total_weight = 5.0  # Max possible weight
        
        # Weights by importance
        if category:
            score += 1.5  # Category is most important
        if brand:
            score += 1.0
        if color:
            score += 0.8
        if style:
            score += 0.5
        if gender:
            score += 0.5
        if material:
            score += 0.3
        if occasion:
            score += 0.3
        if budget:
            score += 0.1
        
        return min(score / total_weight, 1.0)


# =============================================================================
# LEGACY COMPATIBILITY
# =============================================================================

class QueryParser:
    """
    Legacy QueryParser wrapper for backwards compatibility.
    
    Delegates to HybridQueryParser internally.
    """
    
    def __init__(self):
        self._hybrid_parser = HybridQueryParser()
    
    def parse(self, query: str) -> ParsedQuery:
        """Parse query using hybrid approach."""
        return self._hybrid_parser.parse(query)


# Singleton instances for easy import
query_parser = QueryParser()
hybrid_parser = HybridQueryParser()
