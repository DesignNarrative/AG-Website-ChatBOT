# Abhinav Group AI Property Sales Chatbot

A production-ready AI chatbot for Abhinav Group's WordPress website.

## Project Structure

```
abhinav-ai-chatbot/
├── backend/          # FastAPI Python backend
├── frontend/
│   ├── chatbot-widget/   # Vanilla JS/CSS widget
│   └── admin-dashboard/  # React admin interface  
├── wordpress/        # WordPress plugin
├── data/             # Extracted knowledge, images, documents
├── tests/            # Automated test suites
├── scripts/          # Crawling, extraction, maintenance scripts
├── deployment/       # Staging and production configs
└── docs/             # Architecture and operations documentation
```

## Quick Start (Local Development)

### 1. Backend Setup

```bash
cd backend

# Copy environment file
cp ../.env.example .env
# Edit .env — set at minimum:
#   AI_PROVIDER=mock  (keep as mock until you have an API key)
#   DATABASE_URL=sqlite:///./abhinav_chatbot_dev.db

# Install dependencies
pip install -r requirements.txt

# Start the backend
uvicorn app.main:app --reload --port 8000
```

The API is now available at http://localhost:8000
API docs at http://localhost:8000/api/docs

### 2. Run Tests

```bash
cd backend
pytest ../tests/test_phase2.py -v
```

### 3. Admin Dashboard (Phase 7)

```bash
cd frontend/admin-dashboard
npm install
npm run dev
```

### 4. WordPress Plugin

After backend is deployed, install the plugin from:
`wordpress/abhinav-chatbot-plugin/`

## Development Phases

| Phase | Description | Status |
|-------|------------|--------|
| 1 | Audit & Planning | ✅ Complete |
| 2 | Foundation & Schema | ✅ Complete |
| 3 | Website Data Extraction | 🔄 Next |
| 4 | Knowledge Base & RAG | ⏳ Pending |
| 5 | AI Engine (Gemini/OpenAI) | ⏳ Pending (needs API key) |
| 6 | Chat Widget Frontend | ⏳ Pending |
| 7 | Admin Dashboard | ⏳ Pending |
| 8 | Lead Capture & Mdoc | ⏳ Pending |
| 9 | WordPress Plugin | ⏳ Pending |
| 10 | Security Hardening | ⏳ Pending |
| 11 | Testing | ⏳ Pending |
| 12 | Staging Deployment | ⏳ Pending |
| 13 | Production | ⏳ Pending |

## Security

- Never commit `.env` files
- All API keys go in environment variables only
- See `docs/security.md` for full security guide

## Mdoc CRM Integration

Currently in mock mode. Contact info@maksoftbox.com for API credentials.
See `backend/app/integrations/mdoc/adapter.py` for integration details.

## Support

This system is maintained by the development team.
For property enquiries: sales@abhinavinfra.com | +91 9890393838
