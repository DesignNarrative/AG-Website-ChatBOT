"""Projects, Knowledge, Admin, Health endpoint stubs."""
from fastapi import APIRouter, Depends
from app.security.auth import require_admin_or_developer, require_developer, require_any_staff
from app.models.user import User

# --- Projects ---
router_projects = APIRouter()

@router_projects.get("/")
async def list_projects():
    """List all active, approved projects for the chatbot."""
    return {"projects": [], "note": "Phase 3 will populate this from the knowledge base."}

router = router_projects  # exported as 'projects'


# --- Knowledge ---
from fastapi import APIRouter as _APIRouter
router_knowledge = _APIRouter()

@router_knowledge.get("/")
async def list_knowledge_sources(current_user: User = Depends(require_developer)):
    return {"sources": [], "note": "Phase 4 will implement full knowledge management."}

@router_knowledge.post("/reindex")
async def trigger_reindex(current_user: User = Depends(require_developer)):
    """Trigger a full re-indexing of the knowledge base. Developer only."""
    return {"status": "queued", "message": "Re-indexing will be implemented in Phase 4."}


# --- Admin ---
router_admin = _APIRouter()

@router_admin.get("/overview")
async def admin_overview(current_user: User = Depends(require_any_staff)):
    return {
        "total_conversations": 0,
        "total_leads": 0,
        "active_projects": 0,
        "knowledge_chunks": 0,
        "note": "Dashboard data will be live after Phase 7."
    }


# --- Health / System ---
router_health = _APIRouter()

@router_health.get("/health")
async def system_health():
    from app.database.session import check_db_connection
    from app.core.config import settings
    db_ok = await check_db_connection()
    return {
        "database": "ok" if db_ok else "error",
        "ai_provider": settings.ai_provider,
        "mdoc_mode": settings.mdoc_mode,
        "celery_enabled": settings.celery_enabled,
    }
