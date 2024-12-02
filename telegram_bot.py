import logging
import os
import time
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from telegram.ext import Application, CommandHandler
from telegram.ext.filters import COMMAND
from pymongo import MongoClient
import asyncio
import aiohttp
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# FastAPI app instance
app = FastAPI()

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MONGO_URI = os.getenv("MONGO_URI")
HUGGINGFACE_SPACE_URL = os.getenv("HUGGINGFACE_SPACE_URL")

if not TELEGRAM_BOT_TOKEN or not MONGO_URI or not HUGGINGFACE_SPACE_URL:
    raise EnvironmentError("Missing one or more critical environment variables.")

# MongoDB setup
client = MongoClient(MONGO_URI)
db = client.rate_limit_db
rate_limits = db.rate_limits

# Initialize Telegram bot
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# Utility: Rate limiting function
def custom_rate_limit(key: str, limit: int, period: int) -> bool:
    """
    Rate limiter with MongoDB.
    """
    now = time.time()
    record = rate_limits.find_one({"key": key})
    if not record or record["last_reset"] < now - period:
        rate_limits.update_one(
            {"key": key},
            {"$set": {"count": 1, "last_reset": now}},
            upsert=True,
        )
        return True

    if record["count"] >= limit:
        return False

    rate_limits.update_one({"key": key}, {"$inc": {"count": 1}})
    return True

# Command Handlers
async def start(update, context):
    """Handler for /start command."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Welcome! Use /generateimage <prompt> to create an NFT.",
    )

async def generate_image_handler(update, context):
    """Handler for /generateimage command."""
    chat_id = update.effective_chat.id
    if not context.args:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Please provide a prompt. Example: /generateimage cute chibi robot",
        )
        return

    prompt = " ".join(context.args)
    logger.info(f"Generating image for prompt: {prompt}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{HUGGINGFACE_SPACE_URL}/api/predict/",
                json={"param_0": prompt},
            ) as response:
                if response.status != 200:
                    raise HTTPException(status_code=response.status, detail="Image generation failed.")
                result = await response.json()

        image_url = result.get("data", [{}])[0].get("url")
        if image_url:
            await context.bot.send_photo(chat_id=chat_id, photo=image_url)
            logger.info(f"Image sent to user {update.effective_user.id}")
        else:
            await context.bot.send_message(chat_id=chat_id, text="Failed to generate image. No URL found.")
            logger.error("Image generation failed, no URL in response")

    except Exception as e:
        logger.error(f"Error generating image: {e}")
        await context.bot.send_message(chat_id=chat_id, text="An error occurred while generating the image.")

# Register Handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("generateimage", generate_image_handler))

# FastAPI webhook handler
@app.post(f"/{TELEGRAM_BOT_TOKEN}")
async def webhook_handler(request: Request):
    """Handle incoming webhook updates from Telegram."""
    update = await request.json()
    user_id = update.get("message", {}).get("from", {}).get("id")
    if not user_id:
        logger.error("Missing user ID in the update.")
        raise HTTPException(status_code=400, detail="Invalid update payload.")

    key = f"user:{user_id}"
    if not custom_rate_limit(key, limit=1, period=60):
        logger.warning(f"Rate limit exceeded for user {user_id}")
        return {"status": "Rate limit exceeded", "code": 429}

    try:
        await application.process_update(update)
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")

    return {"status": "OK"}

# Main entry point
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
