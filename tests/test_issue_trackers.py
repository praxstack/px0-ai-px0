"""Unit tests for issue trackers (mocked & offline)."""

import pytest
from unittest.mock import MagicMock, patch

from tpt.issue_trackers import (
    BaseIssueTracker,
    Comment,
    Issue,
    IssueNotFoundError,
    IssueStatus,
    User,
    ValidationError,
    get_issue_tracker,
    register_issue_tracker,
)
from tpt.issue_trackers.github import GitHubTracker
from tpt.issue_trackers.linear import LinearTracker


def test_factory_instantiation():
    linear = get_issue_tracker("linear", api_key="dummy_token")
    assert isinstance(linear, LinearTracker)

    github = get_issue_tracker("github", token="dummy_token")
    assert isinstance(github, GitHubTracker)

    with pytest.raises(ValidationError):
        get_issue_tracker("unsupported_provider")


def test_custom_provider_registration():
    class CustomTracker(BaseIssueTracker):
        def list_issues(self, **kwargs): return []
        def get_issue(self, issue_id, **kwargs): pass
        def create_issue(self, title, **kwargs): pass
        def update_issue(self, issue_id, **kwargs): pass
        def close_issue(self, issue_id, **kwargs): pass
        def reopen_issue(self, issue_id, **kwargs): pass
        def get_comments(self, issue_id, **kwargs): return []
        def add_comment(self, issue_id, body, **kwargs): pass
        def add_label(self, issue_id, label, **kwargs): pass
        def remove_label(self, issue_id, label, **kwargs): pass
        def get_assignees(self, **kwargs): return []
        def assign_issue(self, issue_id, user_id_or_name, **kwargs): pass
        def unassign_issue(self, issue_id, user_id_or_name=None, **kwargs): pass

    register_issue_tracker("custom", CustomTracker)
    inst = get_issue_tracker("custom")
    assert isinstance(inst, CustomTracker)


def test_github_tracker_methods():
    tracker = GitHubTracker(token="fake", default_repo="owner/repo")
    tracker.session = MagicMock()

    # Mock get_issue
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": 101,
        "number": 5,
        "title": "Bug in login",
        "body": "Fix it",
        "state": "open",
        "labels": [{"name": "bug"}],
        "assignees": [{"id": 1, "login": "alice", "name": "Alice"}],
        "html_url": "https://github.com/owner/repo/issues/5",
    }
    tracker.session.request.return_value = mock_resp

    issue = tracker.get_issue("5")
    assert issue.identifier == "#5"
    assert issue.title == "Bug in login"
    assert issue.assignee == "alice"
    assert "bug" in issue.labels


def test_linear_tracker_state_mapping():
    tracker = LinearTracker(api_key="fake")
    node = {
        "id": "abc-123",
        "identifier": "ENG-42",
        "title": "Database index tuning",
        "description": "Details here",
        "state": {"id": "s1", "name": "Done", "type": "completed"},
        "labels": {"nodes": [{"id": "l1", "name": "performance"}]},
        "assignee": {"id": "u1", "name": "Bob", "email": "bob@example.com"},
        "priority": 1,
    }
    issue = tracker._parse_issue(node)
    assert issue.identifier == "ENG-42"
    assert issue.status == IssueStatus.COMPLETED
    assert issue.status_name == "Done"
    assert issue.priority == 1
    assert issue.priority_label == "Urgent"
    assert issue.assignee == "Bob"
    assert issue.labels == ["performance"]
