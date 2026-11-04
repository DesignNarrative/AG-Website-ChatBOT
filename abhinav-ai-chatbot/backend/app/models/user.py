"""
Abhinav Group AI Chatbot — User Model
Admin dashboard users with role-based access control.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class UserRole(str, enum.Enum):
    """
    DEVELOPER: Full access including knowledge management.
    ADMIN:     Dashboard access, leads, conversations. No knowledge edits.
    STAFF:     Read-only leads and conversations. Mark leads as contacted.
    """
    DEVELOPER = "developer"
    ADMIN = "admin"
    STAFF = "staff"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole), nullable=False, default=UserRole.STAFF
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __init__(self, **kwargs):
        # Apply Python-level defaults so they work without a DB session
        kwargs.setdefault('id', str(uuid.uuid4()))
        kwargs.setdefault('role', UserRole.STAFF)
        kwargs.setdefault('is_active', True)
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<User {self.email} [{self.role}]>"
