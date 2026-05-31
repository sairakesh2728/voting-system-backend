import datetime

class CandidateHelper:
    """Helper methods for Candidate document formatting."""

    @staticmethod
    def format_candidate(candidate_doc):
        """Formats a MongoDB candidate document for API responses."""
        if not candidate_doc:
            return None
            
        return {
            "id": str(candidate_doc.get("_id")),
            "election_id": str(candidate_doc.get("election_id")),
            "name": candidate_doc.get("name"),
            "party": candidate_doc.get("party"),
            "description": candidate_doc.get("description"),
            "photo_url": candidate_doc.get("photo_url", ""),
            "created_at": candidate_doc.get("created_at").isoformat() if isinstance(candidate_doc.get("created_at"), datetime.datetime) else candidate_doc.get("created_at")
        }
