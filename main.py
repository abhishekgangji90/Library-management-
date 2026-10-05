import os
from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pymongo import MongoClient
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

client = MongoClient(MONGODB_URL)
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
def get_dashboard_stats():
    total_books = sum(b.get("quantity", 0) for b in books_collection.find())
    available_books = sum(b.get("available_copies", 0) for b in books_collection.find())
    issued_books = total_books - available_books
    total_members = members_collection.count_documents({})
    
    # Overdue calculation
    today = datetime.now().date()
    overdue_transactions = 0
    active_transactions = transactions_collection.find({"status": "active"})
    for t in active_transactions:
        due_date = datetime.strptime(t["due_date"], "%Y-%m-%d").date()
        if today > due_date:
            overdue_transactions += 1
            
    recent_activities = list(transactions_collection.find({}, {"_id": 0}).sort("issue_date", -1).limit(5))

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
def get_books():
    books = list(books_collection.find({}, {"_id": 0}))
    return books

@app.post("/api/books")
def add_book(book: BookCreate):
    if book.quantity < 0:
        raise HTTPException(status_code=400, detail="Quantity cannot be negative")
    
    existing_book = books_collection.find_one({"isbn": book.isbn})
    if existing_book:
        raise HTTPException(status_code=400, detail="Book with this ISBN already exists")
    
    book_id = str(uuid.uuid4())
    new_book = book.dict()
    new_book["book_id"] = book_id
    new_book["available_copies"] = book.quantity
    
    books_collection.insert_one(new_book)
    return {"message": "Book added successfully", "book_id": book_id}

@app.put("/api/books/{book_id}")
def update_book(book_id: str, book: BookCreate):
    existing_book = books_collection.find_one({"book_id": book_id})
    if not existing_book:
        raise HTTPException(status_code=404, detail="Book not found")
        
    if book.quantity < 0:
        raise HTTPException(status_code=400, detail="Quantity cannot be negative")
        
    diff = book.quantity - existing_book["quantity"]
    new_available = existing_book["available_copies"] + diff
    if new_available < 0:
        raise HTTPException(status_code=400, detail="Cannot reduce quantity below currently issued copies")
        
    update_data = book.dict()
    update_data["available_copies"] = new_available
    
    books_collection.update_one({"book_id": book_id}, {"$set": update_data})
    return {"message": "Book updated successfully"}

@app.delete("/api/books/{book_id}")
def delete_book(book_id: str):
    active_txn = transactions_collection.find_one({"book_id": book_id, "status": "active"})
    if active_txn:
        raise HTTPException(status_code=400, detail="Cannot delete book. It is currently issued.")
        
    result = books_collection.delete_one({"book_id": book_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Book not found")
    return {"message": "Book deleted successfully"}

# --- Member Endpoints ---
@app.get("/api/members")
def get_members():
    members = list(members_collection.find({}, {"_id": 0}))
    return members

@app.post("/api/members")
def add_member(member: MemberCreate):
    existing_member = members_collection.find_one({"email": member.email})
    if existing_member:
        raise HTTPException(status_code=400, detail="Member with this email already exists")
        
    member_id = str(uuid.uuid4())
    new_member = member.dict()
    new_member["member_id"] = member_id
    new_member["registration_date"] = datetime.now().strftime("%Y-%m-%d")
    
    members_collection.insert_one(new_member)
    return {"message": "Member added successfully", "member_id": member_id}

@app.put("/api/members/{member_id}")
def update_member(member_id: str, member: MemberCreate):
    existing_member = members_collection.find_one({"member_id": member_id})
    if not existing_member:
        raise HTTPException(status_code=404, detail="Member not found")
        
    members_collection.update_one({"member_id": member_id}, {"$set": member.dict()})
    return {"message": "Member updated successfully"}

@app.delete("/api/members/{member_id}")
def delete_member(member_id: str):
    active_txn = transactions_collection.find_one({"member_id": member_id, "status": "active"})
    if active_txn:
        raise HTTPException(status_code=400, detail="Cannot delete member with active book issues.")
        
    result = members_collection.delete_one({"member_id": member_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Member not found")
    return {"message": "Member deleted successfully"}

# --- Transaction Endpoints ---
@app.get("/api/transactions")
def get_transactions():
    txns = list(transactions_collection.find({}, {"_id": 0}))
    # Enrich with member and book details for frontend
    for t in txns:
        book = books_collection.find_one({"book_id": t["book_id"]})
        member = members_collection.find_one({"member_id": t["member_id"]})
        t["book_title"] = book["title"] if book else "Unknown Book"
        t["member_name"] = member["name"] if member else "Unknown Member"
    return txns

@app.post("/api/issue")
def issue_book(req: IssueRequest):
    book = books_collection.find_one({"book_id": req.book_id})
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if book["available_copies"] <= 0:
        raise HTTPException(status_code=400, detail="No copies available for this book")
        
    member = members_collection.find_one({"member_id": req.member_id})
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
        
    existing_txn = transactions_collection.find_one({
        "member_id": req.member_id, 
        "book_id": req.book_id, 
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
        "status": "active"
    }
    
    transactions_collection.insert_one(transaction)
    books_collection.update_one(
        {"book_id": req.book_id},
        {"$inc": {"available_copies": -1}}
    )
    
    return {"message": "Book issued successfully", "transaction_id": txn_id}

@app.post("/api/return")
def return_book(req: ReturnRequest):
    txn = transactions_collection.find_one({"transaction_id": req.transaction_id})
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if txn["status"] == "returned":
        raise HTTPException(status_code=400, detail="Book already returned")
        
    return_date = datetime.now().strftime("%Y-%m-%d")
    
    transactions_collection.update_one(
        {"transaction_id": req.transaction_id},
        {"$set": {"status": "returned", "return_date": return_date}}
    )
    
    books_collection.update_one(
        {"book_id": txn["book_id"]},
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
