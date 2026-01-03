"""
Tests for quest tracking system.

These tests verify that quests can be accepted, tracked, updated,
and completed correctly.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestActiveQuestDataclass:
    """Tests for the ActiveQuest dataclass."""

    def test_create_from_quest_hook(self):
        """Verify ActiveQuest can be created from a quest hook."""
        from src.data_models import ActiveQuest, QuestState

        hook = {
            "quest_id": "hunt_frore_gryphus",
            "title": "The Winged Terror",
            "description": "Slay the beast",
            "quest_giver": "aegnyth_cormick",
            "objective": "Slay or banish the frore gryphus",
            "target_monster": "frore_gryphus",
            "target_count": 1,
            "destination_location": "The Nest of the Frore Gryphus",
            "reward_description": "50gp pooled from the shepherds, plus 1gp per sheep carcass",
        }

        quest = ActiveQuest.from_quest_hook(hook, npc_id="aegnyth_cormick", hex_id="0105")

        assert quest.quest_id == "hunt_frore_gryphus"
        assert quest.title == "The Winged Terror"
        assert quest.state == QuestState.ACCEPTED
        assert quest.quest_giver_npc == "aegnyth_cormick"
        assert quest.quest_giver_hex == "0105"
        assert quest.target_monster == "frore_gryphus"
        assert quest.target_count == 1
        assert quest.reward_gold == 50
        assert "sheep" in quest.reward_per_bonus

    def test_serialization_roundtrip(self):
        """Verify ActiveQuest can serialize and deserialize."""
        from src.data_models import ActiveQuest, QuestState

        quest = ActiveQuest(
            quest_id="test_quest",
            title="Test Quest",
            description="A test",
            state=QuestState.IN_PROGRESS,
            target_monster="goblin",
            progress_count=2,
            notes=["Found the lair", "Killed 2 goblins"],
        )

        data = quest.to_dict()
        restored = ActiveQuest.from_dict(data)

        assert restored.quest_id == quest.quest_id
        assert restored.state == quest.state
        assert restored.progress_count == 2
        assert len(restored.notes) == 2

    def test_check_completion_with_target_monster(self):
        """Verify kill quest completion detection."""
        from src.data_models import ActiveQuest, QuestState

        quest = ActiveQuest(
            quest_id="hunt_quest",
            title="Hunt the Beast",
            description="Kill it",
            target_monster="frore_gryphus",
            target_count=1,
        )

        # Not complete before kill
        assert quest.is_active()
        assert not quest.check_completion(["goblin", "wolf"], "0105")

        # Complete after killing target
        assert quest.check_completion(["frore_gryphus"], "0105")
        assert quest.progress_count == 1


class TestQuestStateEnum:
    """Tests for QuestState enum."""

    def test_all_states_exist(self):
        """Verify all expected quest states exist."""
        from src.data_models import QuestState

        assert QuestState.UNKNOWN.value == "unknown"
        assert QuestState.AVAILABLE.value == "available"
        assert QuestState.ACCEPTED.value == "accepted"
        assert QuestState.IN_PROGRESS.value == "in_progress"
        assert QuestState.COMPLETED.value == "completed"
        assert QuestState.FAILED.value == "failed"
        assert QuestState.ABANDONED.value == "abandoned"


class TestSessionManagerQuestTracking:
    """Tests for SessionManager quest tracking methods."""

    def test_accept_quest(self):
        """Verify quest can be accepted."""
        from src.game_state.session_manager import SessionManager, GameSession

        manager = SessionManager()
        manager._current_session = GameSession(
            session_id="test",
            session_name="Test Session",
        )

        hook = {
            "quest_id": "hunt_frore_gryphus",
            "title": "The Winged Terror",
            "description": "Slay the beast",
            "objective": "Slay or banish the frore gryphus",
            "target_monster": "frore_gryphus",
            "reward_description": "50gp",
        }

        result = manager.accept_quest(hook, npc_id="aegnyth", hex_id="0105")

        assert result is not None
        assert result["quest_id"] == "hunt_frore_gryphus"
        assert "hunt_frore_gryphus" in manager._current_session.active_quests

    def test_cannot_accept_duplicate_quest(self):
        """Verify duplicate quests are rejected."""
        from src.game_state.session_manager import SessionManager, GameSession

        manager = SessionManager()
        manager._current_session = GameSession(
            session_id="test",
            session_name="Test Session",
        )

        hook = {"quest_id": "test_quest", "title": "Test", "description": "Test"}

        # Accept once
        result1 = manager.accept_quest(hook)
        assert result1 is not None

        # Try to accept again
        result2 = manager.accept_quest(hook)
        assert result2 is None

    def test_cannot_accept_completed_quest(self):
        """Verify completed quests cannot be re-accepted."""
        from src.game_state.session_manager import SessionManager, GameSession

        manager = SessionManager()
        manager._current_session = GameSession(
            session_id="test",
            session_name="Test Session",
            completed_quests=["test_quest"],
        )

        hook = {"quest_id": "test_quest", "title": "Test", "description": "Test"}

        result = manager.accept_quest(hook)
        assert result is None

    def test_update_quest_progress(self):
        """Verify quest progress can be updated."""
        from src.game_state.session_manager import SessionManager, GameSession

        manager = SessionManager()
        manager._current_session = GameSession(
            session_id="test",
            session_name="Test Session",
        )

        hook = {"quest_id": "test_quest", "title": "Test", "description": "Test"}
        manager.accept_quest(hook)

        result = manager.update_quest_progress(
            "test_quest",
            progress_count=5,
            note="Found the lair",
        )

        assert result is True
        quest = manager.get_active_quest("test_quest")
        assert quest["progress_count"] == 5
        assert "Found the lair" in quest["notes"]

    def test_complete_quest_on_monster_kill(self):
        """Verify quest completes when target monster is killed."""
        from src.game_state.session_manager import SessionManager, GameSession

        manager = SessionManager()
        manager._current_session = GameSession(
            session_id="test",
            session_name="Test Session",
        )

        hook = {
            "quest_id": "hunt_frore_gryphus",
            "title": "The Winged Terror",
            "description": "Slay the beast",
            "target_monster": "frore_gryphus",
            "target_count": 1,
            "reward_description": "50gp",
        }

        manager.accept_quest(hook, npc_id="aegnyth", hex_id="0105")

        # Kill the target
        completed = manager.on_monster_killed("frore_gryphus", "0105")

        assert len(completed) == 1
        assert completed[0]["quest_id"] == "hunt_frore_gryphus"
        assert "hunt_frore_gryphus" in manager._current_session.completed_quests

    def test_abandon_quest(self):
        """Verify quest can be abandoned."""
        from src.game_state.session_manager import SessionManager, GameSession
        from src.data_models import QuestState

        manager = SessionManager()
        manager._current_session = GameSession(
            session_id="test",
            session_name="Test Session",
        )

        hook = {"quest_id": "test_quest", "title": "Test", "description": "Test"}
        manager.accept_quest(hook)

        result = manager.abandon_quest("test_quest")

        assert result is True
        quest = manager.get_active_quest("test_quest")
        assert quest["state"] == QuestState.ABANDONED.value

    def test_fail_quest_with_reason(self):
        """Verify quest can be failed with a reason."""
        from src.game_state.session_manager import SessionManager, GameSession
        from src.data_models import QuestState

        manager = SessionManager()
        manager._current_session = GameSession(
            session_id="test",
            session_name="Test Session",
        )

        hook = {"quest_id": "test_quest", "title": "Test", "description": "Test"}
        manager.accept_quest(hook)

        result = manager.fail_quest("test_quest", "Target escaped")

        assert result is True
        quest = manager.get_active_quest("test_quest")
        assert quest["state"] == QuestState.FAILED.value
        assert "Failed: Target escaped" in quest["notes"]

    def test_get_all_active_quests(self):
        """Verify all active quests can be retrieved."""
        from src.game_state.session_manager import SessionManager, GameSession

        manager = SessionManager()
        manager._current_session = GameSession(
            session_id="test",
            session_name="Test Session",
        )

        hook1 = {"quest_id": "quest1", "title": "Quest 1", "description": "First"}
        hook2 = {"quest_id": "quest2", "title": "Quest 2", "description": "Second"}

        manager.accept_quest(hook1)
        manager.accept_quest(hook2)

        quests = manager.get_all_active_quests()

        assert len(quests) == 2
        quest_ids = [q["quest_id"] for q in quests]
        assert "quest1" in quest_ids
        assert "quest2" in quest_ids


class TestSessionSerialization:
    """Tests for quest tracking persistence in session."""

    def test_active_quests_serialized(self):
        """Verify active quests are included in session serialization."""
        from src.game_state.session_manager import GameSession

        session = GameSession(
            session_id="test",
            session_name="Test Session",
            active_quests={
                "test_quest": {
                    "quest_id": "test_quest",
                    "title": "Test",
                    "description": "A test quest",
                    "state": "accepted",
                }
            },
        )

        data = session.to_dict()

        assert "active_quests" in data
        assert "test_quest" in data["active_quests"]

    def test_active_quests_deserialized(self):
        """Verify active quests are restored from session data."""
        from src.game_state.session_manager import GameSession

        data = {
            "session_id": "test",
            "session_name": "Test Session",
            "active_quests": {
                "test_quest": {
                    "quest_id": "test_quest",
                    "title": "Test",
                    "description": "A test quest",
                    "state": "in_progress",
                    "progress_count": 3,
                }
            },
        }

        session = GameSession.from_dict(data)

        assert "test_quest" in session.active_quests
        assert session.active_quests["test_quest"]["progress_count"] == 3
