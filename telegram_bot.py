"""Telegram bot for managing affiliate product queue."""
import asyncio
import json
import logging
from typing import Dict, Any

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.error import BadRequest
from telegram import ForceReply
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from affiliate_links import generate_affiliate_link
from pending_queue import (
    clear_queue,
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


def _main_menu_keyboard() -> InlineKeyboardMarkup:
    """Build the main menu inline keyboard."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔍 Search", callback_data="menu:search"),
                InlineKeyboardButton("📋 Queue", callback_data="menu:queue"),
            ],
            [
                InlineKeyboardButton("📊 Status", callback_data="menu:status"),
                InlineKeyboardButton("🗑 Clear", callback_data="menu:clear"),
            ],
        ]
    )


async def _send_main_menu(message, text: str = None) -> None:
    """Send (or re-send) the main menu."""
    if text is None:
        text = "What would you like to do?"
    await message.reply_text(text, reply_markup=_main_menu_keyboard())


async def start_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /start command."""
    config = context.bot_data.get("config", {})
    if not _is_authorized(update, config):
        return

    await update.message.reply_text(
        "Welcome to the Affiliate Automation Agent!"
    )
    await _send_main_menu(update.message)


async def search_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /search command - trigger product search.

    Usage: /search <keywords>  — search for specific terms
           /search              — use default wedding keywords
    """
    config = context.bot_data.get("config", {})
    if not _is_authorized(update, config):
        return

    context.user_data.pop("awaiting_search_keywords", None)

    # Parse custom keywords from the message text
    raw_text = update.message.text or ""
    user_input = raw_text.replace("/search", "", 1).strip()

    if user_input:
        keywords = [kw.strip() for kw in user_input.split(",") if kw.strip()]
        await update.message.reply_text(
            f"Searching AliExpress for: {', '.join(keywords)}..."
        )
    else:
        keywords = None  # will use default WEDDING_KEYWORDS
        await update.message.reply_text("Searching for wedding products on AliExpress...")

    try:
        products = await asyncio.to_thread(
            search_and_save, config, keywords=keywords
        )
        await update.message.reply_text(
            f"Found {len(products)} products! Tap Queue to review them."
        )
        await _send_main_menu(update.message)
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
            "No pending products in the queue."
        )
        await _send_main_menu(update.message)
        return

    await update.message.reply_text(
        f"Showing {len(pending)} pending products..."
    )

    for product in pending:
        caption = _format_product_caption(product)

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


async def clear_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle /clear command - remove all products from the queue."""
    config = context.bot_data.get("config", {})
    if not _is_authorized(update, config):
        return

    removed = clear_queue()
    if removed:
        await update.message.reply_text(f"Cleared {removed} products from the queue.")
    else:
        await update.message.reply_text("Queue is already empty.")


async def _edit_callback_message(query, text: str) -> None:
    """Edit the callback message, handling both photo and text messages."""
    if query.message and query.message.caption is not None:
        await query.edit_message_caption(caption=text)
    else:
        await query.edit_message_text(text=text)


async def _handle_menu_search(query, config) -> None:
    """Handle the Search button press — show search sub-menu."""
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔍 Default keywords", callback_data="search:default")],
            [InlineKeyboardButton("✏️ Enter keywords", callback_data="search:custom")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu:back")],
        ]
    )
    await query.edit_message_text("How would you like to search?", reply_markup=keyboard)


async def _run_search(message, config, keywords=None) -> None:
    """Execute a product search and send results."""
    try:
        products = await asyncio.to_thread(
            search_and_save, config, keywords=keywords
        )
        await message.reply_text(
            f"Found {len(products)} products! Tap Queue to review them."
        )
    except Exception as e:
        logger.error(f"Search failed: {e}")
        await message.reply_text(f"Search failed: {e}\nPlease try again.")
    await _send_main_menu(message)


async def _handle_menu_queue(query) -> None:
    """Handle the Queue button press from the main menu."""
    pending = get_products_by_status("pending")
    if not pending:
        await query.edit_message_text("No pending products. Search first!")
        await _send_main_menu(query.message)
        return

    await query.edit_message_text(f"Showing {len(pending)} pending products...")

    for product in pending:
        caption = _format_product_caption(product)
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
                await query.message.reply_photo(
                    photo=image_url,
                    caption=caption,
                    parse_mode="Markdown",
                    reply_markup=keyboard,
                )
            except Exception:
                await query.message.reply_text(
                    caption, parse_mode="Markdown", reply_markup=keyboard
                )
        else:
            await query.message.reply_text(
                caption, parse_mode="Markdown", reply_markup=keyboard
            )

    await _send_main_menu(query.message)


async def _handle_menu_status(query) -> None:
    """Handle the Status button press from the main menu."""
    counts = count_by_status()
    if not counts:
        await query.edit_message_text("Queue is empty.")
        await _send_main_menu(query.message)
        return

    lines = ["Product Queue Status:\n"]
    for status, count in sorted(counts.items()):
        emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(status, "📦")
        lines.append(f"{emoji} {status.capitalize()}: {count}")
    total = sum(counts.values())
    lines.append(f"\nTotal: {total}")

    await query.edit_message_text("\n".join(lines))
    await _send_main_menu(query.message)


async def _handle_menu_clear(query) -> None:
    """Ask for confirmation before clearing the queue."""
    keyboard = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("✅ Confirm", callback_data="clear:confirm"),
            InlineKeyboardButton("⬅️ Cancel", callback_data="menu:back"),
        ]]
    )
    await query.edit_message_text("Clear the entire queue?", reply_markup=keyboard)


async def button_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle inline keyboard button presses (menu, approve/reject)."""
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

    action, value = data.split(":", 1)

    # Clear stale search-keyword flag unless we're setting it right now
    if not (action == "search" and value == "custom"):
        context.user_data.pop("awaiting_search_keywords", None)

    # Handle main menu buttons
    if action == "menu":
        if value == "search":
            await _handle_menu_search(query, config)
        elif value == "queue":
            await _handle_menu_queue(query)
        elif value == "status":
            await _handle_menu_status(query)
        elif value == "clear":
            await _handle_menu_clear(query)
        elif value == "back":
            await query.edit_message_text(
                "What would you like to do?", reply_markup=_main_menu_keyboard()
            )
        return

    # Handle search sub-menu buttons
    if action == "search":
        if value == "default":
            await query.edit_message_text("Searching for wedding products on AliExpress...")
            await _run_search(query.message, config)
        elif value == "custom":
            context.user_data["awaiting_search_keywords"] = True
            await query.edit_message_text("✏️ Custom search")
            await query.message.reply_text(
                "Enter your search keywords (comma-separated):",
                reply_markup=ForceReply(selective=False),
            )
        return

    # Handle clear confirmation
    if action == "clear" and value == "confirm":
        removed = clear_queue()
        if removed:
            await query.edit_message_text(f"Cleared {removed} products from the queue.")
        else:
            await query.edit_message_text("Queue is already empty.")
        await _send_main_menu(query.message)
        return

    product_id = value

    if action == "approve":
        # Load product first, attempt downstream work before persisting status
        queue = load_queue()
        product = next((p for p in queue if p["id"] == product_id), None)

        if product:
            # Generate affiliate link (blocking, run in thread)
            affiliate_link = await asyncio.to_thread(
                generate_affiliate_link, product["product_url"], config
            )
            if affiliate_link:
                product["affiliate_link"] = affiliate_link

            # Send to WhatsApp (blocking, run in thread)
            try:
                success = await asyncio.to_thread(
                    send_product_to_whatsapp, product, config
                )
                if success:
                    # Only persist approved status after successful send
                    update_product_status(product_id, "approved")
                    if affiliate_link:
                        update_product_field(product_id, "affiliate_link", affiliate_link)
                    text = f"✅ Approved and sent to WhatsApp!\n\n{product['title']}"
                else:
                    text = f"⚠️ WhatsApp send failed. Product remains pending.\n\n{product['title']}"
            except Exception as e:
                logger.error(f"WhatsApp send error: {e}")
                text = f"⚠️ WhatsApp error: {e}. Product remains pending.\n\n{product['title']}"
        else:
            text = "⚠️ Product not found in queue"

        await _edit_callback_message(query, text)

    elif action == "reject":
        update_product_status(product_id, "rejected")
        await _edit_callback_message(query, "❌ Rejected")


async def text_message_handler(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle plain text messages (e.g. search keyword input)."""
    config = context.bot_data.get("config", {})
    if not _is_authorized(update, config):
        return

    if context.user_data.get("awaiting_search_keywords"):
        context.user_data["awaiting_search_keywords"] = False
        raw = update.message.text or ""
        keywords = [kw.strip() for kw in raw.split(",") if kw.strip()]
        if not keywords:
            await update.message.reply_text("No keywords provided.")
            await _send_main_menu(update.message)
            return
        await update.message.reply_text(
            f"Searching AliExpress for: {', '.join(keywords)}..."
        )
        await _run_search(update.message, config, keywords=keywords)
        return

    # Unknown text — show menu
    await _send_main_menu(update.message, "I didn't understand that. Use the menu:")


def _format_product_caption(product: Dict[str, Any]) -> str:
    """Build a Markdown caption with product details."""
    lines = [
        f"*{_escape_markdown(product['title'])}*\n",
        f"Price: ${product['price']}",
        f"Rating: {product.get('rating', 'N/A')}/5",
    ]
    if product.get("orders"):
        lines.append(f"Orders: {product['orders']:,}")
    if product.get("commission_rate") is not None:
        lines.append(f"Commission: {product['commission_rate']}%")
    lines.append(f"\nID: `{product['id']}`")
    return "\n".join(lines)


def _escape_markdown(text: str) -> str:
    """Escape special characters for Telegram Markdown."""
    for char in ["_", "*", "[", "`"]:
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
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))

    return app
