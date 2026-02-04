"""
Tests for the Hybrid Query Parser

Run with: python -m pytest deals/tests/test_query_parser.py -v
"""

import pytest
from deals.services.query_parser import HybridQueryParser, ParsedQuery


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
        result = parser.parse("nike! sneakers?")
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
