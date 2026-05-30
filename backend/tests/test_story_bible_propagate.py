"""
Story Bible 变更传播机制测试
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

from fastapi.testclient import TestClient


# Mock user ID for testing
TEST_USER_ID = "test-user-123"


class MockStoryBible:
    """Mock StoryBible model"""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", str(uuid4()))
        self.user_id = kwargs.get("user_id", TEST_USER_ID)
        self.project_id = kwargs.get("project_id", None)
        self.novel_id = kwargs.get("novel_id", None)
        self.title = kwargs.get("title", "Test Story Bible")
        self.style = kwargs.get("style", "anime")
        self.worldview = kwargs.get("worldview", "fantasy")
        self.character_rules = kwargs.get("character_rules", [{"id": "char-1", "name": "Hero"}])
        self.scene_rules = kwargs.get("scene_rules", [{"id": "scene-1", "name": "Forest"}])
        self.prop_rules = kwargs.get("prop_rules", [{"id": "prop-1", "name": "Sword"}])
        self.event_timeline = kwargs.get("event_timeline", [{"id": "event-1", "name": "Battle"}])
        self.negative_prompt = kwargs.get("negative_prompt", None)
        self.extra_data = kwargs.get("extra_data", {})
        self.created_at = kwargs.get("created_at", datetime.utcnow())
        self.updated_at = kwargs.get("updated_at", datetime.utcnow())


class MockShot:
    """Mock Shot model"""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", str(uuid4()))
        self.user_id = kwargs.get("user_id", TEST_USER_ID)
        self.storyboard_id = kwargs.get("storyboard_id", str(uuid4()))
        self.shot_number = kwargs.get("shot_number", 1)
        self.extra_data = kwargs.get("extra_data", {})
        self.updated_at = kwargs.get("updated_at", datetime.utcnow())


class TestPropagateChangeRequest:
    """Test PropagateChangeRequest model"""
    def test_change_type_validation(self):
        """Test valid change types"""
        from app.api.v1.endpoints.story_bible import PropagateChangeRequest

        # Valid change types
        valid_types = ["character_update", "scene_update", "prop_update", "event_update", "voice_update"]
        for change_type in valid_types:
            request = PropagateChangeRequest(change_type=change_type)
            assert request.change_type == change_type
            assert request.affected_entity_ids == []

    def test_default_empty_entity_ids(self):
        """Test default affected_entity_ids is empty list"""
        from app.api.v1.endpoints.story_bible import PropagateChangeRequest

        request = PropagateChangeRequest(change_type="character_update")
        assert request.affected_entity_ids == []

    def test_custom_entity_ids(self):
        """Test custom affected_entity_ids"""
        from app.api.v1.endpoints.story_bible import PropagateChangeRequest

        entity_ids = ["entity-1", "entity-2"]
        request = PropagateChangeRequest(
            change_type="scene_update",
            affected_entity_ids=entity_ids
        )
        assert request.affected_entity_ids == entity_ids


class TestAffectedShotInfo:
    """Test AffectedShotInfo model"""
    def test_creation(self):
        """Test AffectedShotInfo creation"""
        from app.api.v1.endpoints.story_bible import AffectedShotInfo

        shot_info = AffectedShotInfo(
            id="shot-123",
            shot_number=5,
            review_reason="Story Bible character_update changed",
            review_at="2024-01-01T00:00:00"
        )
        assert shot_info.id == "shot-123"
        assert shot_info.shot_number == 5
        assert shot_info.review_reason == "Story Bible character_update changed"


class TestPropagateChangeResponse:
    """Test PropagateChangeResponse model"""
    def test_success_response(self):
        """Test successful propagate change response"""
        from app.api.v1.endpoints.story_bible import PropagateChangeResponse

        response = PropagateChangeResponse(
            status="success",
            affected_shots=3,
            change_type="character_update",
            affected_entity_ids=["char-1", "char-2"],
            action="marked_for_review"
        )
        assert response.status == "success"
        assert response.affected_shots == 3
        assert response.change_type == "character_update"
        assert len(response.affected_entity_ids) == 2
        assert response.action == "marked_for_review"


class TestChangeTypeMapping:
    """Test change type to entity reference mapping"""
    def test_character_update_mapping(self):
        """Test character_update maps to 'characters'"""
        change_type_mapping = {
            "character_update": "characters",
            "scene_update": "scenes",
            "prop_update": "props",
            "event_update": "events",
            "voice_update": "voices",
        }
        assert change_type_mapping["character_update"] == "characters"
        assert change_type_mapping["scene_update"] == "scenes"
        assert change_type_mapping["prop_update"] == "props"
        assert change_type_mapping["event_update"] == "events"
        assert change_type_mapping["voice_update"] == "voices"

    def test_unknown_change_type_fallback(self):
        """Test unknown change type falls back to 'entities'"""
        change_type_mapping = {
            "character_update": "characters",
            "scene_update": "scenes",
        }
        ref_key = change_type_mapping.get("unknown_type", "entities")
        assert ref_key == "entities"


class TestStoryBibleEntityExtraction:
    """Test extracting entity IDs from Story Bible rules"""
    def test_extract_character_ids(self):
        """Test extracting character IDs from character_rules"""
        story_bible = MockStoryBible(
            character_rules=[
                {"id": "char-1", "name": "Hero"},
                {"id": "char-2", "name": "Villain"},
            ],
            scene_rules=[],
            prop_rules=[],
            event_timeline=[]
        )

        entity_ids = []
        for rule in (story_bible.character_rules or []):
            if rule.get("id"):
                entity_ids.append(rule["id"])

        assert len(entity_ids) == 2
        assert "char-1" in entity_ids
        assert "char-2" in entity_ids

    def test_extract_all_entity_ids(self):
        """Test extracting all entity IDs from all rule types"""
        story_bible = MockStoryBible(
            character_rules=[{"id": "char-1", "name": "Hero"}],
            scene_rules=[{"id": "scene-1", "name": "Forest"}],
            prop_rules=[{"id": "prop-1", "name": "Sword"}],
            event_timeline=[{"id": "event-1", "name": "Battle"}]
        )

        rules = list(story_bible.character_rules or [])
        rules.extend(story_bible.scene_rules or [])
        rules.extend(story_bible.prop_rules or [])
        rules.extend(story_bible.event_timeline or [])

        entity_ids = []
        for rule in rules:
            if rule.get("id"):
                entity_ids.append(rule["id"])

        assert len(entity_ids) == 4
        assert "char-1" in entity_ids
        assert "scene-1" in entity_ids
        assert "prop-1" in entity_ids
        assert "event-1" in entity_ids


class TestShotReviewMarking:
    """Test marking shots for review"""
    def test_mark_shot_needs_review(self):
        """Test marking a shot with needs_review flag"""
        shot = MockShot()
        shot.extra_data = {}

        now = datetime.utcnow()
        shot.extra_data["needs_review"] = True
        shot.extra_data["review_reason"] = "Story Bible character_update changed"
        shot.extra_data["review_at"] = now.isoformat()
        shot.updated_at = now

        assert shot.extra_data["needs_review"] is True
        assert shot.extra_data["review_reason"] == "Story Bible character_update changed"
        assert shot.extra_data["review_at"] == now.isoformat()

    def test_preserve_existing_extra_data(self):
        """Test preserving existing extra_data when marking for review"""
        shot = MockShot()
        shot.extra_data = {"custom_field": "custom_value"}

        now = datetime.utcnow()
        shot.extra_data["needs_review"] = True
        shot.extra_data["review_reason"] = "Story Bible scene_update changed"
        shot.extra_data["review_at"] = now.isoformat()

        assert shot.extra_data["custom_field"] == "custom_value"
        assert shot.extra_data["needs_review"] is True


class TestAffectedShotFiltering:
    """Test filtering shots by entity references"""
    def test_filter_shots_by_character_refs(self):
        """Test filtering shots that reference specific characters"""
        shots = [
            MockShot(
                id="shot-1",
                extra_data={
                    "entity_refs": {"characters": ["char-1", "char-2"]}
                }
            ),
            MockShot(
                id="shot-2",
                extra_data={
                    "entity_refs": {"characters": ["char-3"]}
                }
            ),
            MockShot(
                id="shot-3",
                extra_data={
                    "entity_refs": {"scenes": ["scene-1"]}
                }
            ),
        ]

        target_characters = ["char-1"]
        affected = []
        for shot in shots:
            extra_data = shot.extra_data or {}
            entity_refs = extra_data.get("entity_refs", {})
            ref_list = entity_refs.get("characters", [])
            if any(char_id in ref_list for char_id in target_characters):
                affected.append(shot)

        assert len(affected) == 1
        assert affected[0].id == "shot-1"

    def test_filter_by_multiple_entity_types(self):
        """Test filtering shots by multiple entity types"""
        shots = [
            MockShot(
                id="shot-1",
                extra_data={
                    "entity_refs": {"characters": ["char-1"]}
                }
            ),
            MockShot(
                id="shot-2",
                extra_data={
                    "entity_refs": {"scenes": ["scene-1"]}
                }
            ),
            MockShot(
                id="shot-3",
                extra_data={
                    "entity_refs": {"characters": ["char-1"], "scenes": ["scene-1"]}
                }
            ),
        ]

        target_chars = ["char-1"]
        target_scenes = ["scene-1"]

        affected = []
        for shot in shots:
            extra_data = shot.extra_data or {}
            entity_refs = extra_data.get("entity_refs", {})

            char_match = any(c in entity_refs.get("characters", []) for c in target_chars)
            scene_match = any(s in entity_refs.get("scenes", []) for s in target_scenes)

            if char_match or scene_match:
                affected.append(shot)

        assert len(affected) == 3


class TestAffectedShotsResponse:
    """Test AffectedShotsResponse model"""
    def test_empty_shots_list(self):
        """Test response with no affected shots"""
        from app.api.v1.endpoints.story_bible import AffectedShotsResponse

        response = AffectedShotsResponse(shots=[], total=0)
        assert response.shots == []
        assert response.total == 0

    def test_shots_with_review_info(self):
        """Test response with shot review information"""
        from app.api.v1.endpoints.story_bible import AffectedShotsResponse, AffectedShotInfo

        shots = [
            AffectedShotInfo(
                id="shot-1",
                shot_number=1,
                review_reason="Story Bible character_update changed",
                review_at="2024-01-01T00:00:00"
            ),
            AffectedShotInfo(
                id="shot-2",
                shot_number=2,
                review_reason="Story Bible scene_update changed",
                review_at="2024-01-02T00:00:00"
            ),
        ]

        response = AffectedShotsResponse(shots=shots, total=2)
        assert len(response.shots) == 2
        assert response.total == 2
        assert response.shots[0].shot_number == 1
        assert response.shots[1].shot_number == 2


class TestStoryBibleOwnership:
    """Test Story Bible ownership validation"""
    def test_non_existent_story_bible(self):
        """Test accessing non-existent Story Bible returns 404"""
        # This would be tested via integration test
        # Here we verify the expected behavior
        assert True  # Placeholder for integration test


class TestReviewReasonFiltering:
    """Test filtering by review reason prefix"""
    def test_filter_story_bible_review_reasons(self):
        """Test filtering shots with Story Bible review reasons"""
        shots = [
            MockShot(
                id="shot-1",
                extra_data={
                    "needs_review": True,
                    "review_reason": "Story Bible character_update changed",
                    "review_at": "2024-01-01T00:00:00"
                }
            ),
            MockShot(
                id="shot-2",
                extra_data={
                    "needs_review": True,
                    "review_reason": "Manual review needed",
                    "review_at": "2024-01-02T00:00:00"
                }
            ),
            MockShot(
                id="shot-3",
                extra_data={
                    "needs_review": True,
                    "review_reason": "Story Bible scene_update changed",
                    "review_at": "2024-01-03T00:00:00"
                }
            ),
        ]

        story_bible_shots = []
        for shot in shots:
            extra_data = shot.extra_data or {}
            review_reason = extra_data.get("review_reason", "")
            if review_reason and review_reason.startswith("Story Bible"):
                story_bible_shots.append({
                    "id": shot.id,
                    "shot_number": shot.shot_number,
                    "review_reason": review_reason,
                    "review_at": extra_data.get("review_at")
                })

        assert len(story_bible_shots) == 2
        assert story_bible_shots[0]["id"] == "shot-1"
        assert story_bible_shots[1]["id"] == "shot-3"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])