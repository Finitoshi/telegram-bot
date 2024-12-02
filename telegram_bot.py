# telegram_bot.py

from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, Dispatcher
from flask import Flask, request
import requests
import os

app = Flask(__name__)

# Environment variables for configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # This will be the URL provided by Render.com
PORT = int(os.getenv('PORT', 5000))  # Render uses 10000 by default but can be adjusted

# Telegram bot setup
updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
dispatcher = updater.dispatcher

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Welcome! Send a prompt to generate an NFT.")

def generate_nft(update, context):
    prompt = update.message.text
    # URL for your Render.com service or another intermediary service
    intermediary_url = os.getenv('INTERMEDIARY_URL', 'YOUR_INTERMEDIARY_URL')
    
    response = requests.post(intermediary_url, json={'prompt': prompt})
    
    if response.status_code == 200:
        data = response.json()
        if 'image' in data:
            context.bot.send_photo(chat_id=update.effective_chat.id, photo=data['image'])
        else:
            context.bot.send_message(chat_id=update.effective_chat.id, text="NFT generation failed.")
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Something went wrong!")

# Command handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, generate_nft))

# Webhook handling
@app.route('/' + TELEGRAM_BOT_TOKEN, methods=['POST'])
def webhook_handler():
    update = request.get_json()
    dispatcher.process_update(update)
    return "OK"

if __name__ == '__main__':
    # Start the Flask server
    app.run(host="0.0.0.0", port=PORT)
