# telegram_bot.py

from flask import Flask, request
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, Dispatcher
import os
import requests

app = Flask(__name__)

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
RENDER_INTERMEDIARY_URL = os.getenv('RENDER_INTERMEDIARY_URL')

# Initialize Telegram bot
updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

def start(update, context):
    """Handler for /start command"""
    context.bot.send_message(chat_id=update.effective_chat.id, text="Welcome! Send a prompt to generate an NFT.")

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
        context.bot.send_message(chat_id=update.effective_chat.id, text="Something went wrong!")

# Register handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, generate_nft))

@app.route('/' + TELEGRAM_BOT_TOKEN, methods=['POST'])
def webhook_handler():
    """Handle incoming webhook updates from Telegram"""
    update = request.get_json()
    dispatcher.process_update(update)
    return "OK"

if __name__ == '__main__':
    # This will be set by Render.com
    port = int(os.environ.get('PORT', 5000))
    app.run(host="0.0.0.0", port=port)
