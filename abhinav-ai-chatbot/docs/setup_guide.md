# Abhinav Group AI Property Chatbot — Local Development Setup Guide

## Quick Start (Local Development)

### 1. Requirements
- Python 3.10+
- Node.js 18+ & pnpm
- Git

### 2. Backend Setup
```powershell
cd abhinav-ai-chatbot/backend

# Create virtual environment (optional)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run sync test suite
$env:PYTHONIOENCODING="utf-8"
python run_sync_tests.py
```

### 3. Start Backend Server
```powershell
uvicorn app.main:app --reload --port 8000
```
API Documentation will be available at: `http://localhost:8000/docs`

### 4. Admin Dashboard Setup
```powershell
cd ../frontend/admin-dashboard
pnpm install
pnpm run dev
```
Dashboard will run at: `http://localhost:5173`

### 5. Chatbot Widget Testing
Open `frontend/chatbot-widget/test.html` in your browser. It connects directly to `http://localhost:8000`.

### 6. Build Chatbot Widget Minified Bundle
```powershell
cd ../frontend/chatbot-widget
python build.py
```
This produces `dist/abhinav-chatbot.min.js` and syncs with `wordpress/abhinav-chatbot-plugin/dist/abhinav-chatbot.min.js`.
