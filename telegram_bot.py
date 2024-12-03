import os
import logging
import asyncio
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import httpx
from pymongo import MongoClient
import json
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_fixed
from solana.publickey import PublicKey
from solana.rpc.api import Client
from solana.transaction import Transaction
from solana.message import Message

# Step 1: Configure logging for the app - because who doesn't love a good log?
logging.basicConfig(
    level=logging.DEBUG,  # We're all about that debug life, because who trusts code without debugging?
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("TelegramBotApp")

# Step 2: Utility function to load environment variables - adulting is hard, let's log it!
def get_env_variable(var_name: str, required: bool = True):
    value = os.getenv(var_name)
    if value:
        logger.info(f"Environment variable '{var_name}' loaded successfully. Yeet!")
    elif required:
        logger.error(f"Environment variable '{var_name}' is required but not set. Big oof!")
        raise ValueError(f"Missing required environment variable: {var_name}")
    else:
        logger.warning(f"Environment variable '{var_name}' is not set (optional). Meh.")
    return value

# Step 3: Load all necessary environment variables - 'cause we're not playing games here
TELEGRAM_BOT_TOKEN = get_env_variable('TELEGRAM_BOT_TOKEN')
GROK_API_KEY = get_env_variable('GROK_API_KEY')
GROK_API_URL = get_env_variable('GROK_API_URL', required=False) or "https://api.x.ai/v1/chat/completions"
MONGO_URI = get_env_variable('MONGO_URI')
BITTY_TOKEN_ADDRESS = get_env_variable('BITTY_TOKEN_ADDRESS')  # Token address for token gating
SOLANA_RPC_URL = get_env_variable('SOLANA_RPC_URL', required=False) or "https://api.mainnet-beta.solana.com"  # Default Solana RPC endpoint

# Step 4: Initialize MongoDB client and cache collection - let's cache some chill vibes
client = MongoClient(MONGO_URI)
db = client['bot_db']
cache_collection = db['cache']  # Here we store all the cool responses, so we don't have to keep asking Grok, like, all the time
nonce_collection = db['nonces']  # Nonces are like one-time use codes, but cooler and digital

# Step 5: Initialize the Telegram bot application - let's get this party started
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# Nonce expiry time - because we don't like stale snacks
NONCE_EXPIRY = timedelta(minutes=5)

def generate_nonce(user_id):
    nonce = os.urandom(32).hex()  # Generate 32 bytes of random data, then convert to hex because hex is where it's at
    expiry = datetime.utcnow() + NONCE_EXPIRY
    nonce_collection.update_one(
        {"user_id": user_id}, 
        {"$set": {"nonce": nonce, "expiry": expiry}}, 
        upsert=True
    )
    logger.info(f"Generated nonce for user {user_id}. Expires at {expiry}. Don't be late!")
    return nonce

def get_nonce(user_id):
    nonce_data = nonce_collection.find_one({"user_id": user_id})
    if nonce_data and nonce_data['expiry'] > datetime.utcnow():
        return nonce_data['nonce']
    else:
        nonce_collection.delete_one({"user_id": user_id})
        logger.info(f"Nonce expired or not found for user {user_id}. Time to get a new one, fam.")
        return None

# Step 6: FastAPI application with detailed lifecycle management - because we're fancy like that
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Telegram bot application... 🔥")
    await application.initialize()
    logger.info("Telegram application initialized, all set to go! 🚀")
    logger.info("Starting the Telegram bot application... 🚀")
    await application.start()  # Bot's ready to start flexing
    logger.info("Telegram bot started, we are live! 🔥")
    yield
    logger.info("Stopping Telegram bot application... 🚨")
    await application.stop()
    logger.info("Telegram bot stopped successfully. 🛑")
    logger.info("Shutting down Telegram bot application... 💤")
    await application.shutdown()
    logger.info("Telegram bot shutdown complete. ✅")

app = FastAPI(lifespan=lifespan)

# Step 7: Health check route - just to make sure we're not dead yet
@app.get("/")
async def health_check():
    logger.info("Health check endpoint accessed. Still alive, yo.")
    return {"status": "ok"}

# Step 8: Query Grok API and cache the response - 'cause we're all about that efficiency, no buffering
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))  # Retry 3 times with 2-second wait
async def query_grok(message):
    cached_response = cache_collection.find_one({
        "message": message,
        "persona": "Chibi",  # Cache key now includes persona for that personalized touch
        "cached_at": {"$gte": datetime.utcnow() - timedelta(seconds=60)}
    })

    if cached_response:
        logger.info("Returning cached response from Chibi. We're all about that low-latency life.")
        return cached_response['response']

    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "messages": [
            {
                "role": "system",
                "content": "You are Chibi, a new advanced AI bot. You're vibrant, witty, and highly advanced. Your responses should be infused with a playful, youthful energy, often using slang and modern internet culture references. You're here to help with a cool, tech-savvy attitude, but never forgetting your mission to assist and inform."
            },
            {"role": "user", "content": message}
        ],
        "model": "grok-beta",
        "stream": False,
        "temperature": 0.7  # Increased for more creative, Chibi-like responses
    }
    logger.info(f"Sending to Grok API as Chibi: {payload}. Let's see if Chibi's feeling chatty today.")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:  # Give Chibi a full minute to respond, patience is key
            response = await client.post(GROK_API_URL, headers=headers, json=payload)
            logger.info(f"Received response from Grok API as Chibi: Status code {response.status_code}")
            logger.debug(f"Response content: {response.text}")
            
            response.raise_for_status()  # This will raise an error for HTTP errors
            response_data = response.json()
            logger.info(f"Grok API response as Chibi: {response_data}")
            
            # Extract response from Grok API
            chibi_response = response_data.get('choices', [{}])[0].get('message', {}).get('content', "Chibi didn't respond properly. Guess AI has its off days too.")
            
            # Cache the response with persona
            cache_data = {
                "message": message,
                "persona": "Chibi",
                "response": chibi_response,
                "cached_at": datetime.utcnow()
            }
            cache_collection.insert_one(cache_data)
            return chibi_response
    except httpx.HTTPStatusError as e:
        # Log the specific HTTP error details
        logger.error(f"Grok API HTTP error while asking as Chibi: Status code {e.response.status_code}, Response: {e.response.text}. That's not very Chibi of you!")
        return "An error occurred while querying Chibi. #AIOops"
    except httpx.ReadTimeout:
        logger.error("Grok API request timed out while Chibi was thinking. Chibi must be on a coffee break.")
        return "Sorry, I'm taking longer than usual to respond. Try again in a bit, fam?"
    except Exception as e:
        # Log full exception traceback
        logger.error(f"Unexpected error with Grok API while asking as Chibi: {e}. Chibi's gone rogue!")
        logger.exception("Full exception details")
        return "An unexpected error occurred. Chibi's taking a nap, I guess. Zzz..."

# Step 9: Token gating - let's make sure only the cool cats get in
async def check_token_ownership(wallet_address):
    try:
        solana_client = Client(SOLANA_RPC_URL)
        user_wallet = PublicKey(wallet_address)
        token_balance = solana_client.get_token_account_balance(user_wallet, BITTY_TOKEN_ADDRESS)

        if token_balance and token_balance['result']['amount'] is not None:
            return int(token_balance['result']['amount']) > 0
        else:
            logger.warning(f"No token balance found for user {wallet_address} or token address {BITTY_TOKEN_ADDRESS}. Time to check your wallet, bro.")
            return False
    except Exception as e:
        logger.error(f"Error checking token ownership for user {wallet_address}: {e}. The blockchain gods are not pleased today.")
        return False

# Secure Signature Verification
async def verify_signature(wallet_address, message, signature):
    try:
        # Convert hex strings to bytes
        message_bytes = bytes.fromhex(message)
        signature_bytes = bytes.fromhex(signature)
        
        # Create a mock transaction for verification
        mock_transaction = Transaction().add(Message.new([PublicKey(wallet_address)], nonce=message_bytes))
        if mock_transaction.verify_signature(PublicKey(wallet_address), signature_bytes):
            return True
        else:
            return False
    except Exception as e:
        logger.error(f"Signature verification failed: {e}. Did you sign this with your eyes closed?")
        return False

# Step 10: Webhook handler for Telegram updates - where the magic happens
@app.post("/" + TELEGRAM_BOT_TOKEN)
async def handle_webhook(request: Request):
    update = await request.json()
    logger.info(f"Received update: {json.dumps(update, indent=2)}")  # Log the entire received update
    telegram_update = Update.de_json(update, application.bot)
    
    if telegram_update.message and telegram_update.message.text:
        message = telegram_update.message.text
        chat_id = telegram_update.message.chat_id
        
        if message.lower().startswith("/connect"):
            parts = message.split()
            if len(parts) > 1:
                wallet_address = parts[1]
                
                try:
                    PublicKey(wallet_address)  # This will raise an error if not a valid Solana address
                    nonce = generate_nonce(chat_id)
                    await application.bot.send_message(chat_id=chat_id, text=f"Please sign this nonce with your wallet: {nonce}. Then, send it back with /sign <your_signature>")
                except ValueError:
                    await application.bot.send_message(chat_id=chat_id, text="Invalid wallet address. Looks like you're trying to hack the mainframe. Try again with /connect <your_wallet_address>")
            else:
                await application.bot.send_message(chat_id=chat_id, text="Please provide your Solana wallet address with /connect <your_wallet_address>. Don't be shy, we don't bite... much.")
            return {"status": "ok"}

        if message.lower().startswith("/sign"):
            parts = message.split()
            if len(parts) > 1:
                signature = parts[1]
                expected_nonce = get_nonce(chat_id)
                if expected_nonce:
                    is_verified = await verify_signature(wallet_address, expected_nonce, signature)
                    if is_verified:
                        has_token = await check_token_ownership(wallet_address)
                        if has_token:
                            await application.bot.send_message(chat_id=chat_id, text="Wallet verified and token balance confirmed. Welcome to the club, fam!")
                            # User is now verified for future interactions
                            nonce_collection.delete_one({"user_id": chat_id})  # Clear nonce after successful verification
                        else:
                            await application.bot.send_message(chat_id=chat_id, text="You don't hold enough BITTY tokens to access this bot. Time to hit the crypto gym.")
                    else:
                        await application.bot.send_message(chat_id=chat_id, text="Signature verification failed. Did you try to cheat on the test?")
                else:
                    await application.bot.send_message(chat_id=chat_id, text="Your nonce has expired or is invalid. Please start with /connect again.")
            else:
                await application.bot.send_message(chat_id=chat_id, text="Please provide the signature with /sign <signature>. Don't make me wait!")
            return {"status": "ok"}

        # Check if user has been verified before processing further messages
        if get_nonce(chat_id) is None:  # User has no valid nonce, meaning they're verified or need to connect
            chibi_response = await query_grok(message)
            await application.bot.send_message(chat_id=chat_id, text=chibi_response)
        else:
            await application.bot.send_message(chat_id=chat_id, text="Please verify your wallet to continue. No freeloaders here!")

    return {"status": "ok"}

# Step 11: Middleware to log requests and responses - because we like to keep track of everything
@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"Incoming request: {request.method} {request.url}. What's up, internet?")
    try:
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code} for {request.url}. Peace out!")
        return response
    except Exception as e:
        logger.error(f"Unhandled error during request: {e}. This is why we can't have nice things!")
        raise

# Step 12: Ensure the application listens on the correct port - because we need to be heard
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))  # Default to 8000 if PORT is not set, 'cause we're flexible like that
    uvicorn.run(app, host="0.0.0.0", port=port)
