# telegram_bot.py

import logging
from flask import Flask, request
from telegram.ext import Application, CommandHandler
from telegram.ext.filters import COMMAND
import os
import requests
import json
import asyncio
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.storage import MongoStorage

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# MongoDB Atlas connection string
MONGO_URI = os.getenv('MONGO_URI')

# Rate Limiting Setup with MongoDB
limiter = Limiter(
    app,
    key_func=get_remote_address,
    storage_uri=MONGO_URI,
    storage_options={
        "db_name": "rate_limit_db",  # Name of the database in MongoDB
        "collection_name": "rate_limits"  # Name of the collection
    },
    default_limits=["1 per minute"]
)

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
HUGGINGFACE_SPACE_URL = "https://finitoshi-chibi-bfl-flux-1-schnell.hf.space"

# Initialize Telegram bot using Application
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

def start(update, context):
    """Handler for /start command"""
    logger.info(f"Received /start command from user {update.effective_user.id}")
    context.bot.send_message(chat_id=update.effective_chat.id, text="Welcome! You can generate an NFT by using /generateimage <prompt>.")

@limiter.limit("1 per minute")  # Rate limit the generateimage command
async def generate_image_handler(update, context):
    """Handler for /generateimage command"""
    chat_id = update.effective_chat.id
    try:
        if not context.args:
            await context.bot.send_message(chat_id=chat_id, text="Please provide a prompt after the command. Example: /generateimage cute chibi robot")
            return

        prompt = " ".join(context.args)
        logger.info(f"Generating image for prompt: {prompt}")
        
        # Direct API call to Gradio for image generation
        response = requests.post(
            f"{HUGGINGFACE_SPACE_URL}/api/predict/",
            json={"param_0": prompt}
        )
        response.raise_for_status()
        result = response.json()
        
        if 'url' in result['data'][0]:
            await context.bot.send_photo(chat_id=chat_id, photo=result['data'][0]['url'])
            logger.info(f"Image sent to user {update.effective_user.id}")
        else:
            await context.bot.send_message(chat_id=chat_id, text="Failed to generate image. No URL found in response.")
            logger.error("Image generation failed, no URL in response")
    
    except requests.RequestException as e:
        await context.bot.send_message(chat_id=chat_id, text=f"Failed to generate image: {str(e)}")
        logger.error(f"Error in image generation: {str(e)}")

# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("generateimage", generate_image_handler))

@app.route('/' + TELEGRAM_BOT_TOKEN, methods=['POST'])
async def webhook_handler():
    """Handle incoming webhook updates from Telegram"""
    update = request.get_json()
    logger.info(f"Incoming webhook update: {update}")
    await application.process_update(update)  # Directly await the async function
    return "OK"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask server on port {port}")
    # Note: Flask doesn't support async out of the box for routes. Consider using an ASGI server for production if you're dealing with many async operations.
    app.run(host="0.0.0.0", port=port)
