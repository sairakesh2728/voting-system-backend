import datetime
import bcrypt
import jwt
from flask import current_app

class UserHelper:
    """Helper methods for User document validation, hashing, and token generation."""

    @staticmethod
    def hash_password(password):
        """Hashes a password using bcrypt."""
        if not password:
            raise ValueError("Password cannot be empty")
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    @staticmethod
    def check_password(password, hashed_password):
        """Verifies a password against its bcrypt hash."""
        if not password or not hashed_password:
            return False
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
        except Exception:
            return False

    @staticmethod
    def generate_token(user_id, expiration_hours=None):
        """Generates a JWT auth token for the user."""
        if expiration_hours is None:
            expiration_hours = current_app.config.get("JWT_EXPIRATION_HOURS", 24)
            
        payload = {
            "user_id": str(user_id),
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=expiration_hours),
            "iat": datetime.datetime.utcnow()
        }
        
        token = jwt.encode(
            payload, 
            current_app.config["SECRET_KEY"], 
            algorithm="HS256"
        )
        return token

    @staticmethod
    def format_user(user_doc):
        """Formats a MongoDB user document for safe public API JSON responses."""
        if not user_doc:
            return None
        return {
            "id": str(user_doc.get("_id")),
            "username": user_doc.get("username"),
            "email": user_doc.get("email"),
            "role": user_doc.get("role", "voter"),
            "voted_elections": [str(e_id) for e_id in user_doc.get("voted_elections", [])],
            "created_at": user_doc.get("created_at").isoformat() if isinstance(user_doc.get("created_at"), datetime.datetime) else user_doc.get("created_at")
        }
