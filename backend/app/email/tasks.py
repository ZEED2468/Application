"""Email subsystem beat tasks: warm-up rollover + health scan."""

from __future__ import annotations

import structlog

from app.workers.celery_app import celery_app

log = structlog.get_logger(__name__)


@celery_app.task(name="task.email.warmup_rollover", bind=True)
def warmup_rollover(self) -> None:
    """Daily: reset per-domain counters, advance warm-up stage, drain queued sends."""
    log.info("email.warmup_rollover.tick")
    # TODO(eng2): reset daily counters, re-run governed_send on queued outreach.


@celery_app.task(name="task.email.health_scan", bind=True)
def health_scan(self) -> None:
    """Hourly: pull provider + Postmaster signals; auto-pause unhealthy domains."""
    log.info("email.health_scan.tick")
    # TODO(eng2): aggregate bounce/complaint rates, set is_paused over threshold.
