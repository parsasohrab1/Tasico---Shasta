from fastapi.testclient import TestClient

from tasico_shasta.api import create_app
from tasico_shasta.config import Role, Settings, User, password_context


def make_settings() -> Settings:
    password_hash = password_context.hash("a-strong-test-password")
    return Settings(
        jwt_secret="test-only-secret-with-at-least-32-bytes",
        token_expiry_minutes=30,
        users={
            "operator": User(
                username="operator",
                password_hash=password_hash,
                role=Role.OPERATOR,
                factories=frozenset({"F1"}),
            ),
            "viewer": User(
                username="viewer",
                password_hash=password_hash,
                role=Role.VIEWER,
                factories=frozenset({"F1"}),
            ),
            "admin": User(
                username="admin",
                password_hash=password_hash,
                role=Role.ADMIN,
                factories=frozenset(),
            ),
        },
    )


def get_token(client: TestClient, username: str) -> str:
    response = client.post(
        "/auth/token",
        data={"username": username, "password": "a-strong-test-password"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_factory_access_is_checked_against_user_configuration() -> None:
    with TestClient(create_app(make_settings())) as client:
        token = get_token(client, "operator")
        body = {
            "factory_id": "F2",
            "steam_demand_tph": 10,
            "electricity_demand_kw": 100,
            "gas_price_per_m3": 0.1,
            "electricity_import_price_per_kwh": 0.2,
            "boilers": [
                {
                    "id": "B1",
                    "capacity_tph": 20,
                    "gas_m3_per_tonne_steam": 2,
                }
            ],
        }
        response = client.post(
            "/optimization/dispatch",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403


def test_viewer_cannot_request_optimization_for_an_allowed_factory() -> None:
    with TestClient(create_app(make_settings())) as client:
        token = get_token(client, "viewer")
        body = {
            "factory_id": "F1",
            "steam_demand_tph": 10,
            "electricity_demand_kw": 100,
            "gas_price_per_m3": 0.1,
            "electricity_import_price_per_kwh": 0.2,
            "boilers": [
                {
                    "id": "B1",
                    "capacity_tph": 20,
                    "gas_m3_per_tonne_steam": 2,
                }
            ],
        }
        response = client.post(
            "/optimization/dispatch",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 403


def test_dispatch_is_recommendation_only_and_returns_feasible_result() -> None:
    with TestClient(create_app(make_settings())) as client:
        token = get_token(client, "operator")
        body = {
            "factory_id": "F1",
            "steam_demand_tph": 10,
            "electricity_demand_kw": 100,
            "gas_price_per_m3": 0.1,
            "electricity_import_price_per_kwh": 0.2,
            "boilers": [
                {
                    "id": "B1",
                    "capacity_tph": 20,
                    "gas_m3_per_tonne_steam": 2,
                }
            ],
        }
        response = client.post(
            "/optimization/dispatch",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert response.json()["recommendation_only"] is True
    assert response.json()["total_cost"] == 22


def test_authentication_fails_closed_for_wrong_password() -> None:
    with TestClient(create_app(make_settings())) as client:
        response = client.post(
            "/auth/token",
            data={"username": "operator", "password": "wrong-password"},
        )
    assert response.status_code == 401


def test_authentication_rejects_bcrypt_overlength_password() -> None:
    with TestClient(create_app(make_settings())) as client:
        response = client.post(
            "/auth/token",
            data={"username": "operator", "password": "x" * 73},
        )
    assert response.status_code == 401
