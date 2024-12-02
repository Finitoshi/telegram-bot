# telegram_bot.py

from flask import Flask, request
from telegram.ext import Application, CommandHandler, MessageHandler
from telegram.ext.filters import TEXT, COMMAND
import os
import requests
import json

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
    context.bot.send_message(chat_id=update.effective_chat.id, text="Welcome! You can ask me questions or generate an NFT by sending a prompt.")

def generate_nft(update, context):
    """Handler for NFT generation"""
    prompt = update.message.text

    response = requests.post(RENDER_INTERMEDIARY_URL, json={'prompt': prompt})
    
    if response.status_code == 200:
        data = response.json()
        if 'image' in data:
            context.bot.send_photo(chat_id=update.effective_chat.id, photo=data['image'])
        else:
            context.bot.send_message(chat_id=update.effective_chat.id, text="NFT generation failed.")
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Something went wrong with NFT generation!")

async def ask_grok(update, context):
    """Handler for general messages using Grok API"""
    query = update.message.text

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
        "temperature": 0.7  # Adjust for creativity in responses, 0 for more deterministic
    }

    try:
        response = requests.post(GROK_API_URL, headers=headers, json=payload)
        response.raise_for_status()
        grok_response = response.json().get('choices', [{}])[0].get('message', {}).get('content', "I'm having a tough time thinking. Try again?")
        await context.bot.send_message(chat_id=update.effective_chat.id, text=grok_response)
    except requests.RequestException as e:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Sorry, I encountered an error: {str(e)}")

# Register handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(TEXT & ~COMMAND, ask_grok))  # This will handle general messages
application.add_handler(MessageHandler(TEXT & ~COMMAND, generate_nft))  # This will handle NFT generation

@app.route('/' + TELEGRAM_BOT_TOKEN, methods=['POST'])
async def webhook_handler():
    """Handle incoming webhook updates from Telegram"""
    update = request.get_json()
    await application.process_update(update)
    return "OK"

if __name__ == '__main__':
    # This will be set by Render.com
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port)
