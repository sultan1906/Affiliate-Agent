"""Tests for whatsapp_sender module."""
import os
import pytest
from unittest.mock import patch, MagicMock


def test_download_image_saves_file(tmp_path):
    """download_image saves an image to the specified directory."""
    from whatsapp_sender import download_image

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b"fake_image_data"
    mock_response.headers = {"Content-Type": "image/jpeg"}

    with patch("whatsapp_sender.requests.get", return_value=mock_response):
        path = download_image("http://img.com/test.jpg", str(tmp_path))

    assert os.path.exists(path)
    with open(path, "rb") as f:
        assert f.read() == b"fake_image_data"


def test_send_product_to_whatsapp_calls_api():
    """send_product_to_whatsapp uploads image and sends message."""
    from whatsapp_sender import send_product_to_whatsapp

    product = {
        "title": "Wedding Decor",
        "price": 9.99,
        "rating": 4.8,
        "image_url": "http://img.com/decor.jpg",
        "affiliate_link": "https://s.click.aliexpress.com/e/abc",
    }
    config = {
        "WHATSAPP_PHONE_NUMBER_ID": "phone123",
        "WHATSAPP_ACCESS_TOKEN": "token456",
        "WHATSAPP_GROUP_ID": "group789",
    }

    # Mock image download
    mock_download_response = MagicMock()
    mock_download_response.status_code = 200
    mock_download_response.content = b"fake_image"
    mock_download_response.headers = {"Content-Type": "image/jpeg"}

    # Mock media upload
    mock_upload_response = MagicMock()
    mock_upload_response.status_code = 200
    mock_upload_response.json.return_value = {"id": "media_id_123"}

    # Mock message send
    mock_send_response = MagicMock()
    mock_send_response.status_code = 200
    mock_send_response.json.return_value = {"messages": [{"id": "msg_1"}]}

    with patch("whatsapp_sender.requests.get", return_value=mock_download_response):
        with patch("whatsapp_sender.requests.post") as mock_post:
            mock_post.side_effect = [mock_upload_response, mock_send_response]
            result = send_product_to_whatsapp(product, config)

    assert result is True
    assert mock_post.call_count == 2
