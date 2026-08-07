"""API router aggregation."""

from fastapi import APIRouter

from app.api import (
    admin_email,
    applications,
    ats_checker,
    auth,
    chat,
    cv_runs,
    integrations,
    invites,
    jobs,
    latex,
    onboarding,
    platforms,
    settings,
    sources,
    tracks,
    user,
    va,
)
from app.api.webhooks import webhooks_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(jobs.router)
api_router.include_router(applications.router)
api_router.include_router(onboarding.router)
api_router.include_router(latex.router)
api_router.include_router(ats_checker.router)
api_router.include_router(cv_runs.router)
api_router.include_router(chat.router)
api_router.include_router(va.router)
api_router.include_router(invites.router)
api_router.include_router(platforms.router)
api_router.include_router(settings.router)
api_router.include_router(integrations.router)
api_router.include_router(sources.router)
api_router.include_router(tracks.router)
api_router.include_router(user.router)
api_router.include_router(admin_email.router)
api_router.include_router(webhooks_router)
