"""Entry point for the Affiliate Automation Agent."""
import logging

from config import load_config
from telegram_bot import create_bot


def main() -> None:
    """Load configuration and start the Telegram bot."""
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    logger = logging.getLogger(__name__)

    try:
        config = load_config()
        logger.info("Configuration loaded successfully")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return

    bot = create_bot(config)
    logger.info("Starting Telegram bot...")
    bot.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
