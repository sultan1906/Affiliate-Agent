"""Safe JSON read/write for the pending product queue."""
import json
import os
import fcntl
from typing import Any, Dict, List, Optional


DEFAULT_QUEUE_FILE = "pending_queue.json"


def load_queue(filepath: str = DEFAULT_QUEUE_FILE) -> List[Dict[str, Any]]:
    """Load the product queue from a JSON file.

    Returns an empty list if the file does not exist.
    """
    if not os.path.exists(filepath):
        return []

    with open(filepath, "r") as f:
        fcntl.flock(f, fcntl.LOCK_SH)
        try:
            data = json.load(f)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)

    return data


def save_queue(products: List[Dict[str, Any]], filepath: str = DEFAULT_QUEUE_FILE) -> None:
    """Save the product queue to a JSON file with file locking."""
    with open(filepath, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            f.seek(0)
            f.truncate()
            json.dump(products, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _atomic_update(filepath: str, updater) -> None:
    """Load, mutate, and save queue under a single exclusive lock."""
    # Ensure file exists
    if not os.path.exists(filepath):
        with open(filepath, "w") as f:
            json.dump([], f)

    with open(filepath, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            data = json.load(f)
            updater(data)
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def update_product_status(
    product_id: str, status: str, filepath: str = DEFAULT_QUEUE_FILE
) -> None:
    """Update the status of a product by its id."""
    def _update(products):
        for product in products:
            if product["id"] == product_id:
                product["status"] = status
                break

    _atomic_update(filepath, _update)


def update_product_field(
    product_id: str, field: str, value: Any, filepath: str = DEFAULT_QUEUE_FILE
) -> None:
    """Update an arbitrary field on a product by its id."""
    def _update(products):
        for product in products:
            if product["id"] == product_id:
                product[field] = value
                break

    _atomic_update(filepath, _update)


def get_products_by_status(
    status: str, filepath: str = DEFAULT_QUEUE_FILE
) -> List[Dict[str, Any]]:
    """Return all products with the given status."""
    products = load_queue(filepath)
    return [p for p in products if p.get("status") == status]


def count_by_status(filepath: str = DEFAULT_QUEUE_FILE) -> Dict[str, int]:
    """Return counts of products grouped by status."""
    products = load_queue(filepath)
    counts: Dict[str, int] = {}
    for p in products:
        s = p.get("status", "unknown")
        counts[s] = counts.get(s, 0) + 1
    return counts
