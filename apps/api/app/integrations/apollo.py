"""Apollo people lookup. Finds 2-3 right people at a company.

Targeting priority: team engineer > hiring manager > internal recruiter;
generic "talent" inboxes deprioritized. Fake mode returns deterministic people.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.config import settings

# Lower rank = higher priority.
ROLE_RANK = {"engineer": 0, "hiring_manager": 1, "recruiter": 2, "talent": 9}


@dataclass(slots=True)
class Person:
    full_name: str
    title: str
    role_type: str
    email: str
    linkedin: str | None = None
    apollo_id: str | None = None
    confidence: float = 0.5


def _domain_for(company: str) -> str:
    slug = "".join(c for c in company.lower() if c.isalnum())
    return f"{slug or 'company'}.com"


def _fake_people(company: str) -> list[Person]:
    d = _domain_for(company)
    return [
        Person(f"Dana Ng", "Staff Engineer", "engineer", f"dana@{d}",
               f"https://linkedin.com/in/dana-ng", "apollo-eng-1", 0.8),
        Person(f"Sam Ortiz", "Engineering Manager", "hiring_manager", f"sam@{d}",
               f"https://linkedin.com/in/sam-ortiz", "apollo-hm-1", 0.7),
        Person(f"Riley Cole", "Technical Recruiter", "recruiter", f"riley@{d}",
               None, "apollo-rec-1", 0.5),
    ]


def _prioritize(people: list[Person], limit: int = 3) -> list[Person]:
    return sorted(people, key=lambda p: ROLE_RANK.get(p.role_type, 5))[:limit]


async def lookup_people(*, company: str, role_title: str | None = None, limit: int = 3) -> list[Person]:
    if settings.use_fake_integrations or not settings.apollo_api_key:
        return _prioritize(_fake_people(company), limit)

    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.post(
                "https://api.apollo.io/v1/mixed_people/search",
                headers={"X-Api-Key": settings.apollo_api_key},
                json={"q_organization_domains": _domain_for(company), "page": 1,
                      "person_titles": ["software engineer", "engineering manager", "recruiter"]},
            )
            resp.raise_for_status()
        except httpx.HTTPError:
            return []
        people: list[Person] = []
        for p in resp.json().get("people", []):
            title = (p.get("title") or "").lower()
            role = ("engineer" if "engineer" in title else
                    "hiring_manager" if "manager" in title else
                    "recruiter" if "recruit" in title else "talent")
            people.append(Person(
                p.get("name", ""), p.get("title", ""), role,
                p.get("email") or "", p.get("linkedin_url"), p.get("id"), 0.6,
            ))
        return _prioritize([p for p in people if p.email], limit)
