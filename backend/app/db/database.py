from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from functools import lru_cache
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Pin the driver explicitly: SQLAlchemy 2.1 defaults to psycopg 3, while the
# project installs psycopg2-binary. Preserve explicitly configured drivers.
database_url = settings.DATABASE_URL
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
elif database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg2://", 1)

# SQLAlchemy engine for direct database access
engine = create_engine(
    database_url,
    pool_size=settings.DATABASE_POOL_SIZE,
    pool_pre_ping=True,
    # Bound parameters can contain full CVs and must not be emitted to logs,
    # including development SQL logs or database exception strings.
    echo=False,
    hide_parameters=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for FastAPI to get DB session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
