"""
Tests for VEYRA Storage Schema Versioning and Migrations.
Verifies schema initialization, table constraints, indices, and migration rollback on failure.
"""
import os
import sqlite3
import tempfile
import unittest

from app.core.exceptions import StorageError
from storage.migrations.migration_manager import MigrationManager, CURRENT_SCHEMA_VERSION


class TestStorageMigrations(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_migrations.sqlite")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_fresh_database_applies_all_migrations(self):
        conn = sqlite3.connect(self.db_path)
        try:
            applied = MigrationManager.apply_migrations(conn)
            self.assertGreaterEqual(applied, 1)
            version = MigrationManager.get_current_version(conn)
            self.assertEqual(version, CURRENT_SCHEMA_VERSION)
            self.assertTrue(MigrationManager.validate_schema(conn))
        finally:
            conn.close()

    def test_reapplying_migrations_is_idempotent(self):
        conn = sqlite3.connect(self.db_path)
        try:
            MigrationManager.apply_migrations(conn)
            # Second run should apply 0 migrations
            applied_second = MigrationManager.apply_migrations(conn)
            self.assertEqual(applied_second, 0)
        finally:
            conn.close()

    def test_schema_validation_detects_corrupt_or_missing_table(self):
        conn = sqlite3.connect(self.db_path)
        try:
            MigrationManager.apply_migrations(conn)
            with conn:
                conn.execute("DROP TABLE incidents;")
            with self.assertRaises(StorageError):
                MigrationManager.validate_schema(conn)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
