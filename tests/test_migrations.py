"""Tests for Alembic migrations."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, inspect

from src.db.models import Base


class TestMigrations:
    """Tests for database migration functionality."""

    def test_migration_file_exists(self):
        """Test that initial migration file exists."""
        import src
        package_dir = Path(src.__file__).parent.parent
        migration_file = package_dir / "migrations" / "versions" / "001_initial_schema.py"
        assert migration_file.exists(), "Initial migration file should exist"

    def test_alembic_ini_exists(self):
        """Test that alembic.ini exists."""
        import src
        package_dir = Path(src.__file__).parent.parent
        alembic_ini = package_dir / "alembic.ini"
        assert alembic_ini.exists(), "alembic.ini should exist"

    def test_env_py_exists(self):
        """Test that migrations/env.py exists."""
        import src
        package_dir = Path(src.__file__).parent.parent
        env_py = package_dir / "migrations" / "env.py"
        assert env_py.exists(), "migrations/env.py should exist"

    def test_create_all_creates_tables(self):
        """Test that Base.metadata.create_all creates all expected tables."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            engine = create_engine(f"sqlite:///{db_path}")
            Base.metadata.create_all(engine)

            inspector = inspect(engine)
            tables = set(inspector.get_table_names())

            expected_tables = {
                "supplier_items",
                "asin_candidates",
                "keepa_snapshots",
                "spapi_snapshots",
                "score_history",
                "brand_settings",
                "global_settings",
                "api_logs",
            }

            assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"

        finally:
            Path(db_path).unlink(missing_ok=True)

    def test_migration_has_upgrade_and_downgrade(self):
        """Test that migration file has upgrade and downgrade functions."""
        import src
        package_dir = Path(src.__file__).parent.parent
        migration_file = package_dir / "migrations" / "versions" / "001_initial_schema.py"
        
        content = migration_file.read_text()
        assert "def upgrade()" in content, "Migration should have upgrade function"
        assert "def downgrade()" in content, "Migration should have downgrade function"

    def test_init_database_with_migrations_false(self):
        """Test init_database with use_migrations=False falls back to create_all."""
        from src.db.session import init_database, close_database, _engine
        import src.db.session as session_module
        
        # Use a temp database
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        
        try:
            with patch('src.db.session.get_db_path', return_value=Path(db_path)):
                # Reset the global engine
                session_module._engine = None
                session_module._session_factory = None
                
                # Initialize without migrations
                init_database(use_migrations=False)
                
                # Check tables were created
                from src.db.session import get_engine
                engine = get_engine()
                inspector = inspect(engine)
                tables = inspector.get_table_names()
                
                assert "supplier_items" in tables
                assert "asin_candidates" in tables
                
                # Cleanup
                close_database()
        finally:
            Path(db_path).unlink(missing_ok=True)
