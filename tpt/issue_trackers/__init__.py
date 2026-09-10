"""
TPT Issue Trackers module.

Provides a unified interface across issue tracking providers such as Linear and GitHub.
"""

from tpt.issue_trackers.base import (
    BaseIssueTracker,
    Comment,
    Issue,
    IssueStatus,
    User,
)
from tpt.issue_trackers.exceptions import (
    AuthenticationError,
    IssueNotFoundError,
    IssueTrackerError,
    PermissionDeniedError,
    ProviderAPIError,
    RateLimitExceededError,
    ResourceNotFoundError,
    ValidationError,
)
from tpt.issue_trackers.factory import get_issue_tracker, register_issue_tracker
from tpt.issue_trackers.github import GitHub, GitHubTracker
from tpt.issue_trackers.linear import Linear, LinearTracker

__all__ = [
    # Base abstractions & models
    "BaseIssueTracker",
    "Issue",
    "Comment",
    "User",
    "IssueStatus",
    # Providers
    "LinearTracker",
    "Linear",
    "GitHubTracker",
    "GitHub",
    # Factory
    "get_issue_tracker",
    "register_issue_tracker",
    # Exceptions
    "IssueTrackerError",
    "AuthenticationError",
    "PermissionDeniedError",
    "ResourceNotFoundError",
    "IssueNotFoundError",
    "RateLimitExceededError",
    "ValidationError",
    "ProviderAPIError",
]
