import pytest
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe, load_listings

def test_search_listings_returns_results():
    """Verify that search returns results for a valid query."""
    result = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(result, list)
    assert len(result) > 0

def test_search_listings_empty_results():
    """Verify that search returns empty list when no matches are found."""
    result = search_listings("designer ballgown", size="XXS", max_price=5)
    assert result == []

def test_search_listings_price_filter():
    """Verify that price filter restricts results to <= max_price."""
    result = search_listings("jacket", size=None, max_price=10)
    # Check if there are any jackets under $10 in the mock dataset
    # If there are, verify their prices.
    for item in result:
        assert item["price"] <= 10.0

def test_suggest_outfit_empty_wardrobe():
    """Verify that suggest_outfit works gracefully with an empty wardrobe."""
    listings = load_listings()
    assert len(listings) > 0
    selected_item = listings[0]
    
    empty_wardrobe = get_empty_wardrobe()
    output = suggest_outfit(selected_item, empty_wardrobe)
    
    assert isinstance(output, str)
    assert len(output.strip()) > 0
    # Should contain general styling advice or not crash
    assert "Error suggesting outfit" not in output

def test_create_fit_card_empty_outfit():
    """Verify that create_fit_card returns an error message when outfit is empty."""
    listings = load_listings()
    selected_item = listings[0]
    
    output = create_fit_card("", selected_item)
    
    assert isinstance(output, str)
    assert len(output.strip()) > 0
    assert "Error" in output or "missing" in output.lower() or "cannot create" in output.lower()

def test_returned_search_fields():
    """Verify returned search items include required listing fields."""
    result = search_listings("vintage", size=None, max_price=None)
    assert len(result) > 0
    required_fields = {
        "id", "title", "description", "category", "style_tags",
        "size", "condition", "price", "colors", "brand", "platform"
    }
    for item in result:
        for field in required_fields:
            assert field in item
