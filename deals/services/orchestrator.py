"""
API Orchestrator

Coordinates multiple marketplace APIs.
Aggregates results from Amazon, affiliate networks, and other real data sources.
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
from .ebay_service import ebay_service
from .bestbuy_service import bestbuy_service
from .facebook_service import facebook_service
from .shopify_service import shopify_service
from .affiliates import affiliate_aggregator
from .amazon_service import amazon_service, QuotaExceededException
from .spell_corrector import correct_query
from .vendors import vendor_manager

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
    Orchestrates deal searches across multiple marketplace sources.
    
    Data sources (in priority order):
    1. eBay Browse API - Requires EBAY_APP_ID, EBAY_CERT_ID
    2. Best Buy Products API - Requires BESTBUY_API_KEY
    3. Facebook Marketplace - Requires RAPIDAPI_KEY (or uses mock)
    4. Shopify Stores - No auth required, scrapes /products.json
    5. Mock Data - Always available as fallback
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
            # Reconstruct SearchResult from cached data
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
    
    def _fetch_all_deals_with_spelling(self, parsed: ParsedQuery, raw_query: str):
        """
        Fetch deals from all sources + spell correction in parallel.
        
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
            
            # Add enabled vendors from VendorManager
            for vendor_id, instance in vendor_manager.get_all_instances().items():
                futures[executor.submit(self._fetch_from_vendor, instance, parsed)] = instance.VENDOR_NAME
            
            # Also include affiliate aggregator for compatibility
            futures[executor.submit(self._fetch_affiliates, parsed)] = "Affiliates"
            
            # Include Amazon via RapidAPI
            futures[executor.submit(self._fetch_amazon, parsed)] = "Amazon"
            
            for future in concurrent.futures.as_completed(futures, timeout=20):
                source = futures[future]
                try:
                    result = future.result()
                    if isinstance(result, tuple):
                        deals, is_quota_exceeded = result
                        if is_quota_exceeded:
                            quota_exceeded = True
                    else:
                        deals = result
                    if deals:
                        all_deals.extend(deals)
                        sources_with_results.append(source)
                        logger.info(f"Fetched {len(deals)} deals from {source}")
                except Exception as e:
                    logger.error(f"Error fetching from {source}: {e}")
            
            # Get spell result (non-blocking, already completed or will be fast)
            try:
                spell_result = spell_future.result(timeout=0.5)
            except Exception as e:
                logger.warning(f"Spell correction timed out or failed: {e}")
        
        return all_deals, sources_with_results, quota_exceeded, spell_result
    
    def _fetch_from_vendor(self, vendor_instance, parsed: ParsedQuery) -> List[Dict[str, Any]]:
        """
        Fetch deals from a vendor instance.
        
        Uses the standardized VendorProduct format.
        """
        try:
            search_query = parsed.get_search_terms() or parsed.original
            products = vendor_instance.search_products(
                query=search_query,
                limit=15,
            )
            # Convert VendorProduct to dict if needed
            results = []
            for p in products:
                if hasattr(p, 'to_dict'):
                    results.append(p.to_dict())
                elif isinstance(p, dict):
                    results.append(p)
            
            # Filter by budget if specified
            if parsed.budget:
                results = [p for p in results if p.get('price', 0) <= parsed.budget]
            return results
        except Exception as e:
            logger.warning(f"Vendor fetch error: {e}")
            return []
    
    def _fetch_amazon(self, parsed: ParsedQuery) -> tuple[List[Dict[str, Any]], bool]:
        """Fetch deals from Amazon via RapidAPI. Returns (deals, quota_exceeded)."""
        try:
            search_query = parsed.get_search_terms() or parsed.original
            deals = amazon_service.search(
                query=search_query,
                limit=10,
                max_price=parsed.budget,
            )
            return [d.to_dict() for d in deals], False
        except QuotaExceededException:
            logger.warning("Amazon quota exceeded — skipping Amazon results")
            return [], True
        except Exception as e:
            logger.warning(f"Amazon fetch error: {e}")
            return [], False
    
    def _fetch_ebay(self, parsed: ParsedQuery) -> List[Dict[str, Any]]:
        """Fetch deals from eBay."""
        try:
            deals = ebay_service.search(
                query=parsed.product,
                limit=10,
                max_price=parsed.budget,
            )
            return [d.to_dict() for d in deals]
        except Exception as e:
            logger.warning(f"eBay fetch error: {e}")
            return []
    
    def _fetch_bestbuy(self, parsed: ParsedQuery) -> List[Dict[str, Any]]:
        """Fetch deals from Best Buy."""
        try:
            deals = bestbuy_service.search(
                query=parsed.product,
                limit=10,
                max_price=parsed.budget,
            )
            return [d.to_dict() for d in deals]
        except Exception as e:
            logger.warning(f"Best Buy fetch error: {e}")
            return []
    
    def _fetch_facebook(self, parsed: ParsedQuery) -> List[Dict[str, Any]]:
        """Fetch deals from Facebook Marketplace."""
        try:
            deals = facebook_service.search(
                query=parsed.product,
                limit=8,
                max_price=parsed.budget,
            )
            return [d.to_dict() for d in deals]
        except Exception as e:
            logger.warning(f"Facebook Marketplace fetch error: {e}")
            return []
    

    
    def _fetch_shopify(self, parsed: ParsedQuery) -> List[Dict[str, Any]]:
        """Fetch deals from Shopify stores."""
        try:
            products = shopify_service.search(
                query=parsed.product,
                limit=10,
                max_price=parsed.budget,
            )
            return [p.to_dict() for p in products]
        except Exception as e:
            logger.warning(f"Shopify fetch error: {e}")
            return []
    
    def _fetch_affiliates(self, parsed: ParsedQuery) -> List[Dict[str, Any]]:
        """
        Fetch deals from affiliate networks (CJ, Rakuten, ShareASale).
        
        Provides access to 40,000+ retailers.
        """
        try:
            products = affiliate_aggregator.search_all(
                query=parsed.product,
                limit=15,
                sort_by="price",
            )
            # Filter by budget if specified
            if parsed.budget:
                products = [p for p in products if p.price <= parsed.budget or p.price == 0]
            return [p.to_dict() for p in products]
        except Exception as e:
            logger.warning(f"Affiliate networks fetch error: {e}")
            return []
    
    def _filter_non_fashion(self, deals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Dual-layer filter to ensure only fashion products appear.
        
        Layer 1 (blocklist): Remove items with known non-fashion keywords.
        Layer 2 (allowlist): Of remaining items, keep only those containing
                            at least one fashion keyword in the title.
        
        This catches edge cases like "apple" (groceries) that aren't in
        the blocklist but also don't contain any fashion terms.
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
        
        When the user searches "white coat men", filter out items with
        women-specific terms in the title, and vice versa.
        
        Uses regex word boundaries for men's terms to prevent
        "men" from matching inside "women".
        """
        import re
        
        # Women indicators — simple substring matching (no collision risk)
        WOMEN_INDICATORS = {"women", "womens", "women's", "woman", "ladies", "lady", "girls", "girl", "female", "maternity"}
        
        # Men indicators — use regex word boundaries to avoid matching inside "women"
        # \bmen\b matches "men" but NOT "women" or "menswear"→ wait, menswear IS men's
        # So we use \bmen(?!'s|\w) pattern carefully:
        MEN_PATTERNS = [
            re.compile(r"\bmen\b", re.IGNORECASE),       # "men" as whole word (not "women")
            re.compile(r"\bmens\b", re.IGNORECASE),       # "mens"
            re.compile(r"\bmen's\b", re.IGNORECASE),      # "men's"
            re.compile(r"\bboys?\b", re.IGNORECASE),      # "boy" or "boys"
            re.compile(r"\bmale\b", re.IGNORECASE),       # "male"
            re.compile(r"\bgentleman\b", re.IGNORECASE),  # "gentleman"
        ]
        
        gender_lower = gender.lower()
        
        def passes_gender(deal: Dict[str, Any]) -> bool:
            title = (deal.get("title") or "").lower()
            
            if gender_lower == "men":
                # Remove women's products (simple substring is fine)
                for indicator in WOMEN_INDICATORS:
                    if indicator in title:
                        return False
            elif gender_lower == "women":
                # Remove men's products (use regex to avoid "men" in "women")
                for pattern in MEN_PATTERNS:
                    if pattern.search(title):
                        return False
            elif gender_lower in ("kids", "children"):
                # Remove adult-specific products
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
            # Normalize title for comparison
            title_key = deal.get("title", "").lower()[:50]
            
            if title_key not in seen_titles:
                seen_titles[title_key] = deal
                unique_deals.append(deal)
            else:
                # Keep the cheaper one
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
            # Weighted scoring - ensure all values are numbers, not None
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
                "Shopify": 8,
                "Affiliates": 5,
                "Mock": 0,
            }.get(source, 5)  # Default bonus for affiliate sources
            
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
