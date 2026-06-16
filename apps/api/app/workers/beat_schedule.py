"""Periodic schedule for all timers. Imported by celery_app at startup.

Task bodies live in their pipelines; here we only wire the cadence. The task
names are referenced as strings so this module imports cheaply.
"""

from celery.schedules import crontab

from app.workers.celery_app import celery_app

celery_app.conf.beat_schedule = {
    # Pipeline A: pull new jobs from all enabled sources.
    "poll-sources": {
        "task": "task.apply.poll_sources",
        "schedule": 30 * 60,  # every 30 min
    },
    # Email: daily reset of per-domain counters + warm-up stage advance + drain queue.
    "warmup-rollover": {
        "task": "task.email.warmup_rollover",
        "schedule": crontab(hour=0, minute=5),
    },
    # Pipeline B: follow-up sequencer (4d -> followup1 -> 5d -> followup2 -> stop).
    "sequencer-tick": {
        "task": "task.outreach.sequencer_tick",
        "schedule": 60 * 60,  # hourly
    },
    # Pipeline C: inbox poll backup to webhooks.
    "poll-inboxes": {
        "task": "task.respond.poll_inboxes",
        "schedule": 5 * 60,  # every 5 min
    },
    # Email: pull provider + Postmaster signals, auto-pause unhealthy domains.
    "health-scan": {
        "task": "task.email.health_scan",
        "schedule": 60 * 60,  # hourly
    },
}
