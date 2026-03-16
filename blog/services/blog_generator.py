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
        "How Athleisure Is Evolving in Modern Wardrobes",
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
        "How to Find the Perfect Leather Jacket Under $200",
        "What to Look for When Buying White Sneakers",
        "Affordable Jewelry That Looks Expensive",
        "Finding the Right Denim for Your Body Type",
        "How to Choose Sunglasses for Your Face Shape",
        "The Best Types of Crossbody Bags for Everyday Use",
        "Items Worth Investing In for a Lasting Wardrobe",
        "How to Shop Smart Online for Fashion Deals",
        "How to Get Designer-Level Style on a Budget",
        "Choosing the Right Activewear for Your Workout",
    ],
    "culture": [
        "How Social Media Is Changing Fashion Trends",
        "The Psychology Behind What We Wear",
        "Why Sustainable Fashion Matters More Than Ever",
        "The History of Streetwear and Its Cultural Impact",
        "How Fashion Week Influences What We Actually Buy",
        "The Evolution of Workwear in the Modern Era",
        "Gender-Neutral Fashion: Breaking Traditional Boundaries",
        "The Rise of Rental Fashion and Circular Wardrobes",
        "How Celebrity Style Shapes Everyday Fashion",
        "Fashion as Self-Expression: Finding Your Personal Style",
    ],
}


SYSTEM_PROMPT = """You are an expert fashion editorial writer for Outfi, a premium AI-powered fashion discovery platform at https://outfi.ai.
Write comprehensive, deeply detailed, SEO-optimized blog posts that feel authentic, editorial, and authoritative.

CRITICAL RULES:
- NEVER mention any specific brand names, designer names, or store names.
- Keep all advice and recommendations completely generic and universal.
- Instead of naming brands, describe product qualities, materials, features, and what to look for.
- Use phrases like "look for," "opt for," "consider," "choose items that" instead of naming specific products.

CONTENT REQUIREMENTS:
- Target 1800-2500 words minimum. Posts MUST be long-form and deeply detailed.
- Break content into 5-8 clear sections using H2 headings, with H3 sub-sections where appropriate.
- Each section should be 200-400 words with specific tips, comparisons, and actionable advice.
- Include a "Frequently Asked Questions" section at the end with 3-4 Q&A pairs using H3 for each question.

SEO & KEYWORD REQUIREMENTS:
- Include 8-12 relevant SEO keywords naturally throughout the post.
- Use long-tail keyword phrases (e.g., "best affordable leather jackets for women" instead of just "leather jackets").
- Include keyword variations and synonyms (e.g., "budget fashion," "affordable style," "everyday outfits").
- Start the article with a compelling opening paragraph that includes the primary keyword in the first two sentences.
- Use keywords in H2 headings naturally.
- Include semantic keywords related to fashion trends, style advice, and wardrobe building.

TONE & STYLE:
- Write in a warm, knowledgeable, conversational tone like a real fashion editor.
- Focus on styling tips, what to look for in quality garments, and fashion principles.
- Use blockquotes for expert tips or key takeaways.
- Never use filler phrases like "in today's world," "in this article," "without further ado," or "in conclusion."
- Never mention specific brand names or store names.

INTERNAL LINKING (CRITICAL):
- Include 3-5 internal links within the content pointing to relevant Outfi pages:
  - https://outfi.ai/explore — for browsing curated collections and trending deals
  - https://outfi.ai/home — for discovering new styles
  - https://outfi.ai/explore/dresses, /explore/jackets, /explore/sneakers, /explore/bags etc. for specific categories
  - https://outfi.ai/register — for signing up
- Use natural anchor text with keywords, e.g., "explore the latest sneaker deals" linking to /explore/sneakers.

FORMATTING:
- Use HTML formatting: h2, h3, p, blockquote, ul/li, ol/li, strong, em, a tags
- Use bold for key terms
- Use bullet/numbered lists for recommendations, tips, and comparisons

You must return a valid JSON object with these exact keys:
{
  "title": "Post title (compelling, keyword-rich, under 70 chars, NO brand names)",
  "excerpt": "2-3 sentence preview (under 300 chars, NO brand names)",
  "content": "Full HTML content (1800-2500 words, NO brand names, with internal links and FAQ section)",
  "meta_title": "SEO title under 60 chars (NO brand names)",
  "meta_description": "SEO description under 160 chars (NO brand names)",
  "category": "One of: Trends, Style Tips, Shopping Guide, Culture, Seasonal",
  "tags": ["5-8 relevant lowercase SEO keyword tags"]
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
            max_tokens=4500,
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
