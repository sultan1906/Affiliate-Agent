"""Tests for pending_queue helper functions."""
import json
import os
import pytest


QUEUE_FILE = "/tmp/test_pq.json"


@pytest.fixture(autouse=True)
def cleanup():
    if os.path.exists(QUEUE_FILE):
        os.remove(QUEUE_FILE)
    yield
    if os.path.exists(QUEUE_FILE):
        os.remove(QUEUE_FILE)


def _sample_products():
    return [
        {
            "id": "1",
            "product_id": "ali1",
            "title": "Test Product",
            "price": 5.0,
            "rating": 4.5,
            "image_url": "http://img.com/1.jpg",
            "product_url": "https://aliexpress.com/item/ali1.html",
            "status": "pending",
            "affiliate_link": None,
        }
    ]


def test_load_queue_returns_empty_list_when_no_file():
    """load_queue returns empty list if file doesn't exist."""
    from pending_queue import load_queue
    result = load_queue(QUEUE_FILE)
    assert result == []


def test_save_and_load_queue_roundtrip():
    """save_queue + load_queue preserves data."""
    from pending_queue import load_queue, save_queue
    products = _sample_products()
    save_queue(products, QUEUE_FILE)
    loaded = load_queue(QUEUE_FILE)
    assert loaded == products


def test_update_product_status():
    """update_product_status changes status of a specific product."""
    from pending_queue import load_queue, save_queue, update_product_status
    products = _sample_products()
    save_queue(products, QUEUE_FILE)
    update_product_status("1", "approved", QUEUE_FILE)
    loaded = load_queue(QUEUE_FILE)
    assert loaded[0]["status"] == "approved"


def test_update_product_affiliate_link():
    """update_product_field sets a field on a specific product."""
    from pending_queue import load_queue, save_queue, update_product_field
    products = _sample_products()
    save_queue(products, QUEUE_FILE)
    update_product_field("1", "affiliate_link", "https://aff.link/123", QUEUE_FILE)
    loaded = load_queue(QUEUE_FILE)
    assert loaded[0]["affiliate_link"] == "https://aff.link/123"
