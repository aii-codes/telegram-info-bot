# pyright: reportOptionalMemberAccess=false, reportArgumentType=false
import nest_asyncio
nest_asyncio.apply()

import os
import aiohttp
import asyncio
import threading
import logging
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from telegram.error import Conflict
from aiohttp import web

# --- Logging setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# --- Load BOT_TOKEN ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found in environment variables.")

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "👋 Hello! I'm InfoBot — your friendly info assistant.\n\n"
            "Type /help to see what I can do."
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "🧠 Available Commands:\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n"
            "/joke - Get a random programming joke\n"
            "/fact - Get a random fact\n"
            "/weather <city> - Get current weather info\n\n"
            "Or just type anything, and I’ll reply!"
        )

async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    url = "https://official-joke-api.appspot.com/random_joke"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                joke = f"😂 {data['setup']}\n\n👉 {data['punchline']}"
                await update.message.reply_text(joke)
            else:
                await update.message.reply_text("❌ Couldn't fetch a joke right now.")

async def fact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    url = "https://uselessfacts.jsph.pl/random.json?language=en"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                fact = f"💡 {data['text']}"
                await update.message.reply_text(fact)
            else:
                await update.message.reply_text("❌ Couldn't fetch a fact right now.")

async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not context.args:
        await update.message.reply_text("🌤️ Usage: /weather <city>")
        return

    city = " ".join(context.args)
    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}"
    async with aiohttp.ClientSession() as session:
        async with session.get(geo_url) as geo_response:
            if geo_response.status != 200:
                await update.message.reply_text("❌ Couldn't find that city.")
                return
            geo_data = await geo_response.json()
            if "results" not in geo_data:
                await update.message.reply_text("❌ Couldn't find that city.")
                return
            lat = geo_data["results"][0]["latitude"]
            lon = geo_data["results"][0]["longitude"]
            weather_url = (
                f"https://api.open-meteo.com/v1/forecast?latitude={lat}"
                f"&longitude={lon}&current_weather=true"
            )
            async with session.get(weather_url) as weather_response:
                if weather_response.status == 200:
                    weather_data = await weather_response.json()
                    temp = weather_data["current_weather"]["temperature"]
                    wind = weather_data["current_weather"]["windspeed"]
                    await update.message.reply_text(
                        f"🌤️ Weather in {city.title()}:\n🌡️ {temp}°C\n💨 Wind: {wind} km/h"
                    )
                else:
                    await update.message.reply_text("❌ Couldn't fetch weather right now.")

async def echo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(f"You said: {update.message.text}")


# --- Health check server ---
async def handle_health(request):
    return web.Response(text="ok")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/health", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"🌐 Health check server running on port {port}")


# --- Self-ping background task ---
async def self_ping_task():
    await asyncio.sleep(30)
    url = f"https://{os.getenv('RENDER_EXTERNAL_URL', '')}/health"
    if not url or "http" not in url:
        logging.warning("⚠️ No RENDER_EXTERNAL_URL found; skipping self-ping.")
        return
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    logging.info(f"🔁 Self-ping -> {url} [{resp.status}]")
        except Exception as e:
            logging.warning(f"Self-ping failed: {e}")
        await asyncio.sleep(600)  # 10 min


# --- Bot runner (non-awaitable polling) ---
def run_bot():
    while True:
        try:
            app = ApplicationBuilder().token(BOT_TOKEN).build()
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CommandHandler("help", help_command))
            app.add_handler(CommandHandler("joke", joke_command))
            app.add_handler(CommandHandler("fact", fact_command))
            app.add_handler(CommandHandler("weather", weather_command))
            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_message))

            # Set menu commands (async-safe setup)
            try:
                asyncio.run(app.bot.set_my_commands([
                    BotCommand("start", "Start the bot"),
                    BotCommand("help", "Show help message"),
                    BotCommand("joke", "Get a random joke"),
                    BotCommand("fact", "Get a random fact"),
                    BotCommand("weather", "Check weather for a city"),
                ]))
            except RuntimeError:
                loop = asyncio.get_event_loop()
                loop.run_until_complete(app.bot.set_my_commands([
                    BotCommand("start", "Start the bot"),
                    BotCommand("help", "Show help message"),
                    BotCommand("joke", "Get a random joke"),
                    BotCommand("fact", "Get a random fact"),
                    BotCommand("weather", "Check weather for a city"),
                ]))

            logging.info("🤖 InfoBot is running...")
            app.run_polling()  # synchronous, no await ✅

        except Conflict:
            logging.warning("⚠️ Another polling instance detected. Retrying in 10 s...")
            asyncio.run(asyncio.sleep(10))
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            asyncio.run(asyncio.sleep(10))

# --- Entry point ---
if __name__ == "__main__":
    try:
        threading.Thread(target=lambda: asyncio.run(start_web_server()), daemon=True).start()
        threading.Thread(target=lambda: asyncio.run(self_ping_task()), daemon=True).start()
        run_bot()
    except (KeyboardInterrupt, RuntimeError):
        logging.info("🛑 Bot stopped gracefully.")
