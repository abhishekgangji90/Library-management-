import os
from fastapi import FastAPI, HTTPException, Body, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pymongo import MongoClient
# pyrefly: ignore [missing-import]
import certifi
from typing import List, Optional
from datetime import datetime, date
import uuid
from dotenv import load_dotenv

# Load environment variables from .env (MongoDB Atlas configuration)
load_dotenv(override=True)

app = FastAPI(title="Library Management System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection (Atlas online cloud or local)
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://localhost:27017/")
DATABASE_NAME = os.getenv("DATABASE_NAME", "library_management_system")

client = MongoClient(MONGODB_URL, tlsCAFile=certifi.where())
db = client[DATABASE_NAME]
books_collection = db["books"]
members_collection = db["members"]
transactions_collection = db["transactions"]
users_collection = db["users"]

@app.get("/api/db-status")
def check_db_status():
    """Check MongoDB Atlas connection status"""
    try:
        client.admin.command("ping")
        return {"status": "connected", "database": DATABASE_NAME, "is_cloud": "mongodb.net" in MONGODB_URL}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# Auth Models
class LoginRequest(BaseModel):
    email: str
    password: str

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str

class GoogleAuthRequest(BaseModel):
    email: str
    name: str
    picture: Optional[str] = None
    sub: Optional[str] = None

@app.post("/api/auth/login")
def auth_login(req: LoginRequest):
    email_clean = req.email.strip().lower()
    # Support default admin credentials or registered user
    if (email_clean in ["admin@sspi.edu", "admin"]) and req.password in ["admin123", "admin"]:
        admin_data = {
            "email": "admin@sspi.edu",
            "name": "SSPI Administrator",
            "role": "admin",
            "picture": None,
            "last_login": datetime.now().isoformat()
        }
        users_collection.update_one({"email": admin_data["email"]}, {"$set": admin_data}, upsert=True)
        return {"success": True, "user": admin_data}

    user = users_collection.find_one({"email": email_clean, "password": req.password})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password. Use admin@sspi.edu / admin123 or Sign in with Google.")
    
    return {
        "success": True,
        "user": {
            "email": user["email"],
            "name": user.get("name", email_clean.split("@")[0]),
            "role": user.get("role", "staff"),
            "picture": user.get("picture")
        }
    }

@app.post("/api/auth/google")
def auth_google(req: GoogleAuthRequest):
    email_clean = req.email.strip().lower()
    user_data = {
        "email": email_clean,
        "name": req.name,
        "role": "faculty",
        "picture": req.picture,
        "sub": req.sub,
        "auth_provider": "google",
        "last_login": datetime.now().isoformat()
    }
    users_collection.update_one(
        {"email": email_clean},
        {"$set": user_data},
        upsert=True
    )
    return {"success": True, "user": user_data}

@app.post("/api/auth/register")
def auth_register(req: RegisterRequest):
    email_clean = req.email.strip().lower()
    
    existing_user = users_collection.find_one({"email": email_clean})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    new_user = {
        "email": email_clean,
        "name": req.name,
        "password": req.password,
        "role": "staff",
        "picture": None,
        "last_login": datetime.now().isoformat()
    }
    users_collection.insert_one(new_user)
    
    return {
        "success": True,
        "user": {
            "email": new_user["email"],
            "name": new_user["name"],
            "role": new_user["role"],
            "picture": new_user["picture"]
        }
    }

# Pydantic Models
class Book(BaseModel):
    book_id: str
    title: str
    author: str
    isbn: str
    category: str
    publisher: str
    year: int
    quantity: int
    available_copies: int

class BookCreate(BaseModel):
    title: str
    author: str
    isbn: str
    category: str
    publisher: str
    year: int
    quantity: int

class Member(BaseModel):
    member_id: str
    name: str
    email: str
    phone: str
    course_class: str
    registration_date: str

class MemberCreate(BaseModel):
    name: str
    email: str
    phone: str
    course_class: str

class IssueRequest(BaseModel):
    member_id: str
    book_id: str
    due_date: str

class ReturnRequest(BaseModel):
    transaction_id: str

# Helper to convert MongoDB object `_id` to string if needed, but we rely on our own IDs.

@app.get("/")
def read_root():
    return {"message": "Welcome to Library Management System API"}

# --- Dashboard Statistics ---
@app.get("/api/dashboard")
def get_dashboard_stats(x_user_email: Optional[str] = Header(None)):
    user_filter = {"owner_email": x_user_email} if x_user_email else {}
    
    total_books = sum(b.get("quantity", 0) for b in books_collection.find(user_filter))
    available_books = sum(b.get("available_copies", 0) for b in books_collection.find(user_filter))
    issued_books = total_books - available_books
    total_members = members_collection.count_documents(user_filter)
    
    # Overdue calculation
    today = datetime.now().date()
    overdue_transactions = 0
    active_transactions = transactions_collection.find({**user_filter, "status": "active"})
    for t in active_transactions:
        due_date = datetime.strptime(t["due_date"], "%Y-%m-%d").date()
        if today > due_date:
            overdue_transactions += 1
            
    recent_activities = list(transactions_collection.find(user_filter, {"_id": 0}).sort("issue_date", -1).limit(5))

    return {
        "total_books": total_books,
        "available_books": available_books,
        "issued_books": issued_books,
        "total_members": total_members,
        "overdue_books": overdue_transactions,
        "recent_activities": recent_activities
    }

# --- Book Endpoints ---
@app.get("/api/books")
def get_books(x_user_email: Optional[str] = Header(None)):
    user_filter = {"owner_email": x_user_email} if x_user_email else {}
    books = list(books_collection.find(user_filter, {"_id": 0}))
    return books

@app.post("/api/books")
def add_book(book: BookCreate, x_user_email: Optional[str] = Header(None)):
    if not x_user_email:
        raise HTTPException(status_code=401, detail="User email required for this action")
        
    if book.quantity < 0:
        raise HTTPException(status_code=400, detail="Quantity cannot be negative")
    
    existing_book = books_collection.find_one({"isbn": book.isbn, "owner_email": x_user_email})
    if existing_book:
        raise HTTPException(status_code=400, detail="Book with this ISBN already exists in your library")
    
    book_id = str(uuid.uuid4())
    new_book = book.dict()
    new_book["book_id"] = book_id
    new_book["available_copies"] = book.quantity
    new_book["owner_email"] = x_user_email
    
    books_collection.insert_one(new_book)
    return {"message": "Book added successfully", "book_id": book_id}

@app.put("/api/books/{book_id}")
def update_book(book_id: str, book: BookCreate, x_user_email: Optional[str] = Header(None)):
    existing_book = books_collection.find_one({"book_id": book_id, "owner_email": x_user_email})
    if not existing_book:
        raise HTTPException(status_code=404, detail="Book not found in your library")
        
    if book.quantity < 0:
        raise HTTPException(status_code=400, detail="Quantity cannot be negative")
        
    diff = book.quantity - existing_book["quantity"]
    new_available = existing_book["available_copies"] + diff
    if new_available < 0:
        raise HTTPException(status_code=400, detail="Cannot reduce quantity below currently issued copies")
        
    update_data = book.dict()
    update_data["available_copies"] = new_available
    
    books_collection.update_one({"book_id": book_id, "owner_email": x_user_email}, {"$set": update_data})
    return {"message": "Book updated successfully"}

@app.delete("/api/books/{book_id}")
def delete_book(book_id: str, x_user_email: Optional[str] = Header(None)):
    active_txn = transactions_collection.find_one({"book_id": book_id, "owner_email": x_user_email, "status": "active"})
    if active_txn:
        raise HTTPException(status_code=400, detail="Cannot delete book. It is currently issued.")
        
    result = books_collection.delete_one({"book_id": book_id, "owner_email": x_user_email})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Book not found in your library")
    return {"message": "Book deleted successfully"}

# --- Member Endpoints ---
@app.get("/api/members")
def get_members(x_user_email: Optional[str] = Header(None)):
    user_filter = {"owner_email": x_user_email} if x_user_email else {}
    members = list(members_collection.find(user_filter, {"_id": 0}))
    return members

@app.post("/api/members")
def add_member(member: MemberCreate, x_user_email: Optional[str] = Header(None)):
    if not x_user_email:
        raise HTTPException(status_code=401, detail="User email required for this action")
        
    existing_member = members_collection.find_one({"email": member.email, "owner_email": x_user_email})
    if existing_member:
        raise HTTPException(status_code=400, detail="Member with this email already exists in your library")
        
    member_id = str(uuid.uuid4())
    new_member = member.dict()
    new_member["member_id"] = member_id
    new_member["registration_date"] = datetime.now().strftime("%Y-%m-%d")
    new_member["owner_email"] = x_user_email
    
    members_collection.insert_one(new_member)
    return {"message": "Member added successfully", "member_id": member_id}

@app.put("/api/members/{member_id}")
def update_member(member_id: str, member: MemberCreate, x_user_email: Optional[str] = Header(None)):
    existing_member = members_collection.find_one({"member_id": member_id, "owner_email": x_user_email})
    if not existing_member:
        raise HTTPException(status_code=404, detail="Member not found in your library")
        
    members_collection.update_one({"member_id": member_id, "owner_email": x_user_email}, {"$set": member.dict()})
    return {"message": "Member updated successfully"}

@app.delete("/api/members/{member_id}")
def delete_member(member_id: str, x_user_email: Optional[str] = Header(None)):
    active_txn = transactions_collection.find_one({"member_id": member_id, "owner_email": x_user_email, "status": "active"})
    if active_txn:
        raise HTTPException(status_code=400, detail="Cannot delete member with active book issues.")
        
    result = members_collection.delete_one({"member_id": member_id, "owner_email": x_user_email})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Member not found in your library")
    return {"message": "Member deleted successfully"}

# --- Transaction Endpoints ---
@app.get("/api/transactions")
def get_transactions(x_user_email: Optional[str] = Header(None)):
    user_filter = {"owner_email": x_user_email} if x_user_email else {}
    txns = list(transactions_collection.find(user_filter, {"_id": 0}))
    # Enrich with member and book details for frontend
    for t in txns:
        book = books_collection.find_one({"book_id": t["book_id"], "owner_email": x_user_email})
        member = members_collection.find_one({"member_id": t["member_id"], "owner_email": x_user_email})
        t["book_title"] = book["title"] if book else "Unknown Book"
        t["member_name"] = member["name"] if member else "Unknown Member"
    return txns

@app.post("/api/issue")
def issue_book(req: IssueRequest, x_user_email: Optional[str] = Header(None)):
    if not x_user_email:
        raise HTTPException(status_code=401, detail="User email required for this action")
        
    book = books_collection.find_one({"book_id": req.book_id, "owner_email": x_user_email})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found in your library")
    if book["available_copies"] <= 0:
        raise HTTPException(status_code=400, detail="No copies available for this book")
        
    member = members_collection.find_one({"member_id": req.member_id, "owner_email": x_user_email})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in your library")
        
    existing_txn = transactions_collection.find_one({
        "member_id": req.member_id, 
        "book_id": req.book_id, 
        "owner_email": x_user_email,
        "status": "active"
    })
    if existing_txn:
        raise HTTPException(status_code=400, detail="Member already has an active issue for this book")

    txn_id = str(uuid.uuid4())
    transaction = {
        "transaction_id": txn_id,
        "member_id": req.member_id,
        "book_id": req.book_id,
        "issue_date": datetime.now().strftime("%Y-%m-%d"),
        "due_date": req.due_date,
        "return_date": None,
        "status": "active",
        "owner_email": x_user_email
    }
    
    transactions_collection.insert_one(transaction)
    books_collection.update_one(
        {"book_id": req.book_id, "owner_email": x_user_email},
        {"$inc": {"available_copies": -1}}
    )
    
    return {"message": "Book issued successfully", "transaction_id": txn_id}

@app.post("/api/return")
def return_book(req: ReturnRequest, x_user_email: Optional[str] = Header(None)):
    txn = transactions_collection.find_one({"transaction_id": req.transaction_id, "owner_email": x_user_email})
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found in your library")
    if txn["status"] == "returned":
        raise HTTPException(status_code=400, detail="Book already returned")
        
    return_date = datetime.now().strftime("%Y-%m-%d")
    
    transactions_collection.update_one(
        {"transaction_id": req.transaction_id, "owner_email": x_user_email},
        {"$set": {"status": "returned", "return_date": return_date}}
    )
    
    books_collection.update_one(
        {"book_id": txn["book_id"], "owner_email": x_user_email},
        {"$inc": {"available_copies": 1}}
    )
    
    # Calculate overdue status
    due_date = datetime.strptime(txn["due_date"], "%Y-%m-%d").date()
    returned = datetime.strptime(return_date, "%Y-%m-%d").date()
    overdue_days = (returned - due_date).days
    
    return {
        "message": "Book returned successfully",
        "overdue_days": max(0, overdue_days)
    }
