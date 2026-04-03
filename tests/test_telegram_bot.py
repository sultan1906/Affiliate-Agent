"""Tests for telegram_bot module."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_create_bot_registers_handlers():
    """create_bot returns an Application with all handlers registered."""
    from telegram_bot import create_bot

    config = {
        "TELEGRAM_BOT_TOKEN": "fake:token",
        "TELEGRAM_CHAT_ID": "12345",
        "ALI_APP_KEY": "key",
        "ALI_SECRET": "secret",
        "ALI_TRACKING_ID": "tracking",
        "WHATSAPP_PHONE_NUMBER_ID": "phone",
        "WHATSAPP_ACCESS_TOKEN": "token",
        "WHATSAPP_GROUP_ID": "group",
    }

    app = create_bot(config)

    # Should have 5 handlers (4 commands + 1 callback)
    assert len(app.handlers[0]) == 5
    assert app.bot_data["config"] == config


def test_is_authorized_checks_chat_id():
    """_is_authorized returns True only for configured chat ID."""
    from telegram_bot import _is_authorized

    config = {"TELEGRAM_CHAT_ID": "12345"}

    # Authorized
    update = MagicMock()
    update.effective_chat.id = 12345
    assert _is_authorized(update, config) is True

    # Unauthorized
    update.effective_chat.id = 99999
    assert _is_authorized(update, config) is False


@pytest.mark.asyncio
async def test_start_command_sends_welcome():
    """start_command sends a welcome message to authorized users."""
    from telegram_bot import start_command

    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.bot_data = {"config": {"TELEGRAM_CHAT_ID": "12345"}}

    await start_command(update, context)

    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    assert "Welcome" in call_text


@pytest.mark.asyncio
async def test_status_command_shows_counts():
    """status_command displays product counts."""
    from telegram_bot import status_command

    update = MagicMock()
    update.effective_chat.id = 12345
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.bot_data = {"config": {"TELEGRAM_CHAT_ID": "12345"}}

    with patch("telegram_bot.count_by_status", return_value={"pending": 3, "approved": 1}):
        await status_command(update, context)

    update.message.reply_text.assert_called_once()
    call_text = update.message.reply_text.call_args[0][0]
    assert "Pending: 3" in call_text
    assert "Approved: 1" in call_text
