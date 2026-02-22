"""
Automated Blog Post Generator for Outfi.

Uses OpenAI GPT-4o-mini to generate SEO-optimized fashion blog posts.
Posts are saved as drafts for editorial review before publishing.
"""

import json
import logging
import os
import random

from openai import OpenAI

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────
# Curated fashion topics organized by category
# ──────────────────────────────────────────────────────────
TOPIC_POOL = {
    "trends": [
        "Top Fashion Trends for This Season",
        "Emerging Street Style Trends You Need to Know",
        "Color Trends Taking Over Fashion Right Now",
        "The Rise of Quiet Luxury in Everyday Fashion",
        "Y2K Fashion Revival: What's Coming Back",
        "Sustainable Fashion Trends That Are Here to Stay",
        "How Athleisure Is Evolving in 2026",
        "The Return of Vintage: Why Thrift Is Trending",
        "Minimalist Fashion: Less Is More",
        "Bold Prints and Patterns Making a Comeback",
    ],
    "styling_tips": [
        "How to Build a Capsule Wardrobe on a Budget",
        "5 Ways to Style a White T-Shirt",
        "How to Dress for a Job Interview Without Breaking the Bank",
        "Layering Tips for Transitional Weather",
        "How to Accessorize Any Outfit Like a Pro",
        "The Art of Mixing High and Low Fashion",
        "Weekend Outfit Ideas That Actually Look Polished",
        "How to Style Oversized Clothing Without Looking Sloppy",
        "Color Blocking: A Beginner's Guide",
        "How to Transition Your Wardrobe from Day to Night",
    ],
    "seasonal": [
        "Best Spring Wardrobe Essentials Under $100",
        "Summer Vacation Packing Guide: What to Bring",
        "Fall Fashion Staples Every Closet Needs",
        "Winter Layering Guide: Stay Stylish in the Cold",
        "Festival Season: What to Wear This Year",
        "Holiday Party Outfit Ideas for Every Budget",
        "Beach to Brunch: Versatile Summer Outfits",
        "Back to School Style Guide",
        "Wedding Guest Outfit Ideas by Season",
        "Rainy Day Fashion That Actually Looks Good",
    ],
    "shopping_guides": [
        "Best Leather Jackets Under $200",
        "Top 10 White Sneakers Worth the Investment",
        "Affordable Jewelry Brands That Look Expensive",
        "Best Denim Brands for Every Body Type",
        "Sunglasses Guide: Find Your Perfect Frame Shape",
        "The Best Crossbody Bags for Everyday Use",
        "Investing in Quality: Items Worth Splurging On",
        "Best Online Stores for Budget-Friendly Fashion",
        "Affordable Dupes for Designer Favorites",
        "The Best Activewear Brands for Women",
    ],
    "brand_spotlights": [
        "Why Everyone Is Obsessed With This Emerging Brand",
        "Sustainable Fashion Brands Making a Real Difference",
        "Up-and-Coming Designers to Watch",
        "The Best Direct-to-Consumer Fashion Brands",
        "Luxury Brands That Offer Affordable Lines",
        "Indie Fashion Labels Worth Discovering",
        "Small Business Fashion Brands Supporting Communities",
        "Fashion Tech Startups Changing How We Shop",
        "Celebrity-Founded Fashion Brands Worth Trying",
        "Ethical Fashion Brands for the Conscious Shopper",
    ],
}


SYSTEM_PROMPT = """You are an expert fashion editorial writer for Outfi, a premium fashion discovery platform at https://outfi.ai. 
Write engaging, SEO-optimized blog posts that feel authentic and editorial — not AI-generated.

Rules:
- Write in a warm, knowledgeable, conversational tone
- Include specific product recommendations and styling tips
- Use HTML formatting for the content (h2, h3, p, blockquote, ul/li, strong, em)
- Make content actionable and useful for readers
- Target 800-1200 words
- Include fashion-relevant keywords naturally
- Never use filler phrases like "in today's world" or "in conclusion"
- Write like a real fashion editor at Vogue or Who What Wear
- IMPORTANT: Include 2-3 internal links within the content pointing to relevant Outfi pages:
  - Link to https://outfi.ai/explore for browsing collections (e.g., "explore our curated collection")
  - Link to https://outfi.ai/home for discovering brands (e.g., "discover trending brands")  
  - Link to https://outfi.ai/explore/dresses or /explore/jackets etc. for specific categories
  - Use natural anchor text, never "click here"

You must return a valid JSON object with these exact keys:
{
  "title": "Post title (compelling, under 70 chars)",
  "excerpt": "2-3 sentence preview for the blog listing page (under 300 chars)",
  "content": "Full HTML content of the article (h2, h3, p, blockquote, ul, li, strong, em, a tags with internal links)",
  "meta_title": "SEO title under 60 chars",
  "meta_description": "SEO description under 160 chars",
  "category": "One of: Trends, Style Tips, Shopping Guide, Brand Spotlight, Seasonal",
  "tags": ["3-5 relevant lowercase tags"]
}

Return ONLY the JSON object, no markdown fences, no extra text."""


def generate_blog_post(topic=None):
    """
    Generate a blog post using OpenAI.
    
    Args:
        topic: Optional specific topic. If None, a random topic is selected.
    
    Returns:
        dict with keys: title, excerpt, content, meta_title, meta_description, category, tags
        None if generation fails.
    """
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        logger.error("OPENAI_API_KEY not set — cannot generate blog post")
        return None

    # Pick a random topic if none provided
    if not topic:
        category = random.choice(list(TOPIC_POOL.keys()))
        topic = random.choice(TOPIC_POOL[category])
        logger.info(f"Selected topic: '{topic}' from category '{category}'")

    client = OpenAI(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Write a blog post about: {topic}"},
            ],
            temperature=0.8,
            max_tokens=2500,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)

        # Validate required fields
        required = ["title", "excerpt", "content", "category", "tags"]
        for field in required:
            if field not in data:
                logger.error(f"Missing required field '{field}' in AI response")
                return None

        logger.info(f"Successfully generated post: '{data['title']}'")
        return data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response as JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"OpenAI API call failed: {e}")
        return None


def save_blog_post(data, author=None):
    """
    Save generated blog post data to the database as a draft.
    
    Args:
        data: dict from generate_blog_post()
        author: Optional User instance
    
    Returns:
        Post instance or None
    """
    from blog.models import Post, Category, Tag

    try:
        # Get or create category
        category_name = data.get("category", "Trends")
        category, _ = Category.objects.get_or_create(
            name=category_name,
            defaults={"description": f"Posts about {category_name.lower()}"},
        )

        # Create the post
        post = Post(
            title=data["title"],
            excerpt=data["excerpt"][:300],
            content=data["content"],
            category=category,
            status="draft",
            author=author,
            meta_title=data.get("meta_title", "")[:60],
            meta_description=data.get("meta_description", "")[:160],
        )
        post.save()

        # Add tags
        tag_names = data.get("tags", [])
        for tag_name in tag_names[:5]:
            tag, _ = Tag.objects.get_or_create(name=tag_name.lower().strip())
            post.tags.add(tag)

        logger.info(f"Saved draft post: '{post.title}' (id={post.id})")
        return post

    except Exception as e:
        logger.error(f"Failed to save blog post: {e}")
        return None
