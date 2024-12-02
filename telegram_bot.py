import os
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from telegram.ext import Application
import httpx
from pymongo import MongoClient

# Step 1: Configure logging for the app, because we gotta keep track of everything!
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),  # Output logs to the console, so we can see what's popping.
    ],
)
logger = logging.getLogger("TelegramBotApp")

# Step 2: Utility function to load environment variables. It's like checking if you have everything before heading out.
def get_env_variable(var_name: str, required: bool = True):
    """
    This function gets your environment variable and checks if it's there.
    If it's required and missing, it'll stop you in your tracks.
    """
    value = os.getenv(var_name)
    if value:
        logger.info(f"Environment variable '{var_name}' loaded successfully. ✅")
    elif required:
        logger.error(f"Environment variable '{var_name}' is required but not set. 💥")
        raise ValueError(f"Missing required environment variable: {var_name}")
    else:
        logger.warning(f"Environment variable '{var_name}' is not set (but it's chill).")
    return value

# Step 3: Load all your environment variables like a pro, making sure you're ready to rock and roll.
TELEGRAM_BOT_TOKEN = get_env_variable('TELEGRAM_BOT_TOKEN')
GROK_API_KEY = get_env_variable('GROK_API_KEY')
GROK_API_URL = get_env_variable('GROK_API_URL')
JWK_PATH = get_env_variable('JWK_PATH')
HUGGINGFACE_API_TOKEN = get_env_variable('HUGGINGFACE_API_TOKEN')
HUGGINGFACE_SPACE_URL = get_env_variable('HUGGINGFACE_SPACE_URL')
RENDER_INTERMEDIARY_URL = get_env_variable('RENDER_INTERMEDIARY_URL')
RENDER_TG_BOT_WEBHOOK_URL = get_env_variable('RENDER_TG_BOT_WEBHOOK_URL')
MONGO_URI = get_env_variable('MONGO_URI')

# Step 4: Initialize your Telegram bot. Time to connect with the world, fam.
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# Step 5: FastAPI application setup with lifecycle management – just like keeping track of your vibes all day long.
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    This is where the app gets started and shut down like a well-oiled machine. The bot gets initialized, 
    the webhook gets set, and everything starts or stops as needed.
    """
    # Startup: Let’s kick things off.
    logger.info("Initializing Telegram bot app... 🔥")
    await application.initialize()
    logger.info("Telegram app initialized, all set to go! 🚀")

    logger.info("Starting the Telegram bot app... 🚀")
    await application.start()
    logger.info("Telegram bot started, we are live! 🔥")

    # Setting up the webhook: Gotta let Telegram know where to send those updates.
    webhook_url = f"{RENDER_TG_BOT_WEBHOOK_URL}/{TELEGRAM_BOT_TOKEN}"
    logger.info(f"Setting webhook with this URL: {webhook_url} 💥")
    try:
        await application.bot.set_webhook(url=webhook_url)
        logger.info("Webhook set successfully. 🏆")
    except Exception as e:
        logger.error(f"Failed to set webhook. 🛑 Error: {e}", exc_info=True)

    yield  # The app runs while it's up and running.

    # Shutdown: Time to wrap it up like a pro.
    logger.info("Shutting down Telegram bot app... 👋")
    await application.stop()
    logger.info("Telegram bot stopped. All done! ✅")

    logger.info("Cleaning up... ✨")
    await application.shutdown()
    logger.info("Telegram app shutdown complete. 👌")

# Step 6: Initialize FastAPI app with the lifecycle management from above.
app = FastAPI(lifespan=lifespan)

# Step 7: Health check endpoint – Just like checking if everything's working. ✨
@app.get("/")
async def health_check():
    """
    Health check endpoint to verify the service is up and running.
    Because hey, we gotta make sure we’re not down for the count.
    """
    logger.info("Health check initiated. Are we good to go? ✔️")
    return {"status": "ok", "message": "The app is alive and well!"}

# Step 8: Integrate with external services (like Grok and HuggingFace), because why not make this bot smarter? 🤖

# Test Grok API integration – let’s make sure we’re talking to the right people.
@app.get("/test-grok")
async def test_grok():
    """
    Test the connection to the Grok API. Gotta make sure it's all set up for data flow.
    """
    logger.info("Testing Grok API... 🧠")
    headers = {"Authorization": f"Bearer {GROK_API_KEY}"}
    try:
        response = httpx.post(GROK_API_URL, headers=headers, json={"test": "ping"})
        response.raise_for_status()  # Make sure it doesn't come back with an error.
        logger.info(f"Grok API response: {response.json()} 💬")
        return response.json()
    except Exception as e:
        logger.error(f"Grok API error: {e} 😔", exc_info=True)
        return {"error": str(e)}

# Test HuggingFace API connection – keeping things fresh with AI-powered insights.
@app.get("/test-huggingface")
async def test_huggingface():
    """
    Test HuggingFace API connection. Because AI is cool, right?
    """
    logger.info("Testing HuggingFace API... 🔥")
    headers = {"Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"}
    try:
        response = httpx.get(HUGGINGFACE_SPACE_URL, headers=headers)
        response.raise_for_status()
        logger.info(f"HuggingFace response: {response.text} 🚀")
        return {"message": "HuggingFace connection successful. AI power is real!"}
    except Exception as e:
        logger.error(f"HuggingFace API error: {e} 🤖", exc_info=True)
        return {"error": str(e)}

# Step 9: Test MongoDB connection – Gotta make sure we're storing stuff safely.
@app.get("/test-mongo")
async def test_mongo():
    """
    Test the MongoDB connection. Storing data is important – we don’t want to lose anything!
    """
    logger.info("Testing MongoDB connection... 🧑‍💻")
    try:
        client = MongoClient(MONGO_URI)
        db = client.get_database()
        logger.info(f"Connected to MongoDB. Database: {db.name} 📦")
        return {"message": f"Connected to MongoDB: {db.name}"}
    except Exception as e:
        logger.error(f"MongoDB connection error: {e} 💥", exc_info=True)
        return {"error": str(e)}

# Step 10: Middleware to log all incoming requests – gotta keep tabs on everything coming through. 👀
@app.middleware("http")
async def log_requests(request, call_next):
    """
    Logs all incoming requests and responses. Also catches errors if anything goes wrong.
    Like keeping track of every message in your inbox.
    """
    logger.info(f"Incoming request: {request.method} {request.url} 📡")
    try:
        # Process the request and send the response.
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code} for {request.url} ✅")
        return response
    except Exception as e:
        # If something goes wrong, we catch it and log it.
        logger.error(f"Unhandled error: {e} 🛑", exc_info=True)
        raise  # Re-raise the exception so FastAPI can handle it.

# Step 11: Ensure the app is listening on the right port. No excuses.
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))  # Default to port 8000 if it's not set.
    uvicorn.run(app, host="0.0.0.0", port=port)
