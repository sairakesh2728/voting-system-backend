import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

class Config:
    """Base configuration class."""
    SECRET_KEY = os.environ.get("JWT_SECRET", "super_secret_voting_key_2026_antigravity")
    MONGO_URI = os.environ.get(
        "MONGO_URI",
        "mongodb+srv://sairakesh2728_db_user:epHgT0QFMxFk4y4B@votingcluster.vafqjiy.mongodb.net/?appName=Votingcluster"
    )
    JWT_EXPIRATION_HOURS = int(os.environ.get("JWT_EXPIRATION_HOURS", 24))
    CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "*")
    FLASK_ENV = os.environ.get("FLASK_ENV", "development")
    DEBUG = FLASK_ENV == "development"
