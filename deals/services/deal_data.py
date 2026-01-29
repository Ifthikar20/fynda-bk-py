"""
Deal Data Service

Contains realistic mock deal data for Sony cameras.
This simulates API responses until real API keys are configured.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import random


# Realistic Sony camera deals data
SONY_CAMERA_DEALS = [
    {
        "id": "ebay-001",
        "title": "Sony Alpha a6400 Mirrorless Camera with 16-50mm Lens Kit",
        "description": "24.2MP APS-C sensor, Real-time Eye AF, 4K video recording, 180-degree tiltable touchscreen",
        "price": 898.00,
        "original_price": 999.99,
        "currency": "USD",
        "source": "eBay",
        "seller": "authorized_electronics",
        "seller_rating": 99.2,
        "url": "https://www.ebay.com/itm/sony-a6400-16-50mm",
        "image_url": "https://images.unsplash.com/photo-1516035069371-29a1b244cc32?w=400",
        "condition": "New",
        "shipping": "Free Shipping",
        "rating": 4.8,
        "reviews_count": 2847,
        "in_stock": True,
        "features": ["mirrorless", "lens", "16-50mm", "4k", "eye-af"],
    },
    {
        "id": "bestbuy-001",
        "title": "Sony Alpha a6600 Mirrorless Camera with 18-135mm Lens",
        "description": "24.2MP, in-body stabilization, Real-time tracking, 4K HDR video",
        "price": 1198.00,
        "original_price": 1399.99,
        "currency": "USD",
        "source": "Best Buy",
        "seller": "Best Buy",
        "seller_rating": 100.0,
        "url": "https://www.bestbuy.com/sony-a6600-18-135mm",
        "image_url": "https://images.unsplash.com/photo-1502920917128-1aa500764cbd?w=400",
        "condition": "New",
        "shipping": "Free Shipping",
        "rating": 4.9,
        "reviews_count": 1523,
        "in_stock": True,
        "features": ["mirrorless", "lens", "18-135mm", "stabilization", "4k"],
    },
    {
        "id": "ebay-002",
        "title": "Sony ZV-E10 Vlogging Camera with 16-50mm Power Zoom Lens",
        "description": "24.2MP APS-C, directional 3-capsule mic, Product Showcase mode",
        "price": 648.00,
        "original_price": 799.99,
        "currency": "USD",
        "source": "eBay",
        "seller": "camera_world_outlet",
        "seller_rating": 98.7,
        "url": "https://www.ebay.com/itm/sony-zv-e10-vlog",
        "image_url": "https://images.unsplash.com/photo-1617005082133-548c4dd27f35?w=400",
        "condition": "New",
        "shipping": "Free Shipping",
        "rating": 4.7,
        "reviews_count": 3201,
        "in_stock": True,
        "features": ["mirrorless", "lens", "vlogging", "mic", "16-50mm"],
    },
    {
        "id": "bestbuy-002",
        "title": "Sony Alpha 7 IV Full-Frame Mirrorless Camera (Body Only)",
        "description": "33MP full-frame sensor, 10fps burst, 4K 60p video, advanced AF",
        "price": 2298.00,
        "original_price": 2499.99,
        "currency": "USD",
        "source": "Best Buy",
        "seller": "Best Buy",
        "seller_rating": 100.0,
        "url": "https://www.bestbuy.com/sony-a7iv-body",
        "image_url": "https://images.unsplash.com/photo-1621259182978-fbf93132d53d?w=400",
        "condition": "New",
        "shipping": "Free 2-Day Shipping",
        "rating": 4.9,
        "reviews_count": 892,
        "in_stock": True,
        "features": ["mirrorless", "full-frame", "4k", "professional"],
    },
    {
        "id": "ebay-003",
        "title": "Sony Alpha a7 III with 28-70mm Lens Kit",
        "description": "24.2MP full-frame, 693-point AF, 10fps, 4K HDR video",
        "price": 1798.00,
        "original_price": 2199.99,
        "currency": "USD",
        "source": "eBay",
        "seller": "pro_camera_deals",
        "seller_rating": 99.5,
        "url": "https://www.ebay.com/itm/sony-a7iii-28-70mm",
        "image_url": "https://images.unsplash.com/photo-1606986628509-e7f1cee4a792?w=400",
        "condition": "New",
        "shipping": "Free Shipping",
        "rating": 4.8,
        "reviews_count": 4521,
        "in_stock": True,
        "features": ["mirrorless", "lens", "full-frame", "28-70mm", "4k"],
    },
    {
        "id": "ebay-004",
        "title": "Sony Cyber-shot RX100 VII Premium Compact Camera",
        "description": "20.1MP 1-inch sensor, 24-200mm zoom, 4K video, flip screen",
        "price": 1098.00,
        "original_price": 1299.99,
        "currency": "USD",
        "source": "eBay",
        "seller": "digital_photo_pro",
        "seller_rating": 98.9,
        "url": "https://www.ebay.com/itm/sony-rx100-vii",
        "image_url": "https://images.unsplash.com/photo-1495707902641-75cac5884901?w=400",
        "condition": "New",
        "shipping": "Free Shipping",
        "rating": 4.6,
        "reviews_count": 1876,
        "in_stock": True,
        "features": ["compact", "lens", "zoom", "4k", "pocket"],
    },
    {
        "id": "bestbuy-003",
        "title": "Sony Alpha a6100 Mirrorless Camera Two Lens Kit (16-50mm + 55-210mm)",
        "description": "24.2MP, Real-time Eye AF, 4K video, dual lens bundle",
        "price": 848.00,
        "original_price": 1099.99,
        "currency": "USD",
        "source": "Best Buy",
        "seller": "Best Buy",
        "seller_rating": 100.0,
        "url": "https://www.bestbuy.com/sony-a6100-two-lens",
        "image_url": "https://images.unsplash.com/photo-1510127034890-ba27508e9f1c?w=400",
        "condition": "New",
        "shipping": "Free Shipping",
        "rating": 4.7,
        "reviews_count": 2134,
        "in_stock": True,
        "features": ["mirrorless", "lens", "dual-lens", "bundle", "16-50mm", "55-210mm"],
    },
    {
        "id": "ebay-005",
        "title": "Sony Alpha a7C Compact Full-Frame Camera with 28-60mm Lens",
        "description": "24.2MP full-frame in compact body, 5-axis stabilization, 4K video",
        "price": 1698.00,
        "original_price": 1999.99,
        "currency": "USD",
        "source": "eBay",
        "seller": "camera_superstore",
        "seller_rating": 99.1,
        "url": "https://www.ebay.com/itm/sony-a7c-28-60mm",
        "image_url": "https://images.unsplash.com/photo-1581591524425-c7e0978865fc?w=400",
        "condition": "New",
        "shipping": "Free Shipping",
        "rating": 4.8,
        "reviews_count": 743,
        "in_stock": True,
        "features": ["mirrorless", "lens", "full-frame", "compact", "stabilization"],
    },
    {
        "id": "bestbuy-004",
        "title": "Sony Alpha a6400 Body Only - Black",
        "description": "24.2MP APS-C sensor, world's fastest AF, 4K video, no lens included",
        "price": 698.00,
        "original_price": 899.99,
        "currency": "USD",
        "source": "Best Buy",
        "seller": "Best Buy",
        "seller_rating": 100.0,
        "url": "https://www.bestbuy.com/sony-a6400-body",
        "image_url": "https://images.unsplash.com/photo-1516724562728-afc824a36e84?w=400",
        "condition": "New",
        "shipping": "Free Shipping",
        "rating": 4.8,
        "reviews_count": 1456,
        "in_stock": True,
        "features": ["mirrorless", "body-only", "4k", "fast-af"],
    },
    {
        "id": "ebay-006",
        "title": "Sony Alpha a6500 with 18-135mm OSS Lens - Refurbished",
        "description": "24.2MP, 5-axis stabilization, 4K video, touchscreen AF",
        "price": 749.00,
        "original_price": 1199.99,
        "currency": "USD",
        "source": "eBay",
        "seller": "sony_certified_refurb",
        "seller_rating": 99.8,
        "url": "https://www.ebay.com/itm/sony-a6500-refurb",
        "image_url": "https://images.unsplash.com/photo-1519183071298-a2962feb14f4?w=400",
        "condition": "Refurbished",
        "shipping": "Free Shipping",
        "rating": 4.6,
        "reviews_count": 567,
        "in_stock": True,
        "features": ["mirrorless", "lens", "18-135mm", "stabilization", "refurbished"],
    },
]


class MockDealService:
    """
    Provides realistic mock deal data.
    Simulates eBay and Best Buy API responses.
    """
    
    def __init__(self):
        self.deals = SONY_CAMERA_DEALS
    
    def search(
        self,
        query: str,
        budget: Optional[float] = None,
        requirements: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for deals matching the query.
        
        Args:
            query: Product search terms
            budget: Maximum price filter
            requirements: Required features (e.g., ["lens"])
        
        Returns:
            List of matching deals
        """
        results = []
        query_lower = query.lower()
        requirements = requirements or []
        
        for deal in self.deals:
            # Check if query matches title
            title_lower = deal["title"].lower()
            if not any(word in title_lower for word in query_lower.split() if len(word) > 2):
                continue
            
            # Check budget constraint
            if budget and deal["price"] > budget:
                continue
            
            # Calculate relevance score
            relevance = self._calculate_relevance(deal, query_lower, requirements)
            
            # Create result with added fields
            result = {
                **deal,
                "relevance_score": relevance,
                "discount_percent": self._calculate_discount(deal),
                "fetched_at": datetime.utcnow().isoformat(),
            }
            results.append(result)
        
        # Sort by relevance score (higher is better)
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return results
    
    def _calculate_relevance(
        self, deal: Dict, query: str, requirements: List[str]
    ) -> int:
        """Calculate relevance score (0-100) for a deal."""
        score = 50  # Base score
        
        title_lower = deal["title"].lower()
        features = [f.lower() for f in deal.get("features", [])]
        
        # Boost for query word matches in title
        query_words = [w for w in query.split() if len(w) > 2]
        matches = sum(1 for word in query_words if word in title_lower)
        score += matches * 10
        
        # Boost for requirement matches
        for req in requirements:
            if req.lower() in title_lower or req.lower() in features:
                score += 15
        
        # Boost for lens inclusion when required
        if "lens" in requirements or "lens" in query:
            if "lens" in title_lower and "body only" not in title_lower.lower():
                score += 20
        
        # Boost for higher seller ratings
        seller_rating = deal.get("seller_rating", 95)
        if seller_rating >= 99:
            score += 5
        
        # Boost for high user ratings
        if deal.get("rating", 0) >= 4.7:
            score += 5
        
        # Slight boost for Best Buy (authorized retailer)
        if deal["source"] == "Best Buy":
            score += 3
        
        return min(score, 100)  # Cap at 100
    
    def _calculate_discount(self, deal: Dict) -> int:
        """Calculate discount percentage."""
        if deal["original_price"] and deal["original_price"] > deal["price"]:
            discount = (deal["original_price"] - deal["price"]) / deal["original_price"] * 100
            return round(discount)
        return 0


# Singleton instance
mock_deal_service = MockDealService()
