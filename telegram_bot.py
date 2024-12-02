# telegram_bot.py
from telegram.ext import Updater, MessageHandler, Filters, CommandHandler
import requests

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="Welcome! Send a prompt to generate an NFT.")

def generate_nft(update, context):
    prompt = update.message.text
    # URL for your Render.com service
    intermediary_url = "YOUR_RENDER_SERVICE_URL/generate"
    
    response = requests.post(intermediary_url, json={'prompt': prompt})
    
    if response.status_code == 200:
        data = response.json()
        if 'image' in data:
            context.bot.send_photo(chat_id=update.effective_chat.id, photo=data['image'])
        else:
            context.bot.send_message(chat_id=update.effective_chat.id, text="NFT generation failed.")
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="Something went wrong!")

def main():
    updater = Updater("YOUR_TELEGRAM_BOT_TOKEN", use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, generate_nft))
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
