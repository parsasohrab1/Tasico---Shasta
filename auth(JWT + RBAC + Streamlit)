"""مدل‌های داده کاربر و نقش"""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class Role(str, Enum):
    ADMIN = "admin"        # دسترسی کامل
    MANAGER = "manager"    # مشاهده همه کارخانه‌ها
    OPERATOR = "operator"  # فقط کارخانه خودش
    VIEWER = "viewer"      # فقط مشاهده


class User(BaseModel):
    username: str
    full_name: Optional[str] = None
    role: Role = Role.VIEWER
    factories: List[str] = Field(default_factory=list)  # [] = همه
    disabled: bool = False


class UserInDB(User):
    hashed_password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    role: Role


class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[Role] = None

"""تولید و اعتبارسنجی JWT"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from auth.models import TokenData, Role

SECRET_KEY = os.environ.get("JWT_SECRET", "change-me-in-production-please-" + "x" * 32)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MIN", "60"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, role: str | Role,
                        expires_minutes: Optional[int] = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": subject,
        "role": role.value if isinstance(role, Role) else role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenData(
            username=payload.get("sub"),
            role=Role(payload.get("role", "viewer")),
        )
    except JWTError as e:
        raise ValueError(f"invalid token: {e}")

"""پایگاه کاربران درون‌حافظه‌ای — برای production به DB منتقل شود"""
from typing import Optional
from auth.models import UserInDB, Role
from auth.jwt_handler import hash_password, verify_password


_USERS: dict[str, UserInDB] = {
    "admin": UserInDB(
        username="admin",
        full_name="مدیر سیستم",
        role=Role.ADMIN,
        factories=[],
        hashed_password=hash_password("admin123"),
    ),
    "manager_f1": UserInDB(
        username="manager_f1",
        full_name="مدیر کارخانه F1",
        role=Role.OPERATOR,
        factories=["F1-PAPER"],
        hashed_password=hash_password("manager123"),
    ),
    "viewer": UserInDB(
        username="viewer",
        full_name="بیننده",
        role=Role.VIEWER,
        factories=[],
        hashed_password=hash_password("viewer123"),
    ),
}


def get_user(username: str) -> Optional[UserInDB]:
    return _USERS.get(username)


def authenticate(username: str, password: str) -> Optional[UserInDB]:
    user = get_user(username)
    if not user or user.disabled:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def add_user(user: UserInDB) -> None:
    _USERS[user.username] = user


def list_users() -> list[UserInDB]:
    return list(_USERS.values())

"""وابستگی‌های FastAPI برای auth"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from auth.jwt_handler import decode_token
from auth.models import TokenData, Role
from auth.users import get_user

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    try:
        return decode_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_role(*allowed: Role):
    """Dependency factory برای محدودکردن به نقش‌های مجاز"""
    def _checker(current: TokenData = Depends(get_current_user)) -> TokenData:
        if current.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {[r.value for r in allowed]}",
            )
        return current
    return _checker


def require_factory_access(factory_id: str,
                           current: TokenData = Depends(get_current_user)) -> TokenData:
    """بررسی دسترسی به یک کارخانه خاص"""
    user = get_user(current.username)
    if not user:
        raise HTTPException(401, "user not found")
    if user.role == Role.ADMIN:
        return current
    if user.factories and factory_id not in user.factories:
        raise HTTPException(403, f"no access to factory {factory_id}")
    return current

"""مسیرهای auth برای FastAPI"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from auth.users import authenticate
from auth.jwt_handler import create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES
from auth.models import Token, UserInDB, Role
from auth.dependencies import get_current_user, require_role
from auth.users import list_users

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends()):
    user = authenticate(form.username, form.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(subject=user.username, role=user.role)
    return Token(
        access_token=token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        role=user.role,
    )


@router.get("/me")
def me(current=Depends(get_current_user)):
    return {"username": current.username, "role": current.role}


@router.get("/users")
def get_users(current=Depends(require_role(Role.ADMIN))):
    return [
        {"username": u.username, "role": u.role, "factories": u.factories}
        for u in list_users()
    ]

# api.py — فقط بخش‌های تغییرکرده
from fastapi import FastAPI, HTTPException, Depends
from auth.routes import router as auth_router
from auth.dependencies import get_current_user, require_role, require_factory_access
from auth.models import Role, TokenData

app = FastAPI(title="CEUO Inference API", version="1.1.0")
app.include_router(auth_router)


@app.post("/forecast")
def forecast(req: ForecastRequest,
             current: TokenData = Depends(get_current_user)):
    # دسترسی به کارخانه بررسی شود
    require_factory_access(req.factory_id, current)
    key = (req.factory_id, req.target)
    if key not in app.state.models:
        raise HTTPException(404, f"model not found for {key}")
    obj = app.state.models[key]
    import pandas as pd
    try:
        X = pd.DataFrame([req.features])[obj["features"]]
    except KeyError as e:
        raise HTTPException(400, f"missing feature: {e}")
    pred = float(obj["model"].predict(X)[0])
    return {"prediction": pred, "target": req.target, "factory_id": req.factory_id}


@app.post("/anomaly")
def anomaly(req: AnomalyRequest,
            current: TokenData = Depends(get_current_user)):
    require_factory_access(req.factory_id, current)
    # ... (بدنه قبلی)

credentials:
  usernames:
    admin:
      name: مدیر سیستم
      password: $2b$12$...  # bcrypt hash — با اسکریپت زیر تولید کنید
      roles:
        - admin
    manager_f1:
      name: مدیر کارخانه F1
      password: $2b$12$...
      roles:
        - operator
      factories:
        - F1-PAPER
    viewer:
      name: بیننده
      password: $2b$12$...
      roles:
        - viewer

cookie:
  name: ceuo_auth
  key: change_this_random_key_to_32_chars
  expiry_days: 1

preauthorized:
  emails: []

python -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('admin123'))"

# app.py — ابتدای فایل، بعد از imports
import yaml
import streamlit_authenticator as stauth
from yaml.loader import SafeLoader
from pathlib import Path

# ---------- احراز هویت ----------
CONFIG_PATH = Path("streamlit_auth/config.yaml")
if not CONFIG_PATH.exists():
    st.error(f"auth config not found: {CONFIG_PATH}")
    st.stop()

with open(CONFIG_PATH, encoding="utf-8") as f:
    auth_config = yaml.load(f, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    credentials=auth_config["credentials"],
    cookie_name=auth_config["cookie"]["name"],
    cookie_key=auth_config["cookie"]["key"],
    cookie_expiry_days=auth_config["cookie"]["expiry_days"],
)

# صفحه ورود
name, auth_status, username = authenticator.login(location="main")

if auth_status is False:
    st.error("نام کاربری یا رمز عبور اشتباه است")
    st.stop()
if auth_status is None:
    st.warning("لطفاً وارد شوید")
    st.stop()

# کاربر وارد شده — استخراج نقش
user_roles = auth_config["credentials"]["usernames"][username].get("roles", ["viewer"])
user_factories = auth_config["credentials"]["usernames"][username].get("factories", [])

# دکمه خروج در سایدبار
authenticator.logout("خروج", "sidebar")
st.sidebar.success(f"خوش آمدید، {name} ({', '.join(user_roles)})")

# فیلتر کارخانه‌ها بر اساس دسترسی
def filter_by_access(df, user_factories):
    if not user_factories:
        return df  # دسترسی کامل
    return df[df["factory_id"].isin(user_factories)]

# در main():
df = filter_by_access(df, user_factories)

