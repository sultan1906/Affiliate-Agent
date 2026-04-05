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
                      price="9.99", image_url="http://img.com/1.jpg"):
    """Create a mock product dict as returned by AliExpress API."""
    return {
        "product_id": product_id,
        "product_title": title,
        "target_sale_price": price,
        "evaluate_rate": "4.8",
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
