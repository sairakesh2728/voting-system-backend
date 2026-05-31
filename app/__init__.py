from flask import Flask, jsonify
from flask_cors import CORS
from app.config import Config
from app.db import get_db, setup_indexes

def create_app(config_class=Config):
    """Flask Application Factory."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize CORS
    # Allows cross-origin requests from the allowed origin (e.g. frontend)
    CORS(app, resources={r"/api/*": {"origins": app.config.get("CORS_ALLOWED_ORIGINS", "*")}})

    # Initialize Database on app start
    with app.app_context():
        try:
            db = get_db(app)
            setup_indexes(db)
            print(f"Connected to database: {db.name}")
        except Exception as e:
            print(f"CRITICAL: Failed to initialize database: {e}")

    # Register blueprints (to be imported and registered below)
    from app.routes.auth import auth_bp
    from app.routes.election import election_bp
    from app.routes.candidate import candidate_bp
    from app.routes.vote import vote_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(election_bp, url_prefix="/api/elections")
    app.register_blueprint(candidate_bp, url_prefix="/api/candidates")
    app.register_blueprint(vote_bp, url_prefix="/api/votes")

    # Global Error Handlers to return clean JSON
    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({"success": False, "error": "Bad Request", "message": str(error.description if hasattr(error, 'description') else error)}), 400

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({"success": False, "error": "Not Found", "message": "The requested resource was not found."}), 404

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({"success": False, "error": "Forbidden", "message": "You do not have permission to access this resource."}), 403

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({"success": False, "error": "Unauthorized", "message": "Authentication is required to access this resource."}), 401

    @app.errorhandler(500)
    def internal_server_error(error):
        return jsonify({"success": False, "error": "Internal Server Error", "message": "An unexpected error occurred on the server."}), 500

    @app.route("/health", methods=["GET"])
    def health_check():
        """Basic API health check endpoint."""
        db = get_db()
        from app.db import check_connection
        db_ok = check_connection(db)
        return jsonify({
            "status": "healthy" if db_ok else "unhealthy",
            "database": "connected" if db_ok else "disconnected",
            "service": "online_voting_system_backend"
        }), 200 if db_ok else 503

    return app
