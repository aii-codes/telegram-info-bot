# pyright: reportOptionalMemberAccess=false, reportArgumentType=false

# --- 🧩 Fix event loop conflict (MUST be first) ---
import nest_asyncio
nest_asyncio.apply()

import os
import aiohttp
import asyncio
from dotenv import load_dotenv
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# 1️⃣ Load environment variables (BOT_TOKEN)
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found in environment variables. Check your .env file!")

# 2️⃣ Define command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when the /start command is issued."""
    if update.message:
        await update.message.reply_text(
            "👋 Hello! I'm InfoBot — your friendly info assistant.\n\n"
            "Type /help to see what I can do."
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a list of available commands."""
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

# --- 1️⃣ Random Joke Command ---
async def joke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch a random programming joke."""
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

# --- 2️⃣ Random Fact Command ---
async def fact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch a random fact."""
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

# --- 3️⃣ Weather Command ---
async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch current weather using Open-Meteo API."""
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

# --- 4️⃣ Echo fallback ---
async def echo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Echo any user message."""
    if update.message:
        user_text = update.message.text
        await update.message.reply_text(f"You said: {user_text}")

# 5️⃣ Main bot setup and run
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # 🧠 Add professional menu commands
    commands = [
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Show help message"),
        BotCommand("joke", "Get a random joke"),
        BotCommand("fact", "Get a random fact"),
        BotCommand("weather", "Check weather for a city"),
    ]
    await app.bot.set_my_commands(commands)

    # Register handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("joke", joke_command))
    app.add_handler(CommandHandler("fact", fact_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_message))

    print("🤖 InfoBot is running with a professional menu...")
    await app.run_polling()  # type: ignore[func-returns-value]

# --- Entry point ---
if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except (KeyboardInterrupt, RuntimeError):
        print("\n🛑 Bot stopped gracefully.")


