"""Database session management for Seller Opportunity Scanner."""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.config import get_db_path

from .models import Base

logger = logging.getLogger(__name__)

# Global engine instance
_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    """Get or create the SQLAlchemy engine."""
    global _engine
    if _engine is None:
        db_path = get_db_path()
        _engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False},
        )

        # Enable foreign keys for SQLite
        @event.listens_for(_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Get or create the session factory."""
    global _session_factory
    if _session_factory is None:
        engine = get_engine()
        _session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return _session_factory


def get_session() -> Session:
    """Create a new database session."""
    factory = get_session_factory()
    return factory()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_database(use_migrations: bool = True) -> None:
    """Initialize the database schema.
    
    Args:
        use_migrations: If True, use Alembic migrations. If False, use create_all().
    """
    engine = get_engine()

    if use_migrations:
        _run_migrations(engine)
    else:
        # Fallback to create_all for simple cases
        Base.metadata.create_all(engine)


def _run_migrations(engine: Engine) -> None:
    """Run Alembic migrations to latest version."""
    from alembic import command
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    # Find the alembic.ini file
    # Look relative to the package location
    import src
    package_dir = Path(src.__file__).parent.parent
    alembic_ini = package_dir / "alembic.ini"
    migrations_dir = package_dir / "migrations"

    if not alembic_ini.exists():
        logger.warning(f"alembic.ini not found at {alembic_ini}, falling back to create_all()")
        Base.metadata.create_all(engine)
        return

    # Create Alembic config
    alembic_cfg = Config(str(alembic_ini))
    alembic_cfg.set_main_option("script_location", str(migrations_dir))
    alembic_cfg.set_main_option("sqlalchemy.url", str(engine.url))

    # Check current migration state
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        current_rev = context.get_current_revision()

    # Get the head revision
    script = ScriptDirectory.from_config(alembic_cfg)
    head_rev = script.get_current_head()

    if current_rev is None:
        # Fresh database - check if tables exist
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        if tables and "alembic_version" not in tables:
            # Tables exist but no alembic_version - stamp the database
            logger.info("Existing database detected, stamping with current migration version")
            command.stamp(alembic_cfg, "head")
        else:
            # Fresh database - run all migrations
            logger.info("Running database migrations...")
            command.upgrade(alembic_cfg, "head")
            logger.info("Database migrations completed")
    elif current_rev != head_rev:
        # Need to upgrade
        logger.info(f"Upgrading database from {current_rev} to {head_rev}")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database upgrade completed")
    else:
        logger.debug("Database is up to date")


def reset_database() -> None:
    """Drop and recreate all tables (for testing only)."""
    engine = get_engine()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def close_database() -> None:
    """Close the database connection."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
        _engine = None
    _session_factory = None
