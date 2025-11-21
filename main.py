import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timezone
import hashlib
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Account, Message

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utility functions

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

# Request models
class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str  # farmer | supplier | admin

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class MessageRequest(BaseModel):
    sender_id: str
    receiver_id: str
    content: str

class ToggleActiveRequest(BaseModel):
    account_id: str
    active: bool

@app.get("/")
def read_root():
    return {"message": "Farmer-Supplier Communication API"}

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response

# Auth endpoints
@app.post("/auth/register")
def register(payload: RegisterRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    existing = db["account"].find_one({"email": payload.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    if payload.role not in ["farmer", "supplier", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid role")

    account = Account(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
    )
    inserted_id = create_document("account", account)
    return {"message": "Registered successfully", "id": inserted_id}

@app.post("/auth/login")
def login(payload: LoginRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    account = db["account"].find_one({"email": payload.email})
    if not account:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if account.get("password_hash") != hash_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not account.get("is_active", True):
        raise HTTPException(status_code=403, detail="Account is deactivated")
    account["_id"] = str(account["_id"]) if "_id" in account else None
    return {
        "message": "Login successful",
        "account": {
            "id": account.get("_id"),
            "name": account.get("name"),
            "email": account.get("email"),
            "role": account.get("role"),
            "is_active": account.get("is_active", True),
        },
    }

# Messaging endpoints
@app.post("/messages")
def send_message(payload: MessageRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    # Ensure sender and receiver exist
    try:
        recv_obj = ObjectId(payload.receiver_id)
        send_obj = ObjectId(payload.sender_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user id")

    receiver = db["account"].find_one({"_id": recv_obj})
    sender = db["account"].find_one({"_id": send_obj})
    if not receiver or not sender:
        raise HTTPException(status_code=404, detail="User not found")

    msg_data = Message(
        sender_id=payload.sender_id,
        receiver_id=payload.receiver_id,
        content=payload.content,
        read=False,
    )
    inserted_id = create_document("message", msg_data)
    return {"message": "Message sent", "id": inserted_id}

@app.get("/messages")
def list_messages(user_id: str, peer_id: Optional[str] = None):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    query = {"$or": [{"sender_id": user_id}, {"receiver_id": user_id}]}
    if peer_id:
        query = {"$or": [
            {"sender_id": user_id, "receiver_id": peer_id},
            {"sender_id": peer_id, "receiver_id": user_id},
        ]}
    docs = get_documents("message", query)
    for d in docs:
        d["_id"] = str(d.get("_id")) if d.get("_id") else None
    return {"messages": docs}

# Admin endpoints
@app.get("/admin/accounts")
def admin_list_accounts():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    accounts = get_documents("account")
    for a in accounts:
        a["_id"] = str(a.get("_id")) if a.get("_id") else None
        a.pop("password_hash", None)
    return {"accounts": accounts}

@app.post("/admin/toggle-active")
def admin_toggle_active(payload: ToggleActiveRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    try:
        obj_id = ObjectId(payload.account_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid account id")
    res = db["account"].update_one(
        {"_id": obj_id},
        {"$set": {"is_active": payload.active, "updated_at": datetime.now(timezone.utc)}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Account not found")
    return {"message": "Status updated"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
