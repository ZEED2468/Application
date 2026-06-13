"""Contract gate: every fixture payload must validate against its schema.

Fixtures ARE the inter-team API. A contract change that breaks a fixture is a
visible, reviewable failure here.
"""

import json
from pathlib import Path

import pytest

from app.events.contracts import CONTRACTS
from app.events.names import (
    APPLICATION_SUBMITTED,
    CV_GENERATED,
    JOB_DISCOVERED,
    JOB_SCORED,
    OUTREACH_SENT,
    REPLY_RECEIVED,
)

FIXTURES = Path(__file__).resolve().parents[1] / "app" / "events" / "fixtures"

FIXTURE_EVENT = {
    "job_discovered.json": JOB_DISCOVERED,
    "job_scored.json": JOB_SCORED,
    "cv_generated.json": CV_GENERATED,
    "application_submitted.json": APPLICATION_SUBMITTED,
    "outreach_sent.json": OUTREACH_SENT,
    "reply_received.json": REPLY_RECEIVED,
}


@pytest.mark.parametrize("filename,event", FIXTURE_EVENT.items())
def test_fixture_validates_against_contract(filename, event):
    payload = json.loads((FIXTURES / filename).read_text())
    schema = CONTRACTS[event]
    model = schema.model_validate(payload)  # raises on mismatch
    assert str(model.user_id)  # user_id present on every event


def test_every_event_has_a_fixture():
    assert set(FIXTURE_EVENT.values()) == set(CONTRACTS.keys())
