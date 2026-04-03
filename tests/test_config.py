"""Tests for config module."""
import os
import pytest


def test_load_config_returns_all_required_keys(monkeypatch):
    """Config loads all required environment variables."""
    env_vars = {
        "ALI_APP_KEY": "test_app_key",
        "ALI_SECRET": "test_secret",
        "ALI_TRACKING_ID": "test_tracking",
        "TELEGRAM_BOT_TOKEN": "test_bot_token",
        "TELEGRAM_CHAT_ID": "12345",
        "WHATSAPP_PHONE_NUMBER_ID": "test_phone",
        "WHATSAPP_ACCESS_TOKEN": "test_access",
        "WHATSAPP_GROUP_ID": "test_group",
    }
    for key, val in env_vars.items():
        monkeypatch.setenv(key, val)

    from config import load_config
    cfg = load_config()

    for key, val in env_vars.items():
        assert cfg[key] == val


def test_load_config_raises_on_missing_required_var(monkeypatch):
    """Config raises ValueError when a required var is missing."""
    # Set all but one
    env_vars = {
        "ALI_APP_KEY": "test_app_key",
        "ALI_SECRET": "test_secret",
        "ALI_TRACKING_ID": "test_tracking",
        "TELEGRAM_BOT_TOKEN": "test_bot_token",
        "TELEGRAM_CHAT_ID": "12345",
        "WHATSAPP_PHONE_NUMBER_ID": "test_phone",
        "WHATSAPP_ACCESS_TOKEN": "test_access",
        # Missing WHATSAPP_GROUP_ID
    }
    for key, val in env_vars.items():
        monkeypatch.setenv(key, val)
    monkeypatch.delenv("WHATSAPP_GROUP_ID", raising=False)

    from config import load_config
    with pytest.raises(ValueError, match="WHATSAPP_GROUP_ID"):
        load_config()
