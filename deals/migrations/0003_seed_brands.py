"""
Seed initial fashion brands from Shopify partner stores.
"""

from django.db import migrations


INITIAL_BRANDS = [
    # Women's Fashion
    {"name": "Fashion Nova", "slug": "fashion-nova", "category": "womens", "shopify_domain": "fashionnova.com", "is_featured": True, "website_url": "https://fashionnova.com", "description": "Trendy, affordable women's fashion"},
    {"name": "Princess Polly", "slug": "princess-polly", "category": "womens", "shopify_domain": "us.princesspolly.com", "is_featured": True, "website_url": "https://us.princesspolly.com", "description": "Australian-born women's fashion brand"},
    {"name": "Oh Polly", "slug": "oh-polly", "category": "womens", "shopify_domain": "ohpolly.com", "is_featured": False, "website_url": "https://ohpolly.com", "description": "Bodycon dresses and statement pieces"},
    {"name": "Meshki", "slug": "meshki", "category": "womens", "shopify_domain": "meshki.us", "is_featured": False, "website_url": "https://meshki.us", "description": "Modern women's fashion from Australia"},
    {"name": "Beginning Boutique", "slug": "beginning-boutique", "category": "womens", "shopify_domain": "beginningboutique.com", "is_featured": False, "website_url": "https://beginningboutique.com", "description": "Festival and occasion wear"},

    # Men's & Unisex
    {"name": "Gymshark", "slug": "gymshark", "category": "activewear", "shopify_domain": "gymshark.com", "is_featured": True, "website_url": "https://gymshark.com", "description": "Performance fitness apparel"},
    {"name": "Taylor Stitch", "slug": "taylor-stitch", "category": "mens", "shopify_domain": "taylorstitch.com", "is_featured": False, "website_url": "https://taylorstitch.com", "description": "Responsibly built men's clothing"},
    {"name": "BYLT Basics", "slug": "bylt-basics", "category": "mens", "shopify_domain": "byltbasics.com", "is_featured": False, "website_url": "https://byltbasics.com", "description": "Premium men's basics and essentials"},
    {"name": "True Classic", "slug": "true-classic", "category": "mens", "shopify_domain": "trueclassictees.com", "is_featured": True, "website_url": "https://trueclassictees.com", "description": "Elevated men's t-shirts and basics"},
    {"name": "Cuts Clothing", "slug": "cuts-clothing", "category": "mens", "shopify_domain": "cutsclothing.com", "is_featured": False, "website_url": "https://cutsclothing.com", "description": "Premium crew-neck tees and polos"},
    {"name": "Chubbies", "slug": "chubbies", "category": "mens", "shopify_domain": "chubbiesshorts.com", "is_featured": False, "website_url": "https://chubbiesshorts.com", "description": "Bold shorts and casual menswear"},

    # Shoes
    {"name": "Steve Madden", "slug": "steve-madden", "category": "shoes", "shopify_domain": "stevemadden.com", "is_featured": True, "website_url": "https://stevemadden.com", "description": "On-trend shoes for every occasion"},
    {"name": "Allbirds", "slug": "allbirds", "category": "shoes", "shopify_domain": "allbirds.com", "is_featured": True, "website_url": "https://allbirds.com", "description": "Sustainable comfort footwear"},

    # Bags & Accessories
    {"name": "Rebecca Minkoff", "slug": "rebecca-minkoff", "category": "bags", "shopify_domain": "rebeccaminkoff.com", "is_featured": False, "website_url": "https://rebeccaminkoff.com", "description": "Designer handbags and accessories"},

    # Jewelry
    {"name": "Mejuri", "slug": "mejuri", "category": "jewelry", "shopify_domain": "mejuri.com", "is_featured": True, "website_url": "https://mejuri.com", "description": "Everyday fine jewelry, handcrafted"},
    {"name": "Ana Luisa", "slug": "ana-luisa", "category": "jewelry", "shopify_domain": "analuisa.com", "is_featured": False, "website_url": "https://analuisa.com", "description": "Sustainable, accessible jewelry"},

    # Watches
    {"name": "MVMT", "slug": "mvmt", "category": "jewelry", "shopify_domain": "mvmt.com", "is_featured": False, "website_url": "https://mvmt.com", "description": "Minimalist watches and accessories"},

    # Beauty
    {"name": "ColourPop", "slug": "colourpop", "category": "beauty", "shopify_domain": "colourpop.com", "is_featured": True, "website_url": "https://colourpop.com", "description": "Affordable, cruelty-free beauty"},
    {"name": "Kylie Cosmetics", "slug": "kylie-cosmetics", "category": "beauty", "shopify_domain": "kyliecosmetics.com", "is_featured": True, "website_url": "https://kyliecosmetics.com", "description": "Beauty by Kylie Jenner"},
]


def seed_brands(apps, schema_editor):
    Brand = apps.get_model("deals", "Brand")
    for brand_data in INITIAL_BRANDS:
        Brand.objects.get_or_create(
            slug=brand_data["slug"],
            defaults=brand_data,
        )


def remove_brands(apps, schema_editor):
    Brand = apps.get_model("deals", "Brand")
    slugs = [b["slug"] for b in INITIAL_BRANDS]
    Brand.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("deals", "0002_brand_and_brand_like"),
    ]

    operations = [
        migrations.RunPython(seed_brands, remove_brands),
    ]
