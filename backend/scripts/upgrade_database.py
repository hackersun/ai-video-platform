"""Upgrade a blank or legacy database to the current managed revision."""

import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db_migrations.alembic_bridge import upgrade_database


if __name__ == "__main__":
    print(f"Database migration complete: {upgrade_database()}")
