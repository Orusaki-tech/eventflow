class DomainError(Exception):
    pass


class PastEventError(DomainError):
    pass


class DraftNotFound(DomainError):
    pass


class PermissionDenied(DomainError):
    pass


class InvariantViolation(DomainError):
    pass

