"""
Custom exception hierarchy for messaging integrations.
"""

from typing import Optional


class MessagingError(Exception):
    """Base exception for all messaging operations."""

    def __init__(self, message: str, provider: Optional[str] = None, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code

    def __str__(self) -> str:
        prefix = f"[{self.provider}] " if self.provider else ""
        code_str = f" (Status {self.status_code})" if self.status_code else ""
        return f"{prefix}{self.message}{code_str}"


class AuthenticationError(MessagingError):
    """Raised when authentication credentials (API token/OAuth) are invalid or expired."""
    pass


class PermissionDeniedError(MessagingError):
    """Raised when user/bot lacks permission to perform the requested operation."""
    pass


class ResourceNotFoundError(MessagingError):
    """Raised when a requested resource (channel, message, thread, user) is not found."""
    pass


class ChannelNotFoundError(ResourceNotFoundError):
    """Raised when a specific channel is not found."""
    pass


class MessageNotFoundError(ResourceNotFoundError):
    """Raised when a specific message or thread is not found."""
    pass


class RateLimitExceededError(MessagingError):
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


class ValidationError(MessagingError):
    """Raised when input parameters fail validation or are malformed."""
    pass


class ProviderAPIError(MessagingError):
    """Raised when an unhandled provider-specific error occurs."""
    pass
