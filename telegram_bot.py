import os
import logging
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import httpx
from pymongo import MongoClient

# Step 1: Configure logging for the app
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("TelegramBotApp")

# Step 2: Utility function to load environment variables with logging
def get_env_variable(var_name: str, required: bool = True):
    """Loads environment variables and logs the outcome. Raises an error if a required variable is missing."""
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
GROK_API_KEY = get_env_variable('CHIBI_GROK_KEY')  # Updated to use the new API key
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
    Manages the startup and shutdown lifecycle of the FastAPI app, including Telegram bot initialization,
    webhook setup, and cleanup on shutdown.
    """
    logger.info("Initializing Telegram bot application... 🔥")
    await application.initialize()  # Initialize the bot
    logger.info("Telegram application initialized, all set to go! 🚀")

    logger.info("Starting the Telegram bot application... 🚀")
    await application.start()  # Start the bot
    logger.info("Telegram bot started, we are live! 🔥")

    # Set webhook URL for the bot to listen to updates
    webhook_url = f"{RENDER_TG_BOT_WEBHOOK_URL}/{TELEGRAM_BOT_TOKEN}"
    logger.info(f"Setting webhook with this URL: {webhook_url} 💥")
    try:
        await application.bot.set_webhook(url=webhook_url)
        logger.info("Webhook set successfully. 🏆")
    except Exception as e:
        logger.error(f"Error setting webhook: {e}", exc_info=True)

    yield  # The app runs during this phase

    # Shutdown logic
    logger.info("Stopping Telegram bot application... 🚨")
    await application.stop()  # Stop the bot gracefully
    logger.info("Telegram bot stopped successfully. 🛑")

    logger.info("Shutting down Telegram bot application... 💤")
    await application.shutdown()  # Shutdown the bot
    logger.info("Telegram bot shutdown complete. ✅")

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

# Step 8: Webhook handler for Telegram updates
@app.post("/" + TELEGRAM_BOT_TOKEN)
async def handle_webhook(request: Request):
    """
    Handles webhook updates from Telegram and processes them.
    Receives POST requests from Telegram when a message is sent to the bot.
    """
    update = await request.json()  # Get the webhook update from Telegram
    logger.info(f"Received update: {update}")
    
    # Process the update (e.g., handle commands or messages)
    telegram_update = Update.de_json(update, application.bot)
    
    # Example: Check if we need to use Grok for analysis
    if telegram_update.message.text:
        grok_response = await analyze_with_grok(telegram_update.message.text)
        response_text = f"Grok analysis result: {grok_response}"
    else:
        response_text = "No text received."

    # Send back the response from Grok analysis (if any)
    await application.bot.send_message(chat_id=telegram_update.message.chat_id, text=response_text)
    
    return {"status": "ok"}

# Step 9: Integrating Grok API to process messages
async def analyze_with_grok(text: str):
    """
    Uses the Grok API to analyze incoming text.
    This function sends the text to Grok and returns the analysis response.
    """
    headers = {"Authorization": f"Bearer {GROK_API_KEY}", "Content-Type": "application/json"}
    
    # Prepare the payload to match the structure in the provided curl
    payload = {
        "messages": [
            {"role": "system", "content": "You are a test assistant."},  # System message (you can modify this)
            {"role": "user", "content": text},  # User message
        ],
        "model": "grok-beta",  # Specify the model name (based on the curl example)
        "stream": False,  # Disable streaming (can be adjusted if needed)
        "temperature": 0,  # Control randomness in responses (0 for deterministic)
    }

    try:
        # Sending request to the Grok API
        async with httpx.AsyncClient() as client:
            response = await client.post(GROK_API_URL, headers=headers, json=payload)
            response.raise_for_status()  # Raise an exception for HTTP errors
            analysis_result = response.json()  # Parse the JSON response
            
        logger.info(f"Grok analysis result: {analysis_result}")
        return analysis_result
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred: {e}", exc_info=True)
        return {"error": f"HTTP error: {e.response.status_code}"}
    except Exception as e:
        logger.error(f"Grok API error: {e}", exc_info=True)
        return {"error": str(e)}

# Step 10: Test integration with the Grok API (GET request for testing)
@app.get("/test-grok")
async def test_grok():
    """
    Endpoint to test the integration with the Grok API.
    """
    logger.info("Testing Grok API integration...")
    headers = {"Authorization": f"Bearer {GROK_API_KEY}"}
    try:
        # Sending a test request to the Grok API
        async with httpx.AsyncClient() as client:
            response = await client.post(GROK_API_URL, headers=headers, json={"test": "ping"})
            response.raise_for_status()  # Raise an exception for HTTP errors
            logger.info(f"Grok API response: {response.json()}")
            return response.json()
    except Exception as e:
        logger.error(f"Grok API error: {e}", exc_info=True)
        return {"error": str(e)}

# Step 11: Test integration with HuggingFace API
@app.get("/test-huggingface")
async def test_huggingface():
    """
    Endpoint to test the connection with the HuggingFace API.
    """
    logger.info("Testing HuggingFace API integration...")
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(HUGGINGFACE_SPACE_URL, headers=headers)
            response.raise_for_status()  # Raise an exception for HTTP errors
            logger.info(f"HuggingFace response: {response.text}")
            return {"message": "HuggingFace connection successful"}
    except Exception as e:
        logger.error(f"HuggingFace API error: {e}", exc_info=True)
        return {"error": str(e)}

# Step 12: Test connection to MongoDB
@app.get("/test-mongo")
async def test_mongo():
    """
    Endpoint to test the connection to MongoDB.
    """
    logger.info("Testing MongoDB connection...")
    try:
        client = MongoClient(MONGO_URI)
        db = client.get_database()  # Connect to the database
        logger.info(f"MongoDB connected successfully. Database: {db.name}")
        return {"message": f"Connected to MongoDB: {db.name}"}
    except Exception as e:
        logger.error(f"MongoDB connection error: {e}", exc_info=True)
        return {"error": str(e)}

# Step 13: Middleware to log requests and responses, also logs unhandled errors
@app.middleware("http")
async def log_requests(request, call_next):
    """
    Middleware that logs all incoming HTTP requests and their responses.
    """
    logger.info(f"Request: {request.method} {request.url}")
    response = await call_next(request)
    logger.info(f"Response: {response.status_code}")
    return response
