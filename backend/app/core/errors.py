"""Domain exceptions mapped to HTTP responses in main.py."""


class DomainError(Exception):
    status_code = 400

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class NotFoundError(DomainError):
    status_code = 404


class AuthError(DomainError):
    status_code = 401


class ForbiddenError(DomainError):
    status_code = 403


class ConflictError(DomainError):
    status_code = 409
