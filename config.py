import os
from dotenv import load_dotenv

load_dotenv()  # Load .env file if it exists

# Step 1: Load all necessary environment variables - because we're not playing games here
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GROK_API_KEY = os.getenv('GROK_API_KEY')
GROK_API_URL = os.getenv('GROK_API_URL', "https://api.x.ai/v1/chat/completions")
MONGO_URI = os.getenv('MONGO_URI')
SOLANA_RPC_URL = os.getenv('SOLANA_RPC_URL')
CHIBI_NFT_ADDRESS = os.getenv('CHIBI_NFT_ADDRESS')
BITTY_NFT_ADDRESS = os.getenv('BITTY_NFT_ADDRESS')
