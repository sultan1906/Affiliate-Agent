"""Tests for affiliate_links module."""
import pytest
from unittest.mock import patch, MagicMock


def test_generate_affiliate_link_returns_link():
    """generate_affiliate_link returns an affiliate URL on success."""
    from affiliate_links import generate_affiliate_link

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "aliexpress_affiliate_link_generate_response": {
            "resp_result": {
                "result": {
                    "promotion_links": {
                        "promotion_link": [
                            {"promotion_link": "https://s.click.aliexpress.com/e/abc123"}
                        ]
                    }
                },
                "resp_code": 200,
            }
        }
    }

    config = {
        "ALI_APP_KEY": "test_key",
        "ALI_SECRET": "test_secret",
        "ALI_TRACKING_ID": "test_tracking",
    }

    with patch("affiliate_links.requests.get", return_value=mock_response):
        link = generate_affiliate_link(
            "https://www.aliexpress.com/item/123.html",
            config,
        )

    assert link == "https://s.click.aliexpress.com/e/abc123"


def test_generate_affiliate_link_returns_none_on_failure():
    """generate_affiliate_link returns None when API fails."""
    from affiliate_links import generate_affiliate_link

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.json.return_value = {}

    config = {
        "ALI_APP_KEY": "test_key",
        "ALI_SECRET": "test_secret",
        "ALI_TRACKING_ID": "test_tracking",
    }

    with patch("affiliate_links.requests.get", return_value=mock_response):
        link = generate_affiliate_link(
            "https://www.aliexpress.com/item/123.html",
            config,
        )

    assert link is None
