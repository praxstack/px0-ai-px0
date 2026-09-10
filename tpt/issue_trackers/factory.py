"""
Factory module for instantiating issue tracker providers.
"""

from typing import Any, Dict, Type
from tpt.issue_trackers.base import BaseIssueTracker
from tpt.issue_trackers.exceptions import ValidationError
from tpt.issue_trackers.linear import LinearTracker
from tpt.issue_trackers.github import GitHubTracker

_REGISTRY: Dict[str, Type[BaseIssueTracker]] = {
    "linear": LinearTracker,
    "github": GitHubTracker,
}


def register_issue_tracker(name: str, tracker_cls: Type[BaseIssueTracker]) -> None:
    """
    Register a new issue tracker provider.

    :param name: Provider name (case-insensitive, e.g. "jira", "gitlab").
    :param tracker_cls: Subclass of BaseIssueTracker.
    """
    if not issubclass(tracker_cls, BaseIssueTracker):
        raise TypeError(f"{tracker_cls} must be a subclass of BaseIssueTracker")
    _REGISTRY[name.strip().lower()] = tracker_cls


def get_issue_tracker(provider: str, **kwargs: Any) -> BaseIssueTracker:
    """
    Factory function to instantiate an issue tracker client.

    :param provider: Name of provider ('linear', 'github', etc.).
    :param kwargs: Configuration options passed directly to the tracker constructor.
    :return: An instance implementing BaseIssueTracker.
    """
    key = provider.strip().lower()
    tracker_cls = _REGISTRY.get(key)
    if not tracker_cls:
        supported = ", ".join(repr(k) for k in _REGISTRY.keys())
        raise ValidationError(
            f"Unsupported issue tracker provider '{provider}'. Supported providers: {supported}"
        )
    return tracker_cls(**kwargs)
