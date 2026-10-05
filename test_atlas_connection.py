import os
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure

load_dotenv()

mongo_url = os.getenv("MONGODB_URL", "")
db_name = os.getenv("DATABASE_NAME", "library_management_system")

print("=" * 60)
print("Testing MongoDB Atlas Cloud Connection...")
print("=" * 60)

if not mongo_url or "<username>" in mongo_url or "<password>" in mongo_url:
    print("\n[!] Please update your .env file with your actual MongoDB Atlas connection string.")
    print("    Current value:", mongo_url)
    print("\nFormat:")
    print("    MONGODB_URL=mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority")
    exit(1)

# Mask password for display
masked_url = mongo_url
if "@" in mongo_url and "://" in mongo_url:
    prefix, rest = mongo_url.split("://", 1)
    creds, host = rest.split("@", 1)
    if ":" in creds:
        u, _ = creds.split(":", 1)
        masked_url = f"{prefix}://{u}:******@{host}"

print(f"Connecting to: {masked_url}")

try:
    client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
    # Ping the server
    client.admin.command("ping")
    print("\n[SUCCESS] Successfully connected to MongoDB Atlas!")
    db = client[db_name]
    print(f"[SUCCESS] Database selected: '{db_name}'")
    print(f"Existing collections: {db.list_collection_names()}")
except ServerSelectionTimeoutError as e:
    print("\n[ERROR] Connection timed out!")
    print("Troubleshooting tips:")
    print(" 1. Check your IP Whitelist in MongoDB Atlas:")
    print("    Go to Network Access -> Add IP Address -> 'Allow Access from Anywhere' (0.0.0.0/0).")
    print(" 2. Ensure your internet connection is active.")
except OperationFailure as e:
    print("\n[ERROR] Authentication failed!")
    print("Troubleshooting tips:")
    print(" 1. Verify your username and password in MongoDB Atlas > Database Access.")
    print(" 2. If your password has special characters (@, #, %, etc.), URL-encode them.")
except Exception as e:
    print(f"\n[ERROR] An unexpected error occurred: {e}")
