from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from pydantic import BaseModel, ConfigDict, Field, model_validator

from tasico_shasta.config import Role, Settings, User, password_context
from tasico_shasta.optimization import solve_dispatch

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


class BoilerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100)
    capacity_tph: float = Field(gt=0, allow_inf_nan=False)
    gas_m3_per_tonne_steam: float = Field(gt=0, allow_inf_nan=False)
    minimum_load: float = Field(default=0.0, ge=0, le=1, allow_inf_nan=False)


class TurbineInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=100)
    capacity_mw: float = Field(gt=0, allow_inf_nan=False)
    steam_tonnes_per_mwh: float = Field(gt=0, allow_inf_nan=False)
    minimum_load: float = Field(default=0.0, ge=0, le=1, allow_inf_nan=False)


class DispatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    factory_id: str = Field(min_length=1, max_length=100)
    steam_demand_tph: float = Field(ge=0, allow_inf_nan=False)
    electricity_demand_kw: float = Field(ge=0, allow_inf_nan=False)
    gas_price_per_m3: float = Field(ge=0, allow_inf_nan=False)
    electricity_import_price_per_kwh: float = Field(ge=0, allow_inf_nan=False)
    electricity_export_price_per_kwh: float = Field(default=0, ge=0, allow_inf_nan=False)
    interval_hours: float = Field(default=1, gt=0, allow_inf_nan=False)
    boilers: list[BoilerInput] = Field(min_length=1)
    turbines: list[TurbineInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_prices(self) -> DispatchRequest:
        if self.electricity_export_price_per_kwh > self.electricity_import_price_per_kwh:
            raise ValueError("export price cannot exceed import price")
        if len({boiler.id for boiler in self.boilers}) != len(self.boilers):
            raise ValueError("boiler ids must be unique")
        if len({turbine.id for turbine in self.turbines}) != len(self.turbines):
            raise ValueError("turbine ids must be unique")
        return self


async def current_user(
    request: Request,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    configured: Settings = request.app.state.settings
    try:
        payload = jwt.decode(token, configured.jwt_secret, algorithms=["HS256"])
        username = payload.get("sub")
        if not isinstance(username, str) or not username:
            raise JWTError("missing subject")
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    user = configured.users.get(username)
    if user is None or user.disabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings if settings is not None else Settings.from_env()
        yield

    app = FastAPI(
        title="Tasico Shasta Energy Optimizer",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/auth/token")
    async def issue_token(
        request: Request,
        form: Annotated[OAuth2PasswordRequestForm, Depends()],
    ) -> dict[str, Any]:
        configured: Settings = request.app.state.settings
        user = configured.users.get(form.username)
        if (
            user is None
            or user.disabled
            or len(form.password.encode("utf-8")) > 72
            or not password_context.verify(form.password, user.password_hash)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        now = datetime.now(timezone.utc)
        token = jwt.encode(
            {
                "sub": user.username,
                "iat": now,
                "exp": now + timedelta(minutes=configured.token_expiry_minutes),
            },
            configured.jwt_secret,
            algorithm="HS256",
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": configured.token_expiry_minutes * 60,
        }

    @app.get("/auth/me")
    async def read_current_user(
        user: Annotated[User, Depends(current_user)],
    ) -> dict[str, Any]:
        return {
            "username": user.username,
            "role": user.role.value,
            "factories": sorted(user.factories),
        }

    @app.post("/optimization/dispatch")
    async def dispatch(
        body: DispatchRequest,
        user: Annotated[User, Depends(current_user)],
    ) -> dict[str, Any]:
        if user.role != Role.ADMIN and body.factory_id not in user.factories:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No access to the requested factory",
            )
        if user.role == Role.VIEWER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Viewer role cannot request optimization",
            )
        try:
            result = solve_dispatch(
                steam_demand_tph=body.steam_demand_tph,
                electricity_demand_kw=body.electricity_demand_kw,
                boilers=[item.model_dump() for item in body.boilers],
                turbines=[item.model_dump() for item in body.turbines],
                gas_price_per_m3=body.gas_price_per_m3,
                electricity_import_price_per_kwh=body.electricity_import_price_per_kwh,
                electricity_export_price_per_kwh=body.electricity_export_price_per_kwh,
                interval_hours=body.interval_hours,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
        if result["status"] != "Optimal":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"No optimal feasible dispatch found ({result['status']})",
            )
        return {"factory_id": body.factory_id, "recommendation_only": True, **result}

    return app


app = create_app()
