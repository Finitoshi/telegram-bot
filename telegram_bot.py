import os
import logging
import asyncio
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import httpx
from pymongo import MongoClient
import json
from datetime import datetime, timedelta

# Step 1: Configure logging for the app (Because if it ain't logged, did it even happen?)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("TelegramBotApp")

# Step 2: Utility function to load environment variables with logging (No more excuses, let's get those keys!)
def get_env_variable(var_name: str, required: bool = True):
    value = os.getenv(var_name)
    if value:
        logger.info(f"Environment variable '{var_name}' loaded successfully. Yeet!")
    elif required:
        logger.error(f"Environment variable '{var_name}' is required but not set. Big oof!")
        raise ValueError(f"Missing required environment variable: {var_name}")
    else:
        logger.warning(f"Environment variable '{var_name}' is not set (optional). Meh.")
    return value

# Step 3: Load all necessary environment variables (Time to load the secrets, like unlocking a chest in a video game)
TELEGRAM_BOT_TOKEN = get_env_variable('TELEGRAM_BOT_TOKEN')
GROK_API_KEY = get_env_variable('GROK_API_KEY')
GROK_API_URL = get_env_variable('GROK_API_URL', required=False) or "https://api.x.ai/v1/chat/completions"
MONGO_URI = get_env_variable('MONGO_URI')

# Step 4: Initialize MongoDB client and cache collection (Because caching is like storing your favorite TikToks offline)
client = MongoClient(MONGO_URI)
db = client['bot_db']
cache_collection = db['cache']

# Step 5: Initialize the Telegram bot application (Get ready to roll with the bot, fam)
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# Step 6: FastAPI application with detailed lifecycle management (We got the controls, no stress)
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Telegram bot application... 🔥")  # It's go time, baby!
    await application.initialize()
    logger.info("Telegram application initialized, all set to go! 🚀")
    logger.info("Starting the Telegram bot application... 🚀")
    await application.start()  # Bot's ready to start flexing
    logger.info("Telegram bot started, we are live! 🔥")
    yield  # The bot's doing its thing here
    logger.info("Stopping Telegram bot application... 🚨")  # Uh oh, time's up
    await application.stop()
    logger.info("Telegram bot stopped successfully. 🛑")
    logger.info("Shutting down Telegram bot application... 💤")  # Going to sleep, like a cozy cat
    await application.shutdown()
    logger.info("Telegram bot shutdown complete. ✅")

app = FastAPI(lifespan=lifespan)

# Step 7: Health check route (Like a quick mirror check before going out)
@app.get("/")
async def health_check():
    logger.info("Health check endpoint accessed. Still alive, yo.")  # You gotta check you're not a zombie
    return {"status": "ok"}

# Step 8: Query Grok API and cache the response (Because who needs slow responses? We want instant gratification)
async def query_grok(message):
    # Check if the response is already cached (We don't want to be basic, let's reuse what we got!)
    cached_response = cache_collection.find_one({
        "message": message,
        "cached_at": {"$gte": datetime.utcnow() - timedelta(seconds=60)}  # Cache expiry time. Like leftovers, but only fresh for a minute
    })

    if cached_response:
        logger.info("Returning cached response.")  # Return the OG answer, no need to call Grok again
        return cached_response['response']

    # If no cache, let's hit up Grok like it's the cool new AI at the party
    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "messages": [
            {"role": "system", "content": "You are Grok, a chatbot inspired by the Hitchhiker's Guide to the Galaxy."},
            {"role": "user", "content": message}
        ],
        "model": "grok-beta",
        "stream": False,
        "temperature": 0
    }
    logger.info(f"Sending to Grok API: {payload}")  # Just like sending a text to your BFF
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(GROK_API_URL, headers=headers, json=payload)
            response.raise_for_status()  # If Grok doesn't respond, there's no more chill
            response_data = response.json()
            logger.info(f"Grok API response: {response_data}")
            grok_response = response_data.get('choices', [{}])[0].get('message', {}).get('content', "Grok did not respond properly. Uh-oh.")
            
            # Cache the new response (Gotta keep that info for later, no FOMO here)
            cache_data = {
                "message": message,
                "response": grok_response,
                "cached_at": datetime.utcnow()
            }
            cache_collection.insert_one(cache_data)  # Storing for later. Like saving your memes.
            return grok_response
    except httpx.HTTPStatusError as e:
        logger.error(f"Grok API HTTP error: {e.response.text}. That's not very Grok of you!")  # Oops, Grok's having a rough day
        return "An error occurred while querying Grok. #AIProblems"
    except Exception as e:
        logger.error(f"Unexpected error with Grok API: {e}. Grok's gone rogue!")  # Grok just wants to be left alone
        return "An unexpected error occurred. Grok's taking a nap, I guess."

# Step 9: Webhook handler for Telegram updates (Let’s catch all the messages like we’re Pokéballs)
@app.post("/" + TELEGRAM_BOT_TOKEN)
async def handle_webhook(request: Request):
    update = await request.json()
    logger.info(f"Received update: {update}")  # Look at this juicy update we just got
    telegram_update = Update.de_json(update, application.bot)
    
    if telegram_update.message and telegram_update.message.text:
        message = telegram_update.message.text
        grok_response = await query_grok(message)  # Hit up Grok, like a friend asking for advice
        await application.bot.send_message(chat_id=telegram_update.message.chat_id, text=grok_response)  # Send the response back, like a helpful buddy
    
    return {"status": "ok"}

# Step 10: Middleware to log requests and responses (Just like tracking your late-night snacks: we know everything)
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url}. What's up, internet?")  # It's a party, let's track everything
    try:
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code} for {request.url}. Peace out!")  # We dropped a reply, fam
        return response
    except Exception as e:
        logger.error(f"Unhandled error during request: {e}. This is why we can't have nice things!")  # Oof, something broke
        raise

# Step 11: Ensure the application listens on the correct port (Because if you ain't online, are you even alive?)
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))  # Default to 8000 if PORT isn't set. We go with the flow
    uvicorn.run(app, host="0.0.0.0", port=port)  # Spin up the server, it's go time!
