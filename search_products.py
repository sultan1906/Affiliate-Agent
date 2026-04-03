"""Search AliExpress for wedding-related products and save to queue."""
import uuid
from typing import Any, Dict, List, Optional

from aliexpress_api import AliExpress

from pending_queue import save_queue, load_queue


WEDDING_KEYWORDS = [
    "bridal hair clips",
    "wedding favors",
    "wedding decorations",
    "bridal accessories",
    "wedding centerpieces",
]


def search_and_save(
    output_file: str = "pending_queue.json",
    keywords: Optional[List[str]] = None,
    max_results: int = 10,
) -> List[Dict[str, Any]]:
    """Search AliExpress for products and save top results to queue.

    Args:
        output_file: Path to the JSON queue file.
        keywords: Search keywords (defaults to WEDDING_KEYWORDS).
        max_results: Maximum number of products to save.

    Returns:
        List of product dicts saved to the queue.
    """
    if keywords is None:
        keywords = WEDDING_KEYWORDS

    ali = AliExpress()
    all_products: List[Dict[str, Any]] = []

    for keyword in keywords:
        try:
            result = ali.search_products(keyword)
            products = result.get("products", [])
            all_products.extend(products)
        except Exception as e:
            print(f"Error searching for '{keyword}': {e}")
            continue

    # Deduplicate by product id
    seen_ids: set[str] = set()
    unique_products: List[Dict[str, Any]] = []
    for p in all_products:
        pid = str(p.get("id", ""))
        if pid not in seen_ids:
            seen_ids.add(pid)
            unique_products.append(p)

    # Take top results
    top_products = unique_products[:max_results]

    # Format for queue
    queue_items: List[Dict[str, Any]] = []
    for p in top_products:
        item = {
            "id": str(uuid.uuid4()),
            "product_id": str(p.get("id", "")),
            "title": p.get("title", "Unknown Product"),
            "price": p.get("min_price", 0.0),
            "rating": p.get("rating", 0.0),
            "image_url": p.get("thumbnail", ""),
            "product_url": p.get("url", ""),
            "status": "pending",
            "affiliate_link": None,
        }
        queue_items.append(item)

    # Merge with existing queue — preserve approved/rejected items
    existing = load_queue(output_file)
    existing_product_ids = {p["product_id"] for p in existing}
    new_items = [item for item in queue_items if item["product_id"] not in existing_product_ids]
    merged = existing + new_items

    save_queue(merged, output_file)
    print(f"Added {len(new_items)} new products to {output_file} ({len(merged)} total)")
    return new_items
