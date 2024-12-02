import os
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from telegram.ext import Application
import httpx
from pymongo import MongoClient

# Step 1: Configure logging for the app
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Logs output to the console
    ],
)
logger = logging.getLogger("TelegramBotApp")

# Step 2: Utility function to load environment variables with logging
def get_env_variable(var_name: str, required: bool = True):
    """
    This function retrieves the value of an environment variable and logs its status.
    If the variable is not found and is required, it raises an error.
    """
    value = os.getenv(var_name)
    if value:
        logger.info(f"Environment variable '{var_name}' loaded successfully.")
    elif required:
        logger.error(f"Environment variable '{var_name}' is required but not set.")
        raise ValueError(f"Missing required environment variable: {var_name}")
    else:
        logger.warning(f"Environment variable '{var_name}' is not set (optional).")
    return value

# Step 3: Load all necessary environment variables
TELEGRAM_BOT_TOKEN = get_env_variable('TELEGRAM_BOT_TOKEN')
GROK_API_KEY = get_env_variable('GROK_API_KEY')
GROK_API_URL = get_env_variable('GROK_API_URL')
JWK_PATH = get_env_variable('JWK_PATH')
HUGGINGFACE_API_TOKEN = get_env_variable('HUGGINGFACE_API_TOKEN')
HUGGINGFACE_SPACE_URL = get_env_variable('HUGGINGFACE_SPACE_URL')
RENDER_INTERMEDIARY_URL = get_env_variable('RENDER_INTERMEDIARY_URL')
RENDER_TG_BOT_WEBHOOK_URL = get_env_variable('RENDER_TG_BOT_WEBHOOK_URL')
MONGO_URI = get_env_variable('MONGO_URI')

# Step 4: Initialize the Telegram bot application using the provided token
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# Step 5: FastAPI application with detailed lifecycle management using context managers
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the startup and shutdown lifecycle of the application. This handles
    Telegram bot initialization, webhook setup, and cleanup on shutdown.
    """
    # Startup logic
    logger.info("Initializing Telegram bot application...")
    await application.initialize()
    logger.info("Telegram application initialized successfully.")

    logger.info("Starting Telegram application...")
    await application.start()
    logger.info("Telegram application started successfully.")

    # Set webhook URL
    webhook_url = f"{RENDER_TG_BOT_WEBHOOK_URL}/{TELEGRAM_BOT_TOKEN}"
    logger.info(f"Attempting to set webhook with URL: {webhook_url}")
    try:
        await application.bot.set_webhook(url=webhook_url)
        logger.info("Webhook set successfully.")
    except Exception as e:
        logger.error(f"Error setting webhook: {e}", exc_info=True)

    yield  # The application runs here

    # Shutdown logic
    logger.info("Stopping Telegram application...")
    await application.stop()
    logger.info("Telegram application stopped successfully.")

    logger.info("Shutting down Telegram application...")
    await application.shutdown()
    logger.info("Telegram application shutdown complete.")

# Step 6: Initialize the FastAPI app with lifecycle management
app = FastAPI(lifespan=lifespan)

# Step 7: Example route for health check
@app.get("/")
async def health_check():
    """
    Health check endpoint to verify that the service is running and responsive.
    """
    logger.info("Health check endpoint accessed.")
    return {"status": "ok"}

# Step 8: Example usage of external services with detailed logging

# Test integration with the Grok API
@app.get("/test-grok")
async def test_grok():
    """
    Endpoint to test the integration with the Grok API.
    """
    logger.info("Testing Grok API integration...")
    headers = {"Authorization": f"Bearer {GROK_API_KEY}"}
    try:
        response = httpx.post(GROK_API_URL, headers=headers, json={"test": "ping"})
        response.raise_for_status()  # Raise an exception for HTTP errors
        logger.info(f"Grok API response: {response.json()}")
        return response.json()
    except Exception as e:
        logger.error(f"Grok API error: {e}", exc_info=True)
        return {"error": str(e)}

# Test integration with HuggingFace API
@app.get("/test-huggingface")
async def test_huggingface():
    """
    Endpoint to test the connection with the HuggingFace API.
    """
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

# Test connection to MongoDB
@app.get("/test-mongo")
async def test_mongo():
    """
    Endpoint to test the connection to MongoDB.
    """
    logger.info("Testing MongoDB connection...")
    try:
        client = MongoClient(MONGO_URI)
        db = client.get_database()
        logger.info(f"MongoDB connected successfully. Database: {db.name}")
        return {"message": f"Connected to MongoDB: {db.name}"}
    except Exception as e:
        logger.error(f"MongoDB connection error: {e}", exc_info=True)
        return {"error": str(e)}

# Step 9: Middleware to log requests and responses, also logs unhandled errors
@app.middleware("http")
async def log_requests(request, call_next):
    """
    Middleware to log incoming requests and the responses returned by the API.
    Also handles logging of any unhandled errors during request processing.
    """
    logger.info(f"Incoming request: {request.method} {request.url}")
    try:
        # Process the request and generate a response
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code} for {request.url}")
        return response
    except Exception as e:
        # Log unhandled errors
        logger.error(f"Unhandled error during request: {e}", exc_info=True)
        raise  # Re-raise the exception to let FastAPI handle it
