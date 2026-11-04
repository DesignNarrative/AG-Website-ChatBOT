# Abhinav Group AI Property Chatbot — Maintenance & Operations Guide

## 1. Routine Backups

### PostgreSQL Database
Automated daily dump script:
```bash
docker compose exec postgres pg_dump -U abhinav_admin -d abhinav_chatbot -F c -b -v -f /var/lib/postgresql/data/backup_$(date +%Y%m%d).dump
```

### Vector Store
The FAISS vector index files reside at `data/vector_store/`. Back up this directory before running website crawlers or re-indexing:
```bash
tar -czvf vector_store_backup_$(date +%Y%m%d).tar.gz data/vector_store/
```

---

## 2. Re-crawling Website Information

When Abhinav Group updates properties or launches new projects on `https://abhinavgroup.co.in`:

```powershell
# Run crawler script
python scripts/crawl_website/crawl_abhinav.py

# Review newly extracted pages and projects
cat data/reports/extraction_report.md

# Review unverified facts / missing information
cat data/reports/missing_information_report.md
```

> [!CAUTION]
> Never automatically publish crawled pricing or RERA numbers without manual verification from Abhinav Group management.

---

## 3. Switching AI Providers

The system is provider-agnostic. To switch between Google Gemini and OpenAI:

1. Update `.env`:
   - For Gemini: `AI_PROVIDER=gemini` and set `GEMINI_API_KEY`
   - For OpenAI: `AI_PROVIDER=openai` and set `OPENAI_API_KEY`
   - For local offline testing: `AI_PROVIDER=mock`
2. Restart backend:
   ```bash
   docker compose restart backend
   ```
3. Run the benchmark script to compare performance:
   ```bash
   python scripts/maintenance/benchmark_ai.py
   ```

---

## 4. Mdoc CRM Integration (Activation)

Currently, Mdoc runs in non-blocking mock mode.
When Maksoftbox provides production API credentials:
1. Contact: `info@maksoftbox.com`
2. Set in `.env`:
   ```ini
   MDOC_ENABLED=true
   MDOC_MODE=production
   MDOC_API_BASE=https://api.mdoc.in/v1
   MDOC_API_KEY=your_actual_key
   ```
3. Leads will automatically sync with Mdoc while keeping local copies and retry logs.
