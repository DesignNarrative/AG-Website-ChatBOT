"""
Abhinav Group AI Chatbot — Database Models Package
All SQLAlchemy ORM models are imported here for Alembic auto-detection.
"""
from app.database.session import Base  # noqa: F401

# Import all models so Alembic sees them in metadata
from app.models.user import User  # noqa: F401
from app.models.project import Project, ProjectImage, ProjectDocument  # noqa: F401
from app.models.knowledge import KnowledgeChunk, KnowledgeSource  # noqa: F401
from app.models.conversation import Conversation, Message  # noqa: F401
from app.models.lead import Lead, LeadNote, MdocSyncRecord  # noqa: F401
from app.models.document import Document  # noqa: F401
from app.models.image import Image  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
