"""R04: at most one active publication pipeline per (user, novel).

Partial unique index works on both SQLite and PostgreSQL. Legacy duplicate
active rows (the R04 bug itself) are resolved first: the newest active row per
(user, novel) is kept, older ones become status=cancelled with
blocker_code=superseded_duplicate_active. If the index still cannot be created
we log and the application-level admission check remains the guard.
"""

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.services.publication_pipeline_admission import ACTIVE_PIPELINE_STATUSES

logger = logging.getLogger(__name__)

INDEX_NAME = "uq_publication_pipeline_active_novel"
_STATUSES = ", ".join(f"'{s}'" for s in sorted(ACTIVE_PIPELINE_STATUSES))
_DDL = text(
    f"CREATE UNIQUE INDEX IF NOT EXISTS {INDEX_NAME} ON publication_pipelines "
    f"(user_id, novel_id) WHERE status IN ({_STATUSES})"
)

_SUPERSEDE = text(
    "UPDATE publication_pipelines SET status = 'cancelled', "
    "blocker_code = 'superseded_duplicate_active' "
    f"WHERE status IN ({_STATUSES}) AND id NOT IN ("
    "  SELECT id FROM ("
    "    SELECT id, ROW_NUMBER() OVER (PARTITION BY user_id, novel_id "
    "      ORDER BY created_at DESC, id DESC) AS rn "
    f"    FROM publication_pipelines WHERE status IN ({_STATUSES})"
    "  ) ranked WHERE rn = 1)"
)


def add_active_pipeline_index(engine: Engine) -> None:
    try:
        with engine.begin() as connection:
            connection.execute(_SUPERSEDE)
            connection.execute(_DDL)
    except DBAPIError as error:  # duplicates in legacy data
        logger.warning("active pipeline unique index not created: %s", error.orig)


async def add_active_pipeline_index_async(engine: AsyncEngine) -> None:
    try:
        async with engine.begin() as connection:
            await connection.execute(_SUPERSEDE)
            await connection.execute(_DDL)
    except DBAPIError as error:
        logger.warning("active pipeline unique index not created: %s", error.orig)
