import os
import logging
import asyncio
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import httpx
from pymongo import MongoClient

# Step 1: Configure logging for the app - because who doesn't love a good log?
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("TelegramBotApp")

# Step 2: Utility function to load environment variables with logging - adulting is hard, let's log it!
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

# Step 3: Load all necessary environment variables - 'cause we're not playing games here
TELEGRAM_BOT_TOKEN = get_env_variable('TELEGRAM_BOT_TOKEN')
GROK_API_KEY = get_env_variable('GROK_API_KEY')
GROK_API_URL = get_env_variable('GROK_API_URL')
JWK_PATH = get_env_variable('JWK_PATH')
HUGGINGFACE_API_TOKEN = get_env_variable('HUGGINGFACE_API_TOKEN')
HUGGINGFACE_SPACE_URL = get_env_variable('HUGGINGFACE_SPACE_URL')
RENDER_INTERMEDIARY_URL = get_env_variable('RENDER_INTERMEDIARY_URL')
RENDER_TG_BOT_WEBHOOK_URL = get_env_variable('RENDER_TG_BOT_WEBHOOK_URL')
MONGO_URI = get_env_variable('MONGO_URI')

# Step 4: Initialize the Telegram bot application using the provided token - let's get this party started
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# Step 5: FastAPI application with detailed lifecycle management using context managers - because we're fancy like that
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Telegram bot application... 🔥")
    await application.initialize()
    logger.info("Telegram application initialized, all set to go! 🚀")

    logger.info("Starting the Telegram bot application... 🚀")
    await application.start()
    logger.info("Telegram bot started, we are live! 🔥")

    # Set webhook URL - because who still uses polling? 
    webhook_url = f"{RENDER_TG_BOT_WEBHOOK_URL}/{TELEGRAM_BOT_TOKEN}"
    logger.info(f"Setting webhook with this URL: {webhook_url} 💥")
    try:
        await application.bot.set_webhook(url=webhook_url)
        logger.info("Webhook set successfully. 🏆")
    except Exception as e:
        logger.error(f"Error setting webhook: {e}. Yikes!", exc_info=True)

    yield  # The application runs here

    # Shutdown logic - because all good things must come to an end
    logger.info("Stopping Telegram bot application... 🚨")
    await application.stop()
    logger.info("Telegram bot stopped successfully. 🛑")

    logger.info("Shutting down Telegram bot application... 💤")
    await application.shutdown()
    logger.info("Telegram bot shutdown complete. ✅")

# Step 6: Initialize the FastAPI app with lifecycle management - we're in control here
app = FastAPI(lifespan=lifespan)

# Step 7: Example route for health check - just to make sure we're not dead yet
@app.get("/")
async def health_check():
    logger.info("Health check endpoint accessed. Still alive, yo.")
    return {"status": "ok"}

# New function to interact with Grok API - 'cause we're talking to AI now, like it's no big deal
async def query_grok(message):
    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json"  # Don't forget this or you'll get a 415
    }
    payload = {
        "message": message, 
        "model": "grok-beta"  # Because we're using the cool beta model, duh!
    }
    logger.info(f"Sending to Grok API: {payload}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(GROK_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            response_data = response.json()
            logger.info(f"Grok API response: {response_data}")
            return response_data.get('reply', "Grok did not respond properly. Guess AI has its off days too.")
    except httpx.HTTPStatusError as e:
        logger.error(f"Grok API HTTP error: {e.response.text}. That's not very Grok of you!")
        return "An error occurred while querying Grok. #AIProblems"
    except Exception as e:
        logger.error(f"Unexpected error with Grok API: {e}. Grok's gone rogue!")
        return "An unexpected error occurred. Grok's taking a nap, I guess."

# Step 8: Webhook handler for Telegram updates - where the magic happens
@app.post("/" + TELEGRAM_BOT_TOKEN)
async def handle_webhook(request: Request):
    update = await request.json()
    logger.info(f"Received update: {update}")
    
    telegram_update = Update.de_json(update, application.bot)
    if telegram_update.message and telegram_update.message.text:
        message = telegram_update.message.text
        grok_response = await query_grok(message)
        await application.bot.send_message(chat_id=telegram_update.message.chat_id, text=grok_response)
    
    return {"status": "ok"}

# Step 10: Middleware to log requests and responses, also logs unhandled errors - because we like to keep track of everything
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url}. What's up, internet?")
    try:
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code} for {request.url}. Peace out!")
        return response
    except Exception as e:
        logger.error(f"Unhandled error during request: {e}. This is why we can't have nice things!", exc_info=True)
        raise

# Step 11: Ensure the application listens on the correct port - because we need to be heard
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))  # Default to 8000 if PORT is not set, 'cause we're flexible like that
    uvicorn.run(app, host="0.0.0.0", port=port)
