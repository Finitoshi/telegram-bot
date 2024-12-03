# set_webhook.py

import os
import requests

# Load environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
RENDER_TG_BOT_WEBHOOK_URL = os.getenv('RENDER_TG_BOT_WEBHOOK_URL')

def set_webhook():
    """Set the webhook for the Telegram bot"""
    webhook_url = f"{RENDER_TG_BOT_WEBHOOK_URL}/{TELEGRAM_BOT_TOKEN}"
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
    
    response = requests.post(api_url, data={'url': webhook_url})
    
    if response.status_code == 200:
        print("Webhook set successfully:", response.json())
    else:
        print("Failed to set webhook:", response.text)

if __name__ == '__main__':
    set_webhook()
