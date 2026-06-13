"""Model registry — imports every entity so Alembic autogenerate sees them all.

This is the Day-0 schema-freeze source of truth. Changes after freeze are
additive only (new nullable columns / new tables).
"""

from app.db import Base
from app.models.application import Application
from app.models.contact import Contact
from app.models.dossier import Dossier
from app.models.generated_cv import GeneratedCv
from app.models.job import Job
from app.models.master_profile import MasterProfile
from app.models.outreach import Outreach
from app.models.reply import Reply
from app.models.sending_domain import SendingDomain
from app.models.thread import Thread
from app.models.user import RefreshToken, User
from app.models.va import Va
from app.models.va_assignment import VaAssignment

__all__ = [
    "Base",
    "User",
    "RefreshToken",
    "MasterProfile",
    "SendingDomain",
    "Va",
    "VaAssignment",
    "Job",
    "GeneratedCv",
    "Application",
    "Contact",
    "Outreach",
    "Thread",
    "Reply",
    "Dossier",
]
