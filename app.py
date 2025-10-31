import os
import aiohttp
import asyncio
import logging
from dotenv import load_dotenv
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from aiohttp import web

# --- Logging setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# --- Load BOT_TOKEN with type safety ---
load_dotenv()
BOT_TOKEN: str = os.getenv("BOT_TOKEN") or ""
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN not found in environment variables.")

# --- Suggested cities for quick weather picker (customize as needed) ---
SUGGESTED_CITIES = [
    "Manila", "Quezon City", "Cebu City", "Davao City", "Baguio",
    "Iloilo City", "Bacolod", "Zamboanga City", "Cagayan de Oro",
    "Taguig", "Pasig", "Makati", "General Santos", "Tarlac",
    "Batangas City", "San Fernando", "Olongapo", "Lucena",
    "Legazpi", "Naga", "Tacloban", "Butuan", "Surigao",
    "Tagbilaran", "Puerto Princesa", "Roxas City", "Cotabato City",
    "Dumaguete", "San Pablo", "Dasmariñas", "Santa Rosa", "Lipa",
    "Tuguegarao", "Iligan", "Pagadian", "Dipolog", "Calbayog"
]

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "👋 Hello! I'm AiiMBot – your friendly info assistant.\n\n"
            "Type /help to see what I can do.\n\n"
            "——\n_Developed by Aii_"
        , parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "🧠 Available Commands:\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n"
            "/joke - Get a random programming joke\n"
            "/fact - Get a random fact\n"
            "/weather <city> - Get current weather info\n"
            "/news - Get the latest news\n"
            "/quote - Get an inspirational quote\n"
            "/define <word> - Look up a word definition\n\n"
            "💬 You can also just chat with me naturally — I'll reply using AI!"
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

# --- Reusable weather fetch helper ---
async def fetch_weather_for_city(city: str) -> str:
    """
    Returns a formatted string of current weather for `city`.
    If it can't find the city, returns a friendly error string.
    """
    city = city.strip()
    if not city:
        return "❌ No city provided."

    # Geocoding: get lat/lon
    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(geo_url, timeout=aiohttp.ClientTimeout(total=10)) as geo_response:
                if geo_response.status != 200:
                    return "❌ Couldn't find that city (geocoding failed)."
                geo_data = await geo_response.json()
    except Exception:
        return "❌ Couldn't reach geocoding service."

    if not geo_data or "results" not in geo_data or len(geo_data["results"]) == 0:
        return "❌ Couldn't find that city."

    # Use first result
    loc = geo_data["results"][0]
    lat = loc.get("latitude")
    lon = loc.get("longitude")
    name = loc.get("name") or city
    country = loc.get("country") or ""

    weather_url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        f"&current_weather=true"
    )

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(weather_url, timeout=aiohttp.ClientTimeout(total=10)) as weather_response:
                if weather_response.status != 200:
                    return "❌ Couldn't fetch weather right now."
                weather_data = await weather_response.json()
    except Exception:
        return "❌ Couldn't reach weather service."

    current = weather_data.get("current_weather")
    if not current:
        return "❌ Weather data missing."

    temp = current.get("temperature")
    wind = current.get("windspeed")
    wind_dir = current.get("winddirection")
    return f"🌤️ Weather in {name}, {country}:\n🌡️ {temp}°C\n💨 Wind: {wind} km/h (dir {wind_dir}°)"

# --- Weather command (shows picker if no args) ---
async def weather_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch current weather using Open-Meteo API. If no args show a quick city picker."""
    if not update.message:
        return

    # If user provided a city: use helper
    if context.args:
        city = " ".join(context.args)
        result = await fetch_weather_for_city(city)
        await update.message.reply_text(result)
        return

    # No args: show inline keyboard of suggested cities + 'Enter Manually' button
    keyboard = []
    row = []
    for i, city in enumerate(SUGGESTED_CITIES):
        row.append(InlineKeyboardButton(city, callback_data=f"city:{city}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("Enter city manually", callback_data="manual")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🌤️ Pick a city to get current weather, or choose 'Enter city manually' to type a city name.",
        reply_markup=reply_markup
    )

# --- Callback handler for weather buttons ---
async def weather_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    await query.answer()  # acknowledge the callback to remove spinner

    data = query.data or ""
    if data.startswith("city:"):
        city = data.split("city:", 1)[1]
        await query.edit_message_text(f"🔎 Fetching weather for {city}...")
        result = await fetch_weather_for_city(city)
        await query.edit_message_text(result)
    elif data == "manual":
        # instruct the user to use /weather <city>
        await query.edit_message_text("✍️ Please type `/weather <city>` (for example: `/weather Manila`).")
    else:
        await query.edit_message_text("❌ Unknown action.")

# --- 4️⃣ News Command ---
async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch top news headlines from NewsAPI"""
    if not update.message:
        return

    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        await update.message.reply_text("⚠️ NEWS_API_KEY not set in environment.")
        return

    url = f"https://newsapi.org/v2/top-headlines?country=us&pageSize=3&apiKey={api_key}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                articles = data.get("articles", [])
                if not articles:
                    await update.message.reply_text("😶 No news found.")
                    return
                headlines = "\n\n".join(
                    [f"🗞️ {a['title']}\n🔗 {a.get('url','')}" for a in articles[:3]]
                )
                await update.message.reply_text(f"📰 Top Headlines:\n\n{headlines}")
            else:
                await update.message.reply_text("❌ Couldn't fetch news right now.")

# --- 5️⃣ Quote Command ---
async def quote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch a random motivational quote"""
    if not update.message:
        return

    url = "https://zenquotes.io/api/random"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
            if response.status == 200:
                data = await response.json()
                # API returns a list with a single dict
                quote = data[0].get("q", "")
                author = data[0].get("a", "")
                await update.message.reply_text(f"💬 \"{quote}\"\n— {author}")
            else:
                await update.message.reply_text("❌ Couldn't fetch a quote right now.")

# --- 6️⃣ Define Command ---
async def define_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetch a word definition"""
    if not update.message:
        return

    if not context.args:
        await update.message.reply_text("📘 Usage: /define <word>")
        return

    word = context.args[0]
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data = await resp.json()
                try:
                    meaning = data[0]["meanings"][0]["definitions"][0]["definition"]
                    await update.message.reply_text(f"📖 Definition of {word}:\n{meaning}")
                except Exception:
                    await update.message.reply_text("❌ Couldn't parse definition result.")
            else:
                await update.message.reply_text("❌ Word not found.")

# --- AI Chat Handler (Mistral Integration) ---
async def generate_ai_reply(message: str) -> str:
    """Send user message to Mistral AI and return the reply"""
    api_key = os.getenv("AI_API_KEY")
    if not api_key:
        return "⚠️ AI service is not configured yet."

    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "mistral-tiny",
        "messages": [
            {"role": "system", "content": "You are InfoBot, a helpful, friendly assistant. Keep answers concise and kind."},
            {"role": "user", "content": message}
        ],
        "temperature": 0.7
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    content = data["choices"][0]["message"].get("content") or ""
                    return content.strip()
                else:
                    logging.error(f"AI API Error {resp.status}: {await resp.text()}")
                    return "⚠️ I'm having trouble thinking right now. Try again later!"
    except Exception as e:
        logging.warning(f"AI request failed: {e}")
        return "❌ I couldn't connect to my brain. Please try again later."

async def echo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reply with AI if message isn't a command"""
    if not update.message:
        return

    user_text = (update.message.text or "").strip()

    # Skip if message looks like a bot command
    if user_text.startswith("/"):
        return

    # Use AI for all non-command messages
    ai_reply = await generate_ai_reply(user_text)
    await update.message.reply_text(ai_reply)

# --- Health check server ---
async def handle_health(request):
    return web.Response(text="ok")

async def start_web_server():
    """Start the health check web server"""
    app = web.Application()
    app.router.add_get("/health", handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info(f"🌐 Health check server running on port {port}")
    # Keep the server running
    await asyncio.Event().wait()

# --- Self-ping background task ---
async def self_ping_task():
    """Ping own health endpoint every 10 minutes to keep service alive"""
    await asyncio.sleep(30)  # Initial delay
    url = f"{os.getenv('RENDER_EXTERNAL_URL', '')}/health"
    if not url or "http" not in url:
        logging.warning("⚠️ No RENDER_EXTERNAL_URL found; skipping self-ping.")
        return

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    logging.info(f"🔄 Self-ping -> {url} [{resp.status}]")
        except Exception as e:
            logging.warning(f"Self-ping failed: {e}")
        await asyncio.sleep(600)  # 10 minutes

# --- Main async function ---
async def main():
    """Main function that runs everything concurrently"""
    # Build the bot application - BOT_TOKEN is guaranteed to be str here
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("joke", joke_command))
    app.add_handler(CommandHandler("fact", fact_command))
    app.add_handler(CommandHandler("weather", weather_command))
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("quote", quote_command))
    app.add_handler(CommandHandler("define", define_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_message))
    # CallbackQueryHandler for weather picker
    app.add_handler(CallbackQueryHandler(weather_callback, pattern="^(city:|manual)"))

    # Set bot commands menu
    await app.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("help", "Show help message"),
        BotCommand("joke", "Get a random joke"),
        BotCommand("fact", "Get a random fact"),
        BotCommand("weather", "Check weather for a city"),
        BotCommand("news", "Get the latest news"),
        BotCommand("quote", "Get an inspirational quote"),
        BotCommand("define", "Look up a word definition"),
    ])

    logging.info("🤖 InfoBot is starting...")

    # Initialize the application
    await app.initialize()
    await app.start()

    # Type safety check for updater
    if not app.updater:
        raise RuntimeError("❌ Failed to initialize bot updater")

    # Create tasks for concurrent execution
    tasks = [
        asyncio.create_task(start_web_server(), name="web_server"),
        asyncio.create_task(self_ping_task(), name="self_ping"),
        asyncio.create_task(app.updater.start_polling(), name="bot_polling"),
    ]

    logging.info("✅ All services started successfully!")

    # Wait for all tasks
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logging.info("🛑 Shutting down...")
    finally:
        # Cleanup - safe to access updater now since we checked it exists
        if app.updater:
            await app.updater.stop()
        await app.stop()
        await app.shutdown()

# --- Entry point ---
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🛑 Bot stopped gracefully.")
