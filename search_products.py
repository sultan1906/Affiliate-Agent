"""Search AliExpress for wedding-related products and save to queue."""
import hashlib
import hmac
import time
import uuid
from typing import Any, Dict, List, Optional, Set

import requests

from pending_queue import save_queue, load_queue


API_URL = "https://api-sg.aliexpress.com/sync"

WEDDING_KEYWORDS = [
    "bridal hair clips",
    "wedding favors",
    "wedding decorations",
    "bridal accessories",
    "wedding centerpieces",
]


def _sign_params(params: Dict[str, str], secret: str) -> str:
    """Generate HMAC-MD5 signature for AliExpress global API."""
    sorted_params = sorted(params.items())
    concatenated = "".join(f"{k}{v}" for k, v in sorted_params)
    return hmac.new(
        secret.encode("utf-8"),
        concatenated.encode("utf-8"),
        hashlib.md5,
    ).hexdigest().upper()


def _search_aliexpress(keyword: str, config: Dict[str, str]) -> List[Dict[str, Any]]:
    """Search AliExpress using the official affiliate product query API."""
    params = {
        "app_key": config["ALI_APP_KEY"],
        "method": "aliexpress.affiliate.product.query",
        "sign_method": "hmac",
        "timestamp": str(int(time.time() * 1000)),
        "v": "2.0",
        "format": "json",
        "keywords": keyword,
        "tracking_id": config["ALI_TRACKING_ID"],
        "target_currency": "USD",
        "target_language": "EN",
        "page_no": "1",
        "page_size": "10",
    }

    params["sign"] = _sign_params(params, config["ALI_SECRET"])

    try:
        response = requests.get(API_URL, params=params, timeout=15)
        if response.status_code != 200:
            print(f"AliExpress API returned status {response.status_code} for '{keyword}'")
            return []

        data = response.json()
        resp_result = (
            data.get("aliexpress_affiliate_product_query_response", {})
            .get("resp_result", {})
        )

        if resp_result.get("resp_code") != 200:
            print(f"AliExpress API error for '{keyword}': {resp_result}")
            return []

        products = (
            resp_result.get("result", {})
            .get("products", {})
            .get("product", [])
        )
        return products

    except Exception as e:
        print(f"Error searching for '{keyword}': {e}")
        return []


def search_and_save(
    config: Dict[str, str],
    output_file: str = "pending_queue.json",
    keywords: Optional[List[str]] = None,
    max_results: int = 10,
) -> List[Dict[str, Any]]:
    """Search AliExpress for products and save top results to queue.

    Args:
        config: Configuration dict with ALI_APP_KEY, ALI_SECRET, ALI_TRACKING_ID.
        output_file: Path to the JSON queue file.
        keywords: Search keywords (defaults to WEDDING_KEYWORDS).
        max_results: Maximum number of products to save.

    Returns:
        List of product dicts saved to the queue.
    """
    if keywords is None:
        keywords = WEDDING_KEYWORDS

    all_products: List[Dict[str, Any]] = []

    for keyword in keywords:
        products = _search_aliexpress(keyword, config)
        all_products.extend(products)

    # Deduplicate by product id
    seen_ids: Set[str] = set()
    unique_products: List[Dict[str, Any]] = []
    for p in all_products:
        pid = str(p.get("product_id", ""))
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            unique_products.append(p)

    # Take top results
    top_products = unique_products[:max_results]

    # Format for queue
    queue_items: List[Dict[str, Any]] = []
    for p in top_products:
        sale_price = p.get("target_sale_price", p.get("target_original_price", "0"))
        item = {
            "id": str(uuid.uuid4()),
            "product_id": str(p.get("product_id", "")),
            "title": p.get("product_title", "Unknown Product"),
            "price": float(str(sale_price).replace(",", "")),
            "rating": p.get("evaluate_rate", None),
            "image_url": p.get("product_main_image_url", ""),
            "product_url": p.get("product_detail_url", ""),
            "status": "pending",
            "affiliate_link": p.get("promotion_link", None),
        }
        queue_items.append(item)

    # Merge with existing queue — preserve approved/rejected items
    existing = load_queue(output_file)
    existing_product_ids = {p.get("product_id", "") for p in existing}
    new_items = [item for item in queue_items if item["product_id"] not in existing_product_ids]
    merged = existing + new_items

    save_queue(merged, output_file)
    print(f"Added {len(new_items)} new products to {output_file} ({len(merged)} total)")
    return new_items
