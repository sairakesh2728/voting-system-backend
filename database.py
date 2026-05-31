import os
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from dotenv import load_dotenv

# Monkey-patch AsyncIOMotorClient to prevent Beanie crash due to missing append_metadata
# in some versions of Motor/PyMongo combination
if not hasattr(AsyncIOMotorClient, "append_metadata"):
    AsyncIOMotorClient.append_metadata = lambda *args, **kwargs: None

# Import models to register in Beanie
from models import User, Election, Participant

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb+srv://sairakesh2728_db_user:epHgT0QFMxFk4y4B@votingcluster.vafqjiy.mongodb.net/?appName=Votingcluster"
)

# Extract database name from connection string if present, otherwise default to voting_system
try:
    # Handle uri like mongodb://localhost:27017/voting_system
    db_name = MONGO_URI.split("/")[-1].split("?")[0]
    if not db_name:
        db_name = "voting_system"
except Exception:
    db_name = "voting_system"

# Global Motor client and database references
client = None
db = None

async def init_db():
    """Initialize the MongoDB connection and Beanie ODM."""
    global client, db
    print(f"Connecting to MongoDB database: {db_name}...")
    
    # Initialize Motor Async Client
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[db_name]
    
    # Initialize Beanie ODM
    await init_beanie(
        database=db,
        document_models=[User, Election, Participant]
    )
    print("[SUCCESS] MongoDB & Beanie ODM initialized successfully!")

def get_database():
    """Retrieve database instance."""
    return db

def get_client():
    """Retrieve MongoClient instance."""
    return client
