"""
TPT Messaging module.

Provides an extensible interface across team messaging tools such as Slack.
"""

from tpt.messaging.base import (
    BaseMessagingClient,
    Channel,
    Message,
    Thread,
    User,
)
from tpt.messaging.exceptions import (
    AuthenticationError,
    ChannelNotFoundError,
    MessageNotFoundError,
    MessagingError,
    PermissionDeniedError,
    ProviderAPIError,
    RateLimitExceededError,
    ResourceNotFoundError,
    ValidationError,
)
from tpt.messaging.factory import get_messaging_client, register_messaging_client
from tpt.messaging.slack import Slack, SlackMessaging

__all__ = [
    # Models & Base
    "BaseMessagingClient",
    "Message",
    "Thread",
    "Channel",
    "User",
    # Providers
    "SlackMessaging",
    "Slack",
    # Factory
    "get_messaging_client",
    "register_messaging_client",
    # Exceptions
    "MessagingError",
    "AuthenticationError",
    "PermissionDeniedError",
    "ResourceNotFoundError",
    "ChannelNotFoundError",
    "MessageNotFoundError",
    "RateLimitExceededError",
    "ValidationError",
    "ProviderAPIError",
]
