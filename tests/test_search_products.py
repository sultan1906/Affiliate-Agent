"""Tests for search_products module."""
import json
import os
import pytest
from unittest.mock import patch, MagicMock


QUEUE_FILE = "/tmp/test_pending_queue.json"


@pytest.fixture(autouse=True)
def cleanup_queue():
    """Remove test queue file before and after each test."""
    if os.path.exists(QUEUE_FILE):
        os.remove(QUEUE_FILE)
    yield
    if os.path.exists(QUEUE_FILE):
        os.remove(QUEUE_FILE)


FAKE_CONFIG = {
    "ALI_APP_KEY": "key",
    "ALI_SECRET": "secret",
    "ALI_TRACKING_ID": "tracking",
}


def _make_api_product(product_id="123", title="Wedding Decor",
                      price="9.99", image_url="http://img.com/1.jpg",
                      rating="4.8", volume="500", commission_rate="8.0"):
    """Create a mock product dict as returned by AliExpress hotproduct API."""
    return {
        "product_id": product_id,
        "product_title": title,
        "target_sale_price": price,
        "evaluate_rate": rating,
        "lastest_volume": volume,
        "commission_rate": commission_rate,
        "product_main_image_url": image_url,
        "product_detail_url": f"https://www.aliexpress.com/item/{product_id}.html",
        "promotion_link": None,
    }


def test_search_and_save_creates_queue_file():
    """search_and_save writes products to a JSON file."""
    from search_products import search_and_save

    mock_products = [_make_api_product(str(i)) for i in range(15)]

    with patch("search_products._search_aliexpress", return_value=mock_products):
        search_and_save(FAKE_CONFIG, output_file=QUEUE_FILE, max_results=10)

    assert os.path.exists(QUEUE_FILE)
    with open(QUEUE_FILE) as f:
        data = json.load(f)
    assert len(data) <= 10
    assert all(p["status"] == "pending" for p in data)
    assert all("id" in p and "product_id" in p for p in data)


def test_search_and_save_product_fields():
    """Each saved product has required fields."""
    from search_products import search_and_save

    mock_products = [_make_api_product("42", "Bridal Clip", "5.99", "http://img.com/clip.jpg")]

    with patch("search_products._search_aliexpress", return_value=mock_products):
        search_and_save(FAKE_CONFIG, output_file=QUEUE_FILE, max_results=10)

    with open(QUEUE_FILE) as f:
        data = json.load(f)

    product = data[0]
    assert product["product_id"] == "42"
    assert product["title"] == "Bridal Clip"
    assert product["price"] == 5.99
    assert product["image_url"] == "http://img.com/clip.jpg"
    assert product["product_url"] == "https://www.aliexpress.com/item/42.html"
    assert product["status"] == "pending"
    assert product["affiliate_link"] is None
    assert product["orders"] == 500
    assert product["commission_rate"] == 8.0


def test_quality_filter_rejects_low_orders():
    """Products with fewer than 100 orders are filtered out."""
    from search_products import search_and_save

    low_orders = _make_api_product("1", volume="50", rating="4.9")
    high_orders = _make_api_product("2", volume="200", rating="4.8")

    with patch("search_products._search_aliexpress", return_value=[low_orders, high_orders]):
        result = search_and_save(FAKE_CONFIG, output_file=QUEUE_FILE, max_results=10)

    assert len(result) == 1
    assert result[0]["product_id"] == "2"


def test_quality_filter_rejects_low_rating():
    """Products with rating below 4.5 are filtered out."""
    from search_products import search_and_save

    low_rating = _make_api_product("1", rating="3.9", volume="500")
    good_rating = _make_api_product("2", rating="4.6", volume="500")

    with patch("search_products._search_aliexpress", return_value=[low_rating, good_rating]):
        result = search_and_save(FAKE_CONFIG, output_file=QUEUE_FILE, max_results=10)

    assert len(result) == 1
    assert result[0]["product_id"] == "2"


def test_quality_filter_passes_exact_thresholds():
    """Products exactly at the minimum thresholds pass the filter."""
    from search_products import search_and_save

    product = _make_api_product("1", rating="4.5", volume="100")

    with patch("search_products._search_aliexpress", return_value=[product]):
        result = search_and_save(FAKE_CONFIG, output_file=QUEUE_FILE, max_results=10)

    assert len(result) == 1


def test_search_uses_hotproduct_endpoint():
    """Verify the API call uses the hotproduct query method."""
    from search_products import _search_aliexpress

    with patch("search_products.requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "aliexpress_affiliate_hotproduct_query_response": {
                "resp_result": {
                    "resp_code": 200,
                    "result": {"products": {"product": []}},
                }
            }
        }
        mock_get.return_value = mock_resp

        _search_aliexpress("test", FAKE_CONFIG)

        call_params = mock_get.call_args[1]["params"]
        assert call_params["method"] == "aliexpress.affiliate.hotproduct.query"
        assert call_params["sort"] == "COMMISSION_RATE_DESC"
        assert call_params["ship_to_country"] == "IL"


def test_search_and_save_passes_wedding_categories():
    """search_and_save always anchors to wedding category IDs by default."""
    from search_products import search_and_save, WEDDING_CATEGORY_IDS

    with patch("search_products._search_aliexpress", return_value=[]) as mock_search:
        search_and_save(FAKE_CONFIG, output_file=QUEUE_FILE, max_results=10)

        _, kwargs = mock_search.call_args
        assert kwargs["category_ids"] == WEDDING_CATEGORY_IDS
