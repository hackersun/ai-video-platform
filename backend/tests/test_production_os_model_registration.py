from app.core.database import Base
import app.models  # noqa: F401


def test_production_os_models_are_registered_for_create_all():
    assert {
        "production_state_events",
        "provider_asset_bindings",
        "quality_evaluations",
    }.issubset(Base.metadata.tables)
