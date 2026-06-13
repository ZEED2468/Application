"""Canonical event names. Producers emit these; consumers bind tasks to them.

`evt.<entity>.<pastTense>` crosses pipeline boundaries (the inter-team API).
`task.<pipeline>.<verb>` are internal worker steps within a pipeline.
"""

JOB_DISCOVERED = "evt.job.discovered"
JOB_SCORED = "evt.job.scored"
CV_GENERATED = "evt.cv.generated"
APPLICATION_SUBMITTED = "evt.application.submitted"
OUTREACH_SENT = "evt.outreach.sent"
REPLY_RECEIVED = "evt.reply.received"

ALL_EVENTS = [
    JOB_DISCOVERED,
    JOB_SCORED,
    CV_GENERATED,
    APPLICATION_SUBMITTED,
    OUTREACH_SENT,
    REPLY_RECEIVED,
]
