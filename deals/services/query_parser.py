"""
Query Parser Service v2 — Production-Grade

Hybrid approach combining:
1. Trie-based entity lookup (O(k) where k = query length)
2. N-gram scanning (1, 2, 3-word phrases)
3. Fuzzy matching (Levenshtein distance for typos)
4. Intent detection (search, compare, browse, deal_hunt, trending)
5. Price range extraction ($50-$100, "between 50 and 100")
6. Compound query splitting ("nike shoes and gucci bags")
7. Input sanitization (XSS, SQL injection protection)
8. Query expansion (synonyms for broader results)
9. LRU caching (256 recent parses)

Backwards compatible with v1 — ParsedQuery retains primary brand/color/category
fields while adding multi-entity lists.
"""

import re
import html
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from functools import lru_cache

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

logger = logging.getLogger(__name__)

# Max query length to prevent abuse
MAX_QUERY_LENGTH = 500


# =============================================================================
# SYNONYMS — query expansion for broader results
# =============================================================================
SYNONYMS = {
    "sneakers": ["trainers", "kicks", "running shoes", "athletic shoes"],
    "trainers": ["sneakers", "kicks"],
    "hoodie": ["sweatshirt", "pullover hoodie"],
    "sweatshirt": ["hoodie", "pullover"],
    "pants": ["trousers", "bottoms"],
    "trousers": ["pants", "slacks"],
    "jacket": ["coat", "outerwear"],
    "coat": ["jacket", "overcoat"],
    "purse": ["handbag", "bag"],
    "handbag": ["purse", "bag"],
    "sunglasses": ["shades", "sunnies"],
    "t-shirt": ["tee", "tshirt"],
    "jeans": ["denim pants", "denim"],
    "dress": ["gown", "frock"],
    "heels": ["pumps", "stilettos", "high heels"],
    "loafers": ["slip-ons", "moccasins"],
    "backpack": ["rucksack", "daypack"],
    "watch": ["timepiece", "wristwatch"],
    "scarf": ["wrap", "shawl"],
    "underwear": ["undergarments", "intimates"],
    "swimsuit": ["bathing suit", "swimwear"],
    "activewear": ["sportswear", "athletic wear", "gym clothes"],
    "leggings": ["tights", "yoga pants"],
    "blazer": ["sport coat", "sports jacket"],
    "cardigan": ["knit sweater", "button-up sweater"],
    "boots": ["booties", "ankle boots"],
    "sandals": ["flip flops", "slides"],
    "jewelry": ["jewellery", "accessories"],
    "necklace": ["chain", "pendant"],
    "earrings": ["studs", "hoops"],
}


# =============================================================================
# CONVERSATIONAL INTELLIGENCE — understand vibes, palettes, seasons, negation
# =============================================================================

# Aesthetic / vibe descriptors → search keywords + style hints
AESTHETICS = {
    "elegant": {"styles": ["formal", "classy"], "keywords": ["elegant", "formal", "sophisticated"], "categories": ["dress", "gown", "blazer"]},
    "classy": {"styles": ["formal", "classy"], "keywords": ["classy", "refined", "polished"], "categories": ["dress", "blazer", "heels"]},
    "chic": {"styles": ["chic", "trendy"], "keywords": ["chic", "stylish", "fashionable"], "categories": ["dress", "blouse", "skirt"]},
    "casual": {"styles": ["casual", "relaxed"], "keywords": ["casual", "everyday", "relaxed"], "categories": ["t-shirt", "jeans", "sneakers"]},
    "boho": {"styles": ["bohemian", "boho"], "keywords": ["boho", "bohemian", "free spirit"], "categories": ["dress", "skirt", "sandals"]},
    "bohemian": {"styles": ["bohemian", "boho"], "keywords": ["bohemian", "boho", "flowy"], "categories": ["dress", "maxi dress"]},
    "minimalist": {"styles": ["minimalist", "clean"], "keywords": ["minimalist", "simple", "clean lines"], "categories": ["dress", "blazer", "pants"]},
    "sporty": {"styles": ["sporty", "athletic"], "keywords": ["sporty", "athletic", "activewear"], "categories": ["sneakers", "leggings", "hoodie"]},
    "edgy": {"styles": ["edgy", "punk"], "keywords": ["edgy", "bold", "statement"], "categories": ["jacket", "boots", "jeans"]},
    "romantic": {"styles": ["romantic", "feminine"], "keywords": ["romantic", "feminine", "soft"], "categories": ["dress", "blouse", "skirt"]},
    "preppy": {"styles": ["preppy", "classic"], "keywords": ["preppy", "classic", "polished"], "categories": ["blazer", "polo", "loafers"]},
    "streetwear": {"styles": ["streetwear", "urban"], "keywords": ["streetwear", "urban", "street style"], "categories": ["hoodie", "sneakers", "t-shirt"]},
    "vintage": {"styles": ["vintage", "retro"], "keywords": ["vintage", "retro", "throwback"], "categories": ["dress", "jacket", "jeans"]},
    "glamorous": {"styles": ["glamorous", "glam"], "keywords": ["glamorous", "glam", "sparkle"], "categories": ["dress", "gown", "heels"]},
    "cute": {"styles": ["cute", "sweet"], "keywords": ["cute", "adorable", "sweet"], "categories": ["dress", "top", "skirt"]},
    "sexy": {"styles": ["sexy", "bold"], "keywords": ["sexy", "body-con", "fitted"], "categories": ["dress", "bodysuit", "heels"]},
    "comfy": {"styles": ["casual", "comfortable"], "keywords": ["comfortable", "cozy", "relaxed"], "categories": ["hoodie", "leggings", "sneakers"]},
    "cozy": {"styles": ["casual", "comfortable"], "keywords": ["cozy", "warm", "soft"], "categories": ["sweater", "cardigan", "hoodie"]},
    "flowy": {"styles": ["flowy", "relaxed"], "keywords": ["flowy", "loose", "airy"], "categories": ["dress", "maxi dress", "skirt"]},
    "sophisticated": {"styles": ["formal", "sophisticated"], "keywords": ["sophisticated", "refined", "elegant"], "categories": ["blazer", "dress", "heels"]},
    "trendy": {"styles": ["trendy", "modern"], "keywords": ["trendy", "on-trend", "fashionable"], "categories": ["dress", "top", "sneakers"]},
    "professional": {"styles": ["formal", "professional"], "keywords": ["professional", "work", "office"], "categories": ["blazer", "pants", "dress shirt"]},
}

# Color palette groups → individual colors
COLOR_PALETTES = {
    "pastels": ["light pink", "lavender", "mint", "baby blue", "peach", "lilac", "powder blue"],
    "pastel": ["light pink", "lavender", "mint", "baby blue", "peach", "lilac"],
    "earth tones": ["brown", "tan", "olive", "rust", "terracotta", "khaki", "camel"],
    "earthy": ["brown", "tan", "olive", "rust", "terracotta", "khaki"],
    "neutrals": ["black", "white", "grey", "beige", "cream", "ivory", "taupe"],
    "neutral": ["black", "white", "grey", "beige", "cream", "ivory"],
    "jewel tones": ["emerald", "sapphire", "ruby", "amethyst", "deep purple", "teal"],
    "jewel": ["emerald", "sapphire", "ruby", "amethyst", "teal"],
    "neon": ["neon green", "neon pink", "neon yellow", "neon orange"],
    "monochrome": ["black", "white", "grey"],
    "warm colors": ["red", "orange", "yellow", "coral", "rust"],
    "cool colors": ["blue", "green", "purple", "teal", "mint"],
    "dark": ["black", "navy", "dark grey", "charcoal", "burgundy", "dark green"],
    "bright": ["red", "yellow", "orange", "hot pink", "electric blue", "lime"],
    "muted": ["dusty rose", "sage", "mauve", "slate", "taupe", "stone"],
    "tropical": ["coral", "turquoise", "hot pink", "lime", "mango"],
}

# Month → season mapping
MONTH_TO_SEASON = {
    "january": "winter", "february": "winter",
    "march": "spring", "april": "spring", "may": "spring",
    "june": "summer", "july": "summer", "august": "summer",
    "september": "fall", "october": "fall", "november": "fall",
    "december": "winter",
    # Abbreviations
    "jan": "winter", "feb": "winter", "mar": "spring",
    "apr": "spring", "jun": "summer", "jul": "summer",
    "aug": "summer", "sep": "fall", "oct": "fall",
    "nov": "fall", "dec": "winter",
}

SEASON_KEYWORDS = {
    "summer": ["lightweight", "breathable", "cool", "sundress", "linen"],
    "winter": ["warm", "cozy", "layered", "wool", "insulated"],
    "spring": ["light", "floral", "fresh", "layered"],
    "fall": ["layered", "warm", "cozy", "knit", "leather"],
}

# Relationship → gender inference
RELATIONSHIP_TO_GENDER = {
    "sister": "women", "sisters": "women", "mom": "women", "mother": "women",
    "wife": "women", "girlfriend": "women", "daughter": "women", "daughters": "women",
    "aunt": "women", "grandma": "women", "grandmother": "women",
    "niece": "women", "bridesmaid": "women", "bridesmaids": "women", "bride": "women",
    "her": "women", "she": "women",
    "brother": "men", "brothers": "men", "dad": "men", "father": "men",
    "husband": "men", "boyfriend": "men", "son": "men", "sons": "men",
    "uncle": "men", "grandpa": "men", "grandfather": "men",
    "nephew": "men", "groomsman": "men", "groomsmen": "men", "groom": "men",
    "him": "men", "he": "men",
    "kid": "kids", "child": "kids", "kids": "kids",
    "toddler": "kids", "baby": "kids", "teen": "kids", "teens": "kids",
    # Possessive forms (apostrophe-stripped)
    "sister's": "women", "sisters'": "women",
    "brother's": "men", "brothers'": "men",
    "mom's": "women", "mother's": "women",
    "dad's": "men", "father's": "men",
    "wife's": "women", "husband's": "men",
    "girlfriend's": "women", "boyfriend's": "men",
    "daughter's": "women", "son's": "men",
}

# Negation / exclusion patterns → style alternatives
NEGATION_ALTERNATIVES = {
    "tight": ["loose", "relaxed fit", "flowy"],
    "loose": ["fitted", "slim fit", "tailored"],
    "short": ["long", "maxi", "midi"],
    "long": ["short", "mini", "cropped"],
    "heavy": ["lightweight", "breathable", "thin"],
    "thick": ["thin", "lightweight", "sheer"],
    "boring": ["statement", "bold", "trendy"],
    "basic": ["unique", "statement", "designer"],
    "plain": ["patterned", "printed", "textured"],
    "expensive": ["affordable", "budget", "value"],
    "revealing": ["modest", "covered", "conservative"],
    "flashy": ["subtle", "understated", "minimalist"],
    "dark": ["light", "bright", "pastel"],
    "bright": ["muted", "neutral", "subtle"],
    "formal": ["casual", "relaxed", "everyday"],
    "casual": ["formal", "dressy", "elegant"],
}

# Event context → occasion + search enrichment
EVENT_CONTEXT = {
    "graduation": {"occasion": "graduation", "style_hints": ["formal", "elegant"], "categories": ["dress", "suit", "heels"]},
    "wedding": {"occasion": "wedding", "style_hints": ["formal", "elegant"], "categories": ["dress", "gown", "suit"]},
    "prom": {"occasion": "prom", "style_hints": ["formal", "glamorous"], "categories": ["dress", "gown", "heels"]},
    "interview": {"occasion": "job interview", "style_hints": ["professional", "formal"], "categories": ["blazer", "dress shirt", "pants"]},
    "date": {"occasion": "date night", "style_hints": ["chic", "stylish"], "categories": ["dress", "blouse", "heels"]},
    "date night": {"occasion": "date night", "style_hints": ["chic", "sexy"], "categories": ["dress", "bodysuit", "heels"]},
    "party": {"occasion": "party", "style_hints": ["bold", "fun"], "categories": ["dress", "top", "heels"]},
    "brunch": {"occasion": "brunch", "style_hints": ["casual", "chic"], "categories": ["dress", "blouse", "sandals"]},
    "beach": {"occasion": "beach", "style_hints": ["casual", "relaxed"], "categories": ["dress", "swimsuit", "sandals"]},
    "vacation": {"occasion": "vacation", "style_hints": ["casual", "comfortable"], "categories": ["dress", "shorts", "sandals"]},
    "office": {"occasion": "work", "style_hints": ["professional", "formal"], "categories": ["blazer", "pants", "dress shirt"]},
    "gym": {"occasion": "gym", "style_hints": ["sporty", "athletic"], "categories": ["leggings", "sneakers", "t-shirt"]},
    "festival": {"occasion": "festival", "style_hints": ["boho", "bold"], "categories": ["dress", "boots", "shorts"]},
    "funeral": {"occasion": "funeral", "style_hints": ["formal", "conservative"], "categories": ["dress", "suit", "blazer"]},
    "concert": {"occasion": "concert", "style_hints": ["edgy", "casual"], "categories": ["jeans", "t-shirt", "boots"]},
    "travel": {"occasion": "travel", "style_hints": ["comfortable", "casual"], "categories": ["sneakers", "leggings", "jacket"]},
    "island": {"occasion": "beach", "style_hints": ["relaxed", "tropical"], "categories": ["dress", "sandals", "swimsuit"]},
}


# =============================================================================
# ENTITY TRIE — O(k) multi-word entity matching
# =============================================================================

class TrieNode:
    """A node in the entity recognition trie."""
    __slots__ = ('children', 'entity_type', 'canonical', 'original')

    def __init__(self):
        self.children: Dict[str, 'TrieNode'] = {}
        self.entity_type: Optional[str] = None  # "brand", "color", etc.
        self.canonical: Optional[str] = None     # normalized form
        self.original: Optional[str] = None      # original phrase


class EntityTrie:
    """
    Prefix trie for fast multi-word entity matching.

    Supports 1, 2, and 3-word phrase lookups in O(k) time
    where k is the number of words in the query.

    Usage:
        trie = EntityTrie()
        trie.insert("louis vuitton", "brand", "louis vuitton")
        trie.insert("air jordan", "brand", "air jordan")
        matches = trie.search(["i", "want", "louis", "vuitton", "shoes"])
        # → [Match(entity_type="brand", canonical="louis vuitton", ...)]
    """

    def __init__(self):
        self.root = TrieNode()
        self._size = 0

    def insert(self, phrase: str, entity_type: str, canonical: str):
        """Insert a phrase into the trie."""
        words = phrase.lower().split()
        node = self.root
        for word in words:
            if word not in node.children:
                node.children[word] = TrieNode()
            node = node.children[word]
        node.entity_type = entity_type
        node.canonical = canonical
        node.original = phrase
        self._size += 1

    def search(self, words: List[str]) -> List[Dict]:
        """
        Find all entity matches in a word list.

        Greedy: prefers longest match (3-word > 2-word > 1-word).
        Returns list of dicts with: entity_type, canonical, original, start, end
        """
        matches = []
        i = 0
        matched_positions = set()

        while i < len(words):
            best_match = None
            node = self.root
            j = i

            # Walk the trie as far as possible (greedy longest match)
            while j < len(words) and words[j] in node.children:
                node = node.children[words[j]]
                j += 1
                if node.entity_type is not None:
                    best_match = {
                        "entity_type": node.entity_type,
                        "canonical": node.canonical,
                        "original": node.original,
                        "matched_text": " ".join(words[i:j]),
                        "start": i,
                        "end": j,
                    }

            if best_match and not any(p in matched_positions for p in range(best_match["start"], best_match["end"])):
                matches.append(best_match)
                for p in range(best_match["start"], best_match["end"]):
                    matched_positions.add(p)
                i = best_match["end"]
            else:
                i += 1

        return matches

    @property
    def size(self) -> int:
        return self._size


def _build_entity_trie() -> EntityTrie:
    """Build the global entity trie from all gazetteers."""
    trie = EntityTrie()

    # Brands
    for brand in BRANDS:
        canonical = get_brand_canonical(brand)
        trie.insert(brand, "brand", canonical)

    # Brand aliases
    for alias, canonical in BRAND_ALIASES.items():
        trie.insert(alias, "brand", canonical)

    # Colors
    for color in COLORS:
        canonical = get_color_canonical(color)
        trie.insert(color, "color", canonical)

    # Color aliases
    for alias, canonical in COLOR_ALIASES.items():
        trie.insert(alias, "color", canonical)

    # Categories
    for cat in CATEGORIES:
        canonical = get_category_canonical(cat)
        trie.insert(cat, "category", canonical)

    # Category aliases
    for alias, canonical in CATEGORY_NORMALIZATION.items():
        trie.insert(alias, "category", canonical)

    # Styles
    for style in STYLES:
        trie.insert(style, "style", style)

    # Materials
    for material in MATERIALS:
        trie.insert(material, "material", material)

    # Gender
    for g in GENDER:
        canonical = get_gender_canonical(g)
        trie.insert(g, "gender", canonical)

    # Gender aliases
    for alias, canonical in GENDER_NORMALIZATION.items():
        trie.insert(alias, "gender", canonical)

    # Occasions
    for occasion in OCCASIONS:
        trie.insert(occasion, "occasion", occasion)

    logger.info(f"Built entity trie with {trie.size} entries")
    return trie


# Build once at module load
_ENTITY_TRIE = _build_entity_trie()


# =============================================================================
# PARSED QUERY — v2 with multi-entity support
# =============================================================================

@dataclass
class ParsedQuery:
    """
    Structured representation of a parsed fashion search query.

    Example:
        Input: "red or blue nike sneakers under $100"
        Output:
            original: "red or blue nike sneakers under $100"
            product: "sneakers"
            brand: "nike"
            brands: ["nike"]
            color: "red"
            colors: ["red", "blue"]
            category: "sneakers"
            budget: 100.0
            intent: "search"
            ...
    """
    original: str
    product: str  # Combined product terms

    # Primary entities (backwards compatible)
    brand: Optional[str] = None
    color: Optional[str] = None
    category: Optional[str] = None
    style: Optional[str] = None
    material: Optional[str] = None
    gender: Optional[str] = None
    occasion: Optional[str] = None

    # Multi-entity lists (NEW in v2)
    brands: List[str] = field(default_factory=list)
    colors: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    styles: List[str] = field(default_factory=list)
    materials: List[str] = field(default_factory=list)

    # Constraints
    budget: Optional[float] = None
    min_budget: Optional[float] = None  # NEW: price floor
    requirements: List[str] = field(default_factory=list)

    # Intent (NEW in v2)
    intent: str = "search"  # search/compare/trending/brand_browse/deal_hunt

    # Query expansion (NEW in v2)
    expanded_terms: List[str] = field(default_factory=list)

    # Compound sub-queries (NEW in v2)
    sub_queries: List['ParsedQuery'] = field(default_factory=list)

    # Conversational intelligence (NEW in v3)
    aesthetic: Optional[str] = None          # elegant, boho, edgy, etc.
    season: Optional[str] = None             # summer, winter, spring, fall
    color_palette: Optional[str] = None      # pastels, earth tones, etc.
    palette_colors: List[str] = field(default_factory=list)  # expanded palette colors
    exclusions: List[str] = field(default_factory=list)       # "not tight" → negated attrs
    style_alternatives: List[str] = field(default_factory=list)  # from negations
    inferred_categories: List[str] = field(default_factory=list)  # from aesthetics/events
    search_keywords: List[str] = field(default_factory=list)      # enriched search terms

    # Metadata
    recognized_entities: Dict[str, str] = field(default_factory=dict)
    confidence_score: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        result = {
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
                "min_budget": self.min_budget,
                "requirements": self.requirements,
            },
            "multi": {
                "brands": self.brands,
                "colors": self.colors,
                "categories": self.categories,
                "styles": self.styles,
                "materials": self.materials,
            },
            "intent": self.intent,
            "expanded_terms": self.expanded_terms,
            "entities": self.recognized_entities,
            "confidence": self.confidence_score,
        }

        # Conversational enrichment (only include if present)
        conversational = {}
        if self.aesthetic:
            conversational["aesthetic"] = self.aesthetic
        if self.season:
            conversational["season"] = self.season
        if self.color_palette:
            conversational["color_palette"] = self.color_palette
            conversational["palette_colors"] = self.palette_colors
        if self.exclusions:
            conversational["exclusions"] = self.exclusions
            conversational["style_alternatives"] = self.style_alternatives
        if self.inferred_categories:
            conversational["inferred_categories"] = self.inferred_categories
        if self.search_keywords:
            conversational["search_keywords"] = self.search_keywords
        if conversational:
            result["conversational"] = conversational

        if self.sub_queries:
            result["sub_queries"] = [sq.to_dict() for sq in self.sub_queries]

        return result

    def get_search_terms(self) -> str:
        """Get optimized search terms for marketplace APIs."""
        terms = []

        # Priority: category > brand > color > style > material
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
        if self.gender:
            terms.append(self.gender)

        # Include unrecognized product terms
        if self.product:
            for word in self.product.split():
                if word.lower() not in {t.lower() for t in terms}:
                    terms.append(word)

        # Fallback to original
        if not terms:
            terms.append(self.original)

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
        if self.min_budget:
            filters["min_price"] = self.min_budget

        return filters

    def get_expanded_search_terms(self) -> List[str]:
        """
        Get multiple search term variations for broader results.
        Returns the primary search + synonym-expanded alternatives.
        """
        primary = self.get_search_terms()
        all_terms = [primary]

        for term in self.expanded_terms:
            if term not in all_terms:
                all_terms.append(term)

        return all_terms[:5]  # Cap at 5 variations


# =============================================================================
# HYBRID QUERY PARSER v2
# =============================================================================

class HybridQueryParser:
    """
    Production-grade query parser using hybrid entity recognition.

    Architecture:
    1. Input sanitization (XSS, injection, length limits)
    2. Intent detection (compare, browse, deal_hunt, trending, search)
    3. Compound query splitting ("A and B" → sub-queries)
    4. Trie-based entity matching (O(k) multi-word)
    5. Fuzzy matching fallback (typo tolerance)
    6. Price range extraction (regex)
    7. Full requirements extraction (multi-word)
    8. Query expansion (synonyms)
    9. Confidence scoring

    Example:
        >>> parser = HybridQueryParser()
        >>> result = parser.parse("red nikee sneakers under $100")
        >>> result.brand
        'nike'  # Fuzzy matched from "nikee"
        >>> result.color
        'red'
        >>> result.intent
        'search'
    """

    # ─── Compiled regex patterns ──────────────────────────────────

    # Budget patterns (single price)
    _BUDGET_PATTERNS = [
        re.compile(r'under\s+\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', re.IGNORECASE),
        re.compile(r'(?:less\s+than|below|max)\s+\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', re.IGNORECASE),
        re.compile(r'max\s+(?:price\s+)?\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', re.IGNORECASE),
        re.compile(r'budget\s+(?:is\s+)?(?:of\s+)?\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', re.IGNORECASE),
        re.compile(r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:dollars?|usd)', re.IGNORECASE),
        re.compile(r'\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)(?!\s*[-–]\s*\$?\s*\d)', re.IGNORECASE),
    ]

    # Price range patterns (NEW)
    _RANGE_PATTERNS = [
        re.compile(r'\$\s*(\d+(?:,\d{3})*)\s*[-–to]+\s*\$?\s*(\d+(?:,\d{3})*)', re.IGNORECASE),
        re.compile(r'between\s+\$?\s*(\d+(?:,\d{3})*)\s+and\s+\$?\s*(\d+(?:,\d{3})*)', re.IGNORECASE),
        re.compile(r'(\d+(?:,\d{3})*)\s*[-–]\s*(\d+(?:,\d{3})*)\s*(?:dollars?|usd)', re.IGNORECASE),
        re.compile(r'from\s+\$?\s*(\d+(?:,\d{3})*)\s+to\s+\$?\s*(\d+(?:,\d{3})*)', re.IGNORECASE),
    ]

    # "Around $X" → ±25%
    _APPROX_PATTERN = re.compile(
        r'(?:around|about|approximately|roughly|~)\s+\$?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', re.IGNORECASE
    )

    # Requirement patterns (multi-word extraction)
    _REQUIREMENT_PATTERNS = [
        re.compile(r'(?:with|featuring)\s+(?:a\s+)?(.+?)(?:\s+and\s+|\s*,\s*|$)', re.IGNORECASE),
        re.compile(r'(?:that\s+)?(?:comes?\s+with|includes?|has)\s+(?:a\s+)?(.+?)(?:\.|,|$)', re.IGNORECASE),
    ]

    # Intent detection patterns
    _INTENT_PATTERNS = {
        "compare": re.compile(r'\b(?:compare|vs\.?|versus|or)\b', re.IGNORECASE),
        "trending": re.compile(r'\b(?:trending|popular|hot|what\'?s?\s+(?:new|hot|trending)|top\s+\d+)\b', re.IGNORECASE),
        "deal_hunt": re.compile(r'\b(?:best\s+deal|cheapest|sale|clearance|discount|bargain|lowest\s+price)\b', re.IGNORECASE),
    }

    # Compound query splitter
    _COMPOUND_PATTERN = re.compile(
        r'\s+and\s+(?=[a-z]+\s+(?:' + '|'.join(
            re.escape(c) for c in list(CATEGORIES)[:50]  # Match "and <brand> <category>"
        ) + r'))',
        re.IGNORECASE
    )

    # Sanitization patterns
    _SANITIZE_PATTERNS = [
        re.compile(r'<[^>]+>'),                          # HTML tags
        re.compile(r'javascript\s*:', re.IGNORECASE),    # JS injection
        re.compile(r'on\w+\s*=', re.IGNORECASE),         # Event handlers
        re.compile(r'(?:--|;|/\*|\*/)', re.IGNORECASE),   # SQL comment/terminator
        re.compile(r'\b(?:DROP|DELETE|INSERT|UPDATE|SELECT|UNION|ALTER|CREATE|EXEC)\b', re.IGNORECASE),
    ]

    # Noise words
    NOISE_WORDS = frozenset({
        'i', 'am', 'looking', 'for', 'a', 'an', 'the', 'want', 'need',
        'buy', 'purchase', 'find', 'me', 'and', 'my', 'budget', 'is',
        'that', 'comes', 'with', 'which', 'has', 'includes', 'including',
        'under', 'below', 'less', 'than', 'around', 'about', 'approximately',
        'please', 'can', 'you', 'show', 'get', 'search', 'some', 'any',
        'where', 'to', 'of', 'in', 'on', 'at', 'from', 'like', 'similar',
        'best', 'good', 'great', 'nice', 'cool', 'awesome',
        # Conversational noise
        'she', 'he', 'her', 'him', 'his', 'they', 'their', 'sister',
        'brother', 'mom', 'dad', 'wife', 'husband', 'girlfriend', 'boyfriend',
        'daughter', 'son', 'aunt', 'uncle', 'likes', 'loves', 'prefers',
        'wants', 'something', 'not', 'too', 'but', 'also', 'really',
        'very', 'quite', 'dont', "don't", 'would', 'could', 'should',
    })

    # Common phrase removals (precompiled)
    _PHRASE_REMOVALS = [
        re.compile(r'i\s+(?:am\s+)?looking\s+for', re.IGNORECASE),
        re.compile(r'i\s+want\s+to\s+buy', re.IGNORECASE),
        re.compile(r'show\s+me', re.IGNORECASE),
        re.compile(r'can\s+you\s+find', re.IGNORECASE),
        re.compile(r'search\s+for', re.IGNORECASE),
        re.compile(r'find\s+me', re.IGNORECASE),
        re.compile(r'i\s+need', re.IGNORECASE),
        re.compile(r'help\s+me\s+find', re.IGNORECASE),
    ]

    def __init__(self, fuzzy_threshold: int = 2, enable_fuzzy: bool = True):
        """
        Initialize the parser.

        Args:
            fuzzy_threshold: Max edit distance for fuzzy matching (default: 2)
            enable_fuzzy: Whether to enable fuzzy matching (default: True)
        """
        self.fuzzy_threshold = fuzzy_threshold
        self.enable_fuzzy = enable_fuzzy
        self._trie = _ENTITY_TRIE

        # Precompute lowercase sets for fuzzy fallback
        self._brands_lower = {b.lower() for b in BRANDS}
        self._colors_lower = {c.lower() for c in COLORS}

    # ─── Public API ──────────────────────────────────────────────

    def parse(self, query: str) -> ParsedQuery:
        """
        Parse a natural language query into structured components.

        Pipeline:
        1. Sanitize input
        2. Detect intent
        3. Split compound queries
        4. Trie-based entity extraction
        5. Fuzzy matching fallback
        6. Price extraction
        7. Requirements extraction
        8. Query expansion
        9. Confidence scoring
        """
        # Step 0: Sanitize
        original = query.strip()
        sanitized = self._sanitize(original)

        if not sanitized:
            return ParsedQuery(original=original, product="", confidence_score=0.0)

        query_lower = sanitized.lower()

        # Step 1: Detect intent
        intent = self._detect_intent(query_lower)

        # Step 2: Check for compound queries
        sub_queries = self._split_compound(query_lower)
        if sub_queries and len(sub_queries) > 1:
            # Parse each sub-query independently
            parsed_subs = [self._parse_single(sq, original) for sq in sub_queries]
            # Return the first as primary, attach others
            primary = parsed_subs[0]
            primary.intent = intent
            primary.sub_queries = parsed_subs[1:]
            primary.original = original
            return primary

        # Step 3: Parse as single query
        result = self._parse_single(query_lower, original)
        result.intent = intent

        # Step 4: Brand-browse intent detection
        if result.brand and not result.category and not result.product.strip():
            result.intent = "brand_browse"

        return result

    # ─── Core parsing ────────────────────────────────────────────

    def _parse_single(self, query_lower: str, original: str) -> ParsedQuery:
        """Parse a single (non-compound) query."""
        recognized = {}

        # Tokenize
        words = query_lower.split()

        # Trie-based entity extraction
        trie_matches = self._trie.search(words)

        # Collect multi-entity results
        brands, colors, categories_found = [], [], []
        styles, materials_found = [], []
        gender_val, occasion_val = None, None
        brand_positions, entity_positions = set(), set()

        for match in trie_matches:
            etype = match["entity_type"]
            canonical = match["canonical"]
            matched_text = match["matched_text"]

            for p in range(match["start"], match["end"]):
                entity_positions.add(p)

            if etype == "brand":
                brands.append(canonical)
                for p in range(match["start"], match["end"]):
                    brand_positions.add(p)
                recognized[f'brand:{canonical}'] = f"{matched_text} → {canonical}"
            elif etype == "color":
                colors.append(canonical)
                recognized[f'color:{canonical}'] = f"{matched_text} → {canonical}"
            elif etype == "category":
                categories_found.append(canonical)
                recognized[f'category:{canonical}'] = f"{matched_text} → {canonical}"
            elif etype == "style":
                styles.append(canonical)
                recognized[f'style:{canonical}'] = canonical
            elif etype == "material":
                materials_found.append(canonical)
                recognized[f'material:{canonical}'] = canonical
            elif etype == "gender" and gender_val is None:
                gender_val = canonical
                recognized['gender'] = canonical
            elif etype == "occasion" and occasion_val is None:
                occasion_val = canonical
                recognized['occasion'] = canonical

        # Fuzzy matching fallback for unmatched words
        if self.enable_fuzzy:
            for i, word in enumerate(words):
                if i in entity_positions:
                    continue
                clean_word = ''.join(c for c in word if c.isalnum())
                if not clean_word or clean_word in self.NOISE_WORDS or len(clean_word) < 4:
                    continue

                # Try fuzzy brand match (strict: distance=1, length≥5, first char match)
                if not brands and len(clean_word) >= 5:
                    match = fuzzy_match(clean_word, BRANDS, max_distance=1)
                    if match and self._is_valid_fuzzy_match(clean_word, match[0]):
                        canonical = get_brand_canonical(match[0])
                        brands.append(canonical)
                        entity_positions.add(i)
                        recognized[f'brand:{canonical}'] = f"{clean_word} ~→ {canonical} (fuzzy)"

                # Try fuzzy color match
                if not colors and len(clean_word) >= 4:
                    match = fuzzy_match(clean_word, COLORS, max_distance=1)
                    if match:
                        canonical = get_color_canonical(match[0])
                        colors.append(canonical)
                        entity_positions.add(i)
                        recognized[f'color:{canonical}'] = f"{clean_word} ~→ {canonical} (fuzzy)"

        # Post-process: extract embedded entities from multi-word matches
        # e.g., "leather jacket" matched as category should also yield material=leather
        _materials_lower = {m.lower() for m in MATERIALS}
        _colors_lower = {c.lower() for c in COLORS}
        for match in trie_matches:
            if match["entity_type"] == "category" and " " in match["matched_text"]:
                for word in match["matched_text"].split():
                    if word in _materials_lower and word not in [m.lower() for m in materials_found]:
                        materials_found.append(word)
                        recognized[f'material:{word}'] = f"{word} (from {match['matched_text']})"
                    if word in _colors_lower and word not in [c.lower() for c in colors]:
                        canonical = get_color_canonical(word)
                        colors.append(canonical)
                        recognized[f'color:{canonical}'] = f"{word} (from {match['matched_text']})"

        # Deduplicate while preserving order
        brands = list(dict.fromkeys(brands))
        colors = list(dict.fromkeys(colors))
        categories_found = list(dict.fromkeys(categories_found))
        styles = list(dict.fromkeys(styles))
        materials_found = list(dict.fromkeys(materials_found))

        # Extract price
        min_budget, max_budget = self._extract_price_range(query_lower)
        if max_budget is None:
            max_budget = self._extract_budget(query_lower)

        # Extract requirements (multi-word)
        requirements = self._extract_requirements(query_lower)

        # Build product string (unrecognized terms)
        product = self._extract_product(words, entity_positions, query_lower)

        # Query expansion
        expanded = self._expand_query(
            brands[0] if brands else None,
            colors[0] if colors else None,
            categories_found[0] if categories_found else None,
            styles[0] if styles else None,
            materials_found[0] if materials_found else None,
            gender_val,
        )

        # Confidence score
        confidence = self._calculate_confidence(
            brands, colors, categories_found, styles, materials_found,
            gender_val, occasion_val, max_budget,
        )

        result = ParsedQuery(
            original=original,
            product=product,
            # Primary (backwards compatible)
            brand=brands[0] if brands else None,
            color=colors[0] if colors else None,
            category=categories_found[0] if categories_found else None,
            style=styles[0] if styles else None,
            material=materials_found[0] if materials_found else None,
            gender=gender_val,
            occasion=occasion_val,
            # Multi-entity
            brands=brands,
            colors=colors,
            categories=categories_found,
            styles=styles,
            materials=materials_found,
            # Constraints
            budget=max_budget,
            min_budget=min_budget,
            requirements=requirements,
            # Expansion
            expanded_terms=expanded,
            # Metadata
            recognized_entities=recognized,
            confidence_score=confidence,
        )

        # Conversational enrichment (v3)
        self._conversational_enrich(result, query_lower)

        return result

    # ─── Input sanitization ──────────────────────────────────────

    def _sanitize(self, query: str) -> str:
        """
        Sanitize user input to prevent injection attacks.

        - Strips HTML tags and entities
        - Removes SQL injection patterns
        - Enforces max length
        - Normalizes whitespace and unicode
        """
        if not query:
            return ""

        # Enforce length limit
        if len(query) > MAX_QUERY_LENGTH:
            query = query[:MAX_QUERY_LENGTH]
            logger.warning(f"Query truncated to {MAX_QUERY_LENGTH} chars")

        # Decode HTML entities
        query = html.unescape(query)

        # Remove dangerous patterns
        for pattern in self._SANITIZE_PATTERNS:
            query = pattern.sub('', query)

        # Normalize whitespace
        query = re.sub(r'\s+', ' ', query).strip()

        # Remove non-printable characters (keep basic ascii + common unicode)
        query = ''.join(c for c in query if c.isprintable())

        return query

    # ─── Intent detection ────────────────────────────────────────

    def _detect_intent(self, query: str) -> str:
        """
        Classify the query into an intent type.

        Returns: "search", "compare", "trending", "deal_hunt", or "brand_browse"
        """
        for intent, pattern in self._INTENT_PATTERNS.items():
            if pattern.search(query):
                # "or" between brands = compare, "or" in general = just search
                if intent == "compare":
                    # Only flag as compare if there are 2+ entity-like words around "or"/"vs"
                    if re.search(r'\b\w{3,}\s+(?:vs\.?|versus|or)\s+\w{3,}\b', query, re.IGNORECASE):
                        return "compare"
                    continue
                return intent

        return "search"

    # ─── Compound query splitting ────────────────────────────────

    def _split_compound(self, query: str) -> List[str]:
        """
        Split compound queries like "nike shoes and gucci bags" into sub-queries.

        Only splits if both sides contain identifiable entities.
        """
        # Look for " and " as a splitter
        if ' and ' not in query:
            return [query]

        parts = query.split(' and ')
        if len(parts) != 2:
            return [query]  # Only handle simple A and B

        left, right = parts[0].strip(), parts[1].strip()

        # Only split if both sides have substantial content (3+ chars)
        if len(left) < 3 or len(right) < 3:
            return [query]

        # Check if right side has its own entity (brand or category)
        right_words = right.split()
        right_has_entity = any(
            w in self._brands_lower or w in {c.lower() for c in CATEGORIES}
            for w in right_words
        )

        if right_has_entity:
            return [left, right]

        return [query]

    # ─── Price extraction ────────────────────────────────────────

    def _extract_price_range(self, query: str) -> Tuple[Optional[float], Optional[float]]:
        """
        Extract price range from query.

        Examples:
            "$50-$100"              → (50, 100)
            "between 50 and 100"    → (50, 100)
            "around $75"            → (56.25, 93.75)  ±25%

        Returns: (min_budget, max_budget) or (None, None)
        """
        # Check range patterns first
        for pattern in self._RANGE_PATTERNS:
            match = pattern.search(query)
            if match:
                try:
                    low = float(match.group(1).replace(',', ''))
                    high = float(match.group(2).replace(',', ''))
                    if low > high:
                        low, high = high, low
                    return (low, high)
                except ValueError:
                    continue

        # Check "around $X" pattern
        match = self._APPROX_PATTERN.search(query)
        if match:
            try:
                center = float(match.group(1).replace(',', ''))
                return (round(center * 0.75, 2), round(center * 1.25, 2))
            except ValueError:
                pass

        return (None, None)

    def _extract_budget(self, query: str) -> Optional[float]:
        """Extract single max budget from query."""
        for pattern in self._BUDGET_PATTERNS:
            match = pattern.search(query)
            if match:
                try:
                    return float(match.group(1).replace(',', ''))
                except ValueError:
                    continue
        return None

    # ─── Requirements extraction ─────────────────────────────────

    def _extract_requirements(self, query: str) -> List[str]:
        """
        Extract product requirements/features.

        Keeps multi-word requirements intact:
            "with noise canceling and fast charging"
            → ["noise canceling", "fast charging"]
        """
        requirements = []

        for pattern in self._REQUIREMENT_PATTERNS:
            matches = pattern.findall(query)
            for match in matches:
                req = match.strip().lower()
                # Remove leading articles
                req = re.sub(r'^(?:a|an|the)\s+', '', req)
                # Clean trailing noise
                req = re.sub(r'\s+(?:and|or|the|a|an)$', '', req)

                if req and len(req) > 2:
                    # Keep multi-word requirements
                    words = req.split()
                    # Filter out noise words only if entire req is a noise word
                    if not all(w in self.NOISE_WORDS for w in words):
                        clean_words = [w for w in words if w not in self.NOISE_WORDS or len(words) <= 2]
                        clean_req = ' '.join(clean_words).strip()
                        if clean_req and len(clean_req) > 2:
                            requirements.append(clean_req)

        return list(dict.fromkeys(requirements))  # Dedupe, preserve order

    # ─── Fuzzy match validation ──────────────────────────────────

    def _is_valid_fuzzy_match(self, query_word: str, matched: str) -> bool:
        """Validate fuzzy match to reduce false positives."""
        # Length ratio check (should be similar length)
        len_ratio = len(query_word) / len(matched)
        if len_ratio < 0.6 or len_ratio > 1.5:
            return False

        # First character should match (most brand typos keep the first letter)
        if query_word[0].lower() != matched[0].lower():
            return False

        return True

    # ─── Product extraction ──────────────────────────────────────

    def _extract_product(self, words: List[str], entity_positions: set, query: str) -> str:
        """Extract remaining product terms after entity removal."""
        # Remove budget mentions from query
        cleaned = query
        for pattern in self._BUDGET_PATTERNS:
            cleaned = pattern.sub('', cleaned)
        for pattern in self._RANGE_PATTERNS:
            cleaned = pattern.sub('', cleaned)
        if self._APPROX_PATTERN.search(cleaned):
            cleaned = self._APPROX_PATTERN.sub('', cleaned)

        # Remove common conversational phrases
        for pattern in self._PHRASE_REMOVALS:
            cleaned = pattern.sub('', cleaned)

        # Rebuild from non-entity, non-noise words
        cleaned_words = cleaned.split()
        product_words = []
        for i, word in enumerate(cleaned_words):
            word_clean = re.sub(r'[^\w\s-]', '', word).strip()
            if not word_clean:
                continue
            if word_clean.lower() in self.NOISE_WORDS:
                continue
            # Skip if this position was matched by trie
            if i < len(words) and i in entity_positions:
                continue
            product_words.append(word_clean)

        return ' '.join(product_words).strip()

    # ─── Query expansion ─────────────────────────────────────────

    def _expand_query(
        self,
        brand: Optional[str],
        color: Optional[str],
        category: Optional[str],
        style: Optional[str],
        material: Optional[str],
        gender: Optional[str],
    ) -> List[str]:
        """
        Generate alternative search terms using synonyms.

        Returns up to 3 expanded search strings.
        """
        if not category:
            return []

        expanded = []
        synonyms = SYNONYMS.get(category, [])

        for syn in synonyms[:3]:
            parts = []
            if gender:
                parts.append(gender)
            if color:
                parts.append(color)
            if brand:
                parts.append(brand)
            if material:
                parts.append(material)
            parts.append(syn)
            expanded.append(' '.join(parts))

        return expanded

    # ─── Confidence scoring ──────────────────────────────────────

    def _calculate_confidence(
        self,
        brands: List[str],
        colors: List[str],
        categories: List[str],
        styles: List[str],
        materials: List[str],
        gender: Optional[str],
        occasion: Optional[str],
        budget: Optional[float],
    ) -> float:
        """
        Calculate confidence score based on entities recognized.

        Scale: 0.0 (no understanding) to 1.0 (fully structured).
        """
        score = 0.0
        max_weight = 5.0

        # Primary entity weights
        if categories:
            score += 1.5  # Category is most important
        if brands:
            score += 1.0
        if colors:
            score += 0.8
        if styles:
            score += 0.5
        if gender:
            score += 0.5
        if materials:
            score += 0.3
        if occasion:
            score += 0.3
        if budget:
            score += 0.1

        # Bonus for multi-entity richness
        if len(brands) > 1:
            score += 0.2
        if len(colors) > 1:
            score += 0.1
        if len(categories) > 1:
            score += 0.1

        return min(score / max_weight, 1.0)

    # ─── Conversational intelligence ─────────────────────────────

    # Precompiled negation patterns
    _NEGATION_PATTERN = re.compile(
        r'(?:not\s+(?:too\s+)?|don\'?t\s+want\s+(?:it\s+)?(?:too\s+)?|no\s+|without\s+)'
        r'(\w+)',
        re.IGNORECASE
    )
    _LIKES_PATTERN = re.compile(
        r'(?:she|he|they|i)\s+(?:likes?|loves?|prefers?|wants?)\s+(.+?)(?:\.|,|$)',
        re.IGNORECASE
    )
    _RELATIONSHIP_PATTERN = re.compile(
        r'(?:my\s+|for\s+(?:my\s+)?)(\w+)(?:\'s)?',
        re.IGNORECASE
    )

    def _conversational_enrich(self, result: ParsedQuery, query: str):
        """
        Enrich parsed result with conversational understanding.

        Handles:
        - Aesthetic/vibe descriptors ("elegant" → formal, classy)
        - Color palettes ("pastels" → light pink, lavender, mint)
        - Season inference ("in August" → summer)
        - Relationship → gender ("sister" → women)
        - Negation / exclusions ("not too tight" → flowy, loose)
        - Event context ("graduation" → formal, elegant)
        - "she likes X" pattern extraction

        Modifies result in-place.
        """
        words = query.split()
        search_keywords = []

        # 1. Detect aesthetics/vibes
        for word in words:
            if word in AESTHETICS:
                aest = AESTHETICS[word]
                result.aesthetic = word
                search_keywords.extend(aest["keywords"])
                # Add style hints if no style detected
                if not result.style and aest["styles"]:
                    result.style = aest["styles"][0]
                    if aest["styles"][0] not in result.styles:
                        result.styles.append(aest["styles"][0])
                # Suggest categories if none detected
                if not result.category:
                    result.inferred_categories = aest["categories"]
                result.recognized_entities[f'aesthetic:{word}'] = f"{word} → {aest['styles']}"
                break  # Use the first aesthetic found

        # 2. Detect color palettes
        for palette_name, palette_colors in COLOR_PALETTES.items():
            if palette_name in query:
                result.color_palette = palette_name
                result.palette_colors = palette_colors
                # If no explicit color was found, use first palette color
                if not result.color:
                    result.color = palette_colors[0]
                    result.colors = palette_colors[:3]  # Top 3 from palette
                search_keywords.append(palette_name)
                result.recognized_entities[f'palette:{palette_name}'] = f"{palette_name} → {palette_colors[:4]}"
                break

        # 3. Detect season from month names
        for word in words:
            if word in MONTH_TO_SEASON:
                season = MONTH_TO_SEASON[word]
                result.season = season
                search_keywords.extend(SEASON_KEYWORDS.get(season, [])[:2])
                result.recognized_entities['season'] = f"{word} → {season}"
                break

        # Also check direct season words
        if not result.season:
            for season_word in ('summer', 'winter', 'spring', 'fall', 'autumn'):
                if season_word in query:
                    result.season = 'fall' if season_word == 'autumn' else season_word
                    search_keywords.extend(SEASON_KEYWORDS.get(result.season, [])[:2])
                    result.recognized_entities['season'] = season_word
                    break

        # 4. Detect relationship → gender
        if not result.gender:
            rel_matches = self._RELATIONSHIP_PATTERN.findall(query)
            for rel in rel_matches:
                rel_lower = rel.lower()
                if rel_lower in RELATIONSHIP_TO_GENDER:
                    result.gender = RELATIONSHIP_TO_GENDER[rel_lower]
                    result.recognized_entities['gender_inferred'] = f"{rel} → {result.gender}"
                    break

            # Also check for standalone pronouns
            if not result.gender:
                for word in words:
                    if word in RELATIONSHIP_TO_GENDER:
                        result.gender = RELATIONSHIP_TO_GENDER[word]
                        result.recognized_entities['gender_inferred'] = f"{word} → {result.gender}"
                        break

        # 5. Detect negations / exclusions
        neg_matches = self._NEGATION_PATTERN.findall(query)
        for negated_word in neg_matches:
            negated_lower = negated_word.lower()
            if negated_lower in NEGATION_ALTERNATIVES:
                result.exclusions.append(negated_lower)
                alternatives = NEGATION_ALTERNATIVES[negated_lower]
                result.style_alternatives.extend(alternatives)
                search_keywords.extend(alternatives[:2])
                result.recognized_entities[f'exclusion:{negated_lower}'] = f"NOT {negated_lower} → {alternatives}"

        # 6. Detect event context
        for event_word, event_data in EVENT_CONTEXT.items():
            if event_word in query:
                # Set occasion if not already set
                if not result.occasion:
                    result.occasion = event_data["occasion"]
                # Add style hints
                for hint in event_data["style_hints"]:
                    if hint not in search_keywords:
                        search_keywords.append(hint)
                # Suggest categories if none detected
                if not result.category:
                    result.inferred_categories = list(dict.fromkeys(
                        result.inferred_categories + event_data["categories"]
                    ))
                result.recognized_entities[f'event:{event_word}'] = f"{event_word} → {event_data['occasion']}"
                break  # Use the first event found

        # 7. "she likes X" extraction
        likes_matches = self._LIKES_PATTERN.findall(query)
        for liked_thing in likes_matches:
            liked = liked_thing.strip().lower()
            # Check if it's a palette
            if liked in COLOR_PALETTES and not result.color_palette:
                result.color_palette = liked
                result.palette_colors = COLOR_PALETTES[liked]
                if not result.color:
                    result.color = COLOR_PALETTES[liked][0]
                    result.colors = COLOR_PALETTES[liked][:3]
                search_keywords.append(liked)
                result.recognized_entities[f'liked_palette:{liked}'] = f"likes {liked}"
            # Check if it's an aesthetic
            elif liked in AESTHETICS and not result.aesthetic:
                result.aesthetic = liked
                search_keywords.extend(AESTHETICS[liked]["keywords"][:2])
                result.recognized_entities[f'liked_aesthetic:{liked}'] = f"likes {liked}"
            # Otherwise add as requirement
            elif liked and len(liked) > 2:
                if liked not in result.requirements:
                    result.requirements.append(liked)

        # 8. Build enriched search keywords
        result.search_keywords = list(dict.fromkeys(search_keywords))  # Dedupe

        # 9. Boost confidence for conversational understanding
        if result.aesthetic or result.color_palette or result.season or result.exclusions:
            result.confidence_score = min(result.confidence_score + 0.15, 1.0)


# =============================================================================
# CACHED PARSE — avoid re-parsing identical queries
# =============================================================================

@lru_cache(maxsize=256)
def _cached_parse(query: str) -> dict:
    """
    Cache parse results for identical queries.

    Uses dict serialization since ParsedQuery isn't hashable.
    """
    parser = HybridQueryParser()
    result = parser.parse(query)
    return result.to_dict()


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
