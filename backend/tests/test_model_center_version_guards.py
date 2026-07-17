from __future__ import annotations

import pytest
from sqlalchemy import delete, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from app.db_migrations.model_center import add_model_center_links
from tests.model_center_helpers import (
    create_model_center_engine,
    profile_version,
    recipe_version,
)


def _create_protected_model_center_engine(tmp_path, name: str):
    engine = create_model_center_engine(tmp_path, name)
    add_model_center_links(engine)
    return engine


@pytest.mark.parametrize(
    ("row_factory", "edit"),
    [
        (profile_version, lambda row: setattr(row, "api_model_id", "mutated-model")),
        (recipe_version, lambda row: setattr(row, "spec", {"stages": ["mutated"]})),
    ],
)
def test_published_versions_allow_publish_transition_but_reject_later_edits(
    tmp_path, row_factory, edit,
):
    engine = create_model_center_engine(tmp_path, f"append-only-{row_factory.__name__}.db")

    with Session(engine, expire_on_commit=False) as session:
        row = row_factory()
        session.add(row)
        session.commit()
        row.status = "published"
        session.commit()
        edit(row)
        with pytest.raises(ValueError, match="published version is append-only"):
            session.commit()
        session.rollback()
    engine.dispose()


@pytest.mark.parametrize(
    ("row_factory", "edit"),
    [
        (profile_version, lambda row: setattr(row, "api_model_id", "draft-model")),
        (recipe_version, lambda row: setattr(row, "spec", {"stages": ["draft-edit"]})),
    ],
)
def test_draft_versions_allow_instance_edits_and_deletes(tmp_path, row_factory, edit):
    engine = create_model_center_engine(tmp_path, f"draft-delete-{row_factory.__name__}.db")

    with Session(engine, expire_on_commit=False) as session:
        row = row_factory()
        session.add(row)
        session.commit()
        edit(row)
        session.commit()
        session.delete(row)
        session.commit()
        assert session.get(type(row), row.id) is None
    engine.dispose()


@pytest.mark.parametrize("row_factory", [profile_version, recipe_version])
def test_published_versions_reject_instance_delete(tmp_path, row_factory):
    engine = create_model_center_engine(tmp_path, f"published-delete-{row_factory.__name__}.db")

    with Session(engine, expire_on_commit=False) as session:
        row = row_factory(status="published")
        session.add(row)
        session.commit()
        session.delete(row)
        with pytest.raises(ValueError, match="published version is append-only"):
            session.commit()
        session.rollback()
        assert session.get(type(row), row.id) is not None
    engine.dispose()


@pytest.mark.parametrize(
    ("row_factory", "field_name", "draft_value", "published_value"),
    [
        (profile_version, "api_model_id", "draft-bulk", "published-bulk"),
        (recipe_version, "name", "Draft Bulk", "Published Bulk"),
    ],
)
def test_sqlite_triggers_protect_bulk_update_mappings(
    tmp_path, row_factory, field_name, draft_value, published_value,
):
    engine = _create_protected_model_center_engine(
        tmp_path, f"bulk-mappings-{row_factory.__name__}.db",
    )
    model = type(row_factory())

    with Session(engine) as session:
        draft = row_factory(id="draft-version", version=1)
        published = row_factory(id="published-version", version=2, status="published")
        session.add_all([draft, published])
        session.commit()
        session.bulk_update_mappings(model, [{"id": draft.id, field_name: draft_value}])
        session.commit()
        assert getattr(session.get(model, draft.id), field_name) == draft_value

        with pytest.raises(DBAPIError, match="published version is append-only"):
            session.bulk_update_mappings(model, [{"id": published.id, field_name: published_value}])
            session.commit()
        session.rollback()
    engine.dispose()


@pytest.mark.parametrize(
    ("row_factory", "operation"),
    [
        (profile_version, "update"), (profile_version, "delete"),
        (recipe_version, "update"), (recipe_version, "delete"),
    ],
)
def test_sqlite_triggers_allow_draft_and_reject_published_session_dml(
    tmp_path, row_factory, operation,
):
    engine = _create_protected_model_center_engine(
        tmp_path, f"session-{operation}-{row_factory.__name__}.db",
    )
    model = type(row_factory())

    with Session(engine) as session:
        draft = row_factory(id="draft-version", version=1)
        published = row_factory(id="published-version", version=2, status="published")
        session.add_all([draft, published])
        session.commit()

        if operation == "update":
            draft_statement = update(model).where(model.id == draft.id).values(status="draft")
            published_statement = update(model).where(model.id == published.id).values(status="disabled")
        else:
            draft_statement = delete(model).where(model.id == draft.id)
            published_statement = delete(model).where(model.id == published.id)
        session.execute(draft_statement)
        session.commit()
        with pytest.raises(DBAPIError, match="published version is append-only"):
            session.execute(published_statement)
            session.commit()
        session.rollback()
    engine.dispose()


@pytest.mark.parametrize(
    ("row_factory", "changes"),
    [
        (profile_version, {"api_model_id": "api-model-v2"}),
        (recipe_version, {"spec": {"stages": ["storyboard", "render"]}}),
    ],
)
def test_published_versions_create_unique_next_draft_rows(tmp_path, row_factory, changes):
    engine = create_model_center_engine(tmp_path, f"next-version-{row_factory.__name__}.db")

    with Session(engine, expire_on_commit=False) as session:
        published = row_factory(status="published")
        session.add(published)
        session.commit()
        next_row = published.create_next_version(checksum="b" * 64, **changes)
        assert next_row.id != published.id
        assert next_row.version == published.version + 1
        assert next_row.status == "draft"
        assert next_row.checksum == "b" * 64
        session.add(next_row)
        session.commit()

        duplicate = published.create_next_version(checksum="c" * 64, **changes)
        assert duplicate.id != next_row.id
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    engine.dispose()
