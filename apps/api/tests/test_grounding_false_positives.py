"""Grounding entity seal — false-positive guards.

The seal must flag invented proper nouns, but NOT common resume adjectives ("Proficient") nor
slashed pairs whose halves are both real ("React Native/Expo"). Pure-function tests over a
RuleContext — no compile, no DB.
"""

from app.cv_engine.rules.base import RuleContext
from app.cv_engine.rules.grounding import _entities_verbatim


def _ledger(*texts: str) -> list[dict]:
    return [{"text": t, "payload": {}} for t in texts]


def _flagged(cv_json: dict, ledger: list[dict], name: str = "Ada Hunter") -> set[str]:
    ctx = RuleContext(cv_json=cv_json, ledger=ledger, name=name)
    return {v.span["entity"] for v in _entities_verbatim(ctx)}


def test_common_adjective_is_not_an_invented_entity():
    # "Proficient" (capitalized mid-clause) is a proficiency word, not a proper noun.
    cv = {"summary": "Backend engineer. Proficient in Go and distributed systems."}
    assert _flagged(cv, _ledger("Backend engineer building Go services")) == set()


def test_slashed_pair_grounds_half_by_half():
    # Both halves are in the ledger (as separate tokens) → the pair must pass, not false-flag.
    cv = {"experience": [{"title": "Engineer", "company": "Acme",
                          "bullets": ["Shipped apps with React Native/Expo"]}]}
    led = _ledger("React Native mobile apps", "Expo tooling", "Engineer at Acme")
    assert _flagged(cv, led) == set()


def test_ungrounded_half_of_a_slashed_pair_is_flagged():
    # One half is real, the other invented → flag only the invented half.
    cv = {"experience": [{"title": "Engineer", "company": "Acme",
                          "bullets": ["Shipped apps with React/Kafka"]}]}
    led = _ledger("React web apps", "Engineer at Acme")   # no Kafka anywhere
    assert _flagged(cv, led) == {"Kafka"}


def test_genuine_invented_entity_still_flagged():
    # The seal must still catch a fabricated employer (CamelCase proper noun).
    cv = {"experience": [{"title": "Engineer", "company": "TapPay",
                          "bullets": ["Built services"]}]}
    led = _ledger("Engineer at Streamline")   # TapPay never appears
    assert _flagged(cv, led) == {"TapPay"}
