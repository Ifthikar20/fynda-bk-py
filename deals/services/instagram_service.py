"""
Instagram API Service

Searches for Instagram posts related to products.
Useful for finding sample photos (e.g., photos taken with a camera).
Uses RapidAPI for Instagram access.
"""

import os
import logging
import hashlib
import random
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import requests

logger = logging.getLogger(__name__)


@dataclass
class InstagramPost:
    """Represents an Instagram post."""
    id: str
    image_url: str
    thumbnail_url: str
    caption: str
    author: str
    author_avatar: str
    likes: int
    comments: int
    post_url: str
    is_video: bool
    hashtags: list
    
    def to_dict(self):
        return {
            "id": self.id,
            "image_url": self.image_url,
            "thumbnail_url": self.thumbnail_url,
            "caption": self.caption,
            "author": self.author,
            "author_avatar": self.author_avatar,
            "likes": self.likes,
            "comments": self.comments,
            "post_url": self.post_url,
            "is_video": self.is_video,
            "hashtags": self.hashtags,
            "type": "instagram",
        }


class InstagramService:
    """
    Service for fetching Instagram posts related to products.
    
    Use cases:
    - Find sample photos taken with a camera
    - See how products look in real-world usage
    - Get user-generated content for products
    
    Uses RapidAPI Instagram endpoints.
    Falls back to mock data if API is not configured.
    """
    
    def __init__(self):
        self.api_key = os.getenv("RAPIDAPI_KEY")
        self.api_host = "instagram-scraper-api2.p.rapidapi.com"
        self.timeout = 10
    
    def search_posts(self, query: str, limit: int = 8) -> list[InstagramPost]:
        """
        Search for Instagram posts related to a product.
        
        Args:
            query: Product search query (e.g., "Sony A7III", "Canon R5")
            limit: Maximum number of posts to return
            
        Returns:
            List of InstagramPost objects with sample photos
        """
        if self.api_key:
            try:
                return self._search_api(query, limit)
            except Exception as e:
                logger.warning(f"Instagram API error, using mock: {e}")
        
        return self._get_mock_posts(query, limit)
    
    def _search_api(self, query: str, limit: int) -> list[InstagramPost]:
        """Search Instagram using RapidAPI."""
        # Convert query to hashtag format
        hashtag = self._query_to_hashtag(query)
        
        url = f"https://{self.api_host}/v1/hashtag"
        
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.api_host,
        }
        
        params = {
            "hashtag": hashtag,
        }
        
        response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
        response.raise_for_status()
        
        data = response.json()
        posts = []
        
        items = data.get("data", {}).get("items", [])[:limit * 2]
        
        for item in items:
            if len(posts) >= limit:
                break
            
            # Skip videos for photo comparison
            if item.get("media_type") == 2:  # 2 = video
                continue
            
            user = item.get("user", {})
            caption_data = item.get("caption", {})
            caption_text = caption_data.get("text", "") if caption_data else ""
            
            # Get image URL
            image_versions = item.get("image_versions2", {}).get("candidates", [])
            image_url = image_versions[0].get("url", "") if image_versions else ""
            thumbnail = image_versions[-1].get("url", "") if len(image_versions) > 1 else image_url
            
            posts.append(InstagramPost(
                id=str(item.get("id", "")),
                image_url=image_url,
                thumbnail_url=thumbnail,
                caption=caption_text[:200] if caption_text else "",
                author=user.get("username", ""),
                author_avatar=user.get("profile_pic_url", ""),
                likes=item.get("like_count", 0),
                comments=item.get("comment_count", 0),
                post_url=f"https://instagram.com/p/{item.get('code', '')}",
                is_video=item.get("media_type") == 2,
                hashtags=self._extract_hashtags(caption_text),
            ))
        
        return posts
    
    def _query_to_hashtag(self, query: str) -> str:
        """Convert a product query to a hashtag."""
        # Remove special chars and spaces
        hashtag = query.lower()
        hashtag = ''.join(c for c in hashtag if c.isalnum())
        return hashtag
    
    def _extract_hashtags(self, text: str) -> list:
        """Extract hashtags from caption text."""
        if not text:
            return []
        import re
        return re.findall(r'#(\w+)', text)[:5]
    
    def _get_mock_posts(self, query: str, limit: int) -> list[InstagramPost]:
        """Generate mock Instagram posts for demo purposes."""
        
        # Determine content type based on query
        query_lower = query.lower()
        
        # Camera-related queries
        if any(word in query_lower for word in ['camera', 'lens', 'sony', 'canon', 'nikon', 'fuji', 'photo']):
            templates = self._get_camera_templates(query)
        else:
            templates = self._get_product_templates(query)
        
        posts = []
        for i, template in enumerate(templates[:limit]):
            post_id = hashlib.md5(f"ig-{query}-{i}".encode()).hexdigest()[:12]
            
            posts.append(InstagramPost(
                id=post_id,
                image_url=template["image"],
                thumbnail_url=template["image"],
                caption=template["caption"],
                author=template["author"],
                author_avatar=f"https://i.pravatar.cc/100?u={template['author']}",
                likes=template["likes"],
                comments=template["comments"],
                post_url=f"https://instagram.com/p/{post_id}",
                is_video=False,
                hashtags=template["hashtags"],
            ))
        
        return posts
    
    def _get_camera_templates(self, query: str) -> list:
        """Mock templates for camera-related searches."""
        return [
            {
                "caption": f"Shot on {query} 📸 The colors and sharpness are incredible! #photography",
                "author": "photo_enthusiast",
                "likes": 2340,
                "comments": 89,
                "hashtags": ["photography", query.replace(" ", "").lower(), "shotoncamera"],
                "image": "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=800",
            },
            {
                "caption": f"Golden hour with my {query} 🌅 Low light performance is amazing",
                "author": "sunset_chaser",
                "likes": 5670,
                "comments": 156,
                "hashtags": ["goldenhour", "landscapephotography", "cameratest"],
                "image": "https://images.unsplash.com/photo-1507400492013-162706c8c05e?w=800",
            },
            {
                "caption": f"Portrait mode test - {query} never disappoints 🔥 #portraitphotography",
                "author": "portrait_master",
                "likes": 3420,
                "comments": 112,
                "hashtags": ["portrait", "bokeh", "85mm"],
                "image": "https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=800",
            },
            {
                "caption": f"Street photography with {query} - the autofocus is insane",
                "author": "urban_lens",
                "likes": 1890,
                "comments": 67,
                "hashtags": ["streetphotography", "urbanexplorer", "citylife"],
                "image": "https://images.unsplash.com/photo-1480714378408-67cf0d13bc1b?w=800",
            },
            {
                "caption": f"Wildlife shot at 400mm - {query} handles it perfectly 🦅",
                "author": "nature_shots",
                "likes": 4560,
                "comments": 198,
                "hashtags": ["wildlife", "naturephotography", "birding"],
                "image": "https://images.unsplash.com/photo-1474511320723-9a56873571b7?w=800",
            },
            {
                "caption": f"Night sky with {query} - long exposure magic ✨",
                "author": "astro_photographer",
                "likes": 7890,
                "comments": 234,
                "hashtags": ["astrophotography", "nightsky", "longexposure"],
                "image": "https://images.unsplash.com/photo-1419242902214-272b3f66ee7a?w=800",
            },
            {
                "caption": f"Food photography test - {query} colors are so accurate 🍕",
                "author": "foodie_shots",
                "likes": 1230,
                "comments": 45,
                "hashtags": ["foodphotography", "foodstyling", "delicious"],
                "image": "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=800",
            },
            {
                "caption": f"Macro details with {query} + 90mm lens 🌸 #macrophotography",
                "author": "macro_world",
                "likes": 2100,
                "comments": 78,
                "hashtags": ["macro", "closeup", "details"],
                "image": "https://images.unsplash.com/photo-1490750967868-88aa4486c946?w=800",
            },
        ]
    
    def _get_product_templates(self, query: str) -> list:
        """Generic product templates."""
        return [
            {
                "caption": f"Just got my new {query}! First impressions are amazing 😍",
                "author": "tech_reviewer",
                "likes": 1560,
                "comments": 67,
                "hashtags": ["unboxing", query.replace(" ", "").lower(), "newtech"],
                "image": f"https://picsum.photos/seed/{query}1/800/800",
            },
            {
                "caption": f"Daily essential: {query} 📱 #lifestyle",
                "author": "minimal_life",
                "likes": 2340,
                "comments": 89,
                "hashtags": ["minimalism", "essentials", "lifestyle"],
                "image": f"https://picsum.photos/seed/{query}2/800/800",
            },
            {
                "caption": f"Setup complete with {query} ✨ #aesthetic",
                "author": "setup_goals",
                "likes": 4560,
                "comments": 156,
                "hashtags": ["desksetup", "aesthetic", "workspace"],
                "image": f"https://picsum.photos/seed/{query}3/800/800",
            },
            {
                "caption": f"One month with {query} - still loving it! Review coming soon",
                "author": "honest_review",
                "likes": 890,
                "comments": 34,
                "hashtags": ["review", "honest", "monthlyupdate"],
                "image": f"https://picsum.photos/seed/{query}4/800/800",
            },
        ]


# Singleton instance
instagram_service = InstagramService()
