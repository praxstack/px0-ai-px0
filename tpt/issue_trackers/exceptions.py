"""
Custom exception hierarchy for issue tracking integrations.
"""

from typing import Optional


class IssueTrackerError(Exception):
    """Base exception for all issue tracker operations."""

    def __init__(self, message: str, provider: Optional[str] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code

    def __str__(self) -> str:
        prefix = f"[{self.provider}] " if self.provider else ""
        code_str = f" (Status {self.status_code})" if self.status_code else ""
        return f"{prefix}{self.message}{code_str}"


class AuthenticationError(IssueTrackerError):
    """Raised when authentication credentials (API token/key) are invalid or expired."""
    pass


class PermissionDeniedError(IssueTrackerError):
    """Raised when user lacks permission to perform the requested operation."""
    pass


class ResourceNotFoundError(IssueTrackerError):
    """Raised when a requested resource (issue, comment, user, label, project) is not found."""
    pass


class IssueNotFoundError(ResourceNotFoundError):
    """Raised when a specific issue is not found."""
    pass


class RateLimitExceededError(IssueTrackerError):
    """Raised when the provider's API rate limit has been exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        provider: Optional[str] = None,
        retry_after: Optional[int] = None,
        status_code: Optional[int] = 429,
    ):
        super().__init__(message, provider=provider, status_code=status_code)
        self.retry_after = retry_after


class ValidationError(IssueTrackerError):
    """Raised when input parameters fail validation or are malformed."""
    pass


class ProviderAPIError(IssueTrackerError):
    """Raised when an unexpected or unhandled API error occurs from the upstream provider."""
    pass
