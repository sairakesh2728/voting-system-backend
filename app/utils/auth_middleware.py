from functools import wraps
import jwt
from flask import request, jsonify, current_app
from app.db import get_db
from bson.objectid import ObjectId

def token_required(f):
    """Decorator to secure API endpoints with JWT authentication."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Check for Authorization header
        if "Authorization" in request.headers:
            auth_header = request.headers["Authorization"]
            # Support both "Bearer <token>" and raw "<token>"
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
            else:
                token = auth_header

        if not token:
            return jsonify({
                "success": False,
                "error": "Unauthorized",
                "message": "Authentication token is missing."
            }), 401

        try:
            # Decode the token
            payload = jwt.decode(
                token, 
                current_app.config["SECRET_KEY"], 
                algorithms=["HS256"]
            )
            
            # Fetch user from database
            db = get_db()
            current_user = db.users.find_one({"_id": ObjectId(payload["user_id"])})
            
            if not current_user:
                return jsonify({
                    "success": False,
                    "error": "Unauthorized",
                    "message": "User not found or account has been deleted."
                }), 401

            # Convert ObjectId to string for easy JSON usage later
            current_user["_id"] = str(current_user["_id"])
            # Remove password hash for security
            current_user.pop("password_hash", None)

        except jwt.ExpiredSignatureError:
            return jsonify({
                "success": False,
                "error": "Unauthorized",
                "message": "Token has expired. Please log in again."
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                "success": False,
                "error": "Unauthorized",
                "message": "Invalid authentication token."
            }), 401
        except Exception as e:
            return jsonify({
                "success": False,
                "error": "Unauthorized",
                "message": f"Token verification failed: {str(e)}"
            }), 401

        return f(current_user, *args, **kwargs)

    return decorated

def admin_required(f):
    """Decorator to restrict access to admin users only. Must be used AFTER @token_required."""
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        if current_user.get("role") != "admin":
            return jsonify({
                "success": False,
                "error": "Forbidden",
                "message": "Access denied. Admin privileges required."
            }), 403
        return f(current_user, *args, **kwargs)
    return decorated
