import json

import pytest

from tasico_shasta.config import (
    ConfigurationError,
    Role,
    Settings,
    User,
    password_context,
)


def valid_settings() -> Settings:
    return Settings(
        jwt_secret="test-only-secret-with-at-least-32-bytes",
        token_expiry_minutes=60,
        users={
            "operator": User(
                username="operator",
                password_hash=password_context.hash("a-strong-test-password"),
                role=Role.OPERATOR,
                factories=frozenset({"F1"}),
            )
        },
    )


def test_settings_reject_missing_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("AUTH_USERS_JSON", "[]")
    with pytest.raises(ConfigurationError, match="JWT_SECRET"):
        Settings.from_env()


def test_settings_reject_plaintext_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "test-only-secret-with-at-least-32-bytes")
    monkeypatch.setenv(
        "AUTH_USERS_JSON",
        json.dumps(
            [
                {
                    "username": "operator",
                    "password_hash": "plaintext",
                    "role": "operator",
                    "factories": ["F1"],
                }
            ]
        ),
    )
    with pytest.raises(ConfigurationError, match="password hash"):
        Settings.from_env()


def test_settings_reject_short_secret_even_when_constructed_directly() -> None:
    with pytest.raises(ConfigurationError, match="32 bytes"):
        Settings(
            jwt_secret="too-short",
            token_expiry_minutes=60,
            users=valid_settings().users,
        )


def test_users_are_parsed_with_limited_factory_scope() -> None:
    user = valid_settings().users["operator"]
    assert user.role == Role.OPERATOR
    assert user.factories == frozenset({"F1"})
