"""Telegram bot for managing affiliate product queue."""
import json
import logging
from typing import Dict, Any

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from affiliate_links import generate_affiliate_link
from pending_queue import (
    count_by_status,
    get_products_by_status,
    load_queue,
    update_product_field,
    update_product_status,
)
from search_products import search_and_save
from whatsapp_sender import send_product_to_whatsapp

logger = logging.getLogger(__name__)


def _is_authorized(update: Update, config: Dict[str, str]) -> bool:
    """Check if the message is from the authorized chat."""
    chat_id = str(update.effective_chat.id) if update.effective_chat else ""
    return chat_id == config.get("TELEGRAM_CHAT_ID", "")


async def start_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /start command."""
    config = context.bot_data.get("config", {})
    if not _is_authorized(update, config):
        return

    await update.message.reply_text(
        "Welcome to the Affiliate Automation Agent!\n\n"
        "Available commands:\n"
        "/search - Search for wedding products on AliExpress\n"
        "/queue - Review pending products (approve/reject)\n"
        "/status - Show product queue statistics"
    )


async def search_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /search command - trigger product search."""
    config = context.bot_data.get("config", {})
    if not _is_authorized(update, config):
        return

    await update.message.reply_text("Searching for wedding products on AliExpress...")

    try:
        products = search_and_save()
        await update.message.reply_text(
            f"Found {len(products)} products! Use /queue to review them."
        )
    except Exception as e:
        logger.error(f"Search failed: {e}")
        await update.message.reply_text(
            f"Search failed: {e}\nPlease try again later."
        )


async def queue_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /queue command - show pending products one by one."""
    config = context.bot_data.get("config", {})
    if not _is_authorized(update, config):
        return

    pending = get_products_by_status("pending")

    if not pending:
        await update.message.reply_text(
            "No pending products in the queue. Use /search to find new products."
        )
        return

    await update.message.reply_text(
        f"Showing {len(pending)} pending products..."
    )

    for product in pending:
        caption = (
            f"*{_escape_markdown(product['title'])}*\n\n"
            f"Price: ${product['price']}\n"
            f"Rating: {product.get('rating', 'N/A')}/5\n\n"
            f"ID: `{product['id']}`"
        )

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Approve", callback_data=f"approve:{product['id']}"
                    ),
                    InlineKeyboardButton(
                        "Reject", callback_data=f"reject:{product['id']}"
                    ),
                ]
            ]
        )

        image_url = product.get("image_url", "")
        if image_url:
            try:
                await update.message.reply_photo(
                    photo=image_url,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
            except Exception:
                # If photo fails, send as text
                await update.message.reply_text(
                    caption,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
        else:
            await update.message.reply_text(
                caption,
                parse_mode="Markdown",
                reply_markup=keyboard,
            )


async def status_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /status command - show queue statistics."""
    config = context.bot_data.get("config", {})
    if not _is_authorized(update, config):
        return

    counts = count_by_status()

    if not counts:
        await update.message.reply_text(
            "Queue is empty. Use /search to find products."
        )
        return

    lines = ["Product Queue Status:\n"]
    for status, count in sorted(counts.items()):
        emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(status, "📦")
        lines.append(f"{emoji} {status.capitalize()}: {count}")

    total = sum(counts.values())
    lines.append(f"\nTotal: {total}")

    await update.message.reply_text("\n".join(lines))


async def _edit_callback_message(query, text: str) -> None:
    """Edit the callback message, handling both photo and text messages."""
    try:
        await query.edit_message_caption(caption=text)
    except Exception:
        # Message has no caption (was sent as text, not photo)
        await query.edit_message_text(text=text)


async def button_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle inline keyboard button presses (approve/reject)."""
    query = update.callback_query
    config = context.bot_data.get("config", {})

    chat_id = str(query.message.chat.id) if query.message else ""
    if chat_id != config.get("TELEGRAM_CHAT_ID", ""):
        await query.answer("Unauthorized")
        return

    await query.answer()

    data = query.data
    if not data or ":" not in data:
        return

    action, product_id = data.split(":", 1)

    if action == "approve":
        # Update status
        update_product_status(product_id, "approved")

        # Generate affiliate link
        queue = load_queue()
        product = next((p for p in queue if p["id"] == product_id), None)

        if product:
            affiliate_link = generate_affiliate_link(
                product["product_url"], config
            )
            if affiliate_link:
                update_product_field(product_id, "affiliate_link", affiliate_link)
                product["affiliate_link"] = affiliate_link

            # Send to WhatsApp
            try:
                success = send_product_to_whatsapp(product, config)
                if success:
                    text = f"✅ Approved and sent to WhatsApp!\n\n{product['title']}"
                else:
                    text = f"✅ Approved but WhatsApp send failed.\n\n{product['title']}"
            except Exception as e:
                logger.error(f"WhatsApp send error: {e}")
                text = f"✅ Approved but WhatsApp error: {e}\n\n{product['title']}"
        else:
            text = "✅ Approved (product not found in queue)"

        await _edit_callback_message(query, text)

    elif action == "reject":
        update_product_status(product_id, "rejected")
        await _edit_callback_message(query, "❌ Rejected")


def _escape_markdown(text: str) -> str:
    """Escape special characters for Telegram Markdown."""
    for char in ["_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]:
        text = text.replace(char, f"\\{char}")
    return text


def create_bot(config: Dict[str, str]) -> Application:
    """Create and configure the Telegram bot application.

    Args:
        config: Configuration dict with TELEGRAM_BOT_TOKEN and other settings.

    Returns:
        Configured Application instance ready for polling.
    """
    app = Application.builder().token(config["TELEGRAM_BOT_TOKEN"]).build()

    # Store config in bot_data for handlers to access
    app.bot_data["config"] = config

    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("queue", queue_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CallbackQueryHandler(button_callback))

    return app
