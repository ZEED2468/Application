"""Domain enums shared across models, schemas, and pipelines."""

import enum


class Track(str, enum.Enum):
    frontend = "frontend"
    backend = "backend"
    general = "general"


class UserRole(str, enum.Enum):
    hunter = "hunter"
    admin = "admin"


class PrincipalType(str, enum.Enum):
    user = "user"
    va = "va"


class DnsStatus(str, enum.Enum):
    pending = "pending"
    verified = "verified"
    failed = "failed"


class WarmupStage(str, enum.Enum):
    stage_1 = "stage_1"  # day 1-3:  5/day
    stage_2 = "stage_2"  # day 4-7:  10/day
    stage_3 = "stage_3"  # day 8-14: 20/day
    full = "full"        # day 15+:  full volume


class JobSourceName(str, enum.Enum):
    greenhouse = "greenhouse"
    lever = "lever"
    ashby = "ashby"
    adzuna = "adzuna"
    serpapi = "serpapi"


class JobStatus(str, enum.Enum):
    discovered = "discovered"
    scored = "scored"
    rejected = "rejected"
    tailoring = "tailoring"
    ready = "ready"
    submitted = "submitted"


class CvStatus(str, enum.Enum):
    rendering = "rendering"
    ready = "ready"
    failed = "failed"


class ApplicationStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    interview = "interview"
    rejected = "rejected"
    offer = "offer"
    failed = "failed"


class SequenceStep(str, enum.Enum):
    first = "first"
    followup1 = "followup1"
    followup2 = "followup2"
    stopped = "stopped"


class OutreachStatus(str, enum.Enum):
    drafted = "drafted"
    review = "review"
    queued = "queued"
    sent = "sent"
    bounced = "bounced"
    replied = "replied"
    stopped = "stopped"


class ThreadState(str, enum.Enum):
    open = "open"
    awaiting_va = "awaiting_va"
    awaiting_send = "awaiting_send"
    closed = "closed"


class ReplyDirection(str, enum.Enum):
    inbound = "inbound"
    outbound = "outbound"


class ReplyClassification(str, enum.Enum):
    routine = "routine"
    substantive = "substantive"


class DossierStatus(str, enum.Enum):
    pushed = "pushed"
    va_replied = "va_replied"
    relayed = "relayed"
    closed = "closed"
