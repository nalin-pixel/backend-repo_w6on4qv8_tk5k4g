"""
Database Schemas for Farmer-Supplier Communication App

Each Pydantic model represents a collection in MongoDB.
Collection name is the lowercase of the class name.
"""
from typing import Optional, Literal
from pydantic import BaseModel, Field, EmailStr

class Account(BaseModel):
    """
    User accounts collection schema
    Collection name: "account"
    Roles: farmer, supplier, admin
    """
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Email address")
    password_hash: str = Field(..., description="Hashed password")
    role: Literal["farmer", "supplier", "admin"] = Field(..., description="Account role")
    is_active: bool = Field(True, description="Whether account is active")

class Message(BaseModel):
    """
    Messages between farmers and suppliers
    Collection name: "message"
    """
    sender_id: str = Field(..., description="Sender account _id as string")
    receiver_id: str = Field(..., description="Receiver account _id as string")
    content: str = Field(..., min_length=1, max_length=2000, description="Message text")
    read: bool = Field(False, description="Read status")
