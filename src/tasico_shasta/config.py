from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from passlib.context import CryptContext

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class ConfigurationError(ValueError):
    """Raised when required deployment configuration is invalid."""


class Role(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    OPERATOR = "operator"
    VIEWER = "viewer"


@dataclass(frozen=True)
class User:
    username: str
    password_hash: str
    role: Role
    factories: frozenset[str]
    disabled: bool = False


@dataclass(frozen=True)
class Settings:
    jwt_secret: str
    token_expiry_minutes: int
    users: Mapping[str, User]

    def __post_init__(self) -> None:
        if len(self.jwt_secret.encode("utf-8")) < 32:
            raise ConfigurationError("JWT_SECRET must contain at least 32 bytes")
        if (
            isinstance(self.token_expiry_minutes, bool)
            or not isinstance(self.token_expiry_minutes, int)
            or not 1 <= self.token_expiry_minutes <= 1440
        ):
            raise ConfigurationError(
                "JWT_EXPIRE_MINUTES must be between 1 and 1440"
            )
        if not self.users:
            raise ConfigurationError("at least one user must be configured")
        for username, user in self.users.items():
            if username != user.username or not password_context.identify(user.password_hash):
                raise ConfigurationError(f"user {username!r} has invalid credentials")
        object.__setattr__(self, "users", MappingProxyType(dict(self.users)))

    @classmethod
    def from_env(cls) -> Settings:
        secret = os.environ.get("JWT_SECRET", "")
        if len(secret.encode("utf-8")) < 32:
            raise ConfigurationError("JWT_SECRET must contain at least 32 bytes")

        expiry_text = os.environ.get("JWT_EXPIRE_MINUTES", "60")
        try:
            expiry = int(expiry_text)
        except ValueError as exc:
            raise ConfigurationError("JWT_EXPIRE_MINUTES must be an integer") from exc
        if not 1 <= expiry <= 1440:
            raise ConfigurationError("JWT_EXPIRE_MINUTES must be between 1 and 1440")

        raw_users = os.environ.get("AUTH_USERS_JSON", "")
        if not raw_users:
            raise ConfigurationError("AUTH_USERS_JSON must define at least one user")
        try:
            users = _parse_users(json.loads(raw_users))
        except json.JSONDecodeError as exc:
            raise ConfigurationError("AUTH_USERS_JSON must contain valid JSON") from exc
        if not users:
            raise ConfigurationError("AUTH_USERS_JSON must define at least one user")

        return cls(jwt_secret=secret, token_expiry_minutes=expiry, users=users)


def _parse_users(value: Any) -> dict[str, User]:
    if not isinstance(value, list):
        raise ConfigurationError("AUTH_USERS_JSON must be a JSON array")

    users: dict[str, User] = {}
    allowed_fields = {"username", "password_hash", "role", "factories", "disabled"}
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ConfigurationError(f"AUTH_USERS_JSON item {index} must be an object")
        if set(item) - allowed_fields:
            raise ConfigurationError(f"AUTH_USERS_JSON item {index} has unknown fields")

        username = item.get("username")
        password_hash = item.get("password_hash")
        if not isinstance(username, str) or not username.strip():
            raise ConfigurationError(f"AUTH_USERS_JSON item {index} needs a username")
        if username in users:
            raise ConfigurationError(f"AUTH_USERS_JSON contains duplicate user {username!r}")
        if not isinstance(password_hash, str) or not password_context.identify(password_hash):
            raise ConfigurationError(
                f"AUTH_USERS_JSON user {username!r} needs a supported password hash"
            )
        try:
            role = Role(item.get("role"))
        except (ValueError, TypeError) as exc:
            raise ConfigurationError(
                f"AUTH_USERS_JSON user {username!r} has an invalid role"
            ) from exc

        factories = item.get("factories", [])
        if (
            not isinstance(factories, list)
            or any(not isinstance(factory, str) or not factory.strip() for factory in factories)
        ):
            raise ConfigurationError(
                f"AUTH_USERS_JSON user {username!r} factories must be non-empty strings"
            )
        disabled = item.get("disabled", False)
        if not isinstance(disabled, bool):
            raise ConfigurationError(
                f"AUTH_USERS_JSON user {username!r} disabled must be a boolean"
            )
        users[username] = User(
            username=username,
            password_hash=password_hash,
            role=role,
            factories=frozenset(factories),
            disabled=disabled,
        )
    return users
