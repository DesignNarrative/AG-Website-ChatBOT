"""
Projects API — Returns verified projects for the chatbot widget and admin dashboard.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.project import Project

router = APIRouter()


@router.get("/")
async def list_projects(
    db: AsyncSession = Depends(get_db),
):
    """List all active, approved projects for the chatbot and admin dashboard."""
    query = select(Project).order_by(Project.project_name.asc())
    result = await db.execute(query)
    projects_list = result.scalars().all()

    return {
        "projects": [
            {
                "id": p.id,
                "slug": p.project_id_slug,
                "name": p.project_name,
                "type": (
                    p.project_type.value.capitalize()
                    if hasattr(p.project_type, "value")
                    else str(p.project_type).capitalize()
                ),
                "location": p.location or p.city,
                "address": p.address,
                "configurations": (
                    p.configurations
                    if isinstance(p.configurations, str)
                    else ", ".join(p.configurations)
                    if isinstance(p.configurations, list)
                    else "2 & 3 BHK"
                ),
                "rera": f"{p.rera_number or 'Pending'}",
                "status": (
                    p.project_status.value.upper()
                    if hasattr(p.project_status, "value")
                    else str(p.project_status).upper()
                ),
                "possession": p.possession_date or "Enquire for updates",
                "price_status": "Contact Sales (+91 9309505388)",
                "description": p.description,
            }
            for p in projects_list
        ]
    }
