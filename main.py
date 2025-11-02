import time
import logging
import os
import threading
import random
import asyncio
from collections import deque
from datetime import datetime
import requests
import google.generativeai as genai
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv
from flask import Flask

# ==== LOAD .ENV ====
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
COOLDOWN_SECONDS = int(os.getenv("COOLDOWN_SECONDS", 3))
MEMORY_LIMIT = int(os.getenv("MEMORY_LIMIT", 5))

# Validate environment variables
if not GEMINI_API_KEY or not TELEGRAM_BOT_TOKEN:
    raise ValueError("❌ Missing GEMINI_API_KEY or TELEGRAM_BOT_TOKEN in .env / Render env vars!")

# ==== SETUP ====
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash-lite")

chat_memory = deque(maxlen=MEMORY_LIMIT)
last_request_time = 0

# ==== LOGGING ====
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

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
    full_prompt = f"{style_prompt}\n\nChat so far:\n{context_text}\n\nUser: {prompt}\nOlivia Emma:"

    log(f"🧠 Sending to Gemini:\n   {prompt}")

    try:
        response = model.generate_content(full_prompt)
        text = response.text.strip() if response.text else "..."
        log(f"💬 Olivia replied:\n   {text}")
        return text
    except Exception as e:
        log(f"❌ Gemini error: {e}")
        return "Oh honey, even my errors are fabulous... try again?"

# ==== TELEGRAM HANDLER ====
async def reply_to_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_request_time

    if not update.message or not update.message.text:
        return

    user_message = update.message.text.strip()
    user_name = update.message.from_user.first_name
    chat_id = update.message.chat.id
    chat_type = update.message.chat.type
    current_time = time.time()

    log(f"📩 Msg from {user_name} ({chat_id}, {chat_type}): {user_message}")

    # Ignore commands
    if user_message.startswith("/"):
        log("⚠️ Ignored command.")
        return

    # Cooldown handling
    if current_time - last_request_time < COOLDOWN_SECONDS:
        log("🕒 Cooldown active — skipping.")
        return

    last_request_time = current_time
    chat_memory.append(f"User: {user_message}")

    # ==== RANDOM DELAY (5–20 seconds) ====
    delay = random.uniform(5, 20)
    log(f"💤 Olivia is thinking... waiting {delay:.1f} seconds before replying.")
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    await asyncio.sleep(delay)

    # ==== GENERATE REPLY ====
    reply = get_gemini_reply(user_message)
    chat_memory.append(f"Olivia Emma: {reply}")

    try:
        await update.message.reply_text(reply)
        log(f"✅ Replied to {user_name}: {reply}")
    except Exception as e:
        log(f"❌ Send failed: {e}")

# ==== MAIN ENTRY POINT ====
if __name__ == "__main__":
    log("🤖 Olivia Emma is live & fabulous! 💋")

    # Clear any Telegram webhooks (Render sometimes sets one automatically)
    try:
        requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook")
        log("🧹 Webhook cleared.")
    except Exception as e:
        log(f"⚠️ Webhook clear failed: {e}")

    # Create the Telegram bot application
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply_to_message))

    # ==== RUN MODE ====
    if os.environ.get("PORT"):
        # Render mode (production)
        log("🌐 Render mode: Starting Flask + polling combo...")

        flask_app = Flask(__name__)

        @flask_app.route("/health")
        def health():
            return {"status": "Olivia Emma is fabulous 💋"}, 200

        # Run Flask in background
        def run_flask():
            port = int(os.environ["PORT"])
            flask_app.run(host="0.0.0.0", port=port)

        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()

        # Run Telegram polling in main thread
        app.run_polling(allowed_updates=Update.ALL_TYPES)

    else:
        # Local mode (dev)
        log("🏠 Local mode: Starting polling...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
