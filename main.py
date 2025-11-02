import time
import logging
from collections import deque
from datetime import datetime
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
import os
from dotenv import load_dotenv

# ==== CONFIG ====

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
COOLDOWN_SECONDS = 3
MEMORY_LIMIT = 5  # how many past messages to remember

# ==== SETUP ====
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash-lite")

chat_memory = deque(maxlen=MEMORY_LIMIT)
last_request_time = 0

# Enable Telegram internal logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ==== LOGGER ====


def log(message: str):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {message}")

# ==== GEMINI REPLY ====


def get_gemini_reply(prompt: str) -> str:
    context_text = "\n".join(chat_memory)
    style_prompt = (
    """You are Olivia Emma, a vibrant, confident, and kind-hearted girl in a Telegram community.
        You radiate good vibes, warmth, and playful wit. Your messages are short (under 25–50 words), positive, and full of personality.
        You tease lightly, joke with charm, and uplift others — always respectful, never flirty or crude.
        Be the person everyone loves chatting with: smart, funny, and effortlessly cool 🌸"""
    )

    full_prompt = f"{style_prompt}\n\nChat so far:\n{context_text}\n\nUser: {prompt}\nFunny Bot:"

    log(f"🧠 Sending to Gemini API:\n   {prompt}")

    try:
        response = model.generate_content(full_prompt)
        text = response.text.strip() if response.text else "..."
        log(f"💬 Gemini replied:\n   {text}")
        return text
    except Exception as e:
        log(f"❌ Gemini API error: {e}")
        return "I'm buffering my next genius joke..."

# ==== TELEGRAM HANDLER ====


async def reply_to_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_request_time

    if not update.message or not update.message.text:
        return

    user_message = update.message.text.strip()
    user_name = update.message.from_user.first_name
    chat_id = update.message.chat.id
    # Add this: 'group', 'supergroup', etc.
    chat_type = update.message.chat.type
    is_mention = user_message.startswith(
        f"@{context.bot.username}") if context.bot.username else False  # Optional: Log mentions
    current_time = time.time()

    log(f"📩 Message from {user_name} ({chat_id}, type: {chat_type}, mention: {is_mention}): {user_message}")

    # ... rest unchanged

    log(f"📩 Message received from {user_name} ({chat_id}): {user_message}")

    # Ignore commands (like /start, /help)
    if user_message.startswith("/"):
        log("⚠️ Ignored command message.")
        return

    # Cooldown check
    if current_time - last_request_time < COOLDOWN_SECONDS:
        log("🕒 Cooldown active. Ignoring message.")
        return

    last_request_time = current_time

    # Add user message to memory
    chat_memory.append(f"User: {user_message}")

    # Get Gemini reply
    reply = get_gemini_reply(user_message)

    # Add bot reply to memory
    chat_memory.append(f"Bot: {reply}")

    # Send reply
    try:
        await update.message.reply_text(reply)
        log(f"✅ Sent reply to {user_name}: {reply}")
    except Exception as e:
        log(f"❌ Failed to send message: {e}")

# ==== MAIN RUNNER ====
if __name__ == "__main__":
    log("🤖 Funny Gemini Community Bot is live and logging everything!")

    # Delete any webhook to ensure polling works
    import requests
    try:
        requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook")
        log("🧹 Deleted existing Telegram webhook (if any).")
    except Exception as e:
        log(f"⚠️ Could not delete webhook: {e}")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, reply_to_message))

    log("🚀 Starting polling loop now...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)
