from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from beanie import Document, Indexed, PydanticObjectId
from bson import ObjectId

# ---------------------------------------------------------
# Candidate Model (Embedded Sub-document in Election)
# ---------------------------------------------------------
class Candidate(BaseModel):
    name: str = Field(..., min_length=1, description="Name of the candidate")
    photo_url: Optional[str] = Field(None, description="URL of candidate photo")
    symbol_url: Optional[str] = Field(None, description="URL of candidate party symbol")

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "name": "Jane Doe",
                "photo_url": "https://example.com/photos/jane.jpg",
                "symbol_url": "https://example.com/symbols/star.png"
            }
        }
    )


# ---------------------------------------------------------
# User DB Model (Beanie Document)
# ---------------------------------------------------------
class User(Document):
    name: str
    email: Indexed(EmailStr, unique=True)
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "users"

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )


# ---------------------------------------------------------
# Election DB Model (Beanie Document)
# ---------------------------------------------------------
class Election(Document):
    electionId: UUID = Field(default_factory=uuid4, description="Standard unique UUID for the election")
    name: str = Field(..., min_length=1)
    creator_email: str
    date: str = Field(..., description="Date of the election (e.g., YYYY-MM-DD)")
    time: str = Field(..., description="Time of the election (e.g., HH:MM)")
    election_code: Indexed(str, unique=True)  # unique 6-digit alphanumeric code
    candidates: List[Candidate] = Field(default_factory=list)

    class Settings:
        name = "elections"

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )


# ---------------------------------------------------------
# Participant DB Model (Beanie Document)
# ---------------------------------------------------------
class Participant(Document):
    user_id: PydanticObjectId
    election_id: PydanticObjectId
    full_name: str
    id_number: str
    election_code: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "participants"

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )


# =========================================================
# Pydantic Schemas for Requests and Responses (FastAPI)
# =========================================================

# --- Auth Schemas ---
class UserSignUp(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")

class UserResponse(BaseModel):
    id: str
    name: str
    email: EmailStr
    created_at: datetime

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("id", mode="before")
    @classmethod
    def serialize_id(cls, v):
        if isinstance(v, PydanticObjectId) or isinstance(v, ObjectId) if 'ObjectId' in globals() else False:
            return str(v)
        return str(v)

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # To facilitate Android side, return user info inside response too
    user: UserResponse


# --- Election Schemas ---
class ElectionCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    date: str = Field(..., description="Format: YYYY-MM-DD")
    time: str = Field(..., description="Format: HH:MM")
    candidates: List[Candidate] = Field(..., min_length=1, description="List of at least one candidate is required")

class ElectionResponse(BaseModel):
    id: str
    electionId: UUID
    name: str
    creator_email: str
    date: str
    time: str
    election_code: str
    candidates: List[Candidate]

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("id", mode="before")
    @classmethod
    def serialize_id(cls, v):
        return str(v)


# --- Participation Schemas ---
class JoinElectionRequest(BaseModel):
    election_code: str = Field(..., min_length=6, max_length=6, description="6-digit unique election code")
    full_name: str = Field(..., min_length=2, description="Full name of participant")
    id_number: str = Field(..., min_length=2, description="Voter ID or student ID number")

class ParticipantResponse(BaseModel):
    id: str
    user_id: str
    election_id: str
    full_name: str
    id_number: str
    election_code: str
    timestamp: datetime

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("id", "user_id", "election_id", mode="before")
    @classmethod
    def serialize_object_ids(cls, v):
        return str(v)
