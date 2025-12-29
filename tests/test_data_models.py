"""
Unit tests for core data models.

Tests GameDate, GameTime, CharacterState, and other data structures
from src/data_models.py.
"""

import pytest
from src.data_models import (
    GameDate,
    GameTime,
    Season,
    TimeOfDay,
    WatchPeriod,
    CharacterState,
    Condition,
    ConditionType,
    LocationState,
    LocationType,
    PartyState,
    PartyResources,
    Location,
    StatBlock,
    Monster,
    HexLocation,
)


class TestGameDate:
    """Tests for GameDate class."""

    def test_create_game_date(self):
        """Test creating a game date."""
        date = GameDate(year=1, month=6, day=15)
        assert date.year == 1
        assert date.month == 6
        assert date.day == 15

    def test_advance_days_simple(self):
        """Test advancing date by a few days."""
        date = GameDate(year=1, month=6, day=15)
        new_date = date.advance_days(5)
        assert new_date.day == 20
        assert new_date.month == 6
        assert new_date.year == 1

    def test_advance_days_month_rollover(self):
        """Test advancing date across month boundary."""
        # Month 6 (Greenmont) has 28 days in Dolmenwood calendar
        date = GameDate(year=1, month=6, day=28)
        new_date = date.advance_days(5)
        # 28 + 5 = 33, which is 5 days into month 7 (Moltmont, 30 days)
        assert new_date.day == 5
        assert new_date.month == 7
        assert new_date.year == 1

    def test_advance_days_year_rollover(self):
        """Test advancing date across year boundary."""
        date = GameDate(year=1, month=12, day=25)
        new_date = date.advance_days(10)
        assert new_date.month == 1
        assert new_date.year == 2

    def test_get_season_spring(self):
        """Test spring season detection."""
        for month in [3, 4, 5]:
            date = GameDate(year=1, month=month, day=15)
            assert date.get_season() == Season.SPRING

    def test_get_season_summer(self):
        """Test summer season detection."""
        for month in [6, 7, 8]:
            date = GameDate(year=1, month=month, day=15)
            assert date.get_season() == Season.SUMMER

    def test_get_season_autumn(self):
        """Test autumn season detection."""
        for month in [9, 10, 11]:
            date = GameDate(year=1, month=month, day=15)
            assert date.get_season() == Season.AUTUMN

    def test_get_season_winter(self):
        """Test winter season detection."""
        for month in [12, 1, 2]:
            date = GameDate(year=1, month=month, day=15)
            assert date.get_season() == Season.WINTER

    def test_str_representation(self):
        """Test string representation using Dolmenwood calendar format."""
        date = GameDate(year=1, month=6, day=15)
        date_str = str(date)
        # New format: "15 Greenmont, Year 1"
        assert "Year 1" in date_str
        assert "Greenmont" in date_str  # Month 6 is Greenmont
        assert "15" in date_str


class TestGameTime:
    """Tests for GameTime class."""

    def test_create_game_time(self):
        """Test creating a game time."""
        time = GameTime(hour=10, minute=30)
        assert time.hour == 10
        assert time.minute == 30

    def test_advance_turns_simple(self):
        """Test advancing time by turns."""
        time = GameTime(hour=10, minute=0)
        new_time, days = time.advance_turns(3)  # 30 minutes
        assert new_time.hour == 10
        assert new_time.minute == 30
        assert days == 0

    def test_advance_turns_hour_rollover(self):
        """Test advancing time across hour boundary."""
        time = GameTime(hour=10, minute=50)
        new_time, days = time.advance_turns(2)  # 20 minutes
        assert new_time.hour == 11
        assert new_time.minute == 10
        assert days == 0

    def test_advance_turns_day_rollover(self):
        """Test advancing time across day boundary."""
        time = GameTime(hour=23, minute=30)
        new_time, days = time.advance_turns(6)  # 1 hour
        assert new_time.hour == 0
        assert new_time.minute == 30
        assert days == 1

    def test_advance_hours(self):
        """Test advancing time by hours."""
        time = GameTime(hour=10, minute=0)
        new_time, days = time.advance_hours(4)
        assert new_time.hour == 14
        assert new_time.minute == 0
        assert days == 0

    def test_advance_watch(self):
        """Test advancing time by one watch."""
        time = GameTime(hour=8, minute=0)
        new_time, days = time.advance_watch()
        assert new_time.hour == 12
        assert new_time.minute == 0
        assert days == 0

    def test_get_time_of_day_dawn(self):
        """Test dawn detection."""
        time = GameTime(hour=6, minute=0)
        assert time.get_time_of_day() == TimeOfDay.DAWN

    def test_get_time_of_day_morning(self):
        """Test morning detection."""
        time = GameTime(hour=9, minute=0)
        assert time.get_time_of_day() == TimeOfDay.MORNING

    def test_get_time_of_day_midday(self):
        """Test midday detection."""
        time = GameTime(hour=12, minute=0)
        assert time.get_time_of_day() == TimeOfDay.MIDDAY

    def test_get_time_of_day_evening(self):
        """Test evening detection."""
        time = GameTime(hour=20, minute=0)
        assert time.get_time_of_day() == TimeOfDay.EVENING

    def test_get_time_of_day_midnight(self):
        """Test midnight detection."""
        time = GameTime(hour=0, minute=0)
        assert time.get_time_of_day() == TimeOfDay.MIDNIGHT

    def test_get_current_watch(self):
        """Test watch period detection."""
        test_cases = [
            (2, WatchPeriod.FIRST_WATCH),
            (6, WatchPeriod.SECOND_WATCH),
            (10, WatchPeriod.THIRD_WATCH),
            (14, WatchPeriod.FOURTH_WATCH),
            (18, WatchPeriod.FIFTH_WATCH),
            (22, WatchPeriod.SIXTH_WATCH),
        ]
        for hour, expected_watch in test_cases:
            time = GameTime(hour=hour, minute=0)
            assert time.get_current_watch() == expected_watch

    def test_is_daylight(self):
        """Test daylight detection."""
        # Daylight hours
        for hour in [6, 10, 14, 18, 19]:
            time = GameTime(hour=hour, minute=0)
            assert time.is_daylight() == (6 <= hour < 20)

        # Night hours
        for hour in [0, 2, 4, 20, 22]:
            time = GameTime(hour=hour, minute=0)
            assert time.is_daylight() is False


class TestCharacterState:
    """Tests for CharacterState class."""

    def test_create_character(self, sample_fighter):
        """Test creating a character."""
        assert sample_fighter.name == "Aldric the Bold"
        assert sample_fighter.character_class == "Fighter"
        assert sample_fighter.level == 3
        assert sample_fighter.hp_current == 24
        assert sample_fighter.hp_max == 24

    def test_ability_modifier_high(self):
        """Test ability modifier for high scores."""
        character = CharacterState(
            character_id="test",
            name="Test",
            character_class="Fighter",
            level=1,
            ability_scores={"STR": 18, "INT": 10, "WIS": 10, "DEX": 10, "CON": 10, "CHA": 10},
            hp_current=10,
            hp_max=10,
            armor_class=9,
            base_speed=40,
        )
        assert character.get_ability_modifier("STR") == 3

    def test_ability_modifier_low(self):
        """Test ability modifier for low scores."""
        character = CharacterState(
            character_id="test",
            name="Test",
            character_class="Fighter",
            level=1,
            ability_scores={"STR": 5, "INT": 10, "WIS": 10, "DEX": 10, "CON": 10, "CHA": 10},
            hp_current=10,
            hp_max=10,
            armor_class=9,
            base_speed=40,
        )
        assert character.get_ability_modifier("STR") == -2

    def test_ability_modifier_average(self):
        """Test ability modifier for average scores."""
        character = CharacterState(
            character_id="test",
            name="Test",
            character_class="Fighter",
            level=1,
            ability_scores={"STR": 10, "INT": 10, "WIS": 10, "DEX": 10, "CON": 10, "CHA": 10},
            hp_current=10,
            hp_max=10,
            armor_class=9,
            base_speed=40,
        )
        assert character.get_ability_modifier("STR") == 0

    def test_is_alive_healthy(self, sample_fighter):
        """Test is_alive for healthy character."""
        assert sample_fighter.is_alive() is True

    def test_is_alive_zero_hp(self, sample_fighter):
        """Test is_alive at 0 HP - character is not alive at 0 HP."""
        sample_fighter.hp_current = 0
        # At 0 HP, character is not alive (implementation checks hp_current > 0)
        assert sample_fighter.is_alive() is False

    def test_is_alive_dead_condition(self, sample_fighter):
        """Test is_alive with DEAD condition."""
        sample_fighter.conditions.append(Condition(ConditionType.DEAD))
        assert sample_fighter.is_alive() is False

    def test_is_conscious_healthy(self, sample_fighter):
        """Test is_conscious for healthy character."""
        assert sample_fighter.is_conscious() is True

    def test_is_conscious_unconscious(self, sample_fighter):
        """Test is_conscious when unconscious."""
        sample_fighter.conditions.append(Condition(ConditionType.UNCONSCIOUS))
        assert sample_fighter.is_conscious() is False

    def test_calculate_encumbrance(self):
        """Test encumbrance calculation."""
        from src.data_models import Item

        character = CharacterState(
            character_id="test",
            name="Test",
            character_class="Fighter",
            level=1,
            ability_scores={"STR": 10, "INT": 10, "WIS": 10, "DEX": 10, "CON": 10, "CHA": 10},
            hp_current=10,
            hp_max=10,
            armor_class=9,
            base_speed=40,
            inventory=[
                Item(item_id="sword", name="Sword", weight=50, quantity=1),
                Item(item_id="shield", name="Shield", weight=100, quantity=1),
                Item(item_id="rations", name="Rations", weight=10, quantity=7),
            ],
        )
        assert character.calculate_encumbrance() == 50 + 100 + 70


class TestCondition:
    """Tests for Condition class."""

    def test_condition_tick_permanent(self):
        """Test ticking a permanent condition."""
        condition = Condition(ConditionType.CURSED, duration_turns=None)
        expired = condition.tick()
        assert expired is False

    def test_condition_tick_temporary(self):
        """Test ticking a temporary condition."""
        condition = Condition(ConditionType.CHARMED, duration_turns=3)
        assert condition.tick() is False
        assert condition.duration_turns == 2
        assert condition.tick() is False
        assert condition.duration_turns == 1
        assert condition.tick() is True  # Expired


class TestPartyResources:
    """Tests for PartyResources class."""

    def test_consume_food_sufficient(self):
        """Test consuming food when there's enough."""
        resources = PartyResources(food_days=10)
        result = resources.consume_food(1, party_size=3)
        assert result is True
        assert resources.food_days == 7  # 10 - 3

    def test_consume_food_insufficient(self):
        """Test consuming food when there's not enough."""
        resources = PartyResources(food_days=2)
        result = resources.consume_food(1, party_size=3)
        assert result is False  # Not enough
        assert resources.food_days == -1  # Went negative


class TestStatBlock:
    """Tests for StatBlock class."""

    def test_create_stat_block(self, goblin_stat_block):
        """Test creating a stat block."""
        assert goblin_stat_block.armor_class == 6
        assert goblin_stat_block.hp_current == 4
        assert goblin_stat_block.morale == 7
        assert len(goblin_stat_block.attacks) == 1


class TestMonster:
    """Tests for Monster class."""

    def test_create_monster(self):
        """Test creating a monster."""
        goblin = Monster(
            name="Goblin",
            monster_id="goblin",
            armor_class=6,
            hit_dice="1d8-1",
            hp=4,
            level=1,
            morale=7,
            attacks=["Short Sword +0"],
            damage=["1d6"],
        )
        assert goblin.name == "Goblin"
        assert goblin.armor_class == 6
        assert goblin.morale == 7

    def test_get_saves(self):
        """Test getting monster saves."""
        goblin = Monster(
            name="Goblin",
            monster_id="goblin",
            save_doom=14,
            save_ray=15,
            save_hold=16,
            save_blast=17,
            save_spell=18,
        )
        saves = goblin.get_saves()
        assert saves.doom == 14
        assert saves.ray == 15
        assert saves.spell == 18

    def test_to_stat_block(self):
        """Test converting monster to stat block."""
        goblin = Monster(
            name="Goblin",
            monster_id="goblin",
            armor_class=6,
            hit_dice="1d8-1",
            hp=4,
            level=1,
            morale=7,
            speed=60,
            attacks=["Short Sword"],
            damage=["1d6"],
        )
        stat_block = goblin.to_stat_block()
        assert stat_block.armor_class == 6
        assert stat_block.hp_current == 4
        assert stat_block.movement == 60
        assert stat_block.morale == 7


class TestHexLocation:
    """Tests for HexLocation class."""

    def test_create_hex(self, forest_hex):
        """Test creating a hex location."""
        assert forest_hex.hex_id == "0709"
        assert forest_hex.terrain_type == "forest"
        assert forest_hex.name == "The Whispering Glade"

    def test_coordinates_from_hex_id(self):
        """Test automatic coordinate parsing from hex ID."""
        hex_loc = HexLocation(hex_id="0709")
        assert hex_loc.coordinates == (7, 9)

    def test_terrain_sync(self):
        """Test terrain field synchronization."""
        hex_loc = HexLocation(hex_id="0101", terrain_type="moor")
        assert hex_loc.terrain == "moor"

    def test_tagline_sync(self):
        """Test tagline/flavour_text synchronization."""
        hex_loc = HexLocation(hex_id="0101", tagline="A foggy moor")
        assert hex_loc.flavour_text == "A foggy moor"


class TestLocationState:
    """Tests for LocationState class."""

    def test_create_location_state(self, dungeon_room):
        """Test creating a location state."""
        assert dungeon_room.location_type == LocationType.DUNGEON_ROOM
        assert dungeon_room.location_id == "room_1"
        assert dungeon_room.light_level == "dark"

    def test_settlement_location(self, settlement):
        """Test settlement-specific fields."""
        assert settlement.population == 350
        assert "Inn" in settlement.buildings
        assert "Rest" in settlement.services
