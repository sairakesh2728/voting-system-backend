import os
from app import create_app

# Create Flask application instance
app = create_app()

if __name__ == "__main__":
    # Load running environment parameters
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_ENV", "development") == "development"
    
    print("=" * 60)
    print("Online Voting System Backend is starting...")
    print(f"Server is listening on: http://0.0.0.0:{port}")
    print(f"Debug Mode: {'ACTIVE' if debug_mode else 'INACTIVE'}")
    print("=" * 60)
    
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
