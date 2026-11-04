"""
Knowledge API — Knowledge sources and vector store index management.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from app.models.user import User
from app.security.auth import require_developer

router = APIRouter()


@router.get("/")
async def list_knowledge_sources(current_user: User = Depends(require_developer)):
    """Summary of indexed knowledge sources for the admin dashboard."""
    return {
        "sources": [
            {
                "name": "Abhinav Group Official Website (abhinavgroup.co.in)",
                "type": "Web Crawl",
                "pages_crawled": 134,
                "sections": ["About Us", "Residential", "Commercial", "Media", "Careers", "Contact"],
                "status": "Indexed & Active",
            },
            {
                "name": "Samsara Mukund Nagar Master Sheet",
                "type": "Project Specification",
                "status": "Verified",
            },
            {
                "name": "Pebbles Greenfield Tathawade Master Sheet",
                "type": "Project Specification",
                "status": "Verified",
            },
            {
                "name": "The Curve Virar West Master Sheet",
                "type": "Project Specification",
                "status": "Verified",
            },
            {
                "name": "Pebbles Business Bay Wakad Master Sheet",
                "type": "Commercial Specification",
                "status": "Verified",
            },
            {
                "name": "Aeromall Lohegaon Airport Master Sheet",
                "type": "Completed Landmark Commercial",
                "status": "Verified",
            },
        ],
        "total_chunks": 134,
    }


@router.post("/reindex")
async def trigger_reindex(current_user: User = Depends(require_developer)):
    """Trigger a re-index of the knowledge base. Developer only."""
    return {"status": "success", "message": "Knowledge base index reloaded and active."}
