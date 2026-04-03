"""Send product promotions to WhatsApp using the Cloud API."""
import os
import time
import uuid
from typing import Any, Dict, Optional

import requests


WHATSAPP_API_BASE = "https://graph.facebook.com/v18.0"
DEFAULT_DELAY = 30  # seconds between messages


def download_image(
    image_url: str, images_dir: str = "images"
) -> Optional[str]:
    """Download an image from a URL to a local directory.

    Args:
        image_url: URL of the image to download.
        images_dir: Local directory to save images.

    Returns:
        Local file path of the downloaded image, or None on failure.
    """
    os.makedirs(images_dir, exist_ok=True)

    try:
        response = requests.get(image_url, timeout=30)
        if response.status_code != 200:
            print(f"Failed to download image: HTTP {response.status_code}")
            return None

        # Determine extension from content type or URL
        content_type = response.headers.get("Content-Type", "image/jpeg")
        ext = ".jpg"
        if "png" in content_type:
            ext = ".png"
        elif "webp" in content_type:
            ext = ".webp"

        filename = f"{uuid.uuid4().hex}{ext}"
        filepath = os.path.join(images_dir, filename)

        with open(filepath, "wb") as f:
            f.write(response.content)

        return filepath

    except (requests.RequestException, OSError) as e:
        print(f"Error downloading image: {e}")
        return None


def _upload_media(
    filepath: str,
    config: Dict[str, str],
) -> Optional[str]:
    """Upload a local image to WhatsApp Media API.

    Returns:
        The media ID, or None on failure.
    """
    phone_id = config["WHATSAPP_PHONE_NUMBER_ID"]
    token = config["WHATSAPP_ACCESS_TOKEN"]

    url = f"{WHATSAPP_API_BASE}/{phone_id}/media"
    headers = {"Authorization": f"Bearer {token}"}

    # Detect MIME type from file extension
    ext = os.path.splitext(filepath)[1].lower()
    mime_type = {".png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")

    with open(filepath, "rb") as f:
        files = {
            "file": (os.path.basename(filepath), f, mime_type),
        }
        data = {"messaging_product": "whatsapp"}

        response = requests.post(url, headers=headers, files=files, data=data, timeout=30)

    if response.status_code != 200:
        print(f"Media upload failed: {response.status_code} - {response.text}")
        return None

    return response.json().get("id")


def _send_image_message(
    media_id: str,
    caption: str,
    config: Dict[str, str],
) -> bool:
    """Send an image message to a WhatsApp group.

    Returns:
        True if message sent successfully, False otherwise.
    """
    phone_id = config["WHATSAPP_PHONE_NUMBER_ID"]
    token = config["WHATSAPP_ACCESS_TOKEN"]
    group_id = config["WHATSAPP_GROUP_ID"]

    url = f"{WHATSAPP_API_BASE}/{phone_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": group_id,
        "type": "image",
        "image": {
            "id": media_id,
            "caption": caption,
        },
    }

    response = requests.post(url, headers=headers, json=payload, timeout=30)

    if response.status_code != 200:
        print(f"Message send failed: {response.status_code} - {response.text}")
        return False

    return True


def _format_caption(product: Dict[str, Any]) -> str:
    """Format a product into a WhatsApp message caption."""
    title = product.get("title", "Unknown Product")
    price = product.get("price", "N/A")
    rating = product.get("rating", "N/A")
    link = product.get("affiliate_link") or product.get("product_url", "")

    return (
        f"*{title}*\n\n"
        f"Price: ${price}\n"
        f"Rating: {rating}/5\n\n"
        f"Buy here: {link}"
    )


def send_product_to_whatsapp(
    product: Dict[str, Any],
    config: Dict[str, str],
    images_dir: str = "images",
) -> bool:
    """Send a product promotion to WhatsApp.

    Downloads the product image, uploads to WhatsApp, and sends
    an image message with product details.

    Args:
        product: Product dict with title, price, rating, image_url, affiliate_link.
        config: Configuration dict with WhatsApp API credentials.
        images_dir: Directory for downloaded images.

    Returns:
        True if sent successfully, False otherwise.
    """
    # Download product image
    image_path = download_image(product.get("image_url", ""), images_dir)
    if not image_path:
        print("Failed to download product image")
        return False

    try:
        # Upload to WhatsApp
        media_id = _upload_media(image_path, config)
        if not media_id:
            return False

        # Send message
        caption = _format_caption(product)
        return _send_image_message(media_id, caption, config)

    finally:
        # Clean up local image
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except OSError:
                pass
