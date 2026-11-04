# Abhinav Group AI Property Chatbot — Production Deployment Guide

## Overview

This guide details the steps to deploy the Abhinav Group AI Property Chatbot to staging and production environments.

> [!IMPORTANT]
> The live WordPress website (https://abhinavgroup.co.in) must remain untouched until the backend API and Admin Dashboard are fully deployed, tested, and approved.

---

## Architecture Stack

| Layer | Component | Technology |
|---|---|---|
| **Reverse Proxy & SSL** | Gateway | Caddy 2 (automated Let's Encrypt SSL) |
| **Backend API** | App Server | FastAPI + Uvicorn (Python 3.10, 4 workers) |
| **Primary Database** | Relational Data | PostgreSQL 16 |
| **Vector Database** | Semantic RAG | pgvector extension (768-dim vectors) |
| **Cache & Task Queue** | Session / Rate limits | Redis 7 |
| **Admin Dashboard** | Staff & Dev Portal | React 18 + Vite + Tailwind CSS |
| **Public Chatbot Widget** | Floating Web Widget | Vanilla JavaScript (20.1KB minified, no dependencies) |
| **WordPress Integration** | Website Plugin | Custom PHP Plugin (`abhinav-chatbot-plugin`) |

---

## 1. Prerequisites

A Linux VPS (Ubuntu 22.04 LTS or 24.04 LTS recommended) with:
- 2 CPU cores, 4 GB RAM minimum (8 GB recommended for heavy traffic)
- Docker Engine 24+ & Docker Compose v2
- DNS Records configured:
  - `api.abhinavgroup.co.in` → Server Public IP
  - `admin.abhinavgroup.co.in` → Server Public IP

---

## 2. Server Setup & Repository Clone

```bash
# SSH into your server
ssh ubuntu@your-server-ip

# Clone the project repository
git clone https://github.com/abhinavgroup/abhinav-ai-chatbot.git
cd abhinav-ai-chatbot
```

---

## 3. Environment Variables Configuration

Copy `.env.example` to `deployment/.env`:

```bash
cp .env.example deployment/.env
chmod 600 deployment/.env
nano deployment/.env
```

Ensure the following variables are set with secure random strings:

```ini
APP_ENV=production
DOMAIN=api.abhinavgroup.co.in
ADMIN_DOMAIN=admin.abhinavgroup.co.in

POSTGRES_DB=abhinav_chatbot
POSTGRES_USER=abhinav_admin
POSTGRES_PASSWORD=use_a_strong_random_password_here_min32chars

REDIS_PASSWORD=use_a_strong_random_password_here_min32chars

APP_SECRET_KEY=generate_64_char_hex_secret_here
JWT_SECRET_KEY=generate_64_char_hex_secret_here

AI_PROVIDER=gemini
GEMINI_API_KEY=your_actual_google_gemini_api_key

ALLOWED_ORIGINS=https://abhinavgroup.co.in,https://admin.abhinavgroup.co.in
MDOC_ENABLED=false
```

---

## 4. Run Database Migrations & Initial Knowledge Seed

```bash
cd deployment

# Start PostgreSQL and Redis first
docker compose up -d postgres redis

# Verify PostgreSQL is ready
docker compose exec postgres pg_isready -U abhinav_admin

# Run migrations
docker compose run --rm backend alembic upgrade head

# Run initial knowledge seeder
docker compose run --rm backend python scripts/seed_knowledge/seed_all.py
```

---

## 5. Launch Full Stack

```bash
docker compose up -d --build
```

Verify all containers are healthy:

```bash
docker compose ps
```

Test health check:

```bash
curl -I https://api.abhinavgroup.co.in/health
```

---

## 6. WordPress Plugin Installation

1. In the WordPress Admin Panel (https://abhinavgroup.co.in/wp-admin):
   - Go to **Plugins** → **Add New** → **Upload Plugin**.
   - Upload the zipped plugin folder from `wordpress/abhinav-chatbot-plugin`.
   - Click **Activate Plugin**.
2. Go to **Settings** → **Abhinav Chatbot**:
   - **Chatbot Status:** Enable
   - **API Base URL:** `https://api.abhinavgroup.co.in`
   - **Widget Key:** Your public widget key
   - **Position:** Bottom Right
   - **Auto Open:** Disabled (recommended)
   - Click **Save Changes**.
3. Clear any caching plugins (WP Rocket, LiteSpeed, Cloudflare).
4. Visit the website in an incognito window to verify the floating gold/navy chat bubble appears!
