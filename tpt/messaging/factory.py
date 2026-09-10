"""
Factory module for instantiating messaging clients.
"""

from typing import Any, Dict, Type
from tpt.messaging.base import BaseMessagingClient
from tpt.messaging.exceptions import ValidationError
from tpt.messaging.slack import SlackMessaging

_REGISTRY: Dict[str, Type[BaseMessagingClient]] = {
    "slack": SlackMessaging,
}


def register_messaging_client(name: str, client_cls: Type[BaseMessagingClient]) -> None:
    """
    Register a new messaging client provider.

    :param name: Provider name (case-insensitive, e.g. "slack", "discord", "teams").
    :param client_cls: Subclass of BaseMessagingClient.
    """
    if not issubclass(client_cls, BaseMessagingClient):
        raise TypeError(f"{client_cls} must be a subclass of BaseMessagingClient")
    _REGISTRY[name.strip().lower()] = client_cls


def get_messaging_client(provider: str, **kwargs: Any) -> BaseMessagingClient:
    """
    Factory function to instantiate a messaging client.

    :param provider: Name of provider ('slack', etc.).
    :param kwargs: Configuration options passed directly to the constructor.
    :return: An instance implementing BaseMessagingClient.
    """
    key = provider.strip().lower()
    client_cls = _REGISTRY.get(key)
    if not client_cls:
        supported = ", ".join(repr(k) for k in _REGISTRY.keys())
        raise ValidationError(
            f"Unsupported messaging provider '{provider}'. Supported providers: {supported}"
        )
    return client_cls(**kwargs)
