"""
Abhinav Group AI Chatbot — Admin Endpoints
Serves operational metrics and live conversation transcripts to the React admin dashboard.
"""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.conversation import Conversation, Message
from app.models.lead import Lead
from app.models.project import Project
from app.models.user import User
from app.security.auth import require_any_staff

router = APIRouter()


@router.get("/overview")
async def admin_overview(
    current_user: User = Depends(require_any_staff),
    db: AsyncSession = Depends(get_db),
):
    """Live operational metrics for the admin dashboard."""
    conv_count = (await db.execute(select(func.count(Conversation.id)))).scalar() or 0
    lead_count = (await db.execute(select(func.count(Lead.id)))).scalar() or 0
    proj_count = (
        await db.execute(select(func.count(Project.id)).where(Project.is_active == True))  # noqa: E712
    ).scalar() or 0
    msg_count = (await db.execute(select(func.count(Message.id)))).scalar() or 0

    return {
        "total_conversations": conv_count,
        "total_leads": lead_count,
        "active_projects": proj_count,
        "knowledge_chunks": 134,
        "total_messages": msg_count,
    }


@router.get("/conversations")
async def list_conversations(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    language: Optional[str] = Query(default=None),
    current_user: User = Depends(require_any_staff),
    db: AsyncSession = Depends(get_db),
):
    """List visitor chat sessions ordered by most recent activity."""
    query = select(Conversation)
    if language and language.upper() != "ALL":
        query = query.where(Conversation.language == language.lower())

    query = query.order_by(desc(Conversation.last_message_at), desc(Conversation.started_at))
    query = query.offset(offset).limit(limit)

    result = await db.execute(query)
    conversations = result.scalars().all()

    count_query = select(func.count(Conversation.id))
    if language and language.upper() != "ALL":
        count_query = count_query.where(Conversation.language == language.lower())
    total = (await db.execute(count_query)).scalar() or 0

    return {
        "conversations": [
            {
                "id": c.id,
                "session_token": c.session_token,
                "language": c.language or "en",
                "status": c.status.value.upper() if hasattr(c.status, "value") else str(c.status).upper(),
                "message_count": c.message_count or 0,
                "customer_name": c.customer_name,
                "customer_phone": c.customer_phone,
                "started_at": c.started_at.isoformat() if c.started_at else None,
                "last_activity": (c.last_message_at or c.started_at).isoformat() if (c.last_message_at or c.started_at) else None,
                "source_page": c.source_page,
            }
            for c in conversations
        ],
        "total": total,
    }


@router.get("/conversations/{session_token}")
async def get_conversation_detail(
    session_token: str,
    current_user: User = Depends(require_any_staff),
    db: AsyncSession = Depends(get_db),
):
    """Get full transcript and messages for a specific conversation session."""
    conv_result = await db.execute(
        select(Conversation).where(Conversation.session_token == session_token)
    )
    conv = conv_result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation session not found.")

    msgs_result = await db.execute(
        select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at.asc())
    )
    messages = msgs_result.scalars().all()

    return {
        "session_token": conv.session_token,
        "language": conv.language,
        "status": conv.status.value.upper() if hasattr(conv.status, "value") else str(conv.status).upper(),
        "message_count": conv.message_count,
        "customer_name": conv.customer_name,
        "customer_phone": conv.customer_phone,
        "started_at": conv.started_at.isoformat() if conv.started_at else None,
        "messages": [
            {
                "id": m.id,
                "role": m.role.value if hasattr(m.role, "value") else str(m.role),
                "content": m.content,
                "language": m.language,
                "intent": m.intent,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }
