import datetime
from flask import Blueprint, request, jsonify
from app.db import get_db
from app.models.election import ElectionHelper
from app.utils.auth_middleware import token_required, admin_required
from bson.objectid import ObjectId

election_bp = Blueprint("election", __name__)

@election_bp.route("", methods=["POST"])
@token_required
@admin_required
def create_election(current_user):
    """Create a new election (Admin only)."""
    data = request.get_json() or {}
    
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    start_date_str = data.get("start_date")
    end_date_str = data.get("end_date")
    is_active = data.get("is_active", True)

    if not title or not description or not start_date_str or not end_date_str:
        return jsonify({
            "success": False,
            "error": "Bad Request",
            "message": "Title, description, start_date, and end_date are required fields."
        }), 400

    try:
        # Parse ISO datetime strings
        # Supports format like '2026-05-29T09:00:00' or with timezone '2026-05-29T09:00:00.000Z'
        try:
            start_date = datetime.datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
            end_date = datetime.datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        except ValueError:
            # Fallback to standard formats
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
                try:
                    start_date = datetime.datetime.strptime(start_date_str, fmt)
                    end_date = datetime.datetime.strptime(end_date_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                raise ValueError("Invalid date format. Use ISO 8601 format.")

        # Ensure start is before end
        if start_date >= end_date:
            return jsonify({
                "success": False,
                "error": "Bad Request",
                "message": "Start date must be before end date."
            }), 400

        db = get_db()
        election_document = {
            "title": title,
            "description": description,
            "start_date": start_date,
            "end_date": end_date,
            "is_active": bool(is_active),
            "created_at": datetime.datetime.utcnow()
        }

        result = db.elections.insert_one(election_document)
        election_document["_id"] = result.inserted_id

        return jsonify({
            "success": True,
            "message": "Election created successfully.",
            "election": ElectionHelper.format_election(election_document)
        }), 201

    except ValueError as ve:
        return jsonify({
            "success": False,
            "error": "Bad Request",
            "message": str(ve)
        }), 400
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Internal Server Error",
            "message": f"Failed to create election: {str(e)}"
        }), 500


@election_bp.route("", methods=["GET"])
def get_elections():
    """Get all elections. Supports optional 'active' query parameter filter."""
    active_only = request.args.get("active", "").lower() == "true"
    
    db = get_db()
    query = {}
    
    if active_only:
        now = datetime.datetime.utcnow()
        query = {
            "is_active": True,
            "start_date": {"$lte": now},
            "end_date": {"$gte": now}
        }

    try:
        elections_cursor = db.elections.find(query).sort("start_date", -1)
        elections = [ElectionHelper.format_election(e) for e in elections_cursor]
        
        return jsonify({
            "success": True,
            "count": len(elections),
            "elections": elections
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Internal Server Error",
            "message": f"Failed to fetch elections: {str(e)}"
        }), 500


@election_bp.route("/<id>", methods=["GET"])
def get_election_by_id(id):
    """Get election by ID."""
    if not ObjectId.is_valid(id):
        return jsonify({
            "success": False,
            "error": "Bad Request",
            "message": "Invalid election ID format."
        }), 400

    db = get_db()
    try:
        election = db.elections.find_one({"_id": ObjectId(id)})
        if not election:
            return jsonify({
                "success": False,
                "error": "Not Found",
                "message": "Election not found."
            }), 404

        return jsonify({
            "success": True,
            "election": ElectionHelper.format_election(election)
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Internal Server Error",
            "message": f"Failed to fetch election details: {str(e)}"
        }), 500
