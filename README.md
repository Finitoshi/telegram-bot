# Telegram Bot with NFT Gated Access

Welcome to the coolest bot in town, where your NFTs determine how much fun you can have. Yeet!

## Setup
1. **Install Dependencies**: Run `pip install -r requirements.txt`  
2. **Environment Variables**: Set up your `.env` file with:
   - `TELEGRAM_BOT_TOKEN`
   - `GROK_API_KEY`
   - `GROK_API_URL`
   - `MONGO_URI`
   - `SOLANA_RPC_URL`
   - `CHIBI_NFT_ADDRESS`
   - `BITTY_NFT_ADDRESS`

## Running the Bot
- `uvicorn src.main:app --reload` for development or deploy to your server of choice.

## Features
- **Basic Access**: No NFTs? No problem, get some basic replies.
- **Chibi NFT Access**: Free convo with Grok. It's like having a smart friend, but cooler.
- **Bitty NFT Access**: Get all Chibi perks plus vision capabilities. See the world through Grok's eyes, literally.

## Troubleshooting
- If the bot's not responding, check if Grok's taking a nap or if your NFTs are in the wrong wallet. Big oof if they are!
