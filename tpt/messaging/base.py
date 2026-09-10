"""
Base classes and data models for messaging tool integrations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class User:
    """Represents a user in the messaging system."""
    id: str
    name: str
    real_name: Optional[str] = None
    email: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Message:
    """Represents a chat message or thread reply."""
    id: str
    channel_id: str
    text: str
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    thread_id: Optional[str] = None
    timestamp: Optional[str] = None
    created_at: Optional[datetime] = None
    reactions: List[Dict[str, Any]] = field(default_factory=list)
    permalink: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Thread:
    """Represents a message thread with root and replies."""
    id: str
    channel_id: str
    root_message: Message
    replies: List[Message] = field(default_factory=list)
    reply_count: int = 0
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Channel:
    """Represents a chat channel, room, or direct conversation."""
    id: str
    name: str
    is_private: bool = False
    is_im: bool = False
    topic: Optional[str] = None
    member_count: Optional[int] = None
    raw: Dict[str, Any] = field(default_factory=dict)


class BaseMessagingClient(ABC):
    """
    Abstract Base Class for messaging tools (e.g., Slack, Discord, MS Teams).
    Defines key user actions that people take on team messaging platforms.
    """

    @abstractmethod
    def get_current_user(self) -> User:
        """
        Retrieve the authenticated user or bot information.
        """
        pass

    @abstractmethod
    def list_channels(
        self,
        types: str = "public_channel,private_channel",
        limit: int = 100,
        **kwargs: Any,
    ) -> List[Channel]:
        """
        List channels or conversations accessible to the authenticated entity.
        """
        pass

    @abstractmethod
    def post_message(
        self,
        channel_id: str,
        text: str,
        thread_ts: Optional[str] = None,
        **kwargs: Any,
    ) -> Message:
        """
        Post a message to a channel, or reply to a thread if `thread_ts` is provided.
        """
        pass

    @abstractmethod
    def get_thread(
        self,
        channel_id: str,
        thread_ts: str,
        limit: int = 100,
        **kwargs: Any,
    ) -> Thread:
        """
        Retrieve thread root message and its replies (follow a thread).
        """
        pass

    @abstractmethod
    def get_mentions(
        self,
        user_id: Optional[str] = None,
        limit: int = 50,
        **kwargs: Any,
    ) -> List[Message]:
        """
        Retrieve messages mentioning the user or bot.
        If user_id is None, defaults to the authenticated user/bot ID.
        """
        pass

    @abstractmethod
    def search_messages(
        self,
        query: str,
        limit: int = 50,
        **kwargs: Any,
    ) -> List[Message]:
        """
        Search messages across channels matching query string.
        """
        pass

    @abstractmethod
    def add_reaction(
        self,
        channel_id: str,
        timestamp: str,
        emoji: str,
        **kwargs: Any,
    ) -> bool:
        """
        Add an emoji reaction to a message.
        """
        pass
