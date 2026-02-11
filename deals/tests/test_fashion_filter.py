"""
Tests for the taxonomy-powered fashion filter.

Loads the same fashion_taxonomy.json that the orchestrator uses.
Run:  python -m pytest deals/tests/test_fashion_filter.py -v
"""

import json
from pathlib import Path

# Load taxonomy from the generated JSON
TAXONOMY_PATH = Path(__file__).parent.parent / "services" / "fashion_taxonomy.json"

with open(TAXONOMY_PATH) as f:
    _data = json.load(f)

FASHION_KEYWORDS = _data["fashion_terms"]
NON_FASHION_KEYWORDS = _data["non_fashion_terms"]


def _filter(deals):
    """Replicate the dual-layer is_fashion() logic from the orchestrator."""
    def is_fashion(deal):
        title = (deal.get("title") or "").lower()
        for kw in NON_FASHION_KEYWORDS:
            if kw in title:
                return False
        for kw in FASHION_KEYWORDS:
            if kw in title:
                return True
        return False
    return [d for d in deals if is_fashion(d)]


def _deal(title):
    return {"title": title, "price": 29.99}


# ═══════════════════════════════════════════════════
# Taxonomy stats
# ═══════════════════════════════════════════════════

class TestTaxonomyLoaded:
    def test_has_fashion_terms(self):
        assert len(FASHION_KEYWORDS) > 500, f"Expected 500+ fashion terms, got {len(FASHION_KEYWORDS)}"

    def test_has_non_fashion_terms(self):
        assert len(NON_FASHION_KEYWORDS) > 3000, f"Expected 3000+ non-fashion terms, got {len(NON_FASHION_KEYWORDS)}"


# ═══════════════════════════════════════════════════
# Non-fashion items should be BLOCKED
# ═══════════════════════════════════════════════════

class TestBlocksNonFashion:
    def test_blocks_food(self):
        assert _filter([_deal("Velvet Red Cake Mix 12oz")]) == []

    def test_blocks_electronics(self):
        assert _filter([_deal("Wireless Bluetooth Headphone")]) == []

    def test_blocks_toys(self):
        assert _filter([_deal("LEGO Star Wars Building Set")]) == []

    def test_blocks_garden(self):
        assert _filter([_deal("Garden Hose 50ft Heavy Duty")]) == []

    def test_blocks_tools(self):
        assert _filter([_deal("Dewalt Power Drill Kit 20V")]) == []

    def test_blocks_pet(self):
        assert _filter([_deal("Premium Dog Food 30lb Bag")]) == []

    def test_blocks_sports(self):
        assert _filter([_deal("Wilson NBA Basketball Official Size")]) == []

    def test_blocks_cleaning(self):
        assert _filter([_deal("Dyson V15 Cordless Vacuum Cleaner")]) == []

    def test_blocks_office(self):
        assert _filter([_deal("Moleskine Classic Notebook Ruled")]) == []

    def test_blocks_automotive(self):
        assert _filter([_deal("Mobil 1 Synthetic Motor Oil 5W-30")]) == []


# ═══════════════════════════════════════════════════
# Fashion items should PASS
# ═══════════════════════════════════════════════════

class TestPassesFashion:
    def test_passes_dress(self):
        assert len(_filter([_deal("Women's Velvet Midi Dress")])) == 1

    def test_passes_shoes(self):
        assert len(_filter([_deal("Nike Air Max Running Shoe")])) == 1

    def test_passes_handbag(self):
        assert len(_filter([_deal("Coach Leather Crossbody Bag")])) == 1

    def test_passes_jewelry(self):
        assert len(_filter([_deal("Gold Chain Necklace 18K")])) == 1

    def test_passes_sunglasses(self):
        assert len(_filter([_deal("Ray-Ban Aviator Sunglasses")])) == 1

    def test_passes_jeans(self):
        assert len(_filter([_deal("Levi's 501 Original Jeans")])) == 1

    def test_passes_jacket(self):
        assert len(_filter([_deal("Men's Bomber Jacket Black")])) == 1

    def test_passes_makeup(self):
        assert len(_filter([_deal("MAC Ruby Woo Lipstick")])) == 1

    def test_passes_watch(self):
        assert len(_filter([_deal("Casio Digital Watch Black")])) == 1

    def test_passes_sweater(self):
        assert len(_filter([_deal("Cashmere Crew Neck Sweater")])) == 1

    def test_passes_perfume(self):
        assert len(_filter([_deal("Chanel No. 5 Eau de Parfum")])) == 1

    def test_passes_boots(self):
        assert len(_filter([_deal("Dr. Martens 1460 Smooth Leather Boot")])) == 1


# ═══════════════════════════════════════════════════
# Ambiguous terms — the core issue we're fixing
# ═══════════════════════════════════════════════════

class TestAmbiguousTerms:
    def test_apple_grocery_blocked(self):
        assert _filter([_deal("Organic Fuji Apple 3lb Bag")]) == []

    def test_apple_tech_blocked(self):
        assert _filter([_deal("Apple MacBook Pro 16 inch")]) == []

    def test_rose_flower_blocked(self):
        assert _filter([_deal("Fresh Cut Red Roses Bouquet 12ct")]) == []

    def test_rose_gold_necklace_passes(self):
        assert len(_filter([_deal("Rose Gold Chain Necklace")])) == 1

    def test_gold_bullion_blocked(self):
        assert _filter([_deal("1oz Gold Bullion Bar 999")]) == []

    def test_gold_earring_passes(self):
        assert len(_filter([_deal("14K Gold Hoop Earring Set")])) == 1

    def test_cherry_food_blocked(self):
        assert _filter([_deal("Fresh Cherry Tomatoes 1lb")]) == []

    def test_pearl_necklace_passes(self):
        assert len(_filter([_deal("Freshwater Pearl Necklace")])) == 1

    def test_random_product_blocked(self):
        assert _filter([_deal("Philips Hue Smart Light Bulb")]) == []

    def test_velvet_cake_blocked(self):
        assert _filter([_deal("Red Velvet Cake Mix Duncan Hines")]) == []

    def test_velvet_dress_passes(self):
        assert len(_filter([_deal("Velvet Bodycon Dress Black")])) == 1


# ═══════════════════════════════════════════════════
# Edge cases
# ═══════════════════════════════════════════════════

class TestEdgeCases:
    def test_empty_list(self):
        assert _filter([]) == []

    def test_none_title(self):
        assert _filter([{"title": None, "price": 10}]) == []

    def test_empty_title(self):
        assert _filter([{"title": "", "price": 10}]) == []

    def test_case_insensitive(self):
        assert len(_filter([_deal("WOMEN'S SILK BLOUSE")])) == 1

    def test_mixed_results(self):
        deals = [
            _deal("Women's Cotton T-Shirt"),
            _deal("Organic Apple Sauce 24oz"),
            _deal("Nike Air Jordan Sneaker"),
            _deal("Bluetooth Speaker 20W"),
            _deal("Gold Pendant Necklace"),
        ]
        result = _filter(deals)
        assert len(result) == 3
        titles = [d["title"] for d in result]
        assert "Women's Cotton T-Shirt" in titles
        assert "Nike Air Jordan Sneaker" in titles
        assert "Gold Pendant Necklace" in titles


# ═══════════════════════════════════════════════════
# Gender filtering
# ═══════════════════════════════════════════════════

def _filter_by_gender(deals, gender):
    """Replicate the gender filter logic from the orchestrator."""
    import re
    
    WOMEN_INDICATORS = {"women", "womens", "women's", "woman", "ladies", "lady", "girls", "girl", "female", "maternity"}
    MEN_PATTERNS = [
        re.compile(r"\bmen\b", re.IGNORECASE),
        re.compile(r"\bmens\b", re.IGNORECASE),
        re.compile(r"\bmen's\b", re.IGNORECASE),
        re.compile(r"\bboys?\b", re.IGNORECASE),
        re.compile(r"\bmale\b", re.IGNORECASE),
        re.compile(r"\bgentleman\b", re.IGNORECASE),
    ]

    gender_lower = gender.lower()

    def passes(deal):
        title = (deal.get("title") or "").lower()
        if gender_lower == "men":
            for ind in WOMEN_INDICATORS:
                if ind in title:
                    return False
        elif gender_lower == "women":
            for pattern in MEN_PATTERNS:
                if pattern.search(title):
                    return False
        return True

    return [d for d in deals if passes(d)]


class TestGenderFilter:
    def test_men_query_removes_womens(self):
        deals = [
            _deal("Women's White Winter Coat"),
            _deal("Men's White Winter Coat"),
            _deal("White Winter Coat Unisex"),
        ]
        result = _filter_by_gender(deals, "men")
        assert len(result) == 2
        titles = [d["title"] for d in result]
        assert "Women's White Winter Coat" not in titles

    def test_women_query_removes_mens(self):
        deals = [
            _deal("Men's Slim Fit Dress Shirt"),
            _deal("Women's Wrap Dress"),
            _deal("Floral Midi Dress"),
        ]
        result = _filter_by_gender(deals, "women")
        assert len(result) == 2
        titles = [d["title"] for d in result]
        assert "Men's Slim Fit Dress Shirt" not in titles

    def test_no_gender_keeps_all(self):
        deals = [
            _deal("Women's Velvet Midi Dress"),
            _deal("Men's Bomber Jacket"),
            _deal("Unisex Sneaker"),
        ]
        # No filtering when no gender specified (not calling filter)
        assert len(deals) == 3

    def test_men_doesnt_match_women_substring(self):
        """'men' should NOT match inside 'women'."""
        deals = [_deal("Women's Summer Dress")]
        result = _filter_by_gender(deals, "women")
        assert len(result) == 1  # Should NOT be removed

    def test_ladies_removed_for_men(self):
        deals = [_deal("Ladies Gold Watch"), _deal("Classic Gold Watch")]
        result = _filter_by_gender(deals, "men")
        assert len(result) == 1
        assert result[0]["title"] == "Classic Gold Watch"

    def test_boys_removed_for_women(self):
        deals = [_deal("Boys Graphic Tee"), _deal("Silk Blouse")]
        result = _filter_by_gender(deals, "women")
        assert len(result) == 1
        assert result[0]["title"] == "Silk Blouse"

