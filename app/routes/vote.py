import datetime
from flask import Blueprint, request, jsonify
from app.db import get_db
from app.utils.auth_middleware import token_required
from bson.objectid import ObjectId

vote_bp = Blueprint("vote", __name__)

@vote_bp.route("/cast", methods=["POST"])
@token_required
def cast_vote(current_user):
    """Cast a secure, anonymous vote in an election."""
    data = request.get_json() or {}
    
    election_id_str = data.get("election_id", "").strip()
    candidate_id_str = data.get("candidate_id", "").strip()

    if not election_id_str or not candidate_id_str:
        return jsonify({
            "success": False,
            "error": "Bad Request",
            "message": "Election ID and Candidate ID are required fields."
        }), 400

    if not ObjectId.is_valid(election_id_str) or not ObjectId.is_valid(candidate_id_str):
        return jsonify({
            "success": False,
            "error": "Bad Request",
            "message": "Invalid Election ID or Candidate ID format."
        }), 400

    db = get_db()
    now = datetime.datetime.utcnow()

    # 1. Verify election exists and is currently active
    election = db.elections.find_one({"_id": ObjectId(election_id_str)})
    if not election:
        return jsonify({
            "success": False,
            "error": "Not Found",
            "message": "Election not found."
        }), 404

    if not election.get("is_active", True):
        return jsonify({
            "success": False,
            "error": "Forbidden",
            "message": "This election has been deactivated."
        }), 403

    if now < election["start_date"]:
        return jsonify({
            "success": False,
            "error": "Forbidden",
            "message": f"This election has not started yet. Starts at: {election['start_date'].isoformat()}"
        }), 403

    if now > election["end_date"]:
        return jsonify({
            "success": False,
            "error": "Forbidden",
            "message": "This election has already ended."
        }), 403

    # 2. Verify candidate exists and belongs to this election
    candidate = db.candidates.find_one({
        "_id": ObjectId(candidate_id_str),
        "election_id": ObjectId(election_id_str)
    })
    if not candidate:
        return jsonify({
            "success": False,
            "error": "Not Found",
            "message": "Candidate not found in this election."
        }), 404

    try:
        # 3. Double-voting prevention: Atomically add the election_id to user's voted_elections
        # only if it is NOT already in the list. This avoids race-conditions.
        user_id = ObjectId(current_user["id"])
        election_id = ObjectId(election_id_str)
        
        result = db.users.update_one(
            {
                "_id": user_id, 
                "voted_elections": {"$ne": election_id}
            },
            {
                "$push": {"voted_elections": election_id}
            }
        )

        # If modified_count is 0, the user had already voted in this election (i.e. election_id is in their list)
        if result.modified_count == 0:
            return jsonify({
                "success": False,
                "error": "Conflict",
                "message": "You have already cast a vote in this election."
            }), 409

        # 4. Insert the anonymous vote
        db.votes.insert_one({
            "election_id": election_id,
            "candidate_id": ObjectId(candidate_id_str),
            "timestamp": now
        })

        return jsonify({
            "success": True,
            "message": "Your vote has been securely and anonymously cast."
        }), 201

    except Exception as e:
        # Fallback/Rollback: If inserting the vote fails, remove the election from the user's list
        try:
            db.users.update_one(
                {"_id": user_id},
                {"$pull": {"voted_elections": election_id}}
            )
        except Exception:
            pass
            
        return jsonify({
            "success": False,
            "error": "Internal Server Error",
            "message": f"Failed to cast vote: {str(e)}"
        }), 500


@vote_bp.route("/results", methods=["GET"])
def get_results():
    """Get live election results using an aggregation pipeline."""
    election_id_str = request.args.get("election_id", "").strip()

    if not election_id_str:
        return jsonify({
            "success": False,
            "error": "Bad Request",
            "message": "Election ID is a required parameter."
        }), 400

    if not ObjectId.is_valid(election_id_str):
        return jsonify({
            "success": False,
            "error": "Bad Request",
            "message": "Invalid Election ID format."
        }), 400

    db = get_db()
    election_id = ObjectId(election_id_str)

    # Verify election exists
    election = db.elections.find_one({"_id": election_id})
    if not election:
        return jsonify({
            "success": False,
            "error": "Not Found",
            "message": "Election not found."
        }), 404

    try:
        # Aggregate votes
        pipeline = [
            {"$match": {"election_id": election_id}},
            {"$group": {"_id": "$candidate_id", "vote_count": {"$sum": 1}}},
            # Join with candidates details
            {
                "$lookup": {
                    "from": "candidates",
                    "localField": "_id",
                    "foreignField": "_id",
                    "as": "candidate_info"
                }
            },
            {"$unwind": {"path": "$candidate_info", "preserveNullAndEmptyArrays": True}},
            # Project final fields
            {
                "$project": {
                    "_id": 0,
                    "candidate_id": {"$toString": "$_id"},
                    "vote_count": 1,
                    "name": {"$ifNull": ["$candidate_info.name", "Unknown Candidate"]},
                    "party": {"$ifNull": ["$candidate_info.party", "Independent"]}
                }
            },
            # Sort by vote count descending
            {"$sort": {"vote_count": -1}}
        ]

        results = list(db.votes.aggregate(pipeline))

        # Also find candidates with 0 votes to return them in results as well
        all_candidates = list(db.candidates.find({"election_id": election_id}))
        candidates_with_votes = {r["candidate_id"] for r in results}

        for candidate in all_candidates:
            cand_id_str = str(candidate["_id"])
            if cand_id_str not in candidates_with_votes:
                results.append({
                    "candidate_id": cand_id_str,
                    "vote_count": 0,
                    "name": candidate.get("name", "Unknown Candidate"),
                    "party": candidate.get("party", "Independent")
                })

        # Re-sort because we appended candidates with 0 votes
        results.sort(key=lambda x: x["vote_count"], reverse=True)

        # Count total votes cast
        total_votes = db.votes.count_documents({"election_id": election_id})

        return jsonify({
            "success": True,
            "election_title": election.get("title"),
            "total_votes": total_votes,
            "results": results
        }), 200

    except Exception as e:
        return jsonify({
            "success": False,
            "error": "Internal Server Error",
            "message": f"Failed to calculate results: {str(e)}"
        }), 500
