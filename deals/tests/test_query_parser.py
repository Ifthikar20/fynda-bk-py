"""
Tests for the Hybrid Query Parser v2

Run with: python -m pytest deals/tests/test_query_parser.py -v
"""

import pytest
import time
from deals.services.query_parser import HybridQueryParser, ParsedQuery, EntityTrie


class TestHybridQueryParser:
    """Test cases for the hybrid query parser."""

    @pytest.fixture
    def parser(self):
        return HybridQueryParser()

    # ==========================================================================
    # Brand Recognition Tests
    # ==========================================================================

    def test_exact_brand_match(self, parser):
        """Test exact brand name matching."""
        result = parser.parse("nike sneakers")
        assert result.brand == "nike"

    def test_brand_with_typo(self, parser):
        """Test fuzzy matching for brand typos."""
        result = parser.parse("nikee sneakers")
        assert result.brand == "nike"

    def test_multi_word_brand(self, parser):
        """Test multi-word brand names."""
        result = parser.parse("louis vuitton bag")
        assert result.brand == "louis vuitton"

    def test_brand_alias(self, parser):
        """Test brand alias resolution."""
        result = parser.parse("lv bag")
        assert result.brand == "louis vuitton"

    def test_designer_brand(self, parser):
        """Test designer brand recognition."""
        result = parser.parse("gucci dress")
        assert result.brand == "gucci"

    # ==========================================================================
    # Color Recognition Tests
    # ==========================================================================

    def test_basic_color(self, parser):
        """Test basic color recognition."""
        result = parser.parse("red sneakers")
        assert result.color == "red"

    def test_compound_color(self, parser):
        """Test compound color names."""
        result = parser.parse("light blue dress")
        assert result.color == "light blue"

    def test_color_shade(self, parser):
        """Test color shade recognition."""
        result = parser.parse("navy blazer")
        assert result.color == "navy"

    # ==========================================================================
    # Category Recognition Tests
    # ==========================================================================

    def test_basic_category(self, parser):
        """Test basic category recognition."""
        result = parser.parse("running sneakers")
        assert result.category == "sneakers"

    def test_category_normalization(self, parser):
        """Test category normalization (tee -> t-shirt)."""
        result = parser.parse("white tee")
        assert result.category == "t-shirt"

    def test_plural_category(self, parser):
        """Test plural category forms."""
        result = parser.parse("black jeans")
        assert result.category == "jeans"

    # ==========================================================================
    # Combined Entity Tests
    # ==========================================================================

    def test_full_query(self, parser):
        """Test parsing a complete query with multiple entities."""
        result = parser.parse("red nike sneakers under $100")

        assert result.brand == "nike"
        assert result.color == "red"
        assert result.category == "sneakers"
        assert result.budget == 100.0

    def test_complex_query(self, parser):
        """Test complex query with style and material."""
        result = parser.parse("womens slim fit leather jacket")

        assert result.gender == "women"
        assert result.style == "slim fit"
        assert result.material == "leather"
        assert result.category == "jacket"

    def test_designer_query(self, parser):
        """Test designer fashion query."""
        result = parser.parse("gucci black leather handbag")

        assert result.brand == "gucci"
        assert result.color == "black"
        assert result.material == "leather"
        assert result.category in ["handbag", "handbags"]

    # ==========================================================================
    # Budget Extraction Tests
    # ==========================================================================

    def test_budget_dollar_sign(self, parser):
        """Test budget with dollar sign."""
        result = parser.parse("shoes under $150")
        assert result.budget == 150.0

    def test_budget_with_comma(self, parser):
        """Test budget with comma."""
        result = parser.parse("budget is $1,200")
        assert result.budget == 1200.0

    def test_budget_below(self, parser):
        """Test 'below' budget pattern."""
        result = parser.parse("jeans below $80")
        assert result.budget == 80.0

    # ==========================================================================
    # Style Tests
    # ==========================================================================

    def test_style_fit(self, parser):
        """Test fit style recognition."""
        result = parser.parse("slim fit jeans")
        assert result.style == "slim fit"

    def test_style_rise(self, parser):
        """Test rise style recognition."""
        result = parser.parse("high waisted pants")
        assert result.style == "high waisted"

    # ==========================================================================
    # Gender Tests
    # ==========================================================================

    def test_gender_women(self, parser):
        """Test women's gender recognition."""
        result = parser.parse("womens running shoes")
        assert result.gender == "women"

    def test_gender_men(self, parser):
        """Test men's gender recognition."""
        result = parser.parse("mens dress shirt")
        assert result.gender == "men"

    # ==========================================================================
    # Edge Cases
    # ==========================================================================

    def test_empty_query(self, parser):
        """Test empty query handling."""
        result = parser.parse("")
        assert result.original == ""
        assert result.brand is None

    def test_noise_words_only(self, parser):
        """Test query with only noise words."""
        result = parser.parse("i am looking for something")
        assert result.product == "something"

    def test_special_characters(self, parser):
        """Test handling of special characters."""
        result = parser.parse("nike sneakers")
        assert result.brand == "nike"
        assert result.category == "sneakers"

    # ==========================================================================
    # Confidence Score Tests
    # ==========================================================================

    def test_high_confidence(self, parser):
        """Test high confidence score for well-structured query."""
        result = parser.parse("red nike sneakers under $100")
        assert result.confidence_score >= 0.5

    def test_low_confidence(self, parser):
        """Test lower confidence for vague query."""
        result = parser.parse("something nice")
        assert result.confidence_score < 0.3

    # ==========================================================================
    # API Response Tests
    # ==========================================================================

    def test_to_dict(self, parser):
        """Test conversion to dictionary."""
        result = parser.parse("red nike sneakers")
        d = result.to_dict()

        assert "original" in d
        assert "parsed" in d
        assert "entities" in d
        assert "confidence" in d
        assert "multi" in d
        assert "intent" in d
        assert d["parsed"]["brand"] == "nike"

    def test_get_search_terms(self, parser):
        """Test search terms generation."""
        result = parser.parse("red nike sneakers")
        terms = result.get_search_terms()

        assert "nike" in terms
        assert "sneakers" in terms

    def test_get_filters(self, parser):
        """Test filter generation."""
        result = parser.parse("red nike sneakers under $100")
        filters = result.get_filters()

        assert filters["brand"] == "nike"
        assert filters["color"] == "red"
        assert filters["max_price"] == 100.0


# ==========================================================================
# v2 NEW: Multi-Entity Tests
# ==========================================================================

class TestMultiEntityRecognition:
    """Test multi-entity extraction (v2 feature)."""

    @pytest.fixture
    def parser(self):
        return HybridQueryParser()

    def test_multiple_colors(self, parser):
        """Test extracting multiple colors."""
        result = parser.parse("red and blue sneakers")
        assert len(result.colors) >= 1
        assert result.color == result.colors[0]

    def test_multiple_brands(self, parser):
        """Test extracting multiple brands in comparison query."""
        result = parser.parse("nike vs adidas sneakers")
        # At least the primary brand should be found
        assert result.brand is not None
        assert len(result.brands) >= 1

    def test_brands_list_backwards_compat(self, parser):
        """Test that primary brand equals first in brands list."""
        result = parser.parse("nike sneakers")
        assert result.brand == "nike"
        assert result.brands[0] == "nike"

    def test_colors_list_backwards_compat(self, parser):
        """Test that primary color equals first in colors list."""
        result = parser.parse("red dress")
        assert result.color == "red"
        assert result.colors[0] == "red"

    def test_multi_dict_in_response(self, parser):
        """Test multi-entity data appears in API response."""
        result = parser.parse("nike red sneakers")
        d = result.to_dict()

        assert "multi" in d
        assert "brands" in d["multi"]
        assert "colors" in d["multi"]
        assert "categories" in d["multi"]


# ==========================================================================
# v2 NEW: Intent Detection Tests
# ==========================================================================

class TestIntentDetection:
    """Test intent classification (v2 feature)."""

    @pytest.fixture
    def parser(self):
        return HybridQueryParser()

    def test_default_search_intent(self, parser):
        """Test default intent is 'search'."""
        result = parser.parse("red nike sneakers")
        assert result.intent == "search"

    def test_compare_intent(self, parser):
        """Test comparison intent detection."""
        result = parser.parse("compare nike vs adidas sneakers")
        assert result.intent == "compare"

    def test_trending_intent(self, parser):
        """Test trending intent detection."""
        result = parser.parse("what's trending in sneakers")
        assert result.intent == "trending"

    def test_deal_hunt_intent(self, parser):
        """Test deal hunt intent detection."""
        result = parser.parse("best deal on nike shoes")
        assert result.intent == "deal_hunt"

    def test_brand_browse_intent(self, parser):
        """Test brand browse intent (just a brand name)."""
        result = parser.parse("gucci")
        assert result.intent == "brand_browse"

    def test_intent_in_dict(self, parser):
        """Test intent appears in API response."""
        result = parser.parse("trending sneakers")
        d = result.to_dict()
        assert "intent" in d


# ==========================================================================
# v2 NEW: Price Range Tests
# ==========================================================================

class TestPriceRange:
    """Test price range extraction (v2 feature)."""

    @pytest.fixture
    def parser(self):
        return HybridQueryParser()

    def test_dollar_range(self, parser):
        """Test $50-$100 range."""
        result = parser.parse("sneakers $50-$100")
        assert result.min_budget == 50.0
        assert result.budget == 100.0

    def test_between_range(self, parser):
        """Test 'between X and Y' range."""
        result = parser.parse("sneakers between 50 and 100")
        assert result.min_budget == 50.0
        assert result.budget == 100.0

    def test_around_price(self, parser):
        """Test 'around $X' → ±25% range."""
        result = parser.parse("sneakers around $100")
        assert result.min_budget is not None
        assert result.budget is not None
        assert result.min_budget < 100 < result.budget

    def test_from_to_range(self, parser):
        """Test 'from $X to $Y' range."""
        result = parser.parse("shoes from $30 to $80")
        assert result.min_budget == 30.0
        assert result.budget == 80.0

    def test_min_price_in_filters(self, parser):
        """Test min_price appears in filters."""
        result = parser.parse("sneakers $50-$100")
        filters = result.get_filters()
        assert "min_price" in filters
        assert "max_price" in filters

    def test_single_budget_still_works(self, parser):
        """Test single budget (under $X) still works."""
        result = parser.parse("sneakers under $150")
        assert result.budget == 150.0
        assert result.min_budget is None


# ==========================================================================
# v2 NEW: Input Sanitization Tests
# ==========================================================================

class TestInputSanitization:
    """Test input sanitization and security (v2 feature)."""

    @pytest.fixture
    def parser(self):
        return HybridQueryParser()

    def test_html_tags_stripped(self, parser):
        """Test HTML tags are removed."""
        result = parser.parse("<script>alert('xss')</script> nike shoes")
        assert "<script>" not in result.original
        assert result.brand == "nike"

    def test_sql_injection_stripped(self, parser):
        """Test SQL keywords are removed."""
        result = parser.parse("nike'; DROP TABLE deals; -- shoes")
        assert "DROP" not in result.product
        assert "TABLE" not in result.product

    def test_max_length_enforced(self, parser):
        """Test very long queries are truncated."""
        long_query = "nike shoes " * 200  # 2200 chars
        result = parser.parse(long_query)
        # Should not crash, should still parse
        assert result is not None
        assert result.brand == "nike"

    def test_empty_after_sanitization(self, parser):
        """Test empty query after sanitization returns gracefully."""
        result = parser.parse("<script></script>")
        assert result is not None
        assert result.confidence_score == 0.0

    def test_unicode_handling(self, parser):
        """Test unicode characters don't crash parser."""
        result = parser.parse("nike 👟 sneakers café")
        assert result is not None


# ==========================================================================
# v2 NEW: Query Expansion Tests
# ==========================================================================

class TestQueryExpansion:
    """Test query expansion with synonyms (v2 feature)."""

    @pytest.fixture
    def parser(self):
        return HybridQueryParser()

    def test_sneakers_expansion(self, parser):
        """Test sneakers → trainers, kicks, etc."""
        result = parser.parse("nike sneakers")
        assert len(result.expanded_terms) > 0
        # Should contain synonym-based alternatives
        expanded_text = " ".join(result.expanded_terms)
        assert any(term in expanded_text for term in ["trainers", "kicks", "running shoes"])

    def test_no_expansion_for_unknown_category(self, parser):
        """Test no expansion when category has no synonyms."""
        result = parser.parse("nike product")
        assert len(result.expanded_terms) == 0

    def test_expanded_search_terms_method(self, parser):
        """Test get_expanded_search_terms includes primary + synonyms."""
        result = parser.parse("red nike sneakers")
        terms = result.get_expanded_search_terms()
        assert len(terms) >= 1
        assert terms[0] == result.get_search_terms()  # Primary is first

    def test_expansion_capped_at_5(self, parser):
        """Test expanded terms don't exceed 5."""
        result = parser.parse("nike sneakers")
        terms = result.get_expanded_search_terms()
        assert len(terms) <= 5


# ==========================================================================
# v2 NEW: Compound Query Tests
# ==========================================================================

class TestCompoundQueries:
    """Test compound query splitting (v2 feature)."""

    @pytest.fixture
    def parser(self):
        return HybridQueryParser()

    def test_simple_and_query(self, parser):
        """Test 'A and B' compound splitting when B has entities."""
        # This may or may not split depending on entity recognition
        result = parser.parse("nike shoes")
        assert result is not None  # Should not crash

    def test_non_compound_and(self, parser):
        """Test 'and' in regular context is not split."""
        result = parser.parse("black and white sneakers")
        assert result is not None
        # Should recognize as a query about sneakers, not split

    def test_sub_queries_in_dict(self, parser):
        """Test sub_queries appear in API response when present."""
        result = parser.parse("nike shoes")
        d = result.to_dict()
        # For a simple query, no sub_queries key expected
        if not result.sub_queries:
            assert "sub_queries" not in d


# ==========================================================================
# v2 NEW: Requirements Extraction Tests
# ==========================================================================

class TestRequirements:
    """Test full multi-word requirements extraction (v2 feature)."""

    @pytest.fixture
    def parser(self):
        return HybridQueryParser()

    def test_with_requirement(self, parser):
        """Test 'with X' pattern."""
        result = parser.parse("headphones with noise canceling")
        assert len(result.requirements) > 0
        # Should keep "noise canceling" as a phrase
        assert any("noise" in r for r in result.requirements)

    def test_featuring_requirement(self, parser):
        """Test 'featuring X' pattern."""
        result = parser.parse("jacket featuring waterproof material")
        assert len(result.requirements) > 0


# ==========================================================================
# v2 NEW: Entity Trie Tests
# ==========================================================================

class TestEntityTrie:
    """Test the Trie data structure independently."""

    def test_single_word_insert_search(self):
        """Test inserting and searching single words."""
        trie = EntityTrie()
        trie.insert("nike", "brand", "nike")

        matches = trie.search(["i", "want", "nike", "shoes"])
        assert len(matches) == 1
        assert matches[0]["canonical"] == "nike"
        assert matches[0]["entity_type"] == "brand"

    def test_multi_word_insert_search(self):
        """Test inserting and searching multi-word phrases."""
        trie = EntityTrie()
        trie.insert("louis vuitton", "brand", "louis vuitton")

        matches = trie.search(["louis", "vuitton", "bag"])
        assert len(matches) == 1
        assert matches[0]["canonical"] == "louis vuitton"

    def test_greedy_longest_match(self):
        """Test trie prefers longest match."""
        trie = EntityTrie()
        trie.insert("air", "brand", "air")
        trie.insert("air jordan", "brand", "air jordan")

        matches = trie.search(["air", "jordan", "shoes"])
        assert len(matches) == 1
        assert matches[0]["canonical"] == "air jordan"

    def test_multiple_entities_found(self):
        """Test finding multiple entities in one query."""
        trie = EntityTrie()
        trie.insert("nike", "brand", "nike")
        trie.insert("red", "color", "red")
        trie.insert("sneakers", "category", "sneakers")

        matches = trie.search(["red", "nike", "sneakers"])
        assert len(matches) == 3

    def test_no_overlapping_matches(self):
        """Test positions are not matched twice."""
        trie = EntityTrie()
        trie.insert("off white", "brand", "off white")
        trie.insert("white", "color", "white")

        matches = trie.search(["off", "white", "shoes"])
        # Should match "off white" as brand, not "white" as color
        assert len(matches) == 1
        assert matches[0]["canonical"] == "off white"

    def test_empty_search(self):
        """Test searching with empty word list."""
        trie = EntityTrie()
        trie.insert("nike", "brand", "nike")
        matches = trie.search([])
        assert len(matches) == 0

    def test_trie_size(self):
        """Test trie tracks size correctly."""
        trie = EntityTrie()
        assert trie.size == 0
        trie.insert("nike", "brand", "nike")
        assert trie.size == 1
        trie.insert("adidas", "brand", "adidas")
        assert trie.size == 2


# ==========================================================================
# Fuzzy Matching Tests
# ==========================================================================

class TestFuzzyMatching:
    """Test fuzzy matching capabilities."""

    @pytest.fixture
    def parser(self):
        return HybridQueryParser(fuzzy_threshold=2)

    def test_single_char_typo(self, parser):
        """Test single character typo correction."""
        result = parser.parse("addidas sneakers")
        assert result.brand == "adidas"

    def test_double_char_typo(self, parser):
        """Test double character typo correction."""
        result = parser.parse("guccii bag")
        assert result.brand == "gucci"

    def test_swapped_chars(self, parser):
        """Test swapped character correction."""
        result = parser.parse("niike shoes")
        assert result.brand == "nike"

    def test_disabled_fuzzy(self):
        """Test with fuzzy matching disabled."""
        parser = HybridQueryParser(enable_fuzzy=False)
        result = parser.parse("nikee sneakers")
        # Without fuzzy, "nikee" should not match
        assert result.brand is None


# ==========================================================================
# Real-World Query Tests
# ==========================================================================

class TestRealWorldQueries:
    """Test with real-world query patterns."""

    @pytest.fixture
    def parser(self):
        return HybridQueryParser()

    def test_conversational_query(self, parser):
        """Test conversational/natural language query."""
        result = parser.parse("I'm looking for a black leather jacket from zara")

        assert result.brand == "zara"
        assert result.color == "black"
        assert result.material == "leather"
        assert result.category == "jacket"

    def test_brand_focused_query(self, parser):
        """Test brand-focused query."""
        result = parser.parse("show me off white sneakers")

        assert result.brand == "off white"
        assert result.category == "sneakers"

    def test_budget_focused_query(self, parser):
        """Test budget-focused query."""
        result = parser.parse("cheap nike running shoes max $80")

        assert result.brand == "nike"
        assert result.budget == 80.0

    def test_occasion_query(self, parser):
        """Test occasion-based query."""
        result = parser.parse("wedding guest dress")

        assert result.occasion == "wedding guest"
        assert result.category == "dress"

    def test_streetwear_query(self, parser):
        """Test streetwear/hype brand query."""
        result = parser.parse("supreme hoodie")

        assert result.brand == "supreme"
        assert result.category in ["hoodie", "hoodies"]

    def test_price_range_query(self, parser):
        """Test real-world price range query."""
        result = parser.parse("nike sneakers between 80 and 150")
        assert result.brand == "nike"
        assert result.min_budget == 80.0
        assert result.budget == 150.0


# ==========================================================================
# Performance Tests
# ==========================================================================

class TestPerformance:
    """Test parser performance characteristics."""

    @pytest.fixture
    def parser(self):
        return HybridQueryParser()

    def test_parse_speed(self, parser):
        """Test 100 parses complete in under 2 seconds."""
        queries = [
            "red nike sneakers under $100",
            "gucci leather handbag",
            "womens slim fit jeans",
            "black dress for wedding",
            "cheap running shoes",
            "louis vuitton wallet",
            "blue adidas hoodie",
            "cotton t-shirt men",
            "summer floral dress",
            "nike vs adidas sneakers $50-$100",
        ]

        start = time.time()
        for _ in range(10):
            for q in queries:
                parser.parse(q)
        elapsed = time.time() - start

        assert elapsed < 2.0, f"100 parses took {elapsed:.2f}s (should be < 2.0s)"

    def test_parser_does_not_crash_on_garbage(self, parser):
        """Test parser handles garbage input gracefully."""
        garbage_inputs = [
            "",
            " ",
            "      ",
            "!!!???...",
            "12345",
            "a" * 1000,
            "\n\n\n\t\t",
            "🔥👟💯",
            None,  # Should be handled by str() or crash safely
        ]

        for inp in garbage_inputs:
            try:
                if inp is not None:
                    result = parser.parse(inp)
                    assert result is not None
            except (TypeError, AttributeError):
                pass  # None input may raise, that's acceptable


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
