import sys
from app.db import get_db, check_connection, setup_indexes

def main():
    print("=" * 60)
    print("MongoDB Connection Tester")
    print("=" * 60)
    
    print("Connecting to database using environment configurations...")
    try:
        db = get_db()
        # Fetch the URI being used (with passwords masked if any)
        from app.config import Config
        uri = Config.MONGO_URI
        # Mask password in printing if cluster URI
        masked_uri = uri
        if "@" in uri:
            parts = uri.split("@")
            prefix = parts[0].split("://")
            masked_uri = f"{prefix[0]}://*****:*****@{parts[1]}"
        
        print(f"Target Database: {db.name}")
        print(f"Connection URI: {masked_uri}")
        
        print("\nPinging MongoDB...")
        if check_connection(db):
            print("[SUCCESS] Connected successfully to MongoDB!")
            
            print("\nSetting up database indexes...")
            if setup_indexes(db):
                print("[SUCCESS] Database indexes verified and set up successfully!")
            else:
                print("[WARNING] Could not set up indexes. Check database permissions.")
                
            print("=" * 60)
            print("Status: Database is READY.")
            print("=" * 60)
            sys.exit(0)
        else:
            print("[FAILURE] Failed to connect to MongoDB.")
            print("\nPossible solutions:")
            print("1. If running locally, check if MongoDB service is started.")
            print("   In Windows PowerShell (as Admin): Start-Service MongoDB")
            print("2. If using MongoDB Atlas, check if your IP address is whitelisted in Atlas.")
            print("3. Verify your connection string and credentials in the '.env' file.")
            print("=" * 60)
            sys.exit(1)
            
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred: {e}")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()
