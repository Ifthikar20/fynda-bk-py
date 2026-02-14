"""
Shopify Vendor

Searches multiple Shopify stores via their public /products.json endpoint.
Extends BaseVendorService — returns VendorProduct.
"""

import re
import logging
from typing import List, Optional
from datetime import datetime
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base_vendor import BaseVendorService, VendorProduct

logger = logging.getLogger(__name__)


# Popular Shopify fashion stores to search
DEFAULT_SHOPIFY_STORES = [
    {"name": "Fashion Nova", "domain": "fashionnova.com", "category": "fashion"},
    {"name": "Gymshark", "domain": "gymshark.com", "category": "fitness"},
    {"name": "Allbirds", "domain": "allbirds.com", "category": "shoes"},
    {"name": "MVMT", "domain": "mvmt.com", "category": "watches"},
    {"name": "Chubbies", "domain": "chubbiesshorts.com", "category": "fashion"},
    {"name": "Anker", "domain": "anker.com", "category": "tech"},
    {"name": "Peak Design", "domain": "peakdesign.com", "category": "camera"},
    {"name": "Moment", "domain": "shopmoment.com", "category": "camera"},
    {"name": "Brooklinen", "domain": "brooklinen.com", "category": "home"},
    {"name": "Ruggable", "domain": "ruggable.com", "category": "home"},
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
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self._search_store, store, query): store
                for store in self.stores[:8]
            }
            
            for future in as_completed(futures, timeout=15):
                store = futures[future]
                try:
                    products = future.result()
                    all_products.extend(products)
                except Exception as e:
                    logger.warning(f"Error scraping {store['name']}: {e}")
        
        # Sort by relevance (title word overlap)
        query_lower = query.lower()
        all_products.sort(
            key=lambda p: sum(1 for word in query_lower.split() if word in p.title.lower()),
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
        
        for product in data.get("products", []):
            title = product.get("title", "")
            title_lower = title.lower()
            
            # Filter by query — at least one word must match
            if not any(word in title_lower for word in query_words):
                tags = [t.lower() for t in product.get("tags", [])]
                product_type = product.get("product_type", "").lower()
                if not any(word in tag for word in query_words for tag in tags):
                    if not any(word in product_type for word in query_words):
                        continue
            
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
            
            products.append(VendorProduct(
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
            ))
        
        return products
    
    def add_store(self, name: str, domain: str, category: str = "other"):
        """Add a new Shopify store to the search list."""
        self.stores.append({"name": name, "domain": domain, "category": category})
