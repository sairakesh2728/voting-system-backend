import os
import random
import string
import bcrypt 
import pymongo
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
    User, Election, Participant, UserSignUp, UserResponse, Token,
    ElectionCreate, ElectionResponse, JoinElectionRequest, ParticipantResponse,
    OTPRecord, OtpVerifyRequest
)

# Compatibility fix
# bcrypt.__about__ = type('about', (object,), {'__version__': bcrypt.__version__})
load_dotenv()

# Config
JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_voting_key_2026_antigravity")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

mail_conf = ConnectionConfig(
    MAIL_USERNAME = os.getenv("MAIL_USERNAME") or "",
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD") or "",
    MAIL_FROM = os.getenv("MAIL_FROM") or os.getenv("MAIL_USERNAME") or "no-reply@example.com",
    MAIL_PORT = int(os.getenv("MAIL_PORT", 2525)),
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp-relay.brevo.com"),
    MAIL_STARTTLS = True,
    MAIL_SSL_TLS = False,
    USE_CREDENTIALS = True if os.getenv("MAIL_USERNAME") else False,
    VALIDATE_CERTS = True
)

# Models
class OtpRequest(BaseModel):
    email: str

class OtpResponse(BaseModel):
    otp: str
    message: str

class VoteCreate(BaseModel):
    election_id: str
    candidate_name: str
    voter_email: str
    timestamp: int
    signature: str

class ResultResponse(BaseModel):
    candidate: str
    votes: int

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
def hash_password(password: str): return pwd_context.hash(password)
def verify_password(p, h): return pwd_context.verify(p, h)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="Voting System", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email = payload.get("email")
        user = await User.find_one(User.email == email)
        if not user: raise Exception()
        return user
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/health/mail")
async def health_mail():
    return {"status": "ok", "server": mail_conf.MAIL_SERVER, "from": mail_conf.MAIL_FROM}

# Endpoints
@app.post("/auth/send-otp")
async def send_otp(request: OtpRequest):
    otp = "".join(random.choices(string.digits, k=6))

    # Store OTP in database
    await OTPRecord(email=request.email, otp=otp).insert()

    mail_username = os.getenv("MAIL_USERNAME")
    mail_password = os.getenv("MAIL_PASSWORD")

    if not mail_username or not mail_password:
        print(f"[BYPASS] No email credentials. Email: {request.email}, OTP: {otp}")
        return {"otp": otp, "message": "Bypass mode - Credentials missing"}
        
    fm = FastMail(mail_conf)
    try:
        message = MessageSchema(
            subject="Voting System OTP",
            recipients=[request.email],
            body=f"Your verification code is: {otp}. It will expire in 10 minutes.",
            subtype="plain"
        )
        await fm.send_message(message)
        print(f"[SUCCESS] OTP sent to {request.email}")
        return {"otp": otp, "message": "Sent"}
    except Exception as e:
        print(f"[ERROR] SMTP Failed for {request.email}: {str(e)}")
        # In case of SMTP failure, we return the OTP so it can be checked manually in logs
        return {"otp": otp, "message": f"SMTP Error: {str(e)}"}

@app.post("/auth/verify-otp")
async def verify_otp(request: OtpVerifyRequest):
    # Find the latest OTP for this email
    record = await OTPRecord.find(OTPRecord.email == request.email).sort("-created_at").first_or_none()

    if not record:
        raise HTTPException(status_code=400, detail="No OTP found or expired")

    if record.otp == request.otp:
        await record.delete()
        return {"message": "Verified"}
    else:
        raise HTTPException(status_code=400, detail="Invalid OTP")

@app.post("/auth/signup", response_model=UserResponse, status_code=201)
async def signup(user_data: UserSignUp):
    try:
        user = User(name=user_data.name, email=user_data.email, password_hash=hash_password(user_data.password))
        await user.insert()
        return user
    except pymongo.errors.DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Email already registered")

@app.post("/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await User.find_one(User.email == form_data.username)
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"email": user.email})
    return Token(access_token=token, user=UserResponse(id=str(user.id), name=user.name, email=user.email, created_at=user.created_at))

@app.post("/elections/create", response_model=ElectionResponse, status_code=201)
async def create_election(data: ElectionCreate, user: User = Depends(get_current_user)):
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    election = Election(name=data.name, creator_email=user.email, date=data.date, time=data.time, election_code=code, candidates=data.candidates)
    await election.insert()
    return election

@app.get("/elections/my-elections", response_model=List[ElectionResponse])
async def my_elections(user: User = Depends(get_current_user)):
    return await Election.find(Election.creator_email == user.email).to_list()

@app.post("/elections/join", response_model=ParticipantResponse, status_code=201)
async def join_election(data: JoinElectionRequest, user: User = Depends(get_current_user)):
    election = await Election.find_one(Election.election_code == data.election_code)
    if not election:
        raise HTTPException(status_code=400, detail="Election not found")
    
    # Check if user already joined this election
    existing = await Participant.find_one(
        Participant.user_id == user.id,
        Participant.election_id == election.id
    )
    if existing:
        raise HTTPException(status_code=400, detail="Already joined this election")
        
    participant = Participant(user_id=user.id, election_id=election.id, full_name=data.full_name, id_number=data.id_number, election_code=election.election_code)
    await participant.insert()
    return participant

@app.get("/elections/{election_id}/participants", response_model=List[ParticipantResponse])
async def get_election_participants(election_id: str, user: User = Depends(get_current_user)):
    election = await Election.find_one(Election.id == PydanticObjectId(election_id))
    if not election:
        raise HTTPException(status_code=404, detail="Election not found")
    if election.creator_email != user.email:
        raise HTTPException(status_code=401, detail="Unauthorized: Only the creator can view participants")
    return await Participant.find(Participant.election_id == PydanticObjectId(election_id)).to_list()

@app.get("/elections/joined", response_model=List[ElectionResponse])
async def joined_elections(user: User = Depends(get_current_user)):
    join_records = await Participant.find(Participant.user_id == user.id).to_list()
    return await Election.find({"_id": {"$in": [r.election_id for r in join_records]}}).to_list()

# --- NEW: Cloud Voting & Results ---
@app.post("/votes/cast")
async def cast_vote(vote: VoteCreate, user: User = Depends(get_current_user)):
    # Simple check: one vote per email per election
    from database import db
    existing = await db.votes.find_one({"election_id": vote.election_id, "voter_email": vote.voter_email})
    if existing: return {"message": "Already voted"}
    await db.votes.insert_one(vote.dict())
    return {"message": "Successfully "}

@app.get("/votes/results/{election_id}", response_model=List[ResultResponse])
async def get_results(election_id: str):
    from database import db
    pipeline = [{"$match": {"election_id": election_id}}, {"$group": {"_id": "$candidate_name", "count": {"$sum": 1}}}]
    cursor = db.votes.aggregate(pipeline)
    return [{"candidate": r["_id"], "votes": r["count"]} async for r in cursor]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
