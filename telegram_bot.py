import os
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from telegram.ext import Application
import httpx
from pymongo import MongoClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("TelegramBotApp")

# Load environment variables with logging
def get_env_variable(var_name: str, required: bool = True):
    value = os.getenv(var_name)
    if value:
        logger.info(f"Environment variable '{var_name}' loaded successfully.")
    elif required:
        logger.error(f"Environment variable '{var_name}' is required but not set.")
        raise ValueError(f"Missing required environment variable: {var_name}")
    else:
        logger.warning(f"Environment variable '{var_name}' is not set (optional).")
    return value

# Load environment variables
TELEGRAM_BOT_TOKEN = get_env_variable('TELEGRAM_BOT_TOKEN')
GROK_API_KEY = get_env_variable('GROK_API_KEY')
GROK_API_URL = get_env_variable('GROK_API_URL')
JWK_PATH = get_env_variable('JWK_PATH')
HUGGINGFACE_API_TOKEN = get_env_variable('HUGGINGFACE_API_TOKEN')
HUGGINGFACE_SPACE_URL = get_env_variable('HUGGINGFACE_SPACE_URL')
RENDER_INTERMEDIARY_URL = get_env_variable('RENDER_INTERMEDIARY_URL')
RENDER_TG_BOT_WEBHOOK_URL = get_env_variable('RENDER_TG_BOT_WEBHOOK_URL')
MONGO_URI = get_env_variable('MONGO_URI')

# Telegram bot application
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# FastAPI application with detailed lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    logger.info("Initializing Telegram bot application...")
    await application.initialize()
    logger.info("Telegram application initialized successfully.")

    logger.info("Starting Telegram application...")
    await application.start()
    logger.info("Telegram application started successfully.")

    # Set webhook
    webhook_url = f"{RENDER_TG_BOT_WEBHOOK_URL}/{TELEGRAM_BOT_TOKEN}"
    logger.info(f"Attempting to set webhook with URL: {webhook_url}")
    try:
        await application.bot.set_webhook(url=webhook_url)
        logger.info("Webhook set successfully.")
    except Exception as e:
        logger.error(f"Error setting webhook: {e}", exc_info=True)

    yield  # Application runs here

    # Shutdown logic
    logger.info("Stopping Telegram application...")
    await application.stop()
    logger.info("Telegram application stopped successfully.")

    logger.info("Shutting down Telegram application...")
    await application.shutdown()
    logger.info("Telegram application shutdown complete.")

app = FastAPI(lifespan=lifespan)

# Example route for health check
@app.get("/")
async def health_check():
    logger.info("Health check endpoint accessed.")
    return {"status": "ok"}

# Example usage of external services with detailed logging
@app.get("/test-grok")
async def test_grok():
    logger.info("Testing Grok API integration...")
    headers = {"Authorization": f"Bearer {GROK_API_KEY}"}
    try:
        response = httpx.post(GROK_API_URL, headers=headers, json={"test": "ping"})
        response.raise_for_status()
        logger.info(f"Grok API response: {response.json()}")
        return response.json()
    except Exception as e:
        logger.error(f"Grok API error: {e}", exc_info=True)
        return {"error": str(e)}

@app.get("/test-huggingface")
async def test_huggingface():
    logger.info("Testing HuggingFace API integration...")
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"}
    try:
        response = httpx.get(HUGGINGFACE_SPACE_URL, headers=headers)
        response.raise_for_status()
        logger.info(f"HuggingFace response: {response.text}")
        return {"message": "HuggingFace connection successful"}
    except Exception as e:
        logger.error(f"HuggingFace API error: {e}", exc_info=True)
        return {"error": str(e)}

@app.get("/test-mongo")
async def test_mongo():
    logger.info("Testing MongoDB connection...")
    try:
        client = MongoClient(MONGO_URI)
        db = client.get_database()
        logger.info(f"MongoDB connected successfully. Database: {db.name}")
        return {"message": f"Connected to MongoDB: {db.name}"}
    except Exception as e:
        logger.error(f"MongoDB connection error: {e}", exc_info=True)
        return {"error": str(e)}

# Additional logging for unexpected errors
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url}")
    try:
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code} for {request.url}")
        return response
    except Exception as e:
        logger.error(f"Unhandled error during request: {e}", exc_info=True)
        raise
