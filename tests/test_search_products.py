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


def _make_mock_product(product_id: str = "123", title: str = "Wedding Decor",
                       price: float = 9.99, rating: float = 4.8,
                       image_url: str = "http://img.com/1.jpg") -> dict:
    """Create a mock product dict as returned by AliExpress scraper."""
    return {
        "id": product_id,
        "url": f"https://www.aliexpress.com/item/{product_id}.html",
        "title": title,
        "min_price": price,
        "currency": "USD",
        "thumbnail": image_url,
        "trade": "100+ sold",
        "type": "common",
        "store": {
            "url": "https://store.aliexpress.com/1",
            "name": "Test Store",
            "id": "1",
            "member_id": "1",
        },
    }


def test_search_and_save_creates_queue_file():
    """search_and_save writes products to a JSON file."""
    from search_products import search_and_save

    mock_products = [_make_mock_product(str(i)) for i in range(15)]
    mock_result = {"products": mock_products}

    with patch("search_products.AliExpress") as MockAli:
        instance = MockAli.return_value
        instance.search_products.return_value = mock_result
        search_and_save(output_file=QUEUE_FILE, max_results=10)

    assert os.path.exists(QUEUE_FILE)
    with open(QUEUE_FILE) as f:
        data = json.load(f)
    assert len(data) <= 10
    assert all(p["status"] == "pending" for p in data)
    assert all("id" in p and "product_id" in p for p in data)


def test_search_and_save_product_fields():
    """Each saved product has required fields."""
    from search_products import search_and_save

    mock_products = [_make_mock_product("42", "Bridal Clip", 5.99, 4.9, "http://img.com/clip.jpg")]
    mock_result = {"products": mock_products}

    with patch("search_products.AliExpress") as MockAli:
        instance = MockAli.return_value
        instance.search_products.return_value = mock_result
        search_and_save(output_file=QUEUE_FILE, max_results=10)

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
