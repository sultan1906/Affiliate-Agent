# Affiliate Automation Agent

A Telegram bot that searches AliExpress for wedding-related products, lets you review and approve them, and automatically sends approved products to a WhatsApp group with affiliate links.

## Setup

### 1. Install dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.template .env
```

Fill in your `.env` file with the required API keys:

### 3. Get API keys

**AliExpress Affiliate:**
- Sign up at [AliExpress Affiliate Program](https://portals.aliexpress.com/)
- Create an app to get your App Key and Secret
- Get your Tracking ID from the affiliate dashboard

**Telegram Bot:**
- Message [@BotFather](https://t.me/BotFather) on Telegram
- Create a new bot with `/newbot`
- Copy the bot token
- Get your Chat ID by messaging [@userinfobot](https://t.me/userinfobot)

**WhatsApp Cloud API:**
- Set up a [Meta Developer Account](https://developers.facebook.com/)
- Create a WhatsApp Business app
- Get your Phone Number ID and Access Token from the API Setup page
- Get the Group ID from your WhatsApp group settings

### 4. Run the bot

```bash
python main.py
```

## Usage

Open your Telegram bot and use these commands:

- `/start` - Show welcome message and available commands
- `/search` - Search AliExpress for wedding products (saves to queue)
- `/queue` - Review pending products one by one with Approve/Reject buttons
- `/status` - Show counts of pending, approved, and rejected products

### Workflow

1. Use `/search` to find products
2. Use `/queue` to review each product
3. Tap **Approve** to generate an affiliate link and send to WhatsApp
4. Tap **Reject** to skip the product
5. Use `/status` to check progress

## Project Structure

```
.env.template          # Template for API keys
config.py              # Environment variable loader with validation
search_products.py     # AliExpress product search
pending_queue.json     # Product queue (created at runtime)
pending_queue.py       # Queue read/write helpers with file locking
affiliate_links.py     # Affiliate link generation via AliExpress API
whatsapp_sender.py     # WhatsApp Cloud API message sender
telegram_bot.py        # Telegram bot with command handlers
main.py                # Entry point
tests/                 # Test suite
```
