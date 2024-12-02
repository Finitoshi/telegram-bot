# telegram_bot.py

import logging
from flask import Flask, request
from telegram.ext import Application, CommandHandler, MessageHandler
from telegram.ext.filters import TEXT, COMMAND
import os
import requests
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
RENDER_INTERMEDIARY_URL = os.getenv('RENDER_INTERMEDIARY_URL')
GROK_API_KEY = os.getenv('GROK_API_KEY')
GROK_API_URL = os.getenv('GROK_API_URL')

# Initialize Telegram bot using Application
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

def start(update, context):
    """Handler for /start command"""
    logger.info(f"Received /start command from user {update.effective_user.id}")
    context.bot.send_message(chat_id=update.effective_chat.id, text="Welcome! You can ask me questions or generate an NFT by sending a prompt.")

def generate_nft(update, context):
    """Handler for NFT generation"""
    prompt = update.message.text
    logger.info(f"Generating NFT for prompt: {prompt}")

    try:
        response = requests.post(RENDER_INTERMEDIARY_URL, json={'prompt': prompt})
        response.raise_for_status()
        data = response.json()
        if 'image' in data:
            context.bot.send_photo(chat_id=update.effective_chat.id, photo=data['image'])
            logger.info(f"NFT Image sent to user {update.effective_user.id}")
        else:
            context.bot.send_message(chat_id=update.effective_chat.id, text="NFT generation failed.")
            logger.error("NFT generation failed, no image in response")
    except requests.RequestException as e:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Something went wrong with NFT generation!")
        logger.error(f"Error in NFT generation: {str(e)}")

async def ask_grok(update, context):
    """Handler for general messages using Grok API"""
    query = update.message.text
    logger.info(f"User {update.effective_user.id} asked Grok: {query}")

    headers = {
        'Authorization': f'Bearer {GROK_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        "messages": [
            {
                "role": "system",
                "content": "You are Grok, an AI with a sense of humor and helpfulness, providing answers with wit and insight."
            },
            {
                "role": "user",
                "content": query
            }
        ],
        "model": "grok-beta",
        "stream": False,
        "temperature": 0.7
    }

    try:
        response = requests.post(GROK_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        grok_response = response.json().get('choices', [{}])[0].get('message', {}).get('content', "I'm having a tough time thinking. Try again?")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=grok_response)
        logger.info(f"Grok responded to user {update.effective_user.id}")
    except requests.RequestException as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Sorry, I encountered an error: {str(e)}")
        logger.error(f"Grok API error: {str(e)}")

# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(TEXT & ~COMMAND, ask_grok))  # This will handle general messages
application.add_handler(MessageHandler(TEXT & ~COMMAND, generate_nft))  # This will handle NFT generation

@app.route('/' + TELEGRAM_BOT_TOKEN, methods=['POST'])
def webhook_handler():
    """Handle incoming webhook updates from Telegram"""
    update = request.get_json()
    logger.info(f"Incoming webhook update: {update}")
    application.update_queue.put(update)  # This should be synchronous
    return "OK"

if __name__ == '__main__':
    # This will be set by Render.com
    port = int(os.environ.get('PORT', 5000))
    logger.info(f"Starting Flask server on port {port}")
    app.run(host="0.0.0.0", port=port)
