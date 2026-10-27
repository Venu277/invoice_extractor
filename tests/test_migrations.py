import os
import shutil
import tempfile
from alembic.config import Config
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from app.db import Base
import app.models  # ensure all models are registered in Base.metadata


def test_models_and_migrations_do_not_diverge():
    """
    Guarantees the SQLAlchemy models and Alembic migrations stay in 100% lockstep.
    Fails if any model introduces a table, column, index, or constraint that is not
    present in the latest Alembic migration head.
    """
    tmp_dir = tempfile.mkdtemp()
    try:
        tmp_db_path = os.path.join(tmp_dir, "migration_divergence_test.db")
        db_url = f"sqlite:///{tmp_db_path}"

        # Configure Alembic pointing to the temporary test DB
        cfg = Config("alembic.ini")
        cfg.set_main_option("sqlalchemy.url", db_url)

        # Run all migrations from scratch to head
        command.upgrade(cfg, "head")

        # Compare database schema against SQLAlchemy Base.metadata
        engine = create_engine(db_url)
        with engine.connect() as conn:
            ctx = MigrationContext.configure(conn, opts={"compare_type": True})
            diff = compare_metadata(ctx, Base.metadata)

            assert len(diff) == 0, (
                f"SQLAlchemy models and Alembic migrations have diverged! "
                f"Unmigrated schema changes detected: {diff}"
            )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
