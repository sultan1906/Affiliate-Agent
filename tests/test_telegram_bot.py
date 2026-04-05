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

    # Should have 7 handlers (5 commands + 1 callback + 1 message handler)
    assert len(app.handlers[0]) == 7
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

    # First call is welcome message, second is the menu
    assert update.message.reply_text.call_count == 2
    welcome_text = update.message.reply_text.call_args_list[0][0][0]
    assert "Welcome" in welcome_text
    # Second call should have reply_markup (inline keyboard menu)
    menu_kwargs = update.message.reply_text.call_args_list[1][1]
    assert "reply_markup" in menu_kwargs


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

    # First call is status text, second is menu (via _send_main_menu which
    # is called inside status_command — but status_command itself only calls
    # reply_text once since it doesn't show menu).
    call_text = update.message.reply_text.call_args_list[0][0][0]
    assert "Pending: 3" in call_text
    assert "Approved: 1" in call_text
