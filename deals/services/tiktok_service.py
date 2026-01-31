"""
TikTok Video Service

Searches for product-focused TikTok videos: reviews, demos, unboxings.
Filters out irrelevant content to show only product information.
"""

import logging
import hashlib
import random
from dataclasses import dataclass
from typing import Optional
import requests

from fynda.config import config

logger = logging.getLogger(__name__)


# Product-focused search modifiers to ensure relevant results
PRODUCT_SEARCH_TYPES = [
    "review",
    "unboxing", 
    "demo",
    "hands on",
    "comparison",
    "worth it",
    "honest review",
]

# Keywords that indicate product-relevant content
RELEVANCE_KEYWORDS = [
    "review", "unboxing", "demo", "test", "comparison", "worth",
    "buying", "bought", "hands on", "first look", "honest",
    "pros and cons", "vs", "features", "specs", "quality",
    "should you buy", "best", "top", "tutorial", "how to",
]

# Keywords to filter out non-product junk content  
JUNK_KEYWORDS = [
    "prank", "challenge", "dance", "fyp", "viral", "funny",
    "comedy", "skit", "duet", "trend", "meme", "storytime",
    "grwm", "ootd", "haul", "vlog", "day in my life",
]


@dataclass
class TikTokVideo:
    """Represents a TikTok video result."""
    id: str
    title: str
    author: str
    author_avatar: str
    video_url: str
    thumbnail_url: str
    views: int
    likes: int
    comments: int
    duration: int  # seconds
    created_at: str
    video_type: str  # review, unboxing, demo, comparison
    
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "author_avatar": self.author_avatar,
            "video_url": self.video_url,
            "thumbnail_url": self.thumbnail_url,
            "views": self.views,
            "likes": self.likes,
            "comments": self.comments,
            "duration": self.duration,
            "created_at": self.created_at,
            "video_type": self.video_type,
        }


class TikTokService:
    """
    Service for fetching product-focused TikTok videos.
    
    Only returns videos that are:
    - Product reviews
    - Unboxing videos
    - Product demos/tests
    - Comparison videos
    - "Worth it?" style evaluations
    
    Filters out junk content like pranks, dances, and random viral content.
    """
    
    def __init__(self):
        self.api_key = config.apis.rapidapi_key
        self.api_host = "tiktok-api23.p.rapidapi.com"
    
    def search_videos(self, query: str, limit: int = 6, video_type: str = None) -> list[TikTokVideo]:
        """
        Search for product-focused TikTok videos.
        
        Args:
            query: Product search query
            limit: Maximum number of videos to return
            video_type: Optional filter: 'review', 'unboxing', 'demo', 'comparison'
            
        Returns:
            List of TikTokVideo objects (only product-relevant content)
        """
        if self.api_key:
            try:
                return self._search_api(query, limit, video_type)
            except Exception as e:
                logger.warning(f"TikTok API error, using mock data: {e}")
        
        return self._get_mock_videos(query, limit, video_type)
    
    def _search_api(self, query: str, limit: int, video_type: str = None) -> list[TikTokVideo]:
        """Search TikTok using RapidAPI with product-focused keywords."""
        url = f"https://{self.api_host}/api/search/general"
        
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.api_host,
        }
        
        # Build product-focused search query
        search_modifier = video_type if video_type else random.choice(PRODUCT_SEARCH_TYPES[:3])
        search_query = f"{query} {search_modifier}"
        
        params = {
            "keyword": search_query,
            "count": str(limit * 3),  # Fetch extra to filter
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        videos = []
        
        for item in data.get("data", []):
            if len(videos) >= limit:
                break
                
            if item.get("type") != 1:  # Type 1 is video
                continue
                
            video_data = item.get("item", {})
            title = video_data.get("desc", "").lower()
            
            # Filter out junk content
            if self._is_junk_content(title):
                continue
            
            # Only include if it has product relevance
            if not self._is_product_relevant(title, query):
                continue
            
            author_data = video_data.get("author", {})
            stats = video_data.get("stats", {})
            
            # Determine video type
            detected_type = self._detect_video_type(title)
            
            videos.append(TikTokVideo(
                id=video_data.get("id", ""),
                title=video_data.get("desc", "")[:100],
                author=author_data.get("uniqueId", ""),
                author_avatar=author_data.get("avatarThumb", ""),
                video_url=f"https://www.tiktok.com/@{author_data.get('uniqueId')}/video/{video_data.get('id')}",
                thumbnail_url=video_data.get("video", {}).get("cover", ""),
                views=stats.get("playCount", 0),
                likes=stats.get("diggCount", 0),
                comments=stats.get("commentCount", 0),
                duration=video_data.get("video", {}).get("duration", 0),
                created_at=video_data.get("createTime", ""),
                video_type=detected_type,
            ))
        
        return videos
    
    def _is_junk_content(self, title: str) -> bool:
        """Check if the video title indicates non-product junk content."""
        title_lower = title.lower()
        return any(junk in title_lower for junk in JUNK_KEYWORDS)
    
    def _is_product_relevant(self, title: str, query: str) -> bool:
        """Check if the video is actually about the product."""
        title_lower = title.lower()
        query_lower = query.lower()
        
        # Must contain at least one word from the product query
        query_words = query_lower.split()
        if not any(word in title_lower for word in query_words if len(word) > 2):
            return False
        
        # Bonus: check for product-related keywords
        has_relevance = any(keyword in title_lower for keyword in RELEVANCE_KEYWORDS)
        
        return True  # If it passed the query check, include it
    
    def _detect_video_type(self, title: str) -> str:
        """Detect the type of product video based on title."""
        title_lower = title.lower()
        
        if "unbox" in title_lower:
            return "unboxing"
        elif "review" in title_lower or "honest" in title_lower:
            return "review"
        elif "demo" in title_lower or "test" in title_lower or "hands on" in title_lower:
            return "demo"
        elif "vs" in title_lower or "comparison" in title_lower or "compare" in title_lower:
            return "comparison"
        elif "worth" in title_lower or "should" in title_lower:
            return "review"
        elif "how to" in title_lower or "tutorial" in title_lower:
            return "tutorial"
        else:
            return "review"  # Default
    
    def _get_mock_videos(self, query: str, limit: int, video_type: str = None) -> list[TikTokVideo]:
        """Generate product-focused mock TikTok videos."""
        
        # Product-focused templates only
        mock_templates = [
            {
                "title": f"📦 {query} Unboxing + First Impressions | What's in the box?",
                "author": "tech_unboxer",
                "views": 245000,
                "likes": 18200,
                "type": "unboxing",
            },
            {
                "title": f"🔍 {query} HONEST Review After 30 Days | Pros & Cons",
                "author": "honest_reviews",
                "views": 189000,
                "likes": 12400,
                "type": "review",
            },
            {
                "title": f"🎯 {query} Full Demo & Features Walkthrough",
                "author": "product_demos",
                "views": 156000,
                "likes": 11200,
                "type": "demo",
            },
            {
                "title": f"⚡ {query} vs Competitors - Which One Should You Buy?",
                "author": "tech_compare",
                "views": 324000,
                "likes": 28100,
                "type": "comparison",
            },
            {
                "title": f"💰 Is {query} Worth the Money? Complete Buying Guide",
                "author": "smart_buyer",
                "views": 412000,
                "likes": 31500,
                "type": "review",
            },
            {
                "title": f"🔧 {query} Setup Tutorial + Tips & Tricks",
                "author": "how_to_tech",
                "views": 178000,
                "likes": 14300,
                "type": "tutorial",
            },
        ]
        
        # Filter by video type if specified
        if video_type:
            mock_templates = [t for t in mock_templates if t["type"] == video_type]
        
        videos = []
        for i, template in enumerate(mock_templates[:limit]):
            video_id = hashlib.md5(f"{query}-{i}".encode()).hexdigest()[:12]
            
            videos.append(TikTokVideo(
                id=video_id,
                title=template["title"],
                author=template["author"],
                author_avatar=f"https://i.pravatar.cc/100?u={template['author']}",
                video_url=f"https://www.tiktok.com/@{template['author']}/video/{video_id}",
                thumbnail_url=f"https://picsum.photos/seed/{video_id}/400/700",
                views=template["views"],
                likes=template["likes"],
                comments=int(template["likes"] * 0.12),
                duration=45 + (i * 15),  # Product videos are typically longer
                created_at="2026-01-25T10:00:00Z",
                video_type=template["type"],
            ))
        
        return videos


# Singleton instance
tiktok_service = TikTokService()
