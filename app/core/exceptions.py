"""
Custom exception classes for domain-specific errors.
Following SOLID principles, these exceptions represent domain logic errors
rather than HTTP-specific errors.
"""


class DomainException(Exception):
    """Base exception for all domain-related errors."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class ValidationError(DomainException):
    """Raised when input validation fails."""

    pass


class NotFoundError(DomainException):
    """Raised when a requested resource is not found."""

    pass


class ConflictError(DomainException):
    """Raised when an operation conflicts with current state."""

    pass


class UnauthorizedError(DomainException):
    """Raised when authentication fails."""

    pass


class ForbiddenError(DomainException):
    """Raised when authorization fails."""

    pass


# User-specific exceptions
class UserNotFoundError(NotFoundError):
    """Raised when a user is not found."""

    def __init__(self, user_id: int = None, username: str = None, email: str = None):
        if user_id:
            message = f"User with ID {user_id} not found"
        elif username:
            message = f"User with username '{username}' not found"
        elif email:
            message = f"User with email '{email}' not found"
        else:
            message = "User not found"
        super().__init__(message)


class UserAlreadyExistsError(ConflictError):
    """Raised when attempting to create a user that already exists."""

    def __init__(self, field: str, value: str):
        message = f"User with {field} '{value}' already exists"
        super().__init__(message)


class InvalidCredentialsError(UnauthorizedError):
    """Raised when authentication credentials are invalid."""

    def __init__(self):
        super().__init__("Invalid credentials provided")
