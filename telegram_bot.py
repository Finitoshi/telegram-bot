import os
import logging
import asyncio
import random
import time
from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import httpx
from pymongo import MongoClient
from pymongo.errors import PyMongoError
import json
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_fixed, wait_exponential, retry_if_exception_type
from solana.publickey import PublicKey
from solana.rpc.api import Client
from solana.transaction import Transaction
from solana.message import Message
import base64
from dotenv import load_dotenv
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from typing import Optional
from urllib.parse import urlparse
import torch
from diffusers import FluxPipeline
from PIL import Image
import io

# Step 1: Configure logging - because if you're not logging, are you even coding?
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more detailed logging
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("TelegramBotApp")

# Load .env file if it exists - because adulting means keeping secrets safe
load_dotenv()

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
INTERMEDIARY_URL = get_env_variable('INTERMEDIARY_URL')
FLUX_KEY = get_env_variable('FLUX_KEY')  # New key for Hugging Face

# Step 4: Initialize MongoDB client and cache collection - let's cache some chill vibes
client = MongoClient(MONGO_URI)
db = client['bot_db']
cache_collection = db['cache']  # Here we store all the cool responses, so we don't have to keep asking Grok, like, all the time
nonce_collection = db['nonces']  # Nonces are like one-time use codes, but cooler and digital
# Indexing for performance - because even databases need their smoothie
cache_collection.create_index([('message', 1), ('persona', 1), ('cached_at', -1)])
nonce_collection.create_index('user_id', unique=True)

# Step 5: Initialize the Telegram bot application - let's get this party started
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# Nonce expiry time - because we don't like stale snacks
NONCE_EXPIRY = timedelta(minutes=5)

@retry(stop=stop_after_attempt(3), wait=wait_fixed(5), retry=retry_if_exception_type(PyMongoError))
def generate_nonce(user_id):
    """Generate a nonce for user authentication."""
    timestamp = int(datetime.utcnow().timestamp() * 1000)  # milliseconds since epoch for higher granularity
    random_part = os.urandom(16).hex()  # 16 bytes for randomness
    nonce = f"{timestamp}-{random_part}"
    expiry = datetime.utcnow() + NONCE_EXPIRY
    nonce_collection.update_one(
        {"user_id": user_id}, 
        {"$set": {"nonce": nonce, "expiry": expiry}}, 
        upsert=True
    )
    logger.info(f"Generated nonce for user {user_id}. Expires at {expiry}. Don't be late, or it's back to square one!")
    return nonce

@retry(stop=stop_after_attempt(3), wait=wait_fixed(5), retry=retry_if_exception_type(PyMongoError))
def get_nonce(user_id):
    """Retrieve nonce if not expired. For now, we're bypassing this check for testing."""
    # Bypassing nonce check for now
    return None

# Global variables for rate limiting, state management, and command control
last_image_time = {}
processing_image = {}
user_command_count = {}
image_generation_enabled = True  # Enable image generation for testing
MAX_COMMANDS_PER_MINUTE = 5

# Flux Pipeline Initialization
hf_client = FluxPipeline.from_pretrained("black-forest-labs/FLUX.1-schnell", torch_dtype=torch.bfloat16)
hf_client.enable_model_cpu_offload()  # For memory efficiency

# Step 6: FastAPI application with detailed lifecycle management - because we're fancy like that
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage the lifecycle of our app, because everything needs a start and an end."""
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

# Pydantic model for structuring incoming messages
class MessageModel(BaseModel):
    message: str
    persona: Optional[str] = "Chibi"

# Step 7: Health check route - just to make sure we're not dead yet
@app.get("/health")
async def health_check():
    """Check if the bot's alive or if it's time to call the ghostbusters."""
    logger.info("Health check endpoint accessed. We're still kicking!")
    return {"status": "OK"}

# Step 8: Query Grok API and cache the response - 'cause we're all about that efficiency, no buffering
@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
async def query_grok(message, persona="Chibi", model_id="grok-beta"):
    """Ask Grok the wise about life, the universe, and everything, with a touch of Chibi fun."""
    cached_response = cache_collection.find_one({
        "message": message,
        "persona": persona,  # Dynamic persona for caching
        "cached_at": {"$gte": datetime.utcnow() - timedelta(seconds=60)}
    })

    if cached_response:
        logger.info(f"Returning cached response from {persona}. Low-latency life, yo!")
        return cached_response['response']

    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "messages": [
            {
                "role": "system",
                "content": f"You are {persona}, a vibrant, witty AI with a playful, youthful energy. Infuse your responses with slang, internet culture, and a tech-savvy attitude. Here for fun, but always helpful!"
            },
            {"role": "user", "content": message}
        ],
        "model": model_id,
        "stream": False,
        "temperature": 0.9  # Higher for more playful responses
    }
    logger.info(f"Sending to Grok API as {persona} with model {model_id}: {payload}. Let's get this party started!")
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(GROK_API_URL, headers=headers, json=payload)
            logger.info(f"Received response from Grok API as {persona} with model {model_id}: Status code {response.status_code}")
            logger.debug(f"Response content: {response.text}")
            
            response.raise_for_status()  # This will raise an error for HTTP errors
            response_data = response.json()
            logger.info(f"Grok API response as {persona} with model {model_id}: {response_data}")
            
            # Extract response from Grok API
            chibi_response = response_data.get('choices', [{}])[0].get('message', {}).get('content', f"{persona} didn't respond properly. Guess AI has its off days too.")
            
            # Check if there's an image in the response
            if 'image' in response_data.get('choices', [{}])[0].get('message', {}):
                chibi_response += "\nImage generated: " + response_data['choices'][0]['message']['image']
            
            # Cache the response with persona
            cache_data = {
                "message": message,
                "persona": persona,
                "response": chibi_response,
                "cached_at": datetime.utcnow()
            }
            cache_collection.insert_one(cache_data)
            return chibi_response
    except httpx.HTTPStatusError as e:
        # Log the specific HTTP error details
        logger.error(f"Grok API HTTP error while asking as {persona} with model {model_id}: Status code {e.response.status_code}, Response: {e.response.text}. That's not very {persona} of you!")
        return f"An error occurred while querying {persona}. #AIOops"
    except httpx.ReadTimeout:
        logger.error(f"Grok API request timed out while {persona} with model {model_id} was thinking. {persona} must be on a coffee break.")
        return f"Sorry, I'm taking longer than usual to respond. Try again in a bit, fam?"
    except Exception as e:
        # Log full exception traceback
        logger.error(f"Unexpected error with Grok API while asking as {persona} with model {model_id}: {e}. {persona}'s gone rogue!")
        logger.exception("Full exception details")
        return f"An unexpected error occurred. {persona}'s taking a nap, I guess. Zzz..."

# Step 9: Image Generation - Let's make some cute robo-hippos!

# Define the fixed prompt with placeholders for rarity - because who doesn't love a rare robo-hippo?
BASE_PROMPT = "Imagine this baby robotic pygmy hippo, but with a manga twist. Think big, adorable eyes, a tiny, metallic body, and maybe some cute little robotic accessories like a {accessory}. Style: I'm thinking of that classic manga art style - clean lines, exaggerated features, and a touch of chibi for extra cuteness. Rarity: {rarity}"
# Define the accessories and rarities - because variety is the spice of robo-life
RARITY_LEVELS = {
    'common': ['a bow tie', 'a scarf'],
    'uncommon': ['a propeller hat', 'tiny wings'],
    'rare': ['a mini jetpack', 'a magic wand']
}

@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
def generate_image_prompt():
    """Craft a prompt for generating rad robo-hippo images."""
    rarity = random.choice(list(RARITY_LEVELS.keys()))
    accessory = random.choice(RARITY_LEVELS[rarity])
    prompt = BASE_PROMPT.format(accessory=accessory, rarity=rarity)
    logger.info(f"Generated image prompt: {prompt}. Let's see if we can whip up a rare robo-hippo!")
    return prompt

@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
async def send_prompt_to_intermediary(prompt):
    """
    Send the image generation prompt to an intermediary service for processing.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{INTERMEDIARY_URL}/predict", json={"prompt": prompt}, timeout=60.0)
            response.raise_for_status()
            return True, response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to send prompt to intermediary: HTTP error {e.response.status_code}. Did the robo-hippo escape?")
        return False, None
    except httpx.RequestError as e:
        logger.error(f"Network error while contacting intermediary: {e}")
        return False, None
    except Exception as e:
        logger.error(f"Unexpected error sending prompt to intermediary: {e}. Maybe the hippo got lost in transit.")
        return False, None

@retry(stop=stop_after_attempt(3), 
       wait=wait_exponential(multiplier=1, min=300, max=600),  # 5 minutes to 10 minutes
       retry=retry_if_exception_type(Exception))
async def generate_image_with_flux(prompt, chat_id):
    try:
        await application.bot.send_message(chat_id=chat_id, text="Hang tight! This could take a little while, but I'll definitely let you know when your image is ready! 😎")
        
        image = hf_client(
            prompt=prompt,
            guidance_scale=0.0,  # Required for FLUX.1-schnell
            height=512,  # Adjust based on your needs and available VRAM
            width=512,
            num_inference_steps=4,
            max_sequence_length=256  # Required for FLUX.1-schnell
        ).images[0]
        
        # Convert the image to bytes for Telegram
        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='PNG')
        return img_byte_arr.getvalue()
    except Exception as e:
        logger.error(f"Error during image generation with Flux: {e}")
        await application.bot.send_message(chat_id=chat_id, text="Oops, something didn't vibe right with the image generation. I'll give it another shot soon! 🤖")
        raise

# Step 10: Token gating - let's make sure only the cool cats get in
@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
async def check_token_ownership(wallet_address):
    """Check if someone's got enough of those sweet, sweet tokens."""
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
@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
async def verify_signature(wallet_address, message, signature):
    """Verify if this signature is legit or if someone's just scribbling."""
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

async def reset_command_count(chat_id):
    """Reset command count after some time."""
    await asyncio.sleep(60)
    if chat_id in user_command_count:
        user_command_count[chat_id] = 0

# Step 11: Webhook handler for Telegram updates - where the magic happens
@app.post(f"/{TELEGRAM_BOT_TOKEN}")
async def handle_webhook(request: Request):
    """Handle incoming Telegram messages because we need to keep the conversation flowing."""
    update = await request.json()
    logger.info(f"Received update: {json.dumps(update, indent=2)}")  # Log the entire received update
    telegram_update = Update.de_json(update, application.bot)
    
    if telegram_update.message and telegram_update.message.text:
        message = telegram_update.message.text
        chat_id = telegram_update.message.chat_id
        
        logger.info(f"Received message from user {chat_id}: {message}")
        
        # Command rate limiting
        if chat_id not in user_command_count:
            user_command_count[chat_id] = 0
        user_command_count[chat_id] += 1

        if user_command_count[chat_id] > MAX_COMMANDS_PER_MINUTE:
            await application.bot.send_message(chat_id=chat_id, text="Whoa, slow down! You've hit your command limit for now.")
            asyncio.create_task(reset_command_count(chat_id))
            return {"status": "ok"}

        # Bypassing nonce check for now
        if get_nonce(chat_id) is None:  # User has no valid nonce, meaning they're verified or we're bypassing verification
            if message.lower() in ["/generate_image_test", "/generate_test_image", "/generate_image"]:
                if chat_id in processing_image and processing_image[chat_id]:
                    await application.bot.send_message(chat_id=chat_id, text="Hold on, I'm already working on that image for you!")
                else:
                    processing_image[chat_id] = True
                    try:
                        logger.info(f"Attempting image generation with Flux for user {chat_id}")
                        prompt = generate_image_prompt()
                        await application.bot.send_message(chat_id=chat_id, text=f"Generating image with the prompt: {prompt}")
                        
                        try:
                            img_byte_arr = await generate_image_with_flux(prompt, chat_id)
                            await application.bot.send_photo(chat_id=chat_id, photo=img_byte_arr, caption="Here's your robo-hippo in all its glory!")
                        except Exception as e:
                            logger.error(f"Failed to generate image via Flux for user {chat_id}. Error: {str(e)}")
                    except Exception as e:
                        logger.error(f"General error during image generation process for user {chat_id}: {e}")
                        await application.bot.send_message(chat_id=chat_id, text="Something went wrong with image generation. Try again later?")
                    finally:
                        if chat_id in processing_image:
                            processing_image[chat_id] = False
            else:
                # For text-based queries, use the updated query_grok function
                chibi_response = await query_grok(message)
                await application.bot.send_message(chat_id=chat_id, text=chibi_response)
        else:
            await application.bot.send_message(chat_id=chat_id, text="Please verify your wallet to continue. No freeloaders here!")

    return {"status": "ok"}

# Middleware for logging requests and responses - because we like to keep track of everything
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        logger.info(f"Incoming request: {request.method} {request.url}. What's up, internet?")
        try:
            response = await call_next(request)
            logger.info(f"Response status: {response.status_code} for {request.url}. Peace out!")
            return response
        except Exception as e:
            logger.error(f"Unhandled error during request: {e}. This is why we can't have nice things!")
            raise

app.add_middleware(LoggingMiddleware)

# Error handler for validation errors - because we all make mistakes, even our users
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body},
    )

# Step 13: Ensure the application listens on the correct port - because we need to be heard
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))  # Default to 8000 if PORT is not set, 'cause we're flexible like that
    uvicorn.run(app, host="0.0.0.0", port=port)
