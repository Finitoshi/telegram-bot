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

# Step 1: Configure logging for the app
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("TelegramBotApp")

# Step 2: Utility function to load environment variables
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

# Step 3: Load all necessary environment variables
TELEGRAM_BOT_TOKEN = get_env_variable('TELEGRAM_BOT_TOKEN')
GROK_API_KEY = get_env_variable('GROK_API_KEY')
GROK_API_URL = get_env_variable('GROK_API_URL', required=False) or "https://api.x.ai/v1/chat/completions"
MONGO_URI = get_env_variable('MONGO_URI')
BITTY_TOKEN_ADDRESS = get_env_variable('BITTY_TOKEN_ADDRESS')  # Token address for token gating

# Step 4: Initialize MongoDB client and cache collection
client = MongoClient(MONGO_URI)
db = client['bot_db']
cache_collection = db['cache']

# Step 5: Initialize the Telegram bot application
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# Step 6: FastAPI application with detailed lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Telegram bot application... 🔥")
    await application.initialize()
    logger.info("Telegram application initialized, all set to go! 🚀")
    logger.info("Starting the Telegram bot application... 🚀")
    await application.start()  # Bot's ready to start flexing
    logger.info("Telegram bot started, we are live! 🔥")
    yield
    logger.info("Stopping Telegram bot application... 🚨")
    await application.stop()
    logger.info("Telegram bot stopped successfully. 🛑")
    logger.info("Shutting down Telegram bot application... 💤")
    await application.shutdown()
    logger.info("Telegram bot shutdown complete. ✅")

app = FastAPI(lifespan=lifespan)

# Step 7: Health check route
@app.get("/")
async def health_check():
    logger.info("Health check endpoint accessed. Still alive, yo.")
    return {"status": "ok"}

# Step 8: Query Grok API and cache the response
async def query_grok(message):
    cached_response = cache_collection.find_one({
        "message": message,
        "cached_at": {"$gte": datetime.utcnow() - timedelta(seconds=60)}
    })

    if cached_response:
        logger.info("Returning cached response.")
        return cached_response['response']

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
    logger.info(f"Sending to Grok API: {payload}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(GROK_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            response_data = response.json()
            logger.info(f"Grok API response: {response_data}")
            grok_response = response_data.get('choices', [{}])[0].get('message', {}).get('content', "Grok did not respond properly.")
            
            cache_data = {
                "message": message,
                "response": grok_response,
                "cached_at": datetime.utcnow()
            }
            cache_collection.insert_one(cache_data)
            return grok_response
    except httpx.HTTPStatusError as e:
        logger.error(f"Grok API HTTP error: {e.response.text}.")
        return "An error occurred while querying Grok."
    except Exception as e:
        logger.error(f"Unexpected error with Grok API: {e}.")
        return "An unexpected error occurred."

# Step 9: Token gating (Check if the user holds the required token)
async def check_token_ownership(chat_id):
    # Here, you would call the blockchain API or wallet service to check if the user holds the required token
    # For demonstration, we're assuming the user has the token.
    has_token = True  # Replace with actual check (e.g., checking wallet balance via token address)
    return has_token

# Step 10: Webhook handler for Telegram updates
@app.post("/" + TELEGRAM_BOT_TOKEN)
async def handle_webhook(request: Request):
    update = await request.json()
    logger.info(f"Received update: {update}")
    telegram_update = Update.de_json(update, application.bot)
    
    if telegram_update.message and telegram_update.message.text:
        message = telegram_update.message.text
        chat_id = telegram_update.message.chat_id
        
        # Token gating check before responding
        has_token = await check_token_ownership(chat_id)
        if not has_token:
            await application.bot.send_message(chat_id=chat_id, text="You don't hold the required token to access this bot. 😞")
            return {"status": "ok"}

        grok_response = await query_grok(message)
        await application.bot.send_message(chat_id=chat_id, text=grok_response)
    
    return {"status": "ok"}

# Step 11: Middleware to log requests and responses
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url}.")
    try:
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code} for {request.url}.")
        return response
    except Exception as e:
        logger.error(f"Unhandled error during request: {e}.")
        raise

# Step 12: Ensure the application listens on the correct port
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
