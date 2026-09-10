"""
Linear Issue Tracker implementation.

Implements BaseIssueTracker using Linear's GraphQL API.
"""

from datetime import datetime
import os
from pathlib import Path
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

LINEAR_GRAPHQL_ENDPOINT = "https://api.linear.app/graphql"

PRIORITY_MAP = {
    0: "No priority",
    1: "Urgent",
    2: "High",
    3: "Normal",
    4: "Low",
}

STATUS_MAP = {
    "backlog": IssueStatus.BACKLOG,
    "unstarted": IssueStatus.UNSTARTED,
    "started": IssueStatus.STARTED,
    "completed": IssueStatus.COMPLETED,
    "canceled": IssueStatus.CANCELED,
}


def _get_default_linear_token() -> Optional[str]:
    """Retrieve Linear token from environment or user config."""
    token = os.getenv("LINEAR_API_KEY")
    if token:
        return token

    cfg_file = os.path.expanduser("~/.config/tpt_tokens.env")
    if os.path.isfile(cfg_file):
        try:
            with open(cfg_file) as f:
                for line in f:
                    if line.strip().startswith("export LINEAR_API_KEY="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
        except Exception:
            pass

    # Check px0 credentials file
    px0_creds = Path(os.getenv("PX0_HOME", "~/.px0")).expanduser() / ".state" / "credentials.toml"
    if px0_creds.is_file():
        try:
            import tomllib
            with open(px0_creds, "rb") as f:
                data = tomllib.load(f)
            linear_entry = data.get("linear", {})
            val = linear_entry.get("api_key") or linear_entry.get("token")
            if val:
                return val
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


class LinearTracker(BaseIssueTracker):
    """Linear issue tracker client implementing BaseIssueTracker."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: str = LINEAR_GRAPHQL_ENDPOINT,
        timeout: int = 30,
    ):
        """
        Initialize LinearTracker.

        :param api_key: Linear API token.
        :param endpoint: Linear GraphQL endpoint URL.
        :param timeout: HTTP request timeout in seconds.
        """
        self.api_key = api_key or _get_default_linear_token()
        if not self.api_key:
            raise AuthenticationError(
                "Linear API key is required. Set LINEAR_API_KEY env var or pass api_key parameter.",
                provider="Linear",
            )
        self.endpoint = endpoint
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": self.api_key,
                "Content-Type": "application/json",
            }
        )
        self._teams_cache: Optional[List[Dict[str, Any]]] = None

    def _graphql_query(
        self, query: str, variables: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a GraphQL query/mutation against Linear API with standardized error handling."""
        payload: Dict[str, Any] = {"query": query}
        if variables:
            payload["variables"] = variables

        try:
            response = self.session.post(
                self.endpoint, json=payload, timeout=self.timeout
            )
        except requests.RequestException as e:
            raise ProviderAPIError(f"Network error communicating with Linear: {e}", provider="Linear") from e

        if response.status_code == 401:
            raise AuthenticationError("Linear authentication failed. Invalid or expired token.", provider="Linear", status_code=401)
        if response.status_code == 403:
            raise PermissionDeniedError("Permission denied on Linear.", provider="Linear", status_code=403)
        if response.status_code == 429:
            retry_after = None
            if "retry-after" in response.headers:
                try:
                    retry_after = int(response.headers["retry-after"])
                except Exception:
                    pass
            raise RateLimitExceededError("Linear rate limit exceeded.", provider="Linear", retry_after=retry_after, status_code=429)

        try:
            data = response.json()
        except Exception as e:
            raise ProviderAPIError(f"Non-JSON response from Linear (status {response.status_code}): {response.text}", provider="Linear") from e

        if "errors" in data and data["errors"]:
            messages = [err.get("message", str(err)) for err in data["errors"]]
            combined = "; ".join(messages)
            lower_msg = combined.lower()
            if "not found" in lower_msg or "could not find" in lower_msg:
                raise IssueNotFoundError(f"Linear resource not found: {combined}", provider="Linear")
            if "authentication" in lower_msg or "unauthorized" in lower_msg:
                raise AuthenticationError(combined, provider="Linear")
            if "permission" in lower_msg or "denied" in lower_msg or "forbidden" in lower_msg:
                raise PermissionDeniedError(combined, provider="Linear")
            raise ProviderAPIError(f"Linear GraphQL Error: {combined}", provider="Linear")

        return data.get("data", {})

    def _parse_user(self, user_node: Optional[Dict[str, Any]]) -> Optional[User]:
        if not user_node:
            return None
        return User(
            id=user_node["id"],
            name=user_node.get("name"),
            email=user_node.get("email"),
            username=user_node.get("displayName") or user_node.get("name"),
            avatar_url=user_node.get("avatarUrl"),
            raw_data=user_node,
        )

    def _parse_issue(self, node: Dict[str, Any]) -> Issue:
        """Parse Linear GraphQL issue node into standard Issue dataclass."""
        state_info = node.get("state") or {}
        state_type = (state_info.get("type") or "").lower()
        state_name = state_info.get("name")

        status = STATUS_MAP.get(state_type, IssueStatus.UNKNOWN)

        labels_nodes = (node.get("labels") or {}).get("nodes", [])
        labels = [l.get("name") for l in labels_nodes if l.get("name")]

        assignee_info = node.get("assignee")
        assignee_user = self._parse_user(assignee_info)
        assignees_list = [assignee_user] if assignee_user else []
        assignee_name = assignee_user.name if assignee_user else None

        priority_val = node.get("priority")
        priority_label = PRIORITY_MAP.get(priority_val)

        return Issue(
            id=node["id"],
            identifier=node.get("identifier", node["id"]),
            title=node.get("title", ""),
            description=node.get("description"),
            status=status,
            status_name=state_name,
            priority=priority_val,
            priority_label=priority_label,
            url=node.get("url"),
            assignee=assignee_name,
            assignees=assignees_list,
            labels=labels,
            created_at=_parse_datetime(node.get("createdAt")),
            updated_at=_parse_datetime(node.get("updatedAt")),
            closed_at=_parse_datetime(
                node.get("completedAt") or node.get("canceledAt")
            ),
            raw_data=node,
        )

    def _parse_comment(self, node: Dict[str, Any]) -> Comment:
        """Parse Linear GraphQL comment node into standard Comment dataclass."""
        user_info = node.get("user") or {}
        author = user_info.get("name") or user_info.get("email")

        return Comment(
            id=node["id"],
            body=node.get("body", ""),
            author=author,
            created_at=_parse_datetime(node.get("createdAt")),
            updated_at=_parse_datetime(node.get("updatedAt")),
            raw_data=node,
        )

    def get_teams(self) -> List[Dict[str, Any]]:
        """Fetch list of accessible teams in Linear."""
        query = """
        query Teams {
            teams {
                nodes {
                    id
                    name
                    key
                }
            }
        }
        """
        data = self._graphql_query(query)
        self._teams_cache = data.get("teams", {}).get("nodes", [])
        return self._teams_cache

    def resolve_team_id(self, team_key_or_id: Optional[str] = None) -> str:
        """Resolve team ID from team key, name, or ID."""
        teams = self.get_teams()
        if not teams:
            raise ValidationError("No teams available in Linear workspace.", provider="Linear")

        if not team_key_or_id:
            return teams[0]["id"]

        team_str = team_key_or_id.strip()
        for t in teams:
            if team_str in (t["id"], t["key"], t["name"]):
                return t["id"]

        return team_str

    def get_workflow_states(self, team_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Fetch workflow states for a team (or all teams)."""
        query = """
        query {
            workflowStates {
                nodes {
                    id
                    name
                    type
                    position
                    team {
                        id
                        key
                    }
                }
            }
        }
        """
        data = self._graphql_query(query)
        all_states = data.get("workflowStates", {}).get("nodes", [])
        if team_id:
            return [
                s for s in all_states
                if s.get("team") and s["team"].get("id") == team_id
            ]
        return all_states

    def resolve_state_id(
        self, team_id: str, state_name_or_type: str
    ) -> Optional[str]:
        """Find state ID matching a given state name or state type (e.g., 'completed', 'unstarted')."""
        states = self.get_workflow_states(team_id)
        target = state_name_or_type.strip().lower()

        for s in states:
            if s.get("name", "").lower() == target:
                return s["id"]
        for s in states:
            if s.get("type", "").lower() == target:
                return s["id"]
        for s in states:
            if s.get("id") == target:
                return s["id"]
        return None

    def get_or_create_label_id(self, team_id: str, label_name: str) -> str:
        """Find label ID by name, or create it under the team."""
        query = """
        query IssueLabels {
            issueLabels {
                nodes {
                    id
                    name
                    team {
                        id
                    }
                }
            }
        }
        """
        data = self._graphql_query(query)
        all_labels = data.get("issueLabels", {}).get("nodes", [])

        clean_name = label_name.strip()
        clean_lower = clean_name.lower()

        for lab in all_labels:
            if lab["id"] == clean_name:
                return lab["id"]

        for lab in all_labels:
            if lab.get("team") and lab["team"]["id"] == team_id and lab.get("name", "").lower() == clean_lower:
                return lab["id"]

        for lab in all_labels:
            if not lab.get("team") and lab.get("name", "").lower() == clean_lower:
                return lab["id"]

        mutation = """
        mutation CreateIssueLabel($input: IssueLabelCreateInput!) {
            issueLabelCreate(input: $input) {
                success
                issueLabel {
                    id
                    name
                }
            }
        }
        """
        create_res = self._graphql_query(
            mutation,
            {"input": {"name": clean_name, "teamId": team_id}},
        )
        created = create_res.get("issueLabelCreate", {}).get("issueLabel")
        if created and "id" in created:
            return created["id"]

        raise ProviderAPIError(f"Could not resolve or create label '{label_name}' for team {team_id}", provider="Linear")

    def resolve_label_ids(
        self, team_id: str, label_names_or_ids: List[str]
    ) -> List[str]:
        """Resolve a list of label names or IDs to valid label IDs for the team."""
        resolved_ids: List[str] = []
        for name_or_id in label_names_or_ids:
            resolved_ids.append(self.get_or_create_label_id(team_id, name_or_id))
        return resolved_ids

    def list_issues(
        self,
        project_or_team: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        **kwargs: Any,
    ) -> List[Issue]:
        query = """
        query Issues($first: Int, $filter: IssueFilter) {
            issues(first: $first, filter: $filter) {
                nodes {
                    id
                    identifier
                    title
                    description
                    priority
                    url
                    createdAt
                    updatedAt
                    completedAt
                    canceledAt
                    team {
                        id
                        key
                        name
                    }
                    state {
                        id
                        name
                        type
                    }
                    labels {
                        nodes {
                            id
                            name
                        }
                    }
                    assignee {
                        id
                        name
                        email
                        displayName
                        avatarUrl
                    }
                }
            }
        }
        """
        issue_filter: Dict[str, Any] = {}
        if project_or_team:
            team_id = self.resolve_team_id(project_or_team)
            issue_filter["team"] = {"id": {"eq": team_id}}

        if status:
            status_lower = status.strip().lower()
            if status_lower in ("backlog", "unstarted", "started", "completed", "canceled"):
                issue_filter["state"] = {"type": {"eq": status_lower}}
            else:
                issue_filter["state"] = {"name": {"eq": status.strip()}}

        if "filter" in kwargs and isinstance(kwargs["filter"], dict):
            issue_filter.update(kwargs["filter"])

        variables = {
            "first": min(limit, 250),
            "filter": issue_filter if issue_filter else None,
        }

        data = self._graphql_query(query, variables)
        nodes = data.get("issues", {}).get("nodes", [])
        return [self._parse_issue(n) for n in nodes]

    def get_issue(self, issue_id: str, **kwargs: Any) -> Issue:
        query = """
        query Issue($id: String!) {
            issue(id: $id) {
                id
                identifier
                title
                description
                priority
                url
                createdAt
                updatedAt
                completedAt
                canceledAt
                team {
                    id
                    key
                    name
                }
                state {
                    id
                    name
                    type
                }
                labels {
                    nodes {
                        id
                        name
                    }
                }
                assignee {
                    id
                    name
                    email
                    displayName
                    avatarUrl
                }
            }
        }
        """
        data = self._graphql_query(query, {"id": issue_id})
        issue_node = data.get("issue")
        if not issue_node:
            raise IssueNotFoundError(f"Issue not found: {issue_id}", provider="Linear")
        return self._parse_issue(issue_node)

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
        team_id = self.resolve_team_id(project_or_team)

        mutation = """
        mutation CreateIssue($input: IssueCreateInput!) {
            issueCreate(input: $input) {
                success
                issue {
                    id
                    identifier
                    title
                    description
                    priority
                    url
                    createdAt
                    updatedAt
                    completedAt
                    canceledAt
                    team {
                        id
                        key
                        name
                    }
                    state {
                        id
                        name
                        type
                    }
                    labels {
                        nodes {
                            id
                            name
                        }
                    }
                    assignee {
                        id
                        name
                        email
                        displayName
                        avatarUrl
                    }
                }
            }
        }
        """
        input_data: Dict[str, Any] = {
            "teamId": team_id,
            "title": title,
        }
        if description is not None:
            input_data["description"] = description
        if priority is not None:
            input_data["priority"] = priority
        if assignee_id:
            resolved_uid = self._resolve_user_id(assignee_id)
            input_data["assigneeId"] = resolved_uid
        if status:
            state_id = self.resolve_state_id(team_id, status)
            if state_id:
                input_data["stateId"] = state_id
        if labels:
            input_data["labelIds"] = self.resolve_label_ids(team_id, labels)

        for k, v in kwargs.items():
            if k not in input_data and v is not None:
                input_data[k] = v

        data = self._graphql_query(mutation, {"input": input_data})
        result = data.get("issueCreate", {})
        if not result.get("success") or not result.get("issue"):
            raise ProviderAPIError(f"Failed to create issue: {data}", provider="Linear")

        return self._parse_issue(result["issue"])

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
        actual_issue = self.get_issue(issue_id)
        raw_id = actual_issue.id
        team_info = actual_issue.raw_data.get("team") or {}
        team_id = team_info.get("id")
        if not team_id and "-" in actual_issue.identifier:
            team_key = actual_issue.identifier.split("-")[0]
            team_id = self.resolve_team_id(team_key)

        mutation = """
        mutation UpdateIssue($id: String!, $input: IssueUpdateInput!) {
            issueUpdate(id: $id, input: $input) {
                success
                issue {
                    id
                    identifier
                    title
                    description
                    priority
                    url
                    createdAt
                    updatedAt
                    completedAt
                    canceledAt
                    team {
                        id
                        key
                        name
                    }
                    state {
                        id
                        name
                        type
                    }
                    labels {
                        nodes {
                            id
                            name
                        }
                    }
                    assignee {
                        id
                        name
                        email
                        displayName
                        avatarUrl
                    }
                }
            }
        }
        """
        input_data: Dict[str, Any] = {}
        if title is not None:
            input_data["title"] = title
        if description is not None:
            input_data["description"] = description
        if priority is not None:
            input_data["priority"] = priority
        if assignee_id is not None:
            input_data["assigneeId"] = self._resolve_user_id(assignee_id) if assignee_id else None
        if status is not None:
            state_id = self.resolve_state_id(team_id or "", status) if team_id else None
            input_data["stateId"] = state_id or status
        if labels is not None:
            if team_id:
                input_data["labelIds"] = self.resolve_label_ids(team_id, labels)
            else:
                input_data["labelIds"] = labels

        for k, v in kwargs.items():
            if k not in input_data and v is not None:
                input_data[k] = v

        data = self._graphql_query(mutation, {"id": raw_id, "input": input_data})
        result = data.get("issueUpdate", {})
        if not result.get("success") or not result.get("issue"):
            raise ProviderAPIError(f"Failed to update issue {issue_id}: {data}", provider="Linear")

        return self._parse_issue(result["issue"])

    def close_issue(
        self, issue_id: str, reason: Optional[str] = None, **kwargs: Any
    ) -> Issue:
        issue = self.get_issue(issue_id)
        team_id = None
        if "team" in issue.raw_data and issue.raw_data["team"]:
            team_id = issue.raw_data["team"].get("id")

        if not team_id and "-" in issue.identifier:
            team_key = issue.identifier.split("-")[0]
            team_id = self.resolve_team_id(team_key)

        completed_state_id = self.resolve_state_id(team_id or "", "completed")
        if not completed_state_id:
            for candidate in ("Done", "Closure", "Closed", "completed"):
                completed_state_id = self.resolve_state_id(team_id or "", candidate)
                if completed_state_id:
                    break

        if not completed_state_id:
            raise ResourceNotFoundError(f"Could not find completed/closure state for issue {issue_id}", provider="Linear")

        updated_issue = self.update_issue(issue.id, status=completed_state_id, **kwargs)

        if reason:
            self.add_comment(issue.id, f"Closing issue: {reason}")

        return updated_issue

    def reopen_issue(self, issue_id: str, **kwargs: Any) -> Issue:
        issue = self.get_issue(issue_id)
        team_id = None
        if "team" in issue.raw_data and issue.raw_data["team"]:
            team_id = issue.raw_data["team"].get("id")

        if not team_id and "-" in issue.identifier:
            team_key = issue.identifier.split("-")[0]
            team_id = self.resolve_team_id(team_key)

        unstarted_state_id = self.resolve_state_id(team_id or "", "unstarted")
        if not unstarted_state_id:
            for candidate in ("Todo", "Open", "Research", "unstarted", "backlog"):
                unstarted_state_id = self.resolve_state_id(team_id or "", candidate)
                if unstarted_state_id:
                    break

        if not unstarted_state_id:
            raise ResourceNotFoundError(f"Could not find open/unstarted state for issue {issue_id}", provider="Linear")

        return self.update_issue(issue.id, status=unstarted_state_id, **kwargs)

    def get_comments(self, issue_id: str, **kwargs: Any) -> List[Comment]:
        actual_issue = self.get_issue(issue_id)
        query = """
        query IssueComments($id: String!) {
            issue(id: $id) {
                comments {
                    nodes {
                        id
                        body
                        createdAt
                        updatedAt
                        user {
                            id
                            name
                            email
                        }
                    }
                }
            }
        }
        """
        data = self._graphql_query(query, {"id": actual_issue.id})
        nodes = (
            data.get("issue", {})
            .get("comments", {})
            .get("nodes", [])
        )
        return [self._parse_comment(n) for n in nodes]

    def add_comment(self, issue_id: str, body: str, **kwargs: Any) -> Comment:
        actual_issue = self.get_issue(issue_id)
        mutation = """
        mutation CreateComment($input: CommentCreateInput!) {
            commentCreate(input: $input) {
                success
                comment {
                    id
                    body
                    createdAt
                    updatedAt
                    user {
                        id
                        name
                        email
                    }
                }
            }
        }
        """
        data = self._graphql_query(
            mutation, {"input": {"issueId": actual_issue.id, "body": body}}
        )
        result = data.get("commentCreate", {})
        if not result.get("success") or not result.get("comment"):
            raise ProviderAPIError(f"Failed to create comment on issue {issue_id}: {data}", provider="Linear")

        return self._parse_comment(result["comment"])

    def add_label(self, issue_id: str, label: str, **kwargs: Any) -> Issue:
        actual_issue = self.get_issue(issue_id)
        current_labels = list(actual_issue.labels)
        if label not in current_labels:
            current_labels.append(label)

        return self.update_issue(actual_issue.id, labels=current_labels)

    def remove_label(self, issue_id: str, label: str, **kwargs: Any) -> Issue:
        actual_issue = self.get_issue(issue_id)
        current_labels = [l for l in actual_issue.labels if l.lower() != label.lower().strip()]
        return self.update_issue(actual_issue.id, labels=current_labels)

    def get_assignees(self, project_or_team: Optional[str] = None, **kwargs: Any) -> List[User]:
        query = """
        query Users {
            users {
                nodes {
                    id
                    name
                    email
                    displayName
                    avatarUrl
                }
            }
        }
        """
        data = self._graphql_query(query)
        nodes = data.get("users", {}).get("nodes", [])
        users = []
        for n in nodes:
            # Skip system/bot email if present
            if n.get("email", "").endswith("@linear.linear.app"):
                continue
            u = self._parse_user(n)
            if u:
                users.append(u)
        return users

    def _resolve_user_id(self, user_id_or_name: str) -> str:
        clean = user_id_or_name.strip()
        users = self.get_assignees()
        for u in users:
            if clean in (u.id, u.name, u.email, u.username):
                return u.id
        return clean

    def assign_issue(self, issue_id: str, user_id_or_name: str, **kwargs: Any) -> Issue:
        user_id = self._resolve_user_id(user_id_or_name)
        return self.update_issue(issue_id, assignee_id=user_id)

    def unassign_issue(
        self, issue_id: str, user_id_or_name: Optional[str] = None, **kwargs: Any
    ) -> Issue:
        actual_issue = self.get_issue(issue_id)
        mutation = """
        mutation Unassign($id: String!) {
            issueUpdate(id: $id, input: { assigneeId: null }) {
                success
                issue {
                    id
                    identifier
                    title
                    description
                    priority
                    url
                    createdAt
                    updatedAt
                    completedAt
                    canceledAt
                    team {
                        id
                        key
                        name
                    }
                    state {
                        id
                        name
                        type
                    }
                    labels {
                        nodes {
                            id
                            name
                        }
                    }
                    assignee {
                        id
                        name
                        email
                    }
                }
            }
        }
        """
        data = self._graphql_query(mutation, {"id": actual_issue.id})
        result = data.get("issueUpdate", {})
        if not result.get("success") or not result.get("issue"):
            raise ProviderAPIError(f"Failed to unassign issue {issue_id}: {data}", provider="Linear")

        return self._parse_issue(result["issue"])

    def delete_issue(self, issue_id: str) -> bool:
        """Delete an issue from Linear."""
        actual_issue = self.get_issue(issue_id)
        mutation = """
        mutation IssueDelete($id: String!) {
            issueDelete(id: $id) {
                success
            }
        }
        """
        res = self._graphql_query(mutation, {"id": actual_issue.id})
        return bool(res.get("issueDelete", {}).get("success"))


# Convenience alias
Linear = LinearTracker
