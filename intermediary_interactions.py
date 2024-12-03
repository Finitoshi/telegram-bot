# This file is where the magic happens! It's like the middleman at a party, ensuring Chibi and the image gen app are on good terms. 

import os
import logging
from pymongo import MongoClient
import base64
import datetime
from gradio_client import Client
from io import BytesIO
import httpx
from telegram import Update
from telegram.ext import Application

# Step 1: Configure logging for the app - because who doesn't love a good log?
logging.basicConfig(
    level=logging.DEBUG,  # We're all about that debug life, because who trusts code without debugging?
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("ChibiImageGen")

# Environment variables - because secrets should stay secret, right?
INTERMEDIARY_URL = os.environ.get("INTERMEDIARY_URL")
HF_TOKEN = os.environ.get("HF_TOKEN")
MONGO_URI = os.environ.get("MONGO_URI")

# Connect to MongoDB - let's cache some chill vibes
mongo_client = MongoClient(MONGO_URI)
db = mongo_client['bot_db']
image_collection = db['images']  # Collection to store those manga masterpieces

# Connect to Gradio app - where the real art happens
gradio_client = Client("your-huggingface-space-name", hf_token=HF_TOKEN)

# Function to chat with the intermediary - like sending a secret message in a bottle
async def send_prompt_to_intermediary(prompt):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(INTERMEDIARY_URL, json={"prompt": prompt})
            response.raise_for_status()
            return True, response.json()
    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to send prompt to intermediary: HTTP error {e.response.status_code}. Looks like the bridge just collapsed!")
        return False, None
    except Exception as e:
        logger.error(f"Unexpected error sending prompt to intermediary: {e}. The universe might be glitching, try again!")
        return False, None

# In handle_webhook or wherever you're processing user requests - this is where we decide if it's image time!
if "image" in message.lower() or "comic" in message.lower():
    prompt = await generate_image_prompt(message)
    await application.bot.send_message(chat_id=chat_id, text="Generating a detailed prompt for your image request... Hang tight, fam!")
    
    success, response = await send_prompt_to_intermediary(prompt)
    if success:
        await application.bot.send_message(chat_id=chat_id, text=f"Image generation initiated! Check back soon for your manga magic. This could be the next big thing!")
    else:
        await application.bot.send_message(chat_id=chat_id, text="Oops! Failed to start image generation. Try again later. Technology, am I right?")
