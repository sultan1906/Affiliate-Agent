"""Configuration loader for the Affiliate Automation Agent."""
import os
from typing import Dict

from dotenv import load_dotenv


REQUIRED_VARS = [
    "ALI_APP_KEY",
    "ALI_SECRET",
    "ALI_TRACKING_ID",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
]

OPTIONAL_VARS = [
    "WHATSAPP_PHONE_NUMBER_ID",
    "WHATSAPP_ACCESS_TOKEN",
    "WHATSAPP_GROUP_ID",
]


def load_config() -> Dict[str, str]:
    """Load and validate all required environment variables.

    Returns:
        Dictionary of configuration key-value pairs.

    Raises:
        ValueError: If any required environment variable is not set.
    """
    load_dotenv()

    config: Dict[str, str] = {}
    missing: list[str] = []

    for var in REQUIRED_VARS:
        value = os.environ.get(var)
        if not value:
            missing.append(var)
        else:
            config[var] = value

    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    for var in OPTIONAL_VARS:
        value = os.environ.get(var)
        if value:
            config[var] = value

    return config
