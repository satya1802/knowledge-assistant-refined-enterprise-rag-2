"""Test configuration: guarantee a clean database before tests.

The application creates its SQLite database at import time — ``main.py``
calls ``Base.metadata.create_all`` at module level, before any test runs.
If a stale ``app.db`` with an incompatible schema is present (e.g. left
over from a previous schema version), ``create_all`` silently skips the
existing tables and inserts fail with NOT-NULL constraint errors.

This conftest runs before any test module is imported.  It points
``DATABASE_URL`` at a throwaway file and removes any pre-existing database
files so the application always recreates them with the current schema.
"""

from __future__ import annotations

import os
from pathlib import Path

# Use a throwaway database file for the test session so tests never touch
# the development database.
_test_db = "test_app.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db}"

# Remove any pre-existing database files so the schema is always fresh.
for _name in ("app.db", _test_db):
    _p = Path(_name)
    if _p.exists():
        _p.unlink()
