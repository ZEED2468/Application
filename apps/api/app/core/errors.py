"""Domain exceptions mapped to HTTP responses in main.py.

Each carries a machine-readable `code` and an optional `remediation` (what the user
can do to fix it) so the frontend can render actionable errors.
"""


class DomainError(Exception):
    status_code = 400
    code = "domain_error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        remediation: str | None = None,
        action: dict | None = None,
    ):
        self.message = message
        if code:
            self.code = code
        self.remediation = remediation
        # Optional structured next-step for the client, e.g. {"label": "Upload Resume",
        # "route": "/profile?track=backend"}.
        self.action = action
        super().__init__(message)


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class AuthError(DomainError):
    status_code = 401
    code = "unauthenticated"


class ForbiddenError(DomainError):
    status_code = 403
    code = "forbidden"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"
