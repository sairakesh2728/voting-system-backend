import datetime
from flask import Blueprint, request, jsonify
from app.db import get_db
from app.models.user import UserHelper
from app.utils.auth_middleware import token_required

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a new user."""
    data = request.get_json() or {}
    
    username = data.get("username", "").strip()
    email = data.get("email", "").strip()
    password = data.get("password", "")
    role = data.get("role", "voter").strip().lower()

    # Basic validations
    if not username or not email or not password:
        return jsonify({
            "success": False,
            "error": "Bad Request",
            "message": "Username, email, and password are required fields."
        }), 400

    if role not in ["voter", "admin"]:
        role = "voter"

    db = get_db()

    # Check if username or email already exists
    if db.users.find_one({"username": username}):
        return jsonify({
            "success": False,
            "error": "Conflict",
            "message": "Username is already registered."
        }), 409

    if db.users.find_one({"email": email}):
        return jsonify({
            "success": False,
            "error": "Conflict",
            "message": "Email is already registered."
        }), 409

    try:
        # Hash password and save user
        password_hash = UserHelper.hash_password(password)
        
        user_document = {
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "role": role,
            "voted_elections": [],
            "created_at": datetime.datetime.utcnow()
        }

        result = db.users.insert_one(user_document)
        user_document["_id"] = result.inserted_id

        return jsonify({
            "success": True,
            "message": "User registered successfully.",
            "user": UserHelper.format_user(user_document)
        }), 201

    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Internal Server Error",
            "message": f"Registration failed: {str(e)}"
        }), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    """Voter or Admin Login."""
    data = request.get_json() or {}
    
    login_identifier = data.get("username_or_email", "").strip()
    # Also support separate username/email fields
    if not login_identifier:
        login_identifier = data.get("username", "").strip() or data.get("email", "").strip()
        
    password = data.get("password", "")

    if not login_identifier or not password:
        return jsonify({
            "success": False,
            "error": "Bad Request",
            "message": "Username/email and password are required fields."
        }), 400

    db = get_db()

    # Search user by username OR email
    user = db.users.find_one({
        "$or": [
            {"username": login_identifier},
            {"email": login_identifier}
        ]
    })

    if not user or not UserHelper.check_password(password, user.get("password_hash")):
        return jsonify({
            "success": False,
            "error": "Unauthorized",
            "message": "Invalid username/email or password."
        }), 401

    try:
        # Generate token
        token = UserHelper.generate_token(user["_id"])
        
        return jsonify({
            "success": True,
            "message": "Login successful.",
            "token": token,
            "user": UserHelper.format_user(user)
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Internal Server Error",
            "message": f"Login failed: {str(e)}"
        }), 500


@auth_bp.route("/profile", methods=["GET"])
@token_required
def profile(current_user):
    """Get authenticated user profile."""
    # current_user is already formatted and password_hash stripped by the middleware
    return jsonify({
        "success": True,
        "user": current_user
    }), 200
