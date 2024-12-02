# telegram_bot.py

import logging
from flask import Flask, request, g
from telegram.ext import Application, CommandHandler, MessageHandler
from telegram.ext.filters import TEXT, COMMAND
import os
import requests
import json
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Rate Limiting Setup
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["1 per minute"],
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
def generate_image_handler(update, context):
    """Handler for /generateimage command"""
    chat_id = update.effective_chat.id
    try:
        if len(context.args) < 1:
            context.bot.send_message(chat_id=chat_id, text="Please provide a prompt after the command. Example: /generateimage cute chibi robot")
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
            context.bot.send_photo(chat_id=chat_id, photo=result['data'][0]['url'])
            logger.info(f"Image sent to user {update.effective_user.id}")
        else:
            context.bot.send_message(chat_id=chat_id, text="Failed to generate image. No URL found in response.")
            logger.error("Image generation failed, no URL in response")
    
    except requests.RequestException as e:
        context.bot.send_message(chat_id=chat_id, text=f"Failed to generate image: {str(e)}")
        logger.error(f"Error in image generation: {str(e)}")

# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("generateimage", generate_image_handler))

@app.route('/' + TELEGRAM_BOT_TOKEN, methods=['POST'])
def webhook_handler():
    """Handle incoming webhook updates from Telegram"""
    update = request.get_json()
    logger.info(f"Incoming webhook update: {update}")
    application.process_update(update)  # Process updates synchronously
    return "OK"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host="0.0.0.0", port=port)
