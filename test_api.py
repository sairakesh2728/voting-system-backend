import os
import random
import string
import sys
from fastapi.testclient import TestClient

# Import main FastAPI application
from main import app
from models import User, Election, Participant

def generate_random_string(length=8):
    """Generate a random lowercase string."""
    letters = string.ascii_lowercase
    return "".join(random.choices(letters, k=length))

def run_tests():
    print("=" * 60)
    print("FastAPI + Beanie ODM API Integration Verification")
    print("=" * 60)

    # Use TestClient with 'with' context to trigger FastAPI lifespan (DB connection & init)
    try:
        with TestClient(app) as client:
            print("[1/6] Database Connection & Initialization: OK")
            
            # Generate test user details
            random_suffix = generate_random_string()
            test_email = f"user_{random_suffix}@example.com"
            test_password = "securepassword123"
            test_name = f"Test User {random_suffix.upper()}"
            
            # ---------------------------------------------------------
            # 1. Sign Up Test
            # ---------------------------------------------------------
            print("\n[2/6] Testing Sign Up...")
            signup_data = {
                "name": test_name,
                "email": test_email,
                "password": test_password
            }
            response = client.post("/auth/signup", json=signup_data)
            assert response.status_code == 201, f"Signup failed: {response.text}"
            signup_res = response.json()
            assert signup_res["email"] == test_email
            assert signup_res["name"] == test_name
            assert "id" in signup_res
            assert "password_hash" not in signup_res
            print(f" -> SUCCESS: User registered with ID {signup_res['id']}")

            # Try duplicate signup
            response = client.post("/auth/signup", json=signup_data)
            assert response.status_code == 400, "Duplicate signup should have failed"
            print(" -> SUCCESS: Prevented duplicate registration")

            # ---------------------------------------------------------
            # 2. Login Test
            # ---------------------------------------------------------
            print("\n[3/6] Testing Login...")
            # OAuth2 Password Flow uses form data (x-www-form-urlencoded)
            login_data = {
                "username": test_email,
                "password": test_password
            }
            response = client.post("/auth/login", data=login_data)
            assert response.status_code == 200, f"Login failed: {response.text}"
            login_res = response.json()
            assert "access_token" in login_res
            assert login_res["token_type"] == "bearer"
            assert login_res["user"]["email"] == test_email
            
            # Extract access token and verify details inside the token
            token = login_res["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            print(" -> SUCCESS: Access Token obtained")

            # ---------------------------------------------------------
            # 3. Create Election Test
            # ---------------------------------------------------------
            print("\n[4/6] Testing Election Creation...")
            election_data = {
                "name": f"Presidential Election {generate_random_string(3).upper()}",
                "date": "2026-06-15",
                "time": "08:00",
                "candidates": [
                    {
                        "name": "Alice Smith",
                        "photo_url": "https://example.com/alice.jpg",
                        "symbol_url": "https://example.com/star.png"
                    },
                    {
                        "name": "Bob Jones",
                        "photo_url": "https://example.com/bob.jpg",
                        "symbol_url": "https://example.com/shield.png"
                    }
                ]
            }
            response = client.post("/elections/create", json=election_data, headers=headers)
            assert response.status_code == 201, f"Election creation failed: {response.text}"
            election_res = response.json()
            election_code = election_res["election_code"]
            election_id = election_res["id"]
            assert len(election_code) == 6
            assert election_res["creator_email"] == test_email
            assert len(election_res["candidates"]) == 2
            print(f" -> SUCCESS: Election '{election_res['name']}' created with unique join code: {election_code}")

            # Verify "My Elections" list
            response = client.get("/elections/my-elections", headers=headers)
            assert response.status_code == 200
            my_elections_res = response.json()
            assert any(el["id"] == election_id for el in my_elections_res)
            print(" -> SUCCESS: Election appears in creator's 'My Elections' list")

            # ---------------------------------------------------------
            # 4. Join Election Test
            # ---------------------------------------------------------
            print("\n[5/6] Testing Joining Election...")
            join_data = {
                "election_code": election_code,
                "full_name": test_name,
                "id_number": f"VOTER-{generate_random_string(4).upper()}"
            }
            response = client.post("/elections/join", json=join_data, headers=headers)
            assert response.status_code == 201, f"Join election failed: {response.text}"
            join_res = response.json()
            assert join_res["election_code"] == election_code
            assert join_res["full_name"] == test_name
            print(f" -> SUCCESS: Joined election using code {election_code} successfully")

            # Verify joining same election twice fails
            response = client.post("/elections/join", json=join_data, headers=headers)
            assert response.status_code == 400, "Double join should have failed"
            print(" -> SUCCESS: Prevented double joining of same election (400 Bad Request)")

            # Verify "Joined Elections" list
            response = client.get("/elections/joined", headers=headers)
            assert response.status_code == 200
            joined_list = response.json()
            assert any(el["id"] == election_id for el in joined_list)
            print(" -> SUCCESS: Joined election appears in 'Joined Elections' list")

            # ---------------------------------------------------------
            # 5. List Participants (Admin) Test
            # ---------------------------------------------------------
            print("\n[6/6] Testing List Participants (Creator/Admin)...")
            response = client.get(f"/elections/{election_id}/participants", headers=headers)
            assert response.status_code == 200, f"List participants failed: {response.text}"
            participants = response.json()
            assert len(participants) == 1
            assert participants[0]["full_name"] == test_name
            print(f" -> SUCCESS: Creator retrieved participant list containing voter {test_name}")

            # Verify that unauthorized user cannot fetch participants
            # Generate another user
            unauthorized_suffix = generate_random_string()
            unauth_email = f"unauth_{unauthorized_suffix}@example.com"
            unauth_password = "password123"
            
            client.post("/auth/signup", json={
                "name": "Unauthorized User",
                "email": unauth_email,
                "password": unauth_password
            })
            unauth_login = client.post("/auth/login", data={
                "username": unauth_email,
                "password": unauth_password
            }).json()
            
            unauth_headers = {"Authorization": f"Bearer {unauth_login['access_token']}"}
            response = client.get(f"/elections/{election_id}/participants", headers=unauth_headers)
            assert response.status_code == 401, "Should return 401 unauthorized for non-creators"
            print(" -> SUCCESS: Restrict participant retrieval to election creator only (401 Unauthorized)")

            print("\n" + "=" * 60)
            print(" ALL TESTS PASSED SUCCESSFULLY! ")
            print("=" * 60)
            
    except AssertionError as ae:
        print(f"\n[FAIL] Assertion failed during test verification: {ae}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
