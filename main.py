import os
import random
import string
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List, Optional

import jwt
from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from beanie import PydanticObjectId

# Database configuration and schemas
from database import init_db
from models import (
    User,
    Election,
    Participant,
    UserSignUp,
    UserResponse,
    Token,
    ElectionCreate,
    ElectionResponse,
    JoinElectionRequest,
    ParticipantResponse,
)

# Load environment variables
load_dotenv()

# JWT Config
JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_voting_key_2026_antigravity")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", 24))

# Password hashing setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict) -> str:
    """Generate JWT containing email and id in the payload."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_access_token(token: str) -> Optional[dict]:
    """Decode JWT access token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None


# ---------------------------------------------------------
# Lifecycle Context (FastAPI Lifespan)
# ---------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB and Beanie ODM
    await init_db()
    yield
    # Shutdown (No special shutdown hooks required for Motor/Beanie)


# Initialize FastAPI app
app = FastAPI(
    title="Voting System REST API",
    description="Production-ready FastAPI backend for Voting System Android application.",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------
# CORS Middleware Setup
# ---------------------------------------------------------
cors_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "*")
cors_origins = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# OAuth2 Security & User Authentication Dependency
# ---------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """Dependency to retrieve currently authenticated user from JWT."""
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    email = payload.get("email") or payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    user = await User.find_one(User.email == email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------
async def generate_unique_election_code() -> str:
    """Generate a unique 6-digit uppercase alphanumeric election code."""
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choices(alphabet, k=6))
        # Ensure code uniqueness across database
        exists = await Election.find_one(Election.election_code == code)
        if not exists:
            return code


# =========================================================
# API Endpoints
# =========================================================

# --- Root Endpoint ---
@app.get("/", tags=["General"])
async def root():
    return {
        "status": "online",
        "message": "Voting System REST API is running successfully.",
        "docs_url": "/docs"
    }


# --- Auth Endpoints ---
@app.post(
    "/auth/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"],
)
async def signup(user_data: UserSignUp):
    """Register a new user with standard bcrypt password hashing."""
    # Check duplicate email
    existing_user = await User.find_one(User.email == user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
        
    # Hash password & Save
    hashed = hash_password(user_data.password)
    user = User(
        name=user_data.name,
        email=user_data.email,
        password_hash=hashed,
    )
    await user.insert()
    return user


@app.post("/auth/login", response_model=Token, tags=["Authentication"])
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Authenticate credentials and generate a secure JWT access token."""
    # Lookup user by email (represented as form_data.username)
    user = await User.find_one(User.email == form_data.username)
    if user is None or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Include both email and ID in payload for client-side convenience
    token_payload = {
        "sub": user.email,
        "id": str(user.id),
        "email": user.email,
    }
    access_token = create_access_token(data=token_payload)
    
    # Structure details to simplify client application ingestion
    user_response = UserResponse(
        id=str(user.id),
        name=user.name,
        email=user.email,
        created_at=user.created_at,
    )
    
    return Token(access_token=access_token, user=user_response)


# --- Elections Endpoints ---
@app.post(
    "/elections/create",
    response_model=ElectionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Elections"],
)
async def create_election(
    election_data: ElectionCreate,
    current_user: User = Depends(get_current_user)
):
    """Create a new election (Restricted to logged-in users)."""
    # Generate unique 6-digit code
    code = await generate_unique_election_code()
    
    # Save the election
    election = Election(
        name=election_data.name,
        creator_email=current_user.email,
        date=election_data.date,
        time=election_data.time,
        election_code=code,
        candidates=election_data.candidates,
    )
    await election.insert()
    return election


@app.get(
    "/elections/my-elections",
    response_model=List[ElectionResponse],
    tags=["Elections"],
)
async def my_elections(current_user: User = Depends(get_current_user)):
    """Fetch elections created by the currently authenticated user."""
    elections = await Election.find(Election.creator_email == current_user.email).to_list()
    return elections


# --- Participation Endpoints ---
@app.post(
    "/elections/join",
    response_model=ParticipantResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Participation"],
)
async def join_election(
    join_data: JoinElectionRequest,
    current_user: User = Depends(get_current_user)
):
    """Join an election using a 6-digit election code."""
    # 1. Verify election exists
    election = await Election.find_one(Election.election_code == join_data.election_code)
    if election is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Election not found with code {join_data.election_code}",
        )
        
    # 2. Verify user has not already joined this election
    already_joined = await Participant.find_one(
        Participant.user_id == current_user.id,
        Participant.election_id == election.id
    )
    if already_joined:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already joined this election",
        )
        
    # 3. Create join participant record
    participant = Participant(
        user_id=current_user.id,
        election_id=election.id,
        full_name=join_data.full_name,
        id_number=join_data.id_number,
        election_code=election.election_code,
    )
    await participant.insert()
    return participant


@app.get(
    "/elections/joined",
    response_model=List[ElectionResponse],
    tags=["Participation"],
)
async def joined_elections(current_user: User = Depends(get_current_user)):
    """Fetch all elections the current user has joined."""
    # Find all join records for the current user
    join_records = await Participant.find(Participant.user_id == current_user.id).to_list()
    
    # Extract corresponding election_ids
    election_ids = [record.election_id for record in join_records]
    
    # Bulk fetch elections matching those IDs
    if not election_ids:
        return []
        
    joined_elections = await Election.find({"_id": {"$in": election_ids}}).to_list()
    return joined_elections


# --- Admin Endpoints ---
@app.get(
    "/elections/{election_id}/participants",
    response_model=List[ParticipantResponse],
    tags=["Admin"],
)
async def list_participants(
    election_id: str,
    current_user: User = Depends(get_current_user)
):
    """List all participants for a specific election (Restricted to election creator)."""
    # 1. Parse and validate election_id format
    try:
        obj_id = PydanticObjectId(election_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid election ID format",
        )
        
    # 2. Retrieve election
    election = await Election.get(obj_id)
    if election is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found",
        )
        
    # 3. Verify current user is indeed the election creator
    if election.creator_email != current_user.email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized access: You are not the creator of this election",
        )
        
    # 4. Fetch all participants for this election
    participants = await Participant.find(Participant.election_id == obj_id).to_list()
    return participants


# Run application direct execution handler
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting FastAPI on port {port}...")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
