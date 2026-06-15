from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

class TestSearchListings:
    def test_happy_path_returns_best_match_first(self):
        results = search_listings(description="Levi's Faded Black Straight Leg Jeans", max_price=30.00)
        assert results[0]["id"] == "lst_037"

    def test_no_match_returns_empty_list(self):
        assert search_listings(description="Vintage jacket", size="S", max_price=1.00) == []

    def test_price_filter_excludes_over_budget(self):
        results = search_listings(description="jacket", max_price=20.00)
        assert all(r["price"] <= 20.00 for r in results)

    def test_size_filter(self):
        results_pants = search_listings(description="jeans", size="W28")
        results_shoes = search_listings(description="shoes", size="US 10")
        assert all("w28" in r["size"].lower() for r in results_pants)
        assert all("us10" in r["size"].lower() for r in results_shoes)

class TestSuggestOutfit:
    ITEM = {"title": "Vintage Tee", "description": "90s graphic tee", "size": "M", "colors": ["white"], "price": 15.00}

    def test_returns_string(self):
        result = suggest_outfit(self.ITEM, get_example_wardrobe())
        assert isinstance(result, str) and len(result) > 0

    def test_empty_wardrobe_still_returns_advice(self):
        result = suggest_outfit(self.ITEM, get_empty_wardrobe())
        assert isinstance(result, str) and len(result) > 0


class TestCreateFitCard:
    ITEM = {"title": "Vintage Tee", "price": 15.00, "platform": "depop"}

    def test_returns_caption_string(self):
        result = create_fit_card("White tee with baggy jeans and chunky sneakers", self.ITEM)
        assert isinstance(result, str) and len(result) > 0

    def test_empty_outfit_returns_error_message(self):
        result = create_fit_card("", self.ITEM)
        assert "no caption" in result.lower() or "no outfit" in result.lower()