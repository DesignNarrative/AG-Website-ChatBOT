"""
Abhinav Group AI Chatbot — API v1 Router
Assembles all endpoint routers.
"""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    chat,
    leads,
    projects,
    knowledge,
    admin,
    health,
)

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(chat.router, prefix="/chat", tags=["Chat"])
router.include_router(leads.router, prefix="/leads", tags=["Leads"])
router.include_router(projects.router, prefix="/projects", tags=["Projects"])
router.include_router(knowledge.router, prefix="/knowledge", tags=["Knowledge"])
router.include_router(admin.router, prefix="/admin", tags=["Admin"])
router.include_router(health.router, prefix="/system", tags=["System"])
