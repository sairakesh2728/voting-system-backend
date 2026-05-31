import datetime
from flask import Blueprint, request, jsonify
from app.db import get_db
from app.models.candidate import CandidateHelper
from app.utils.auth_middleware import token_required, admin_required
from bson.objectid import ObjectId

candidate_bp = Blueprint("candidate", __name__)

@candidate_bp.route("", methods=["POST"])
@token_required
@admin_required
def add_candidate(current_user):
    """Add a candidate to an election (Admin only)."""
    data = request.get_json() or {}
    
    election_id_str = data.get("election_id", "").strip()
    name = data.get("name", "").strip()
    party = data.get("party", "").strip()
    description = data.get("description", "").strip()
    photo_url = data.get("photo_url", "").strip()

    if not election_id_str or not name or not party or not description:
        return jsonify({
            "success": False,
            "error": "Bad Request",
            "message": "Election ID, candidate name, party, and description are required fields."
        }), 400

    if not ObjectId.is_valid(election_id_str):
        return jsonify({
            "success": False,
            "error": "Bad Request",
            "message": "Invalid election ID format."
        }), 400

    db = get_db()
    
    # Verify election exists
    election = db.elections.find_one({"_id": ObjectId(election_id_str)})
    if not election:
        return jsonify({
            "success": False,
            "error": "Not Found",
            "message": "The specified election does not exist."
        }), 404

    try:
        candidate_document = {
            "election_id": ObjectId(election_id_str),
            "name": name,
            "party": party,
            "description": description,
            "photo_url": photo_url,
            "created_at": datetime.datetime.utcnow()
        }

        result = db.candidates.insert_one(candidate_document)
        candidate_document["_id"] = result.inserted_id

        return jsonify({
            "success": True,
            "message": "Candidate added successfully to the election.",
            "candidate": CandidateHelper.format_candidate(candidate_document)
        }), 201

    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Internal Server Error",
            "message": f"Failed to add candidate: {str(e)}"
        }), 500


@candidate_bp.route("", methods=["GET"])
def get_candidates():
    """Get candidates. Optionally filter by 'election_id' parameter."""
    election_id_str = request.args.get("election_id", "").strip()
    
    db = get_db()
    query = {}
    
    if election_id_str:
        if not ObjectId.is_valid(election_id_str):
            return jsonify({
                "success": False,
                "error": "Bad Request",
                "message": "Invalid election ID format."
            }), 400
        query["election_id"] = ObjectId(election_id_str)

    try:
        candidates_cursor = db.candidates.find(query).sort("name", 1)
        candidates = [CandidateHelper.format_candidate(c) for c in candidates_cursor]
        
        return jsonify({
            "success": True,
            "count": len(candidates),
            "candidates": candidates
        }), 200
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Internal Server Error",
            "message": f"Failed to fetch candidates: {str(e)}"
        }), 500
