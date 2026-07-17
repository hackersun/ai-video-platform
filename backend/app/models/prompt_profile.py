"""Immutable, model-aware Prompt Profile persistence."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    event,
    inspect,
    Integer,
    JSON,
    select,
    String,
    Text,
    UniqueConstraint,
)

from app.core.database import Base
from app.core.time_utils import utc_now


def _persisted_status(target) -> str:
    history = inspect(target).attrs.status.history
    return history.deleted[0] if history.deleted else target.status


def _reject_published_update(_mapper, _connection, target) -> None:
    state = inspect(target)
    changed = any(
        state.attrs[column.key].history.has_changes()
        for column in state.mapper.column_attrs
    )
    if _persisted_status(target) == "published" and changed:
        raise ValueError("published prompt version is append-only; create a draft instead")


def _reject_published_delete(_mapper, _connection, target) -> None:
    if _persisted_status(target) == "published":
        raise ValueError("published prompt version is append-only; deletion is not allowed")


def _has_published_history(connection, profile_id: str) -> bool:
    statement = (
        select(PromptProfileVersion.id)
        .where(
            PromptProfileVersion.profile_id == profile_id,
            PromptProfileVersion.status == "published",
        )
        .limit(1)
    )
    return connection.execute(statement).first() is not None


def _reject_profile_with_published_history(_mapper, connection, target) -> None:
    if _has_published_history(connection, target.id):
        raise ValueError("prompt profile with published history is immutable")


class PromptProfile(Base):
    __tablename__ = "prompt_profiles"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), nullable=False, index=True)
    key = Column(String(120), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    task = Column(String(80), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)


class PromptProfileVersion(Base):
    __tablename__ = "prompt_profile_versions"
    __table_args__ = (
        UniqueConstraint("profile_id", "version", name="uq_prompt_profile_version"),
        CheckConstraint("version >= 1", name="ck_prompt_profile_version_positive"),
        CheckConstraint(
            "status IN ('draft', 'published', 'disabled')",
            name="ck_prompt_profile_version_status",
        ),
    )

    id = Column(String(36), primary_key=True)
    profile_id = Column(String(36), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    stage = Column(String(80))
    content = Column(Text, nullable=False)
    variables = Column(JSON, nullable=False, default=dict)
    routing = Column(JSON, nullable=False, default=dict)
    output_contract = Column(String(120))
    evaluation = Column(JSON, nullable=False, default=dict)
    status = Column(String(30), nullable=False, default="draft", index=True)
    checksum = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    published_at = Column(DateTime)


event.listen(PromptProfileVersion, "before_update", _reject_published_update)
event.listen(PromptProfileVersion, "before_delete", _reject_published_delete)
event.listen(PromptProfile, "before_update", _reject_profile_with_published_history)
event.listen(PromptProfile, "before_delete", _reject_profile_with_published_history)
