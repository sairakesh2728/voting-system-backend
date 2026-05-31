import urllib.parse
from pymongo import MongoClient

# Global variables for db and client
_client = None
_db = None

def get_db(app=None):
    """
    Returns the database instance.
    If an app is provided, loads the configuration from it.
    """
    global _client, _db
    if _db is not None:
        return _db

    if app:
        mongo_uri = app.config.get("MONGO_URI")
    else:
        import os
        from dotenv import load_dotenv
        load_dotenv()
        mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/voting_system")

    # Connect to MongoDB
    _client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)

    # Parse database name from URI, defaulting to 'voting_system'
    try:
        parsed_uri = urllib.parse.urlparse(mongo_uri)
        db_name = parsed_uri.path.strip("/")
        if not db_name:
            db_name = "voting_system"
    except Exception:
        db_name = "voting_system"

    _db = _client[db_name]
    return _db

def check_connection(db_instance):
    """Checks if the MongoDB database is reachable."""
    try:
        db_instance.client.admin.command("ping")
        return True
    except Exception:
        return False

def setup_indexes(db_instance):
    """Sets up the necessary indexes for uniqueness and performance."""
    try:
        # Create unique indexes on username and email in the users collection
        db_instance.users.create_index("username", unique=True)
        db_instance.users.create_index("email", unique=True)
        
        # Performance indexes for quick querying
        db_instance.candidates.create_index("election_id")
        db_instance.votes.create_index("election_id")
        db_instance.votes.create_index([("election_id", 1), ("candidate_id", 1)])
        return True
    except Exception as e:
        print(f"Error creating indexes: {e}")
        return False
