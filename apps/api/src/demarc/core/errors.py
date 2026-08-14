"""Application errors mapped to HTTP responses by the handler in demarc.main."""

from __future__ import annotations


class DemarcError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.__class__.__name__)
        self.message = message or "An unexpected error occurred."


class NotFoundError(DemarcError):
    status_code = 404
    code = "not_found"


class ConflictError(DemarcError):
    status_code = 409
    code = "conflict"


class ValidationError(DemarcError):
    status_code = 422
    code = "validation_error"


class AuthenticationError(DemarcError):
    status_code = 401
    code = "unauthenticated"


class PermissionDeniedError(DemarcError):
    status_code = 403
    code = "permission_denied"


class BootstrapClosedError(DemarcError):
    status_code = 409
    code = "bootstrap_closed"
    message = "This deployment has already been initialized."
