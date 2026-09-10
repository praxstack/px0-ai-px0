"""
Base interfaces and data models for issue tracking systems.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class IssueStatus(str, Enum):
    """Standardized issue status categories across providers."""
    BACKLOG = "backlog"
    UNSTARTED = "unstarted"
    STARTED = "started"
    COMPLETED = "completed"
    CANCELED = "canceled"
    UNKNOWN = "unknown"


@dataclass
class User:
    """Represents a user/assignee in an issue tracking system."""
    id: str
    name: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None
    avatar_url: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Comment:
    """Represents a comment on an issue."""
    id: str
    body: str
    author: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Issue:
    """Represents a standardized issue across issue tracker systems."""
    id: str
    identifier: str  # e.g., "ENG-123" or "#42"
    title: str
    description: Optional[str] = None
    status: IssueStatus = IssueStatus.UNKNOWN
    status_name: Optional[str] = None  # Provider-specific state name, e.g. "In Progress", "Closed"
    priority: Optional[int] = None
    priority_label: Optional[str] = None
    url: Optional[str] = None
    assignee: Optional[str] = None  # Display name or username of primary assignee
    assignees: List[User] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


class BaseIssueTracker(ABC):
    """Abstract base class defining core issue tracking capabilities."""

    @abstractmethod
    def list_issues(
        self,
        project_or_team: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        **kwargs: Any,
    ) -> List[Issue]:
        """
        List issues matching the given filters.

        :param project_or_team: Project/repository/team key or identifier.
        :param status: Status or state filter ('open', 'closed', 'backlog', etc.).
        :param limit: Maximum number of issues to fetch.
        :param kwargs: Provider-specific filtering arguments.
        :return: List of Issue objects.
        """
        pass

    @abstractmethod
    def get_issue(self, issue_id: str, **kwargs: Any) -> Issue:
        """
        Retrieve a single issue by ID or identifier (e.g. key or number).

        :param issue_id: Issue ID or key/identifier.
        :return: Issue object.
        """
        pass

    @abstractmethod
    def create_issue(
        self,
        title: str,
        description: Optional[str] = None,
        project_or_team: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        assignee_id: Optional[str] = None,
        labels: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Issue:
        """
        Create a new issue.

        :param title: Issue title.
        :param description: Optional markdown or text description.
        :param project_or_team: Target repository, project, or team identifier.
        :param status: Initial status or state name/ID.
        :param priority: Priority value.
        :param assignee_id: User identifier to assign to.
        :param labels: List of label names to attach.
        :param kwargs: Additional provider-specific fields.
        :return: Created Issue object.
        """
        pass

    @abstractmethod
    def update_issue(
        self,
        issue_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        assignee_id: Optional[str] = None,
        labels: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Issue:
        """
        Update fields on an existing issue.

        :param issue_id: Issue ID or key/identifier.
        :param title: Updated title.
        :param description: Updated description.
        :param status: Updated status / state.
        :param priority: Updated priority.
        :param assignee_id: Updated assignee ID.
        :param labels: Complete updated list of label names.
        :param kwargs: Additional provider-specific update parameters.
        :return: Updated Issue object.
        """
        pass

    @abstractmethod
    def close_issue(self, issue_id: str, reason: Optional[str] = None, **kwargs: Any) -> Issue:
        """
        Close or mark an issue as completed/done.

        :param issue_id: Issue ID or key/identifier.
        :param reason: Optional closing note or reason.
        :param kwargs: Provider-specific options.
        :return: Updated Issue object.
        """
        pass

    @abstractmethod
    def reopen_issue(self, issue_id: str, **kwargs: Any) -> Issue:
        """
        Reopen a closed issue (moves to open / unstarted state).

        :param issue_id: Issue ID or key/identifier.
        :param kwargs: Provider-specific options.
        :return: Updated Issue object.
        """
        pass

    @abstractmethod
    def get_comments(self, issue_id: str, **kwargs: Any) -> List[Comment]:
        """
        Fetch all comments for a given issue.

        :param issue_id: Issue ID or key/identifier.
        :return: List of Comment objects.
        """
        pass

    @abstractmethod
    def add_comment(self, issue_id: str, body: str, **kwargs: Any) -> Comment:
        """
        Post a comment to an issue.

        :param issue_id: Issue ID or key/identifier.
        :param body: Comment markdown or plain text.
        :return: Created Comment object.
        """
        pass

    @abstractmethod
    def add_label(self, issue_id: str, label: str, **kwargs: Any) -> Issue:
        """
        Add a label to an issue.

        :param issue_id: Issue ID or key/identifier.
        :param label: Label name to add.
        :return: Updated Issue object.
        """
        pass

    @abstractmethod
    def remove_label(self, issue_id: str, label: str, **kwargs: Any) -> Issue:
        """
        Remove a label from an issue.

        :param issue_id: Issue ID or key/identifier.
        :param label: Label name to remove.
        :return: Updated Issue object.
        """
        pass

    @abstractmethod
    def get_assignees(self, project_or_team: Optional[str] = None, **kwargs: Any) -> List[User]:
        """
        Get potential assignees (members or collaborators) for the workspace/team/repository.

        :param project_or_team: Target repository, project, or team identifier.
        :return: List of User objects.
        """
        pass

    @abstractmethod
    def assign_issue(self, issue_id: str, user_id_or_name: str, **kwargs: Any) -> Issue:
        """
        Assign an issue to a user.

        :param issue_id: Issue ID or key/identifier.
        :param user_id_or_name: User ID, username, or identifier to assign.
        :return: Updated Issue object.
        """
        pass

    @abstractmethod
    def unassign_issue(
        self, issue_id: str, user_id_or_name: Optional[str] = None, **kwargs: Any
    ) -> Issue:
        """
        Unassign an issue. If user_id_or_name is omitted, clears all assignees.

        :param issue_id: Issue ID or key/identifier.
        :param user_id_or_name: Specific user ID or name to remove, or None to unassign all.
        :return: Updated Issue object.
        """
        pass
