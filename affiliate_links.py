"""Generate AliExpress affiliate promotion links."""
import hashlib
import hmac
import time
from typing import Any, Dict, Optional

import requests


API_URL = "https://eco.taobao.com/router/rest"


def _sign_params(params: Dict[str, str], secret: str) -> str:
    """Generate HMAC-MD5 signature for AliExpress TOP API."""
    sorted_params = sorted(params.items())
    concatenated = "".join(f"{k}{v}" for k, v in sorted_params)
    sign_str = secret + concatenated + secret
    return hmac.new(
        secret.encode("utf-8"),
        sign_str.encode("utf-8"),
        hashlib.md5,
    ).hexdigest().upper()


def generate_affiliate_link(
    product_url: str,
    config: Dict[str, str],
) -> Optional[str]:
    """Generate an affiliate promotion link for a product URL.

    Uses the AliExpress affiliate API (TOP protocol) to convert a
    regular product URL into an affiliate tracking link.

    Args:
        product_url: The original AliExpress product URL.
        config: Configuration dict with ALI_APP_KEY, ALI_SECRET, ALI_TRACKING_ID.

    Returns:
        The affiliate link string, or None if generation failed.
    """
    try:
        params = {
            "app_key": config["ALI_APP_KEY"],
            "method": "aliexpress.affiliate.link.generate",
            "sign_method": "hmac-md5",
            "timestamp": str(int(time.time() * 1000)),
            "v": "2.0",
            "format": "json",
            "promotion_link_type": "0",
            "source_values": product_url,
            "tracking_id": config["ALI_TRACKING_ID"],
        }

        params["sign"] = _sign_params(params, config["ALI_SECRET"])

        response = requests.get(API_URL, params=params, timeout=10)

        if response.status_code != 200:
            print(f"Affiliate API returned status {response.status_code}")
            return None

        data = response.json()
        resp_result = (
            data.get("aliexpress_affiliate_link_generate_response", {})
            .get("resp_result", {})
        )

        if resp_result.get("resp_code") != 200:
            print(f"Affiliate API error: {resp_result}")
            return None

        links = (
            resp_result.get("result", {})
            .get("promotion_links", {})
            .get("promotion_link", [])
        )

        if links:
            return links[0].get("promotion_link")

        return None

    except Exception as e:
        print(f"Error generating affiliate link: {e}")
        return None
