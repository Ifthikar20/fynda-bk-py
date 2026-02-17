"""
Shopify Vendor

Searches multiple Shopify stores via their public /products.json endpoint.
Extends BaseVendorService — returns VendorProduct.
"""

import re
import math
import logging
from typing import List, Optional
from datetime import datetime
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base_vendor import BaseVendorService, VendorProduct

logger = logging.getLogger(__name__)


# Popular Shopify fashion stores to search
DEFAULT_SHOPIFY_STORES = [
    # Women's Fashion
    {"name": "Fashion Nova", "domain": "fashionnova.com", "category": "fashion"},
    {"name": "Princess Polly", "domain": "us.princesspolly.com", "category": "fashion"},
    {"name": "Oh Polly", "domain": "ohpolly.com", "category": "fashion"},
    {"name": "Meshki", "domain": "meshki.us", "category": "fashion"},
    {"name": "Beginning Boutique", "domain": "beginningboutique.com", "category": "fashion"},
    # Men's & Unisex Fashion
    {"name": "Gymshark", "domain": "gymshark.com", "category": "fitness"},
    {"name": "Chubbies", "domain": "chubbiesshorts.com", "category": "fashion"},
    {"name": "Taylor Stitch", "domain": "taylorstitch.com", "category": "fashion"},
    {"name": "BYLT Basics", "domain": "byltbasics.com", "category": "fashion"},
    {"name": "True Classic", "domain": "trueclassictees.com", "category": "fashion"},
    {"name": "Cuts Clothing", "domain": "cutsclothing.com", "category": "fashion"},
    # Shoes & Bags
    {"name": "Steve Madden", "domain": "stevemadden.com", "category": "shoes"},
    {"name": "Allbirds", "domain": "allbirds.com", "category": "shoes"},
    {"name": "Rebecca Minkoff", "domain": "rebeccaminkoff.com", "category": "bags"},
    # Accessories & Jewelry
    {"name": "MVMT", "domain": "mvmt.com", "category": "watches"},
    {"name": "Mejuri", "domain": "mejuri.com", "category": "jewelry"},
    {"name": "Ana Luisa", "domain": "analuisa.com", "category": "jewelry"},
    # Beauty
    {"name": "ColourPop", "domain": "colourpop.com", "category": "beauty"},
    {"name": "Kylie Cosmetics", "domain": "kyliecosmetics.com", "category": "beauty"},
]


class ShopifyVendor(BaseVendorService):
    """Shopify multi-store product search via public /products.json."""
    
    VENDOR_ID = "shopify"
    VENDOR_NAME = "Shopify"
    PRIORITY = 60
    TIMEOUT = 10
    
    def __init__(self, stores: list = None):
        self.stores = stores or DEFAULT_SHOPIFY_STORES
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        super().__init__()
    
    def is_configured(self) -> bool:
        # Shopify public JSON endpoint requires no auth
        return True
    
    # ── BaseVendorService._do_search implementation ─────────────
    
    def _do_search(self, query: str, limit: int) -> List[VendorProduct]:
        all_products = []
        
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(self._search_store, store, query): store
                for store in self.stores[:15]
            }
            
            for future in as_completed(futures, timeout=15):
                store = futures[future]
                try:
                    products = future.result()
                    all_products.extend(products)
                except Exception as e:
                    logger.warning(f"Error scraping {store['name']}: {e}")
        
        # Sort by relevance score (set during _parse_products)
        all_products.sort(
            key=lambda p: getattr(p, '_relevance_score', 0),
            reverse=True,
        )
        
        logger.info(f"Shopify returned {min(len(all_products), limit)} products for '{query}'")
        return all_products[:limit]
    
    def _search_store(self, store: dict, query: str) -> List[VendorProduct]:
        """Search a single Shopify store."""
        domain = store["domain"]
        store_name = store["name"]
        
        for protocol in ["https", "http"]:
            try:
                url = f"{protocol}://{domain}/products.json"
                response = requests.get(
                    url,
                    params={"limit": 50},
                    headers=self.headers,
                    timeout=self.timeout,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_products(data, query, store_name, domain)
            except requests.exceptions.SSLError:
                continue
            except Exception as e:
                logger.debug(f"Failed to fetch {domain}: {e}")
                continue
        
        return []
    
    def _parse_products(self, data: dict, query: str, store_name: str, domain: str) -> List[VendorProduct]:
        """Parse products from Shopify JSON response."""
        products = []
        query_words = set(query.lower().split())
        num_query_words = len(query_words)
        # For multi-word queries, require at least 60% word match (ceil rounds up)
        min_match = max(1, math.ceil(num_query_words * 0.6)) if num_query_words > 1 else 1
        
        for product in data.get("products", []):
            title = product.get("title", "")
            title_lower = title.lower()
            
            # Build searchable text — exclude cross-sell tags (pair:...)
            raw_tags = product.get("tags", [])
            clean_tags = [t.lower() for t in raw_tags if not t.lower().startswith("pair:")]
            product_type = product.get("product_type", "").lower()
            variant_text = " ".join(
                v.get("title", "").lower() for v in product.get("variants", [])
            )
            
            # Use word-level matching (split into individual words) to avoid
            # substring false-positives like 'bag' matching inside 'handbag'
            searchable_words = set(
                re.split(r'[\s\-/,]+', f"{title_lower} {product_type} {' '.join(clean_tags)} {variant_text}")
            )
            
            # Count how many query words appear as whole words
            matched_words = sum(1 for word in query_words if word in searchable_words)
            
            if matched_words < min_match:
                continue
            
            # Relevance score: boost if matches are in title (most relevant)
            title_words = set(re.split(r'[\s\-/,]+', title_lower))
            title_matches = sum(1 for word in query_words if word in title_words)
            relevance = (matched_words + title_matches) / (num_query_words * 2) if num_query_words else 0
            
            variants = product.get("variants", [])
            if not variants:
                continue
            
            # Find best in-stock variant
            variant = None
            for v in variants:
                if v.get("available", True):
                    variant = v
                    break
            if not variant:
                variant = variants[0]
            
            try:
                price = float(variant.get("price", 0))
            except (TypeError, ValueError):
                continue
            
            if price == 0:
                continue
            
            # Compare-at price
            compare_at = None
            discount = 0
            try:
                compare_at_str = variant.get("compare_at_price")
                if compare_at_str:
                    compare_at = float(compare_at_str)
                    if compare_at > price:
                        discount = int((1 - price / compare_at) * 100)
            except (TypeError, ValueError):
                pass
            
            # Image
            images = product.get("images", [])
            image_url = images[0].get("src", "") if images else ""
            
            # Clean description (strip HTML)
            description = product.get("body_html", "") or ""
            description = re.sub(r'<[^>]+>', '', description).strip()[:300]
            
            tags = product.get("tags", [])
            
            vp = VendorProduct(
                id=f"shopify-{domain}-{product.get('id', '')}",
                title=title,
                description=description,
                price=price,
                original_price=compare_at,
                discount_percent=discount,
                currency="USD",
                url=f"https://{domain}/products/{product.get('handle', '')}",
                image_url=image_url,
                source=f"Shopify ({store_name})",
                merchant_name=store_name,
                brand=product.get("vendor", ""),
                seller=product.get("vendor", store_name),
                in_stock=variant.get("available", True),
                category=product.get("product_type", ""),
                features=tags[:5],
                shipping="Varies",
                fetched_at=datetime.now().isoformat(),
            )
            vp._relevance_score = relevance
            products.append(vp)
        
        return products
    
    def add_store(self, name: str, domain: str, category: str = "other"):
        """Add a new Shopify store to the search list."""
        self.stores.append({"name": name, "domain": domain, "category": category})
