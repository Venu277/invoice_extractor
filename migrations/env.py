import sys
import os
from pathlib import Path
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import settings
from app.db import Base
import app.models  # register all models

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Use URL passed to Alembic Config if custom; otherwise fallback to settings.DATABASE_URL
current_url = config.get_main_option("sqlalchemy.url")
if not current_url or current_url == "driver://user:pass@localhost/dbname":
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Ensure database directory exists before connecting (especially in Linux/Docker/Render)
    if settings.DATABASE_URL.startswith("sqlite:///"):
        db_path_str = settings.DATABASE_URL.replace("sqlite:///", "")
        if db_path_str and db_path_str != ":memory:":
            Path(db_path_str).parent.mkdir(parents=True, exist_ok=True)

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True  # Important for SQLite schema migrations
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
