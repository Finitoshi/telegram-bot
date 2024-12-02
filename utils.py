import logging
from pymongo import MongoClient
from datetime import datetime, timedelta

# Step 2: Configure logging for the app - because who doesn't love a good log?
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("TelegramBotApp")

# Step 3: Utility functions - because we're all about that efficiency, no buffering

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

# MongoDB setup - let's cache some chill vibes
client = MongoClient(MONGO_URI)
db = client['bot_db']
cache_collection = db['cache']
