"""
GitHub Issue Tracker implementation.

Implements BaseIssueTracker using GitHub REST API v3.
"""

from datetime import datetime
import os
import shutil
import subprocess
from typing import Any, Dict, List, Optional
import requests

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
    PermissionDeniedError,
    ProviderAPIError,
    RateLimitExceededError,
    ResourceNotFoundError,
    ValidationError,
)

GITHUB_API_BASE = "https://api.github.com"


def _get_default_github_token() -> Optional[str]:
    """Retrieve GitHub token from environment, user config, or GitHub CLI (gh)."""
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        return token

    # Check local config file if present
    cfg_file = os.path.expanduser("~/.config/tpt_tokens.env")
    if os.path.isfile(cfg_file):
        try:
            with open(cfg_file) as f:
                for line in f:
                    if line.strip().startswith("export GITHUB_TOKEN="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
        except Exception:
            pass

    # Try gh auth token if CLI is installed
    if shutil.which("gh"):
        try:
            out = subprocess.check_output(
                ["gh", "auth", "token"],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5,
            ).strip()
            if out:
                return out
        except Exception:
            pass

    return None


def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


class GitHubTracker(BaseIssueTracker):
    """GitHub issue tracker client implementing BaseIssueTracker."""

    def __init__(
        self,
        token: Optional[str] = None,
        default_repo: Optional[str] = None,
        api_base: str = GITHUB_API_BASE,
        timeout: int = 30,
    ):
        """
        Initialize GitHubTracker.

        :param token: GitHub personal access token or OAuth token.
                      Defaults to GITHUB_TOKEN / GH_TOKEN env vars or GitHub CLI (gh auth token).
        :param default_repo: Default repository in "owner/repo" format (e.g. "px0-ai/px0").
        :param api_base: Base URL for GitHub API.
        :param timeout: HTTP timeout in seconds.
        """
        self.token = token or _get_default_github_token()
        if not self.token:
            raise AuthenticationError(
                "GitHub token is required. Set GITHUB_TOKEN / GH_TOKEN or pass token parameter.",
                provider="GitHub",
            )
        self.default_repo = default_repo or os.getenv("GITHUB_REPOSITORY", "px0-ai/px0")
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    def _resolve_repo(self, repo: Optional[str] = None) -> str:
        target = repo or self.default_repo
        if not target or "/" not in target:
            raise ValidationError(
                f"Invalid repository '{target}'. Must be in 'owner/repo' format.",
                provider="GitHub",
            )
        return target

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = f"{self.api_base}/{path.lstrip('/')}"
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_data,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise ProviderAPIError(f"Network error connecting to GitHub: {e}", provider="GitHub") from e

        if response.status_code == 401:
            raise AuthenticationError("GitHub authentication failed. Bad credentials.", provider="GitHub", status_code=401)
        if response.status_code == 403:
            if "rate limit" in response.text.lower():
                retry_after = None
                if "retry-after" in response.headers:
                    try:
                        retry_after = int(response.headers["retry-after"])
                    except Exception:
                        pass
                raise RateLimitExceededError("GitHub rate limit exceeded.", provider="GitHub", retry_after=retry_after, status_code=403)
            raise PermissionDeniedError(f"Permission denied on GitHub: {response.text}", provider="GitHub", status_code=403)
        if response.status_code == 404:
            raise IssueNotFoundError(f"GitHub resource not found at {path}", provider="GitHub", status_code=404)
        if response.status_code == 422:
            raise ValidationError(f"GitHub validation error: {response.text}", provider="GitHub", status_code=422)
        if not response.ok:
            raise ProviderAPIError(f"GitHub error ({response.status_code}): {response.text}", provider="GitHub", status_code=response.status_code)

        if response.status_code == 204 or not response.content:
            return None

        return response.json()

    def _parse_user(self, data: Optional[Dict[str, Any]]) -> Optional[User]:
        if not data:
            return None
        return User(
            id=str(data.get("id")),
            name=data.get("name"),
            username=data.get("login"),
            avatar_url=data.get("avatar_url"),
            raw_data=data,
        )

    def _parse_issue(self, data: Dict[str, Any]) -> Issue:
        state = (data.get("state") or "open").lower()
        status = IssueStatus.COMPLETED if state == "closed" else IssueStatus.STARTED

        labels = []
        for l in data.get("labels") or []:
            if isinstance(l, dict) and "name" in l:
                labels.append(l["name"])
            elif isinstance(l, str):
                labels.append(l)

        assignees_list: List[User] = []
        for u in data.get("assignees") or []:
            parsed_u = self._parse_user(u)
            if parsed_u:
                assignees_list.append(parsed_u)

        primary_assignee = None
        if data.get("assignee"):
            primary_assignee = data["assignee"].get("login")
        elif assignees_list:
            primary_assignee = assignees_list[0].username

        return Issue(
            id=str(data["id"]),
            identifier=f"#{data['number']}",
            title=data.get("title", ""),
            description=data.get("body"),
            status=status,
            status_name=state,
            url=data.get("html_url"),
            assignee=primary_assignee,
            assignees=assignees_list,
            labels=labels,
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
            closed_at=_parse_datetime(data.get("closed_at")),
            raw_data=data,
        )

    def _parse_comment(self, data: Dict[str, Any]) -> Comment:
        author = (data.get("user") or {}).get("login")
        return Comment(
            id=str(data["id"]),
            body=data.get("body", ""),
            author=author,
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
            raw_data=data,
        )

    def _parse_issue_number(self, issue_id: str) -> int:
        clean = issue_id.strip().lstrip("#")
        try:
            return int(clean)
        except ValueError:
            raise ValidationError(f"Invalid GitHub issue identifier '{issue_id}'. Expected issue number like 12 or '#12'.", provider="GitHub")

    def list_issues(
        self,
        project_or_team: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        **kwargs: Any,
    ) -> List[Issue]:
        repo = self._resolve_repo(project_or_team)
        params: Dict[str, Any] = {"per_page": min(limit, 100)}

        if status:
            s_lower = status.lower().strip()
            if s_lower in ("completed", "closed"):
                params["state"] = "closed"
            elif s_lower in ("open", "started", "unstarted", "backlog"):
                params["state"] = "open"
            else:
                params["state"] = s_lower
        else:
            params["state"] = "all"

        for k, v in kwargs.items():
            if v is not None:
                params[k] = v

        data = self._request("GET", f"repos/{repo}/issues", params=params)
        issues = [item for item in data if "pull_request" not in item]
        return [self._parse_issue(item) for item in issues[:limit]]

    def get_issue(self, issue_id: str, repo: Optional[str] = None, **kwargs: Any) -> Issue:
        target_repo = self._resolve_repo(repo)
        num = self._parse_issue_number(issue_id)
        data = self._request("GET", f"repos/{target_repo}/issues/{num}")
        return self._parse_issue(data)

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
        repo = self._resolve_repo(project_or_team)
        payload: Dict[str, Any] = {"title": title}
        if description is not None:
            payload["body"] = description
        if assignee_id:
            payload["assignees"] = [assignee_id]
        if labels:
            payload["labels"] = labels

        for k, v in kwargs.items():
            if v is not None:
                payload[k] = v

        data = self._request("POST", f"repos/{repo}/issues", json_data=payload)
        created_issue = self._parse_issue(data)

        if status and status.lower() in ("closed", "completed"):
            return self.close_issue(str(data["number"]), repo=repo)

        return created_issue

    def update_issue(
        self,
        issue_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[int] = None,
        assignee_id: Optional[str] = None,
        labels: Optional[List[str]] = None,
        repo: Optional[str] = None,
        **kwargs: Any,
    ) -> Issue:
        target_repo = self._resolve_repo(repo)
        num = self._parse_issue_number(issue_id)
        payload: Dict[str, Any] = {}

        if title is not None:
            payload["title"] = title
        if description is not None:
            payload["body"] = description
        if status is not None:
            s_lower = status.lower().strip()
            if s_lower in ("closed", "completed", "canceled"):
                payload["state"] = "closed"
            else:
                payload["state"] = "open"
        if assignee_id is not None:
            payload["assignees"] = [assignee_id] if assignee_id else []
        if labels is not None:
            payload["labels"] = labels

        for k, v in kwargs.items():
            if v is not None:
                payload[k] = v

        data = self._request("PATCH", f"repos/{target_repo}/issues/{num}", json_data=payload)
        return self._parse_issue(data)

    def close_issue(self, issue_id: str, reason: Optional[str] = None, repo: Optional[str] = None, **kwargs: Any) -> Issue:
        target_repo = self._resolve_repo(repo)
        num = self._parse_issue_number(issue_id)
        payload: Dict[str, Any] = {"state": "closed"}
        if reason:
            payload["state_reason"] = "completed"

        data = self._request("PATCH", f"repos/{target_repo}/issues/{num}", json_data=payload)
        if reason:
            self.add_comment(issue_id, f"Closing issue: {reason}", repo=target_repo)
        return self._parse_issue(data)

    def reopen_issue(self, issue_id: str, repo: Optional[str] = None, **kwargs: Any) -> Issue:
        target_repo = self._resolve_repo(repo)
        num = self._parse_issue_number(issue_id)
        payload: Dict[str, Any] = {"state": "open", "state_reason": "reopened"}
        data = self._request("PATCH", f"repos/{target_repo}/issues/{num}", json_data=payload)
        return self._parse_issue(data)

    def get_comments(self, issue_id: str, repo: Optional[str] = None, **kwargs: Any) -> List[Comment]:
        target_repo = self._resolve_repo(repo)
        num = self._parse_issue_number(issue_id)
        data = self._request("GET", f"repos/{target_repo}/issues/{num}/comments")
        return [self._parse_comment(c) for c in data]

    def add_comment(self, issue_id: str, body: str, repo: Optional[str] = None, **kwargs: Any) -> Comment:
        target_repo = self._resolve_repo(repo)
        num = self._parse_issue_number(issue_id)
        data = self._request("POST", f"repos/{target_repo}/issues/{num}/comments", json_data={"body": body})
        return self._parse_comment(data)

    def add_label(self, issue_id: str, label: str, repo: Optional[str] = None, **kwargs: Any) -> Issue:
        target_repo = self._resolve_repo(repo)
        num = self._parse_issue_number(issue_id)
        self._request("POST", f"repos/{target_repo}/issues/{num}/labels", json_data={"labels": [label]})
        return self.get_issue(str(num), repo=target_repo)

    def remove_label(self, issue_id: str, label: str, repo: Optional[str] = None, **kwargs: Any) -> Issue:
        target_repo = self._resolve_repo(repo)
        num = self._parse_issue_number(issue_id)
        try:
            self._request("DELETE", f"repos/{target_repo}/issues/{num}/labels/{label}")
        except IssueNotFoundError:
            pass
        return self.get_issue(str(num), repo=target_repo)

    def get_assignees(self, project_or_team: Optional[str] = None, **kwargs: Any) -> List[User]:
        repo = self._resolve_repo(project_or_team)
        data = self._request("GET", f"repos/{repo}/assignees")
        users = []
        for u in data:
            parsed = self._parse_user(u)
            if parsed:
                users.append(parsed)
        return users

    def assign_issue(self, issue_id: str, user_id_or_name: str, repo: Optional[str] = None, **kwargs: Any) -> Issue:
        target_repo = self._resolve_repo(repo)
        num = self._parse_issue_number(issue_id)
        self._request("POST", f"repos/{target_repo}/issues/{num}/assignees", json_data={"assignees": [user_id_or_name]})
        return self.get_issue(str(num), repo=target_repo)

    def unassign_issue(
        self, issue_id: str, user_id_or_name: Optional[str] = None, repo: Optional[str] = None, **kwargs: Any
    ) -> Issue:
        target_repo = self._resolve_repo(repo)
        num = self._parse_issue_number(issue_id)
        if user_id_or_name:
            self._request("DELETE", f"repos/{target_repo}/issues/{num}/assignees", json_data={"assignees": [user_id_or_name]})
        else:
            current = self.get_issue(str(num), repo=target_repo)
            existing = [u.username for u in current.assignees if u.username]
            if existing:
                self._request("DELETE", f"repos/{target_repo}/issues/{num}/assignees", json_data={"assignees": existing})

        return self.get_issue(str(num), repo=target_repo)


# Convenience alias
GitHub = GitHubTracker
