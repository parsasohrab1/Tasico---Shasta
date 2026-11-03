-- TimescaleDB schema for CEUO
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================
-- 1) کارخانه‌ها، واحدها، خطوط
-- ============================================================
CREATE TABLE IF NOT EXISTS factories (
    id          VARCHAR(50) PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    type        VARCHAR(50) NOT NULL,
    location    VARCHAR(200),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lines (
    id          VARCHAR(50) PRIMARY KEY,
    factory_id  VARCHAR(50) NOT NULL REFERENCES factories(id),
    name        VARCHAR(200),
    capacity_tph NUMERIC(10,2),
    product     VARCHAR(100)
);

-- ============================================================
-- 2) تجهیزات
-- ============================================================
CREATE TABLE IF NOT EXISTS equipment (
    id          VARCHAR(50) PRIMARY KEY,
    factory_id  VARCHAR(50) NOT NULL REFERENCES factories(id),
    kind        VARCHAR(30) NOT NULL,   -- boiler | turbine | pump | ...
    name        VARCHAR(200),
    cap         NUMERIC(10,3),
    eff         NUMERIC(5,4),
    min_load    NUMERIC(5,4) DEFAULT 0.0,
    metadata    JSONB DEFAULT '{}'::jsonb
);

-- ============================================================
-- 3) نقاط اندازه‌گیری
-- ============================================================
CREATE TABLE IF NOT EXISTS tags (
    id          SERIAL PRIMARY KEY,
    tag_id      VARCHAR(200) UNIQUE NOT NULL,
    factory_id  VARCHAR(50) NOT NULL REFERENCES factories(id),
    equipment_id VARCHAR(50) REFERENCES equipment(id),
    unit        VARCHAR(20),           -- kWh, m3, ton, ...
    description TEXT,
    source      VARCHAR(50),           -- opcua | modbus | manual | csv
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 4) داده سری‌زمانی اصلی (hypertable)
-- ============================================================
CREATE TABLE IF NOT EXISTS readings (
    time        TIMESTAMPTZ NOT NULL,
    factory_id  VARCHAR(50) NOT NULL,
    tag_id      VARCHAR(200) NOT NULL,
    value       DOUBLE PRECISION,
    quality     VARCHAR(20) DEFAULT 'good',
    metadata    JSONB DEFAULT '{}'::jsonb
);
SELECT create_hypertable('readings', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS idx_readings_factory_tag_time
    ON readings (factory_id, tag_id, time DESC);

-- ============================================================
-- 5) داده تجمیعی ساعتی (continuous aggregate)
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS readings_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS bucket,
    factory_id,
    tag_id,
    AVG(value) AS avg_value,
    MIN(value) AS min_value,
    MAX(value) AS max_value,
    COUNT(*) AS n_samples
FROM readings
GROUP BY bucket, factory_id, tag_id
WITH NO DATA;

SELECT add_continuous_aggregate_policy('readings_hourly',
    start_offset => INTERVAL '3 days',
    end_offset   => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');

-- ============================================================
-- 6) شاخص‌های محاسبه‌شده
-- ============================================================
CREATE TABLE IF NOT EXISTS kpis (
    time        TIMESTAMPTZ NOT NULL,
    factory_id  VARCHAR(50) NOT NULL,
    line_id     VARCHAR(50),
    kpi_name    VARCHAR(100) NOT NULL,   -- kwh_per_ton | steam_per_ton | ...
    value       DOUBLE PRECISION,
    unit        VARCHAR(20),
    metadata    JSONB DEFAULT '{}'::jsonb
);
SELECT create_hypertable('kpis', 'time', if_not_exists => TRUE);

-- ============================================================
-- 7) هشدارها و گردش کار
-- ============================================================
CREATE TABLE IF NOT EXISTS alerts (
    id          BIGSERIAL PRIMARY KEY,
    factory_id  VARCHAR(50) NOT NULL,
    kind        VARCHAR(50) NOT NULL,
    severity    VARCHAR(20) NOT NULL,   -- low | medium | high
    message     TEXT,
    status      VARCHAR(20) DEFAULT 'new',   -- new | assigned | in_progress | resolved | closed
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    assigned_to VARCHAR(100),
    resolved_at TIMESTAMPTZ,
    metadata    JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status, created_at DESC);

CREATE TABLE IF NOT EXISTS alert_actions (
    id          BIGSERIAL PRIMARY KEY,
    alert_id    BIGINT NOT NULL REFERENCES alerts(id) ON DELETE CASCADE,
    action      VARCHAR(50),
    note        TEXT,
    actor       VARCHAR(100),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 8) سناریوها و نتایج بهینه‌سازی
-- ============================================================
CREATE TABLE IF NOT EXISTS scenarios (
    id          BIGSERIAL PRIMARY KEY,
    factory_id  VARCHAR(50) NOT NULL,
    name        VARCHAR(200),
    params      JSONB NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS optimization_results (
    id          BIGSERIAL PRIMARY KEY,
    scenario_id BIGINT REFERENCES scenarios(id),
    factory_id  VARCHAR(50) NOT NULL,
    time        TIMESTAMPTZ NOT NULL,
    status      VARCHAR(30),
    total_cost  DOUBLE PRECISION,
    details     JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- 9) کاربران (اگر می‌خواهید از DB به‌جای in-memory استفاده کنید)
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL PRIMARY KEY,
    username        VARCHAR(100) UNIQUE NOT NULL,
    full_name       VARCHAR(200),
    hashed_password VARCHAR(200) NOT NULL,
    role            VARCHAR(30) NOT NULL DEFAULT 'viewer',
    factories       TEXT[] DEFAULT '{}',
    disabled        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

"""مدل‌های SQLAlchemy برای CEUO"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    Column, String, Integer, BigInteger, Numeric, Boolean,
    DateTime, Text, ForeignKey, ARRAY, Index, func
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column

Base = declarative_base()


class Factory(Base):
    __tablename__ = "factories"
    id = Column(String(50), primary_key=True)
    name = Column(String(200), nullable=False)
    type = Column(String(50), nullable=False)
    location = Column(String(200))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lines = relationship("Line", back_populates="factory")
    equipment = relationship("Equipment", back_populates="factory")
    tags = relationship("Tag", back_populates="factory")


class Line(Base):
    __tablename__ = "lines"
    id = Column(String(50), primary_key=True)
    factory_id = Column(String(50), ForeignKey("factories.id"), nullable=False)
    name = Column(String(200))
    capacity_tph = Column(Numeric(10, 2))
    product = Column(String(100))

    factory = relationship("Factory", back_populates="lines")


class Equipment(Base):
    __tablename__ = "equipment"
    id = Column(String(50), primary_key=True)
    factory_id = Column(String(50), ForeignKey("factories.id"), nullable=False)
    kind = Column(String(30), nullable=False)
    name = Column(String(200))
    cap = Column(Numeric(10, 3))
    eff = Column(Numeric(5, 4))
    min_load = Column(Numeric(5, 4), default=0.0)
    metadata_ = Column("metadata", JSONB, default=dict)

    factory = relationship("Factory", back_populates="equipment")


class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True)
    tag_id = Column(String(200), unique=True, nullable=False)
    factory_id = Column(String(50), ForeignKey("factories.id"), nullable=False)
    equipment_id = Column(String(50), ForeignKey("equipment.id"))
    unit = Column(String(20))
    description = Column(Text)
    source = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    factory = relationship("Factory", back_populates="tags")


class Reading(Base):
    """hypertable"""
    __tablename__ = "readings"
    time = Column(DateTime(timezone=True), primary_key=True)
    factory_id = Column(String(50), primary_key=True)
    tag_id = Column(String(200), primary_key=True)
    value = Column(Numeric, nullable=True)
    quality = Column(String(20), default="good")
    metadata_ = Column("metadata", JSONB, default=dict)

    __table_args__ = (
        Index("idx_readings_factory_tag_time", "factory_id", "tag_id", "time"),
    )


class KPI(Base):
    __tablename__ = "kpis"
    time = Column(DateTime(timezone=True), primary_key=True)
    factory_id = Column(String(50), primary_key=True)
    line_id = Column(String(50), primary_key=True, default="")
    kpi_name = Column(String(100), primary_key=True)
    value = Column(Numeric)
    unit = Column(String(20))
    metadata_ = Column("metadata", JSONB, default=dict)


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    factory_id = Column(String(50), nullable=False)
    kind = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    message = Column(Text)
    status = Column(String(20), default="new")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    assigned_to = Column(String(100))
    resolved_at = Column(DateTime(timezone=True))
    metadata_ = Column("metadata", JSONB, default=dict)


class AlertAction(Base):
    __tablename__ = "alert_actions"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    alert_id = Column(BigInteger, ForeignKey("alerts.id", ondelete="CASCADE"))
    action = Column(String(50))
    note = Column(Text)
    actor = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserORM(Base):
    __tablename__ = "users"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    full_name = Column(String(200))
    hashed_password = Column(String(200), nullable=False)
    role = Column(String(30), default="viewer")
    factories = Column(ARRAY(String), default=list)
    disabled = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    """مدل‌های Pydantic برای API و اعتبارسنجی"""
from datetime import datetime
from typing import Optional, Dict, List
from pydantic import BaseModel, Field, ConfigDict


class FactoryIn(BaseModel):
    id: str = Field(..., max_length=50)
    name: str
    type: str
    location: Optional[str] = None


class TagIn(BaseModel):
    tag_id: str = Field(..., max_length=200)
    factory_id: str
    equipment_id: Optional[str] = None
    unit: Optional[str] = None
    description: Optional[str] = None
    source: Optional[str] = None


class ReadingIn(BaseModel):
    time: datetime
    factory_id: str
    tag_id: str
    value: Optional[float] = None
    quality: str = "good"
    metadata: Dict = Field(default_factory=dict)


class ReadingOut(ReadingIn):
    model_config = ConfigDict(from_attributes=True)


class KPIIn(BaseModel):
    time: datetime
    factory_id: str
    line_id: str = ""
    kpi_name: str
    value: float
    unit: Optional[str] = None
    metadata: Dict = Field(default_factory=dict)


class AlertIn(BaseModel):
    factory_id: str
    kind: str
    severity: str = "medium"
    message: Optional[str] = None
    metadata: Dict = Field(default_factory=dict)


class AlertOut(AlertIn):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    created_at: datetime

    """مدیریت session پایگاه داده"""
import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from db.models import Base

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://ceu:ceu@localhost:5432/ceu"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db():
    """ساخت جداول (برای development؛ در production از Alembic استفاده کنید)"""
    Base.metadata.create_all(engine)


@contextmanager
def get_session() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

        [alembic]
script_location = alembic
prepend_sys_path = .
sqlalchemy.url = postgresql+psycopg2://ceu:ceu@localhost:5432/ceu

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S

from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os, sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

# خواندن URL از env
config.set_main_option(
    "sqlalchemy.url",
    os.environ.get("DATABASE_URL",
                   "postgresql+psycopg2://ceu:ceu@localhost:5432/ceu")
)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata,
                      literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection,
                          target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

    """initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    op.create_table(
        "factories",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("location", sa.String(200)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "lines",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("factory_id", sa.String(50), sa.ForeignKey("factories.id"), nullable=False),
        sa.Column("name", sa.String(200)),
        sa.Column("capacity_tph", sa.Numeric(10, 2)),
        sa.Column("product", sa.String(100)),
    )

    op.create_table(
        "equipment",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("factory_id", sa.String(50), sa.ForeignKey("factories.id"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("name", sa.String(200)),
        sa.Column("cap", sa.Numeric(10, 3)),
        sa.Column("eff", sa.Numeric(5, 4)),
        sa.Column("min_load", sa.Numeric(5, 4), server_default="0"),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
    )

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tag_id", sa.String(200), unique=True, nullable=False),
        sa.Column("factory_id", sa.String(50), sa.ForeignKey("factories.id"), nullable=False),
        sa.Column("equipment_id", sa.String(50), sa.ForeignKey("equipment.id")),
        sa.Column("unit", sa.String(20)),
        sa.Column("description", sa.Text),
        sa.Column("source", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "readings",
        sa.Column("time", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("factory_id", sa.String(50), primary_key=True),
        sa.Column("tag_id", sa.String(200), primary_key=True),
        sa.Column("value", sa.Numeric),
        sa.Column("quality", sa.String(20), server_default="good"),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
    )
    op.execute("SELECT create_hypertable('readings', 'time', if_not_exists => TRUE)")
    op.create_index("idx_readings_factory_tag_time", "readings",
                    ["factory_id", "tag_id", "time"])

    op.create_table(
        "kpis",
        sa.Column("time", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("factory_id", sa.String(50), primary_key=True),
        sa.Column("line_id", sa.String(50), primary_key=True, server_default=""),
        sa.Column("kpi_name", sa.String(100), primary_key=True),
        sa.Column("value", sa.Numeric),
        sa.Column("unit", sa.String(20)),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
    )
    op.execute("SELECT create_hypertable('kpis', 'time', if_not_exists => TRUE)")

    op.create_table(
        "alerts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("factory_id", sa.String(50), nullable=False),
        sa.Column("kind", sa.String(50), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("message", sa.Text),
        sa.Column("status", sa.String(20), server_default="new"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("assigned_to", sa.String(100)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
    )
    op.create_index("idx_alerts_status", "alerts", ["status", "created_at"])

    op.create_table(
        "alert_actions",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("alert_id", sa.BigInteger, sa.ForeignKey("alerts.id", ondelete="CASCADE")),
        sa.Column("action", sa.String(50)),
        sa.Column("note", sa.Text),
        sa.Column("actor", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "scenarios",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("factory_id", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200)),
        sa.Column("params", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "optimization_results",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("scenario_id", sa.BigInteger, sa.ForeignKey("scenarios.id")),
        sa.Column("factory_id", sa.String(50), nullable=False),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(30)),
        sa.Column("total_cost", sa.Numeric),
        sa.Column("details", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(100), unique=True, nullable=False),
        sa.Column("full_name", sa.String(200)),
        sa.Column("hashed_password", sa.String(200), nullable=False),
        sa.Column("role", sa.String(30), server_default="viewer"),
        sa.Column("factories", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("disabled", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("users")
    op.drop_table("optimization_results")
    op.drop_table("scenarios")
    op.drop_table("alert_actions")
    op.drop_table("alerts")
    op.drop_table("kpis")
    op.drop_table("readings")
    op.drop_table("tags")
    op.drop_table("equipment")
    op.drop_table("lines")
    op.drop_table("factories")

    # 1) ساخت دیتابیس (یک بار)
docker run -d --name ceu-pg -p 5432:5432 `
    -e POSTGRES_USER=ceu -e POSTGRES_PASSWORD=ceu -e POSTGRES_DB=ceu `
    timescale/timescaledb:latest-pg16

# 2) اعمال migrations
alembic upgrade head

# 3) بررسی
python -c "from db.session import engine; from sqlalchemy import inspect; print(inspect(engine).get_table_names())"

# 4) seed اولیه (اختیاری)
python -c "
from db.session import get_session
from db.models import Factory, Equipment
with get_session() as s:
    for f in [('F1-PAPER','کاغذ','paper'),('F2-TISSUE','تیشو','tissue'),('F3-WOOD','چوب','wood')]:
        s.merge(Factory(id=f[0], name=f[1], type=f[2]))
    print('seeded')
"

