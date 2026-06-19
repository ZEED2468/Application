"""API router aggregation."""

from fastapi import APIRouter

from app.api import (
    admin_email,
    applications,
    auth,
    chat,
    invites,
    jobs,
    onboarding,
    platforms,
    va,
)
from app.api.webhooks import webhooks_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(jobs.router)
api_router.include_router(applications.router)
api_router.include_router(onboarding.router)
api_router.include_router(chat.router)
api_router.include_router(va.router)
api_router.include_router(invites.router)
api_router.include_router(platforms.router)
api_router.include_router(admin_email.router)
api_router.include_router(webhooks_router)
