"""
API Orchestrator

Coordinates multiple marketplace APIs via the unified vendor layer.
Aggregates results from all enabled vendors (Amazon, eBay, affiliates, etc.).

Adding a new vendor requires ZERO changes here — just create a vendor
file in vendors/ and register it in vendor_registry.py.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging
import hashlib
import json
import concurrent.futures

from django.core.cache import cache

from .query_parser import query_parser, ParsedQuery
from .spell_corrector import correct_query
from .vendors import vendor_manager, QuotaExceededError

logger = logging.getLogger(__name__)

# Cache TTL: 6 hours (in seconds)
SEARCH_CACHE_TTL = 6 * 60 * 60

# ── Fashion taxonomy — loaded from JSON built from professional datasets ──
# Source: Google Product Taxonomy + Fashionpedia + hand-curated extras
# Rebuild: python deals/services/build_taxonomy.py
import json as _json
from pathlib import Path as _Path

_TAXONOMY_PATH = _Path(__file__).parent / "fashion_taxonomy.json"

def _load_taxonomy():
    """Load fashion/non-fashion terms from taxonomy JSON."""
    try:
        with open(_TAXONOMY_PATH) as f:
            data = _json.load(f)
        return data["fashion_terms"], data["non_fashion_terms"]
    except (FileNotFoundError, KeyError) as e:
        logger.warning(f"Taxonomy file missing or invalid ({e}), using fallback")
        # Minimal fallback so the app still works without the JSON
        return (
            ["dress", "shirt", "shoe", "bag", "jacket", "jeans", "sweater",
             "boot", "sneaker", "necklace", "earring", "watch", "hat",
             "scarf", "belt", "skirt", "coat", "blouse", "sandal", "heel"],
            ["cake", "laptop", "toy", "furniture", "garden", "drill",
             "dog food", "vitamin", "basketball", "vacuum"],
        )

FASHION_KEYWORDS, NON_FASHION_KEYWORDS = _load_taxonomy()
logger.info(f"Taxonomy loaded: {len(FASHION_KEYWORDS)} fashion, {len(NON_FASHION_KEYWORDS)} non-fashion terms")


@dataclass
class SearchResult:
    """Container for search results."""
    query: ParsedQuery
    deals: List[Dict[str, Any]]
    sources_queried: List[str]
    sources_with_results: List[str]
    cache_hit: bool
    search_time_ms: int
    quota_exceeded: bool = False
    suggested_query: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "query": self.query.to_dict(),
            "deals": self.deals,
            "meta": {
                "total_results": len(self.deals),
                "sources_queried": self.sources_queried,
                "sources_with_results": self.sources_with_results,
                "cache_hit": self.cache_hit,
                "search_time_ms": self.search_time_ms,
            },
            "detected_gender": self.query.gender,
        }
        if self.suggested_query:
            result["suggested_query"] = self.suggested_query
        if self.quota_exceeded:
            result["quota_warning"] = "Some marketplace results may be limited right now. Please try again later."
        return result


class DealOrchestrator:
    """
    Orchestrates deal searches across all enabled vendors.
    
    Uses the VendorManager to discover and query all registered vendors.
    Adding a new vendor requires zero changes to this file.
    
    Pipeline:
    1. Parse query (NLP)
    2. Fetch from all vendors in parallel + spell correction
    3. Budget filter
    4. Deduplicate
    5. Fashion filter
    6. Gender filter
    7. Rank & limit
    """
    
    def __init__(self):
        # Get source names from enabled vendors
        enabled = vendor_manager.get_enabled_vendors()
        self.all_sources = [v.name for v in enabled]
    
    def _get_cache_key(self, query: str) -> str:
        """Generate a normalized cache key for a search query."""
        normalized = query.lower().strip()
        query_hash = hashlib.md5(normalized.encode()).hexdigest()
        return f"search:{query_hash}"
    
    def search(self, query: str) -> SearchResult:
        """
        Search for deals matching the natural language query.
        
        Uses Django cache to avoid redundant API calls.
        Queries all configured marketplaces in parallel and aggregates results.
        
        Args:
            query: Natural language search string
                   e.g., "sony camera $1200 with lens"
        
        Returns:
            SearchResult with parsed query, deals, and metadata
        """
        start_time = datetime.now()
        
        # Check cache first
        cache_key = self._get_cache_key(query)
        cached = cache.get(cache_key)
        if cached:
            logger.info(f"Cache HIT for query: '{query}'")
            search_time = int((datetime.now() - start_time).total_seconds() * 1000)
            parsed = query_parser.parse(query)
            return SearchResult(
                query=parsed,
                deals=cached["deals"],
                sources_queried=cached.get("sources_queried", self.all_sources),
                sources_with_results=cached.get("sources_with_results", []),
                cache_hit=True,
                search_time_ms=search_time,
                quota_exceeded=cached.get("quota_exceeded", False),
            )
        
        logger.info(f"Cache MISS for query: '{query}' — fetching from APIs")
        
        # Step 1: Parse the query
        parsed = query_parser.parse(query)
        logger.info(f"Parsed query: product='{parsed.product}', budget={parsed.budget}, requirements={parsed.requirements}")
        
        # Step 2: Fetch deals + spell correction in parallel
        deals, sources_with_results, quota_exceeded, spell_result = self._fetch_all_deals_with_spelling(parsed, query)
        
        # Step 3: Apply budget filter
        if parsed.budget:
            deals = [d for d in deals if d.get("price", 0) <= parsed.budget]
        
        # Step 4: Deduplicate similar listings
        deals = self._deduplicate_deals(deals)
        
        # Step 4.5: Filter non-fashion products
        pre_filter = len(deals)
        deals = self._filter_non_fashion(deals)
        if pre_filter != len(deals):
            logger.info(f"Fashion filter removed {pre_filter - len(deals)} non-fashion items")
        
        # Step 4.6: Filter by gender when specified in query
        if parsed.gender:
            pre_gender = len(deals)
            deals = self._filter_by_gender(deals, parsed.gender)
            if pre_gender != len(deals):
                logger.info(f"Gender filter removed {pre_gender - len(deals)} items (kept: {parsed.gender})")
        
        # Step 5: Rank results
        deals = self._rank_deals(deals, parsed)
        
        # Limit to top 20
        deals = deals[:20]
        
        # Calculate search time
        search_time = int((datetime.now() - start_time).total_seconds() * 1000)
        
        # Cache the results (6 hours)
        cache.set(cache_key, {
            "deals": deals,
            "sources_queried": self.all_sources,
            "sources_with_results": sources_with_results,
            "quota_exceeded": quota_exceeded,
        }, SEARCH_CACHE_TTL)
        logger.info(f"Cached {len(deals)} deals for query: '{query}' (TTL: {SEARCH_CACHE_TTL}s)")
        
        # Include spell suggestion if results are scarce and we have a correction
        suggested_query = None
        if spell_result and spell_result.was_corrected and len(deals) < 3:
            suggested_query = spell_result.corrected
            logger.info(f"Suggesting corrected query: '{query}' → '{suggested_query}'")
        
        return SearchResult(
            query=parsed,
            deals=deals,
            sources_queried=self.all_sources,
            sources_with_results=sources_with_results,
            cache_hit=False,
            search_time_ms=search_time,
            quota_exceeded=quota_exceeded,
            suggested_query=suggested_query,
        )
    
    # ── Vendor fetching (generic — no per-vendor methods) ───────
    
    def _fetch_all_deals_with_spelling(self, parsed: ParsedQuery, raw_query: str):
        """
        Fetch deals from ALL enabled vendors + spell correction in parallel.
        
        Uses vendor_manager.get_all_instances() so new vendors are
        automatically included without editing this method.
        
        Returns:
            Tuple of (all_deals, sources_with_results, quota_exceeded, spell_result)
        """
        all_deals = []
        sources_with_results = []
        quota_exceeded = False
        spell_result = None
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {}
            
            # Fire spell correction in parallel
            spell_future = executor.submit(correct_query, raw_query)
            
            # Submit search to ALL enabled vendors — generic loop
            for vendor_id, instance in vendor_manager.get_all_instances().items():
                futures[executor.submit(
                    self._fetch_from_vendor, instance, parsed
                )] = instance.VENDOR_NAME
            
            # Collect results as they complete
            for future in concurrent.futures.as_completed(futures, timeout=20):
                source = futures[future]
                try:
                    result = future.result()
                    if isinstance(result, tuple):
                        deals, is_quota = result
                        if is_quota:
                            quota_exceeded = True
                    else:
                        deals = result
                    if deals:
                        all_deals.extend(deals)
                        sources_with_results.append(source)
                        logger.info(f"Fetched {len(deals)} deals from {source}")
                except Exception as e:
                    logger.error(f"Error fetching from {source}: {e}")
            
            # Get spell result (non-blocking)
            try:
                spell_result = spell_future.result(timeout=0.5)
            except Exception as e:
                logger.warning(f"Spell correction timed out or failed: {e}")
        
        return all_deals, sources_with_results, quota_exceeded, spell_result
    
    def _fetch_from_vendor(self, vendor_instance, parsed: ParsedQuery):
        """
        Fetch deals from a single vendor.
        
        The circuit breaker in BaseVendorService.search_products()
        handles failures automatically — no try/except needed here
        for vendor-level errors.
        
        Returns:
            (deals_list, quota_exceeded) tuple, or just deals_list
        """
        search_query = parsed.get_search_terms() or parsed.original
        quota_exceeded = False
        
        try:
            products = vendor_instance.search_products(
                query=search_query,
                limit=15,
            )
        except QuotaExceededError:
            logger.warning(f"{vendor_instance.VENDOR_NAME} quota exceeded")
            return [], True
        except Exception as e:
            logger.warning(f"{vendor_instance.VENDOR_NAME} fetch error: {e}")
            return []
        
        # Convert VendorProduct to dict
        results = []
        for p in products:
            if hasattr(p, 'to_dict'):
                results.append(p.to_dict())
            elif isinstance(p, dict):
                results.append(p)
        
        # Filter by budget if specified
        if parsed.budget:
            results = [p for p in results if p.get('price', 0) <= parsed.budget]
        
        return results, quota_exceeded
    
    # ── Filtering and ranking (unchanged) ──────────────────────
    
    def _filter_non_fashion(self, deals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Dual-layer filter to ensure only fashion products appear.
        
        Layer 1 (blocklist): Remove items with known non-fashion keywords.
        Layer 2 (allowlist): Of remaining items, keep only those containing
                            at least one fashion keyword in the title.
        """
        def is_fashion(deal: Dict[str, Any]) -> bool:
            title = (deal.get("title") or "").lower()
            
            # Layer 1: Block known non-fashion items
            for keyword in NON_FASHION_KEYWORDS:
                if keyword in title:
                    return False
            
            # Layer 2: Must contain at least one fashion keyword
            for keyword in FASHION_KEYWORDS:
                if keyword in title:
                    return True
            
            # No fashion keyword found — reject
            return False
        
        return [d for d in deals if is_fashion(d)]
    
    def _filter_by_gender(self, deals: List[Dict[str, Any]], gender: str) -> List[Dict[str, Any]]:
        """
        Remove products that are clearly for the opposite gender.
        
        Uses regex word boundaries for men's terms to prevent
        "men" from matching inside "women".
        """
        import re
        
        WOMEN_INDICATORS = {"women", "womens", "women's", "woman", "ladies", "lady", "girls", "girl", "female", "maternity"}
        
        MEN_PATTERNS = [
            re.compile(r"\bmen\b", re.IGNORECASE),
            re.compile(r"\bmens\b", re.IGNORECASE),
            re.compile(r"\bmen's\b", re.IGNORECASE),
            re.compile(r"\bboys?\b", re.IGNORECASE),
            re.compile(r"\bmale\b", re.IGNORECASE),
            re.compile(r"\bgentleman\b", re.IGNORECASE),
        ]
        
        gender_lower = gender.lower()
        
        def passes_gender(deal: Dict[str, Any]) -> bool:
            title = (deal.get("title") or "").lower()
            
            if gender_lower == "men":
                for indicator in WOMEN_INDICATORS:
                    if indicator in title:
                        return False
            elif gender_lower == "women":
                for pattern in MEN_PATTERNS:
                    if pattern.search(title):
                        return False
            elif gender_lower in ("kids", "children"):
                for indicator in WOMEN_INDICATORS:
                    if indicator in title:
                        return False
                for pattern in MEN_PATTERNS:
                    if pattern.search(title):
                        return False
            
            return True
        
        return [d for d in deals if passes_gender(d)]
    
    def _deduplicate_deals(self, deals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate listings based on title similarity.
        Keeps the cheapest version of similar items.
        """
        seen_titles = {}
        unique_deals = []
        
        for deal in deals:
            title_key = deal.get("title", "").lower()[:50]
            
            if title_key not in seen_titles:
                seen_titles[title_key] = deal
                unique_deals.append(deal)
            else:
                existing = seen_titles[title_key]
                if deal.get("price", float("inf")) < existing.get("price", float("inf")):
                    unique_deals.remove(existing)
                    unique_deals.append(deal)
                    seen_titles[title_key] = deal
        
        return unique_deals
    
    def _rank_deals(
        self, deals: List[Dict[str, Any]], parsed: ParsedQuery
    ) -> List[Dict[str, Any]]:
        """
        Rank deals by value (best deals first).
        
        Ranking factors:
        1. Relevance score (matches query/requirements)
        2. Discount percentage
        3. Seller rating
        4. User reviews
        5. Source priority (real APIs ranked higher)
        """
        def score(deal: Dict) -> float:
            relevance = deal.get("relevance_score") if deal.get("relevance_score") is not None else 50
            discount = deal.get("discount_percent") if deal.get("discount_percent") is not None else 0
            rating = deal.get("rating") if deal.get("rating") is not None else 4.0
            reviews_count = deal.get("reviews_count") if deal.get("reviews_count") is not None else 0
            reviews = min(reviews_count / 1000, 5)
            
            # Source priority bonus
            source = deal.get("source", "") or ""
            source_bonus = {
                "Amazon": 18,
                "eBay": 15,
                "Best Buy": 15,
                "Facebook Marketplace": 10,
            }.get(source, 0)
            
            # Shopify and Affiliate sources (partial match)
            if not source_bonus:
                if "Shopify" in source:
                    source_bonus = 8
                elif "Affiliate" in source:
                    source_bonus = 5
            
            # Check if deal meets requirements
            requirement_bonus = 0
            if parsed.requirements:
                features = [f.lower() for f in deal.get("features", []) or []]
                title_lower = (deal.get("title", "") or "").lower()
                for req in parsed.requirements:
                    if req.lower() in features or req.lower() in title_lower:
                        requirement_bonus += 20
            
            return (
                float(relevance) * 0.3 +
                float(discount) * 0.2 +
                float(rating) * 4 +
                float(reviews) * 2 +
                source_bonus +
                requirement_bonus
            )
        
        return sorted(deals, key=score, reverse=True)


# Singleton instance
orchestrator = DealOrchestrator()
