from collections.abc import Generator
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from app.config import settings

# Ensure database directory exists before connecting (especially in Linux/Docker/Render)
if settings.DATABASE_URL.startswith("sqlite:///"):
    db_path_str = settings.DATABASE_URL.replace("sqlite:///", "")
    if db_path_str and db_path_str != ":memory:":
        Path(db_path_str).parent.mkdir(parents=True, exist_ok=True)

# Engine setup
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
