"""
Pinterest API Service

Searches for Pinterest pins related to products.
Shows social ranking and popularity metrics.
Uses RapidAPI for Pinterest access.
"""

import os
import logging
import hashlib
import random
from dataclasses import dataclass
from typing import Optional
import requests

logger = logging.getLogger(__name__)


@dataclass
class PinterestPin:
    """Represents a Pinterest pin."""
    id: str
    image_url: str
    title: str
    description: str
    pin_url: str
    source_url: str  # The linked website from the pin
    source_domain: str  # Domain name for display
    board_name: str
    pinner_name: str
    pinner_avatar: str
    saves: int
    comments: int
    is_video: bool
    
    def to_dict(self):
        return {
            "id": self.id,
            "image_url": self.image_url,
            "title": self.title,
            "description": self.description,
            "pin_url": self.pin_url,
            "source_url": self.source_url,
            "source_domain": self.source_domain,
            "board_name": self.board_name,
            "pinner_name": self.pinner_name,
            "pinner_avatar": self.pinner_avatar,
            "saves": self.saves,
            "comments": self.comments,
            "is_video": self.is_video,
            "type": "pinterest",
        }


@dataclass
class PinterestTrend:
    """Represents trending data for a search term."""
    query: str
    pin_count: int
    trending_score: float  # 0-100
    engagement_level: str  # "low", "medium", "high", "viral"
    related_terms: list
    top_boards: list
    
    def to_dict(self):
        return {
            "query": self.query,
            "pin_count": self.pin_count,
            "trending_score": self.trending_score,
            "engagement_level": self.engagement_level,
            "related_terms": self.related_terms,
            "top_boards": self.top_boards,
        }


class PinterestService:
    """
    Service for fetching Pinterest pins and trend data.
    
    Use cases:
    - See how popular/trending a product is on Pinterest
    - Get inspiration pins for products
    - Analyze social engagement metrics
    
    Uses RapidAPI Pinterest endpoints.
    Falls back to mock data if API is not configured.
    
    Supported RapidAPI Pinterest APIs:
    1. pinterest-scraper-api.p.rapidapi.com (primary)
    2. pinterest40.p.rapidapi.com (fallback)
    """
    
    # List of RapidAPI Pinterest endpoints to try
    API_ENDPOINTS = [
        {
            "host": "pinterest-scraper-api.p.rapidapi.com",
            "search_path": "/v1/search",
            "query_param": "query",
        },
        {
            "host": "pinterest40.p.rapidapi.com",
            "search_path": "/search",
            "query_param": "query",
        },
    ]
    
    def __init__(self):
        self.api_key = os.getenv("RAPIDAPI_KEY")
        self.timeout = 10
    
    def search_pins(self, query: str, limit: int = 8) -> list[PinterestPin]:
        """
        Search for Pinterest pins related to a product.
        
        Args:
            query: Product search query
            limit: Maximum number of pins to return
            
        Returns:
            List of PinterestPin objects
        """
        if self.api_key:
            try:
                return self._search_api(query, limit)
            except Exception as e:
                logger.warning(f"Pinterest API error, using mock: {e}")
        
        return self._get_mock_pins(query, limit)
    
    def get_trend_data(self, query: str) -> PinterestTrend:
        """
        Get trend/popularity data for a search term.
        
        Args:
            query: Product search query
            
        Returns:
            PinterestTrend with ranking metrics
        """
        if self.api_key:
            try:
                return self._get_trend_api(query)
            except Exception as e:
                logger.warning(f"Pinterest trend API error, using mock: {e}")
        
        return self._get_mock_trend(query)
    
    def _search_api(self, query: str, limit: int) -> list[PinterestPin]:
        """Search Pinterest using RapidAPI - tries multiple endpoints."""
        from urllib.parse import urlparse
        
        last_error = None
        
        for endpoint in self.API_ENDPOINTS:
            try:
                url = f"https://{endpoint['host']}{endpoint['search_path']}"
                
                headers = {
                    "X-RapidAPI-Key": self.api_key,
                    "X-RapidAPI-Host": endpoint["host"],
                }
                
                params = {
                    endpoint["query_param"]: query,
                    "limit": str(limit * 2),
                }
                
                response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
                response.raise_for_status()
                
                data = response.json()
                pins = []
                
                # Handle different response formats from different APIs
                pin_list = data.get("pins", []) or data.get("results", []) or data.get("data", [])
                
                for item in pin_list[:limit]:
                    source_url = item.get("link", "") or item.get("source_url", "") or item.get("url", "")
                    source_domain = ""
                    if source_url:
                        try:
                            source_domain = urlparse(source_url).netloc.replace("www.", "")
                        except:
                            pass
                    
                    # Handle different field names
                    image_url = (item.get("image", {}).get("url", "") or 
                                item.get("images", {}).get("orig", {}).get("url", "") or
                                item.get("image_url", "") or
                                item.get("thumbnail", ""))
                    
                    pins.append(PinterestPin(
                        id=str(item.get("id", "")),
                        image_url=image_url,
                        title=(item.get("title", "") or item.get("name", ""))[:100],
                        description=(item.get("description", "") or "")[:200],
                        pin_url=f"https://pinterest.com/pin/{item.get('id', '')}",
                        source_url=source_url,
                        source_domain=source_domain,
                        board_name=item.get("board", {}).get("name", "") if isinstance(item.get("board"), dict) else "",
                        pinner_name=item.get("pinner", {}).get("username", "") if isinstance(item.get("pinner"), dict) else item.get("pinner", ""),
                        pinner_avatar=item.get("pinner", {}).get("profile_image", "") if isinstance(item.get("pinner"), dict) else "",
                        saves=item.get("save_count", 0) or item.get("saves", 0) or item.get("repin_count", 0),
                        comments=item.get("comment_count", 0) or item.get("comments", 0),
                        is_video=item.get("is_video", False),
                    ))
                
                if pins:
                    logger.info(f"Pinterest API success using {endpoint['host']}: {len(pins)} pins")
                    return pins
                    
            except Exception as e:
                last_error = e
                logger.debug(f"Pinterest endpoint {endpoint['host']} failed: {e}")
                continue
        
        # All endpoints failed
        if last_error:
            raise last_error
        return []
    
    def _get_trend_api(self, query: str) -> PinterestTrend:
        """Get trend data from API (would require a trends endpoint)."""
        # Most Pinterest APIs don't have a direct trends endpoint
        # We can estimate from search volume
        pins = self._search_api(query, 20)
        
        total_saves = sum(p.saves for p in pins)
        avg_saves = total_saves / len(pins) if pins else 0
        
        # Calculate trending score based on engagement
        if avg_saves > 10000:
            score = 90 + random.randint(0, 10)
            level = "viral"
        elif avg_saves > 5000:
            score = 70 + random.randint(0, 15)
            level = "high"
        elif avg_saves > 1000:
            score = 50 + random.randint(0, 15)
            level = "medium"
        else:
            score = 20 + random.randint(0, 20)
            level = "low"
        
        return PinterestTrend(
            query=query,
            pin_count=len(pins) * 1000,  # Estimate
            trending_score=min(score, 100),
            engagement_level=level,
            related_terms=[f"{query} ideas", f"{query} inspiration", f"best {query}"],
            top_boards=[p.board_name for p in pins[:3] if p.board_name],
        )
    
    def _get_mock_pins(self, query: str, limit: int) -> list[PinterestPin]:
        """Generate mock Pinterest pins with source website links."""
        
        templates = [
            {
                "title": f"Best {query} for 2024 ✨",
                "description": f"Top picks for {query}. Save for later!",
                "board": "Shopping Wishlist",
                "pinner": "deals_finder",
                "saves": 15420,
                "source_url": "https://www.amazon.com",
                "source_domain": "amazon.com",
            },
            {
                "title": f"{query} Inspiration Board",
                "description": f"Ideas and inspiration for your next {query} purchase",
                "board": "Product Ideas",
                "pinner": "tech_inspiration",
                "saves": 8930,
                "source_url": "https://www.bhphotovideo.com",
                "source_domain": "bhphotovideo.com",
            },
            {
                "title": f"Aesthetic {query} Setup 📸",
                "description": f"Beautiful {query} setups and arrangements",
                "board": "Aesthetic Vibes",
                "pinner": "aesthetic_home",
                "saves": 23100,
                "source_url": "https://www.adorama.com",
                "source_domain": "adorama.com",
            },
            {
                "title": f"{query} Buying Guide",
                "description": f"Everything you need to know before buying {query}",
                "board": "Buying Guides",
                "pinner": "smart_shopper",
                "saves": 12650,
                "source_url": "https://www.bestbuy.com",
                "source_domain": "bestbuy.com",
            },
            {
                "title": f"Top Rated {query}",
                "description": f"Highest rated {query} based on real reviews",
                "board": "Top Picks",
                "pinner": "review_guru",
                "saves": 19870,
                "source_url": "https://www.ebay.com",
                "source_domain": "ebay.com",
            },
            {
                "title": f"Budget {query} Options 💰",
                "description": f"Affordable {query} that don't compromise on quality",
                "board": "Budget Finds",
                "pinner": "budget_queen",
                "saves": 31200,
                "source_url": "https://www.walmart.com",
                "source_domain": "walmart.com",
            },
            {
                "title": f"Premium {query} Collection",
                "description": f"Luxury {query} for those who want the best",
                "board": "Luxury Items",
                "pinner": "luxury_lifestyle",
                "saves": 7890,
                "source_url": "https://www.newegg.com",
                "source_domain": "newegg.com",
            },
            {
                "title": f"Minimalist {query}",
                "description": f"Clean, minimalist {query} options",
                "board": "Minimalist Style",
                "pinner": "less_is_more",
                "saves": 14320,
                "source_url": "https://www.target.com",
                "source_domain": "target.com",
            },
        ]
        
        pins = []
        for i, template in enumerate(templates[:limit]):
            pin_id = hashlib.md5(f"pin-{query}-{i}".encode()).hexdigest()[:12]
            
            pins.append(PinterestPin(
                id=pin_id,
                image_url=f"https://picsum.photos/seed/pin{query}{i}/600/800",
                title=template["title"],
                description=template["description"],
                pin_url=f"https://pinterest.com/pin/{pin_id}",
                source_url=template["source_url"],
                source_domain=template["source_domain"],
                board_name=template["board"],
                pinner_name=template["pinner"],
                pinner_avatar=f"https://i.pravatar.cc/100?u={template['pinner']}",
                saves=template["saves"] + random.randint(-1000, 1000),
                comments=random.randint(50, 500),
                is_video=False,
            ))
        
        return pins
    
    def _get_mock_trend(self, query: str) -> PinterestTrend:
        """Generate mock trend data based on query."""
        
        # Popular product categories get higher scores
        popular_keywords = ['camera', 'iphone', 'macbook', 'airpods', 'jordan', 'nike', 'ps5', 'switch']
        trending_keywords = ['oled', 'mirrorless', '4k', 'wireless', 'vintage', 'aesthetic']
        
        query_lower = query.lower()
        
        # Base score
        base_score = 45
        
        # Boost for popular products
        if any(kw in query_lower for kw in popular_keywords):
            base_score += 30
        
        # Boost for trending terms
        if any(kw in query_lower for kw in trending_keywords):
            base_score += 15
        
        # Add some randomness
        score = min(100, max(15, base_score + random.randint(-10, 15)))
        
        # Determine engagement level
        if score >= 80:
            level = "viral"
            pin_count = random.randint(500000, 2000000)
        elif score >= 60:
            level = "high"
            pin_count = random.randint(100000, 500000)
        elif score >= 40:
            level = "medium"
            pin_count = random.randint(25000, 100000)
        else:
            level = "low"
            pin_count = random.randint(5000, 25000)
        
        # Generate related terms
        related = [
            f"{query} ideas",
            f"best {query} 2024",
            f"{query} aesthetic",
            f"cheap {query}",
            f"{query} setup",
        ]
        
        # Top boards
        top_boards = [
            f"{query.title()} Wishlist",
            "Shopping Ideas",
            "Tech & Gadgets",
        ]
        
        return PinterestTrend(
            query=query,
            pin_count=pin_count,
            trending_score=score,
            engagement_level=level,
            related_terms=related[:4],
            top_boards=top_boards,
        )


# Singleton instance
pinterest_service = PinterestService()
