"""Search AliExpress for wedding-related products and save to queue."""
import hashlib
import hmac
import time
import uuid
from typing import Any, Dict, List, Optional, Set

import requests

from pending_queue import merge_new_products


API_URL = "https://api-sg.aliexpress.com/sync"

WEDDING_KEYWORDS = [
    "bridal hair clips",
    "wedding favors",
    "wedding decorations",
    "bridal accessories",
    "wedding centerpieces",
]

# Default sorting: highest commission first. Alternative: SALES_NEXT_7_DAYS_DESC
DEFAULT_SORT = "COMMISSION_RATE_DESC"

# Post-processing quality thresholds
MIN_ORDERS = 100
MIN_RATING = 4.5

# Default shipping region
DEFAULT_SHIP_TO = "IL"

# Wedding category IDs — anchors all searches to prevent keyword bleed
WEDDING_CATEGORY_IDS = "320"  # Weddings & Events (top-level)


def _sign_params(params: Dict[str, str], secret: str) -> str:
    """Generate HMAC-MD5 signature for AliExpress global API."""
    sorted_params = sorted(params.items())
    concatenated = "".join(f"{k}{v}" for k, v in sorted_params)
    return hmac.new(
        secret.encode("utf-8"),
        concatenated.encode("utf-8"),
        hashlib.md5,
    ).hexdigest().upper()


def _passes_quality_filter(product: Dict[str, Any]) -> bool:
    """Return True if the product meets minimum social-proof thresholds."""
    try:
        volume = int(str(product.get("lastest_volume", "0")).replace(",", ""))
    except (ValueError, TypeError):
        volume = 0
    if volume < MIN_ORDERS:
        return False

    # Check rating
    try:
        rating = float(str(product.get("evaluate_rate", "0")))
    except (ValueError, TypeError):
        rating = 0.0
    if rating < MIN_RATING:
        return False

    return True


def _search_aliexpress(
    keyword: str,
    config: Dict[str, str],
    category_ids: Optional[str] = None,
    ship_to_country: Optional[str] = None,
    sort: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search AliExpress using the hotproduct query API (Incentive inventory)."""
    params = {
        "app_key": config["ALI_APP_KEY"],
        "method": "aliexpress.affiliate.hotproduct.query",
        "sign_method": "hmac",
        "timestamp": str(int(time.time() * 1000)),
        "v": "2.0",
        "format": "json",
        "keywords": keyword,
        "tracking_id": config["ALI_TRACKING_ID"],
        "target_currency": "USD",
        "target_language": "EN",
        "page_no": "1",
        "page_size": "50",
        "sort": sort or DEFAULT_SORT,
        "ship_to_country": ship_to_country or DEFAULT_SHIP_TO,
    }

    if category_ids:
        params["category_ids"] = category_ids

    params["sign"] = _sign_params(params, config["ALI_SECRET"])

    try:
        response = requests.get(API_URL, params=params, timeout=15)
        if response.status_code != 200:
            print(f"AliExpress API returned status {response.status_code} for '{keyword}'")
            return []

        data = response.json()
        resp_result = (
            data.get("aliexpress_affiliate_hotproduct_query_response", {})
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
    category_ids: Optional[str] = None,
    ship_to_country: Optional[str] = None,
    sort: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Search AliExpress for products and save top results to queue.

    Uses the hotproduct endpoint (Incentive inventory) with commission-based
    sorting and post-processing quality filters.

    Args:
        config: Configuration dict with ALI_APP_KEY, ALI_SECRET, ALI_TRACKING_ID.
        output_file: Path to the JSON queue file.
        keywords: Search keywords (defaults to WEDDING_KEYWORDS).
        max_results: Maximum number of products to save.
        category_ids: Comma-separated AliExpress category IDs for anchoring.
        ship_to_country: Two-letter country code (default: IL).
        sort: Sort order (default: COMMISSION_RATE_DESC).

    Returns:
        List of product dicts saved to the queue.
    """
    if keywords is None:
        keywords = WEDDING_KEYWORDS
    if category_ids is None:
        category_ids = WEDDING_CATEGORY_IDS

    all_products: List[Dict[str, Any]] = []

    print(f"Starting AliExpress search with {len(keywords)} keywords: {keywords}")
    for keyword in keywords:
        print(f"Searching AliExpress for: '{keyword}'")
        products = _search_aliexpress(
            keyword, config,
            category_ids=category_ids,
            ship_to_country=ship_to_country,
            sort=sort,
        )
        print(f"  Found {len(products)} products for '{keyword}'")
        all_products.extend(products)

    # Deduplicate by product id
    seen_ids: Set[str] = set()
    unique_products: List[Dict[str, Any]] = []
    for p in all_products:
        pid = str(p.get("product_id", ""))
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            unique_products.append(p)

    # Apply social-proof quality filter
    before_filter = len(unique_products)
    filtered_products = [p for p in unique_products if _passes_quality_filter(p)]
    print(f"Quality filter: {before_filter} -> {len(filtered_products)} products "
          f"(min {MIN_ORDERS} orders, min {MIN_RATING} rating)")

    # Take top results
    top_products = filtered_products[:max_results]

    # Format for queue
    queue_items: List[Dict[str, Any]] = []
    for p in top_products:
        sale_price_raw = p.get("target_sale_price", p.get("target_original_price", "0"))
        try:
            sale_price = float(str(sale_price_raw).replace(",", ""))
        except (ValueError, TypeError):
            sale_price = 0.0

        try:
            commission_rate = p.get("commission_rate", "")
            commission_str = str(commission_rate).rstrip("%")
            commission = float(commission_str) if commission_str else None
        except (ValueError, TypeError):
            commission = None

        try:
            order_count = int(str(p.get("lastest_volume", "0")).replace(",", ""))
        except (ValueError, TypeError):
            order_count = 0

        item = {
            "id": str(uuid.uuid4()),
            "product_id": str(p.get("product_id", "")),
            "title": p.get("product_title", "Unknown Product"),
            "price": sale_price,
            "rating": p.get("evaluate_rate", None),
            "orders": order_count,
            "commission_rate": commission,
            "image_url": p.get("product_main_image_url", ""),
            "product_url": p.get("product_detail_url", ""),
            "status": "pending",
            "affiliate_link": p.get("promotion_link", None),
        }
        queue_items.append(item)

    # Atomically merge with existing queue — dedup handled under lock
    new_items = merge_new_products(queue_items, output_file)
    print(f"Added {len(new_items)} new products to {output_file}")
    return new_items
