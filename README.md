# Lumina Library Management System

A modern, simple, and responsive Library Management System built with HTML/JS, FastAPI, and MongoDB.

## Features

- **Dashboard**: Track overall statistics (total books, available books, issued books, total members, overdue books, and recent activities).
- **Books Management**: Add, update, delete, and search books. Manages available copies automatically.
- **Members Management**: Register, update, and remove library members.
- **Transactions**: Issue books, return books, and automatically track status (Active, Returned, Overdue).

## Prerequisites

1. **Python 3.8+** installed on your system.
2. **MongoDB** (either free online **MongoDB Atlas** or local MongoDB).

## Setup Instructions

### 1. MongoDB Database Setup (MongoDB Atlas Cloud - Recommended)

To use MongoDB Atlas online without running anything locally:

1. Sign up / Log in to [MongoDB Atlas](https://www.mongodb.com/cloud/atlas/register) (Free M0 Cluster).
2. Create a new Cluster (Choose **M0 Free**).
3. Under **Security > Database Access**:
   - Create a database user with username and password (e.g. `admin` and a strong password).
4. Under **Security > Network Access**:
   - Click **Add IP Address** -> Select **Allow Access from Anywhere** (`0.0.0.0/0`) or your current IP.
5. Under **Deployment > Database**:
   - Click **Connect** -> Choose **Drivers** (Python).
   - Copy your connection string:
     ```
     mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
     ```
6. Open your [.env](file:///.env) file and paste your connection string:
   ```env
   MONGODB_URL=mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   DATABASE_NAME=library_management_system
   ```
   *(Note: Remember to replace `<username>` and `<password>` with your actual MongoDB Atlas user credentials).*

### 2. Install Python Dependencies
Open your terminal in the project directory and run:
```bash
pip install -r requirements.txt
```

### 3. Start the FastAPI Backend
Run the backend server using Uvicorn:
```bash
uvicorn main:app --reload
```
The API will run at `http://127.0.0.1:8000`.

- **API Documentation (Swagger UI)**: Open your browser and go to `http://127.0.0.1:8000/docs` to view and test the API endpoints.

### 4. Open the Frontend
Since the frontend uses vanilla HTML, CSS, and JS (with Fetch API), you can simply double-click the `index.html` file to open it in any modern web browser.

Alternatively, you can serve it using a local HTTP server:
```bash
python -m http.server 3000
```
Then visit `http://localhost:3000/index.html`.

## Project Structure
- `index.html`: The complete frontend UI, styles, and logic.
- `main.py`: The FastAPI backend application connecting to MongoDB.
- `requirements.txt`: Python dependencies.
- `README.md`: Project documentation.
