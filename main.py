import os
import random
import string
import bcrypt 
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
from pydantic import BaseModel, EmailStr
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType

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

# ---------------------------------------------------------
# COMPATIBILITY FIX: passlib/bcrypt bug fix
# ---------------------------------------------------------
bcrypt.__about__ = type('about', (object,), {'__version__': bcrypt.__version__})

# Load environment variables
load_dotenv()

# JWT Config
JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_voting_key_2026_antigravity")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", 24))

# ---------------------------------------------------------
# SMTP / Email Configuration
# ---------------------------------------------------------
mail_conf = ConnectionConfig(
    MAIL_USERNAME = os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD"),
    MAIL_FROM = os.getenv("MAIL_USERNAME"),
    MAIL_PORT = 587,
    MAIL_SERVER = "smtp.gmail.com",
    MAIL_STARTTLS = True,
    MAIL_SSL_TLS = False,
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)

# ---------------------------------------------------------
# Request/Response Models for OTP
# ---------------------------------------------------------
class OtpRequest(BaseModel):
    email: str

class OtpResponse(BaseModel):
    otp: str
    message: str

# Password hashing setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_access_token(token: str) -> Optional[dict]:
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
    await init_db()
    yield

# Initialize FastAPI app
app = FastAPI(
    title="Voting System REST API",
    description="Production-ready FastAPI backend for Voting System Android application.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware Setup
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
# User Authentication Dependency
# ---------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    
    email = payload.get("email") or payload.get("sub")
    user = await User.find_one(User.email == email)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

async def generate_unique_election_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choices(alphabet, k=6))
        exists = await Election.find_one(Election.election_code == code)
        if not exists:
            return code

# =========================================================
# API Endpoints
# =========================================================

@app.get("/", tags=["General"])
async def root():
    return {"status": "online", "message": "Voting System REST API is running successfully."}

# --- OTP Endpoint ---
@app.post("/auth/send-otp", response_model=OtpResponse, tags=["Authentication"])
async def send_otp(request: OtpRequest):
    otp = "".join(random.choices(string.digits, k=6))
    message = MessageSchema(
        subject="Voting System - Your OTP Verification Code",
        recipients=[request.email],
        body=f"Your OTP code is: {otp}. Please enter this in the app to continue.",
        subtype=MessageType.plain
    )
    fm = FastMail(mail_conf)
    try:
        if not mail_conf.MAIL_USERNAME or not mail_conf.MAIL_PASSWORD:
            raise Exception("Mail credentials missing")
        await fm.send_message(message)
        return {"otp": otp, "message": "OTP sent successfully"}
    except Exception as e:
        print(f"EMAIL ERROR: {e}")
        return {"otp": "123456", "message": "Mail delivery failed. Using demo bypass code 123456."}

# --- Auth Endpoints ---
@app.post("/auth/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["Authentication"])
async def signup(user_data: UserSignUp):
    existing_user = await User.find_one(User.email == user_data.email)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    hashed = hash_password(user_data.password)
    user = User(name=user_data.name, email=user_data.email, password_hash=hashed)
    await user.insert()
    return user

@app.post("/auth/login", response_model=Token, tags=["Authentication"])
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await User.find_one(User.email == form_data.username)
    if user is None or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    token_payload = {"sub": user.email, "id": str(user.id), "email": user.email}
    access_token = create_access_token(data=token_payload)
    user_response = UserResponse(id=str(user.id), name=user.name, email=user.email, created_at=user.created_at)
    return Token(access_token=access_token, user=user_response)

# --- Elections Endpoints ---
@app.post("/elections/create", response_model=ElectionResponse, status_code=status.HTTP_201_CREATED, tags=["Elections"])
async def create_election(election_data: ElectionCreate, current_user: User = Depends(get_current_user)):
    code = await generate_unique_election_code()
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

@app.get("/elections/my-elections", response_model=List[ElectionResponse], tags=["Elections"])
async def my_elections(current_user: User = Depends(get_current_user)):
    return await Election.find(Election.creator_email == current_user.email).to_list()

@app.post("/elections/join", response_model=ParticipantResponse, status_code=status.HTTP_201_CREATED, tags=["Participation"])
async def join_election(join_data: JoinElectionRequest, current_user: User = Depends(get_current_user)):
    election = await Election.find_one(Election.election_code == join_data.election_code)
    if election is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Election not found")
    already_joined = await Participant.find_one(Participant.user_id == current_user.id, Participant.election_id == election.id)
    if already_joined:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You have already joined this election")
    participant = Participant(
        user_id=current_user.id,
        election_id=election.id,
        full_name=join_data.full_name,
        id_number=join_data.id_number,
        election_code=election.election_code,
    )
    await participant.insert()
    return participant

@app.get("/elections/joined", response_model=List[ElectionResponse], tags=["Participation"])
async def joined_elections(current_user: User = Depends(get_current_user)):
    join_records = await Participant.find(Participant.user_id == current_user.id).to_list()
    election_ids = [record.election_id for record in join_records]
    if not election_ids:
        return []
    return await Election.find({"_id": {"$in": election_ids}}).to_list()

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 5000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
