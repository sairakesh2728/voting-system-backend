import datetime

class ElectionHelper:
    """Helper methods for Election document formatting and validation."""

    @staticmethod
    def format_election(election_doc):
        """Formats a MongoDB election document for API responses."""
        if not election_doc:
            return None
            
        return {
            "id": str(election_doc.get("_id")),
            "title": election_doc.get("title"),
            "description": election_doc.get("description"),
            "start_date": election_doc.get("start_date").isoformat() if isinstance(election_doc.get("start_date"), datetime.datetime) else election_doc.get("start_date"),
            "end_date": election_doc.get("end_date").isoformat() if isinstance(election_doc.get("end_date"), datetime.datetime) else election_doc.get("end_date"),
            "is_active": election_doc.get("is_active", True),
            "created_at": election_doc.get("created_at").isoformat() if isinstance(election_doc.get("created_at"), datetime.datetime) else election_doc.get("created_at")
        }
