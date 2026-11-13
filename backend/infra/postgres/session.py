from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import get_settings


settings = get_settings()
engine = create_engine(
    settings.resolved_database_url,
    pool_pre_ping=True,
    connect_args=settings.database_connect_args,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
