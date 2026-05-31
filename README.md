# Online Voting System Backend (Flask & MongoDB)

A secure, high-performance, and robust RESTful API backend for an Online Voting System built with **Flask**, **PyMongo (MongoDB)**, and **JSON Web Tokens (JWT)**.

This backend is designed with a **privacy-first anonymous ballot policy** (secrecy of the ballot) and features **atomic prevention of double voting** to eliminate race conditions. It is fully cross-origin resource sharing (CORS) compatible, enabling quick integration with your static frontend.

---

## Key Features

* 🔐 **JWT Token Authentication & Role-Based Authorization** (Voters vs. Administrators).
* 🗳️ **Atomic Double-Voting Prevention**: Utilizes race-condition-proof atomic queries inside MongoDB.
* 🕶️ **Ballot Anonymity**: Complete decoupling of voter identities from cast ballot sheets.
* 📅 **Election Activity Window Enforcement**: Enforces that votes can only be cast within active time boundaries (start date & end date).
* 📈 **Live Aggregate Election Results**: Uses highly optimized MongoDB aggregation pipelines to join candidate details and count votes in real-time.
* 🌐 **Full CORS Support**: Allows any frontend server to query and interact with the endpoints.

---

## Tech Stack

* **Framework:** Flask (Python 3.12+)
* **Database:** MongoDB (using PyMongo driver)
* **Security:** Bcrypt (Password Hashing) & PyJWT (Access Tokens)
* **Environment Configuration:** Python-Dotenv

---

## Project Structure

```text
Voting system backend/
│
├── venv/                       # isolated python environment
├── requirements.txt            # list of dependencies
├── .env                        # local environment parameters (hidden)
├── .gitignore                  # files to exclude from git
├── run.py                      # server launch script
├── test_connection.py          # database connectivity test helper
├── README.md                   # this documentation
│
└── app/                        # application source
    ├── __init__.py             # Flask App Factory & CORS mapping
    ├── config.py               # configuration loader
    ├── db.py                   # MongoDB setup and index configurations
    │
    ├── models/                 # serialization helpers
    │   ├── user.py
    │   ├── election.py
    │   ├── candidate.py
    │   └── __init__.py
    │
    ├── routes/                 # REST API blueprints
    │   ├── auth.py             # signup, login, profile
    │   ├── election.py         # election management
    │   ├── candidate.py        # candidate management
    │   ├── vote.py             # voting operations & aggregate results
    │   └── __init__.py
    │
    └── utils/                  # security middleware
        ├── auth_middleware.py  # token validators
        └── __init__.py
```

---

## Quickstart Guide

### 1. Prerequisite Checks
Make sure you have the Python launcher `py` installed (standard with Python installation on Windows).

### 2. Configure Environment Variables
We have already created a `.env` file for you in the root directory. To connect to a local MongoDB server or a cloud MongoDB Atlas instance, edit the `MONGO_URI` variable:
```ini
# Connect to local MongoDB:
MONGO_URI=mongodb://localhost:27017/voting_system

# OR Connect to MongoDB Atlas (Cloud):
# MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/voting_system?retryWrites=true&w=majority
```

If you want to use the provided Atlas SRV string directly, set:
```ini
MONGO_URI=mongodb+srv://sairakesh2728_db_user:epHgT0QFMxFk4y4B@votingcluster.vafqjiy.mongodb.net/?appName=Votingcluster
```

### 3. Install Dependencies
Install the required Python packages, including the SRV-enabled PyMongo driver:
```bash
python -m pip install -r requirements.txt
```

If you prefer to install only the Atlas DNS SRV driver directly:
```bash
python -m pip install "pymongo[srv]"
```

### 4. Verify Database Connectivity
Run the test script to ensure your database connection is valid and reachable. This script also automatically initializes the database indexes (such as unique constraints for email and username):
```bash
py test_connection.py
```

### 4. Start the Application Server
Run the Flask server:
```bash
py run.py
```
The server will boot up and listen on **`http://localhost:5000`**. You can verify it is online by visiting the health check in your browser: `http://localhost:5000/health`.

---

## API Documentation

All request bodies must be sent as JSON (`Content-Type: application/json`).

### 1. Authentication Endpoints

#### 📌 Register User
* **Method:** `POST`
* **Route:** `/api/auth/register`
* **Auth Required:** None (Public)
* **Request Body:**
```json
{
  "username": "rakesh_reddy",
  "email": "rakesh@example.com",
  "password": "securepassword123",
  "role": "voter" // Optional. Options: 'voter', 'admin' (defaults to 'voter')
}
```
* **Response (201 Created):**
```json
{
  "success": true,
  "message": "User registered successfully.",
  "user": {
    "id": "603dcc1d1b32f143c0ec5481",
    "username": "rakesh_reddy",
    "email": "rakesh@example.com",
    "role": "voter",
    "voted_elections": [],
    "created_at": "2026-05-29T04:15:33"
  }
}
```

#### 📌 Login User
* **Method:** `POST`
* **Route:** `/api/auth/login`
* **Auth Required:** None (Public)
* **Request Body:**
```json
{
  "username_or_email": "rakesh_reddy", // Can be username OR email
  "password": "securepassword123"
}
```
* **Response (200 OK):**
```json
{
  "success": true,
  "message": "Login successful.",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", // Use this token in Authorization headers
  "user": {
    "id": "603dcc1d1b32f143c0ec5481",
    "username": "rakesh_reddy",
    "email": "rakesh@example.com",
    "role": "voter",
    "voted_elections": []
  }
}
```

#### 📌 Get Current User Profile
* **Method:** `GET`
* **Route:** `/api/auth/profile`
* **Auth Required:** Yes (`Authorization: Bearer <token>`)
* **Response (200 OK):**
```json
{
  "success": true,
  "user": {
    "id": "603dcc1d1b32f143c0ec5481",
    "username": "rakesh_reddy",
    "email": "rakesh@example.com",
    "role": "voter",
    "voted_elections": []
  }
}
```

---

### 2. Election Endpoints

#### 📌 Create Election
* **Method:** `POST`
* **Route:** `/api/elections`
* **Auth Required:** Yes (Admin Only) (`Authorization: Bearer <token>`)
* **Request Body:**
```json
{
  "title": "Gitam Student Council Election 2026",
  "description": "Annual elections for Gitam Student Body Council representatives.",
  "start_date": "2026-05-29T00:00:00",
  "end_date": "2026-06-05T23:59:59",
  "is_active": true
}
```
* **Response (201 Created):**
```json
{
  "success": true,
  "message": "Election created successfully.",
  "election": {
    "id": "603dcc2d1b32f143c0ec5482",
    "title": "Gitam Student Council Election 2026",
    "description": "Annual elections for Gitam Student Body Council representatives.",
    "start_date": "2026-05-29T00:00:00",
    "end_date": "2026-06-05T23:59:59",
    "is_active": true,
    "created_at": "2026-05-29T04:16:12"
  }
}
```

#### 📌 List Elections
* **Method:** `GET`
* **Route:** `/api/elections`
* **Auth Required:** None (Public)
* **Query Parameters:**
  * `active` (boolean, optional): Set `/api/elections?active=true` to list only elections currently active based on system time and state.
* **Response (200 OK):**
```json
{
  "success": true,
  "count": 1,
  "elections": [
    {
      "id": "603dcc2d1b32f143c0ec5482",
      "title": "Gitam Student Council Election 2026",
      "description": "Annual elections for Gitam Student Body Council representatives.",
      "start_date": "2026-05-29T00:00:00",
      "end_date": "2026-06-05T23:59:59",
      "is_active": true
    }
  ]
}
```

---

### 3. Candidate Endpoints

#### 📌 Add Candidate
* **Method:** `POST`
* **Route:** `/api/candidates`
* **Auth Required:** Yes (Admin Only) (`Authorization: Bearer <token>`)
* **Request Body:**
```json
{
  "election_id": "603dcc2d1b32f143c0ec5482",
  "name": "Sai Rakesh Reddy",
  "party": "Innovation Alliance",
  "description": "Engineering student pledging for research grants and better lab equipment.",
  "photo_url": "https://example.com/photos/rakesh.jpg" // Optional
}
```
* **Response (201 Created):**
```json
{
  "success": true,
  "message": "Candidate added successfully to the election.",
  "candidate": {
    "id": "603dcc3d1b32f143c0ec5483",
    "election_id": "603dcc2d1b32f143c0ec5482",
    "name": "Sai Rakesh Reddy",
    "party": "Innovation Alliance",
    "description": "Engineering student pledging for research grants and better lab equipment.",
    "photo_url": "https://example.com/photos/rakesh.jpg",
    "created_at": "2026-05-29T04:17:15"
  }
}
```

#### 📌 Get Candidates
* **Method:** `GET`
* **Route:** `/api/candidates`
* **Auth Required:** None (Public)
* **Query Parameters:**
  * `election_id` (string, optional): `/api/candidates?election_id=603dcc2d1b32f143c0ec5482` gets only candidates running in that election.
* **Response (200 OK):**
```json
{
  "success": true,
  "count": 1,
  "candidates": [
    {
      "id": "603dcc3d1b32f143c0ec5483",
      "election_id": "603dcc2d1b32f143c0ec5482",
      "name": "Sai Rakesh Reddy",
      "party": "Innovation Alliance",
      "description": "Engineering student pledging for research grants and better lab equipment.",
      "photo_url": "https://example.com/photos/rakesh.jpg"
    }
  ]
}
```

---

### 4. Voting Endpoints

#### 📌 Cast An Anonymous Vote
* **Method:** `POST`
* **Route:** `/api/votes/cast`
* **Auth Required:** Yes (`Authorization: Bearer <token>`)
* **Request Body:**
```json
{
  "election_id": "603dcc2d1b32f143c0ec5482",
  "candidate_id": "603dcc3d1b32f143c0ec5483"
}
```
* **Response (201 Created):**
```json
{
  "success": true,
  "message": "Your vote has been securely and anonymously cast."
}
```
* **Common Error Responses:**
  * **409 Conflict:** If you have already voted in this election.
  * **403 Forbidden:** If the election hasn't started yet, has ended, or is deactivated.

#### 📌 View Live Election Results
* **Method:** `GET`
* **Route:** `/api/votes/results`
* **Auth Required:** None (Public)
* **Query Parameters:**
  * `election_id` (string, required): `/api/votes/results?election_id=603dcc2d1b32f143c0ec5482`
* **Response (200 OK):**
```json
{
  "success": true,
  "election_title": "Gitam Student Council Election 2026",
  "total_votes": 254,
  "results": [
    {
      "candidate_id": "603dcc3d1b32f143c0ec5483",
      "name": "Sai Rakesh Reddy",
      "party": "Innovation Alliance",
      "vote_count": 145
    },
    {
      "candidate_id": "603dcc4d1b32f143c0ec5484",
      "name": "Candidate B",
      "party": "Progressive Front",
      "vote_count": 109
    }
  ]
}
```

---

## How to Integrate with your Frontend

1. **Configure CORS**: The backend automatically allows request methods `GET`, `POST`, `OPTIONS`, `PUT`, `DELETE` from any origin.
2. **Storing JWT**: When your frontend logs in successfully, store the returned `token` in `localStorage` or `sessionStorage`.
3. **Attaching Headers**: For all authenticated requests (e.g., casting a vote or fetching user profile), add the token to the HTTP header:
   ```javascript
   headers: {
     'Content-Type': 'application/json',
     'Authorization': 'Bearer ' + storedToken
   }
   ```
4. **Live Dynamic Data**: Replace your React/HTML static state arrays with fetch calls to the corresponding backend GET endpoints (e.g., `fetch('http://localhost:5000/api/elections?active=true')`).
#   v o t i n g - s y s t e m - b a c k e n d  
 