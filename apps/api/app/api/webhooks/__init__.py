"""Webhook routers: Resend (inbound mail + events) and the WhatsApp bridge."""

from fastapi import APIRouter

from app.api.webhooks import bridge, resend

webhooks_router = APIRouter(prefix="/webhooks", tags=["webhooks"])
webhooks_router.include_router(resend.router)
webhooks_router.include_router(bridge.router)
