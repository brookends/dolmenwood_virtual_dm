"""
Faction effects interpreter.

Executes effect commands when faction actions complete.
Supports:
- Territory changes (claim_territory, cede_territory)
- Flag manipulation (set_flag, clear_flag)
- Rumor generation (add_rumor)
- Modifier application (apply_modifier_next_turn)
- Standing changes (adjust_standing)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from src.factions.faction_models import (
        EffectCommand,
        FactionTurnState,
        PartyFactionState,
    )

logger = logging.getLogger(__name__)


@dataclass
class EffectResult:
    """Result of applying an effect."""
    success: bool
    effect_type: str
    description: str
    changes: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class FactionEffectsInterpreter:
    """
    Interprets and applies effect commands to faction state.

    All effects are deterministic - they mutate state in a predictable way
    without any RNG. If RNG is needed for an effect, it should be resolved
    by the FactionEngine before calling the interpreter.
    """

    def __init__(self):
        """Initialize the interpreter."""
        # Registry of effect handlers
        self._handlers: dict[str, Any] = {
            "claim_territory": self._handle_claim_territory,
            "cede_territory": self._handle_cede_territory,
            "set_flag": self._handle_set_flag,
            "clear_flag": self._handle_clear_flag,
            "add_rumor": self._handle_add_rumor,
            "apply_modifier_next_turn": self._handle_apply_modifier,
            "adjust_standing": self._handle_adjust_standing,
            "log_news": self._handle_log_news,
            "complete_goal": self._handle_complete_goal,
        }

        # Persistent flags across factions (global game state)
        self._global_flags: dict[str, Any] = {}
        # Pending rumors to be delivered
        self._pending_rumors: list[dict[str, Any]] = []

    @property
    def global_flags(self) -> dict[str, Any]:
        """Get all global flags."""
        return self._global_flags.copy()

    @property
    def pending_rumors(self) -> list[dict[str, Any]]:
        """Get pending rumors."""
        return list(self._pending_rumors)

    def clear_pending_rumors(self) -> list[dict[str, Any]]:
        """Clear and return pending rumors."""
        rumors = self._pending_rumors
        self._pending_rumors = []
        return rumors

    def set_global_flags(self, flags: dict[str, Any]) -> None:
        """Restore global flags from persistence."""
        self._global_flags = flags.copy()

    def apply_effect(
        self,
        effect: "EffectCommand",
        faction_state: "FactionTurnState",
        party_state: Optional["PartyFactionState"] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> EffectResult:
        """
        Apply a single effect command.

        Args:
            effect: The effect to apply
            faction_state: The faction's current state (mutable)
            party_state: The party's faction state (mutable, optional)
            context: Additional context (e.g., current date, affected factions)

        Returns:
            EffectResult describing what happened
        """
        handler = self._handlers.get(effect.type)
        if not handler:
            logger.warning(f"Unknown effect type: {effect.type}")
            return EffectResult(
                success=False,
                effect_type=effect.type,
                description="Unknown effect type",
                error=f"No handler for effect type: {effect.type}",
            )

        try:
            return handler(effect, faction_state, party_state, context or {})
        except Exception as e:
            logger.error(f"Error applying effect {effect.type}: {e}")
            return EffectResult(
                success=False,
                effect_type=effect.type,
                description=f"Error: {e}",
                error=str(e),
            )

    def apply_effects(
        self,
        effects: list["EffectCommand"],
        faction_state: "FactionTurnState",
        party_state: Optional["PartyFactionState"] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> list[EffectResult]:
        """
        Apply multiple effects in order.

        Args:
            effects: List of effects to apply
            faction_state: The faction's current state (mutable)
            party_state: The party's faction state (mutable, optional)
            context: Additional context

        Returns:
            List of EffectResult objects
        """
        results = []
        for effect in effects:
            result = self.apply_effect(effect, faction_state, party_state, context)
            results.append(result)
        return results

    # =========================================================================
    # EFFECT HANDLERS
    # =========================================================================

    def _handle_claim_territory(
        self,
        effect: "EffectCommand",
        faction_state: "FactionTurnState",
        party_state: Optional["PartyFactionState"],
        context: dict[str, Any],
    ) -> EffectResult:
        """
        Claim territory for the faction.

        If territory is already held by another faction, uses oracle fate check
        to adjudicate the contest. The losing faction loses the territory.

        Data fields:
        - hex: Hex ID to claim
        - settlement: Settlement ID to claim
        - stronghold: Stronghold ID to claim
        - domain: Domain ID to claim
        """
        changes = {}
        descriptions = []
        oracle_events = []

        # Get context for contested territory checks
        oracle = context.get("oracle")
        all_faction_states = context.get("all_faction_states", {})
        faction_definitions = context.get("faction_definitions", {})
        relations = context.get("relations")
        rules = context.get("rules")
        date = context.get("date", "")
        attacker_id = faction_state.faction_id

        def get_faction_level(fid: str) -> int:
            """Get faction level from territory points."""
            if not rules:
                return 1
            fstate = all_faction_states.get(fid)
            if not fstate:
                return 1
            points = fstate.territory.compute_points(rules.territory_point_values)
            return rules.get_level_for_points(points)

        def get_relationship(fid1: str, fid2: str) -> int:
            """Get relationship score between factions."""
            if not relations:
                return 0
            return relations.get_relation(fid1, fid2)

        def find_current_holder(territory_type: str, territory_id: str) -> Optional[str]:
            """Find which faction currently holds a territory."""
            for fid, fstate in all_faction_states.items():
                if fid == attacker_id:
                    continue
                territory = fstate.territory
                if territory_type == "hex" and territory_id in territory.hexes:
                    return fid
                if territory_type == "settlement" and territory_id in territory.settlements:
                    return fid
                if territory_type == "stronghold" and territory_id in territory.strongholds:
                    return fid
                if territory_type == "domain" and territory_id in territory.domains:
                    return fid
            return None

        def resolve_contest(territory_type: str, territory_id: str, defender_id: str) -> bool:
            """
            Resolve a contested territory claim via oracle fate check.

            Returns True if attacker wins, False if defender keeps territory.
            """
            if not oracle or not oracle.config.enabled or not oracle.config.contested_territory_enabled:
                # Without oracle, attacker wins by default
                return True

            attacker_level = get_faction_level(attacker_id)
            defender_level = get_faction_level(defender_id)
            relationship = get_relationship(attacker_id, defender_id)

            likelihood = oracle.determine_contest_likelihood(
                attacker_level=attacker_level,
                defender_level=defender_level,
                relationship_score=relationship,
            )

            question = f"Does {attacker_id} successfully claim {territory_type} {territory_id} from {defender_id}?"

            fate_event = oracle.fate_check(
                question=question,
                likelihood=likelihood,
                date=date,
                faction_id=attacker_id,
                tag="contested_territory",
            )

            oracle_events.append(fate_event)
            return oracle.is_yes(fate_event)

        def claim_territory_item(territory_type: str, territory_id: str) -> bool:
            """Attempt to claim a single territory item. Returns True if successful."""
            defender_id = find_current_holder(territory_type, territory_id)

            if defender_id:
                # Contested - resolve via oracle
                attacker_wins = resolve_contest(territory_type, territory_id, defender_id)

                if attacker_wins:
                    # Remove from defender
                    defender_state = all_faction_states.get(defender_id)
                    if defender_state:
                        if territory_type == "hex":
                            defender_state.territory.hexes.discard(territory_id)
                        elif territory_type == "settlement":
                            defender_state.territory.settlements.discard(territory_id)
                        elif territory_type == "stronghold":
                            defender_state.territory.strongholds.discard(territory_id)
                        elif territory_type == "domain":
                            defender_state.territory.domains.discard(territory_id)
                    return True
                else:
                    return False
            else:
                # Uncontested
                return True

        # Process each territory type
        if "hex" in effect.data:
            hex_id = effect.data["hex"]
            if claim_territory_item("hex", hex_id):
                faction_state.territory.hexes.add(hex_id)
                changes["hex_added"] = hex_id
                descriptions.append(f"claimed hex {hex_id}")
            else:
                descriptions.append(f"failed to claim hex {hex_id} (contested)")

        if "settlement" in effect.data:
            settlement_id = effect.data["settlement"]
            if claim_territory_item("settlement", settlement_id):
                faction_state.territory.settlements.add(settlement_id)
                changes["settlement_added"] = settlement_id
                descriptions.append(f"claimed settlement {settlement_id}")
            else:
                descriptions.append(f"failed to claim settlement {settlement_id} (contested)")

        if "stronghold" in effect.data:
            stronghold_id = effect.data["stronghold"]
            if claim_territory_item("stronghold", stronghold_id):
                faction_state.territory.strongholds.add(stronghold_id)
                changes["stronghold_added"] = stronghold_id
                descriptions.append(f"claimed stronghold {stronghold_id}")
            else:
                descriptions.append(f"failed to claim stronghold {stronghold_id} (contested)")

        if "domain" in effect.data:
            domain_id = effect.data["domain"]
            if claim_territory_item("domain", domain_id):
                faction_state.territory.domains.add(domain_id)
                changes["domain_added"] = domain_id
                descriptions.append(f"claimed domain {domain_id}")
            else:
                descriptions.append(f"failed to claim domain {domain_id} (contested)")

        if oracle_events:
            changes["oracle_events"] = [e.to_dict() for e in oracle_events]

        return EffectResult(
            success=True,
            effect_type="claim_territory",
            description=", ".join(descriptions) if descriptions else "no territory claimed",
            changes=changes,
        )

    def _handle_cede_territory(
        self,
        effect: "EffectCommand",
        faction_state: "FactionTurnState",
        party_state: Optional["PartyFactionState"],
        context: dict[str, Any],
    ) -> EffectResult:
        """
        Remove territory from the faction.

        Data fields:
        - hex: Hex ID to cede
        - settlement: Settlement ID to cede
        - stronghold: Stronghold ID to cede
        - domain: Domain ID to cede
        """
        changes = {}
        descriptions = []

        if "hex" in effect.data:
            hex_id = effect.data["hex"]
            faction_state.territory.hexes.discard(hex_id)
            changes["hex_removed"] = hex_id
            descriptions.append(f"ceded hex {hex_id}")

        if "settlement" in effect.data:
            settlement_id = effect.data["settlement"]
            faction_state.territory.settlements.discard(settlement_id)
            changes["settlement_removed"] = settlement_id
            descriptions.append(f"ceded settlement {settlement_id}")

        if "stronghold" in effect.data:
            stronghold_id = effect.data["stronghold"]
            faction_state.territory.strongholds.discard(stronghold_id)
            changes["stronghold_removed"] = stronghold_id
            descriptions.append(f"ceded stronghold {stronghold_id}")

        if "domain" in effect.data:
            domain_id = effect.data["domain"]
            faction_state.territory.domains.discard(domain_id)
            changes["domain_removed"] = domain_id
            descriptions.append(f"ceded domain {domain_id}")

        return EffectResult(
            success=True,
            effect_type="cede_territory",
            description=", ".join(descriptions) if descriptions else "no territory ceded",
            changes=changes,
        )

    def _handle_set_flag(
        self,
        effect: "EffectCommand",
        faction_state: "FactionTurnState",
        party_state: Optional["PartyFactionState"],
        context: dict[str, Any],
    ) -> EffectResult:
        """
        Set a global flag.

        Data fields:
        - flag: Flag name
        - value: Flag value (default True)
        """
        flag_name = effect.data.get("flag", "")
        flag_value = effect.data.get("value", True)

        if not flag_name:
            return EffectResult(
                success=False,
                effect_type="set_flag",
                description="Missing flag name",
                error="flag field required",
            )

        self._global_flags[flag_name] = flag_value

        return EffectResult(
            success=True,
            effect_type="set_flag",
            description=f"set flag {flag_name} = {flag_value}",
            changes={"flag": flag_name, "value": flag_value},
        )

    def _handle_clear_flag(
        self,
        effect: "EffectCommand",
        faction_state: "FactionTurnState",
        party_state: Optional["PartyFactionState"],
        context: dict[str, Any],
    ) -> EffectResult:
        """
        Clear a global flag.

        Data fields:
        - flag: Flag name
        """
        flag_name = effect.data.get("flag", "")

        if not flag_name:
            return EffectResult(
                success=False,
                effect_type="clear_flag",
                description="Missing flag name",
                error="flag field required",
            )

        was_set = flag_name in self._global_flags
        self._global_flags.pop(flag_name, None)

        return EffectResult(
            success=True,
            effect_type="clear_flag",
            description=f"cleared flag {flag_name}" + (" (was set)" if was_set else " (was not set)"),
            changes={"flag": flag_name, "was_set": was_set},
        )

    def _handle_add_rumor(
        self,
        effect: "EffectCommand",
        faction_state: "FactionTurnState",
        party_state: Optional["PartyFactionState"],
        context: dict[str, Any],
    ) -> EffectResult:
        """
        Add a rumor to the pending rumors list.

        Data fields:
        - text: Rumor text
        - source: Source faction or location
        - veracity: "true", "partially_true", "false"
        - tags: List of tags for filtering
        """
        rumor = {
            "text": effect.data.get("text", ""),
            "source_faction": faction_state.faction_id,
            "source": effect.data.get("source", ""),
            "veracity": effect.data.get("veracity", "unknown"),
            "tags": effect.data.get("tags", []),
            "date": context.get("date", ""),
        }

        self._pending_rumors.append(rumor)

        return EffectResult(
            success=True,
            effect_type="add_rumor",
            description=f"added rumor: {rumor['text'][:50]}...",
            changes={"rumor": rumor},
        )

    def _handle_apply_modifier(
        self,
        effect: "EffectCommand",
        faction_state: "FactionTurnState",
        party_state: Optional["PartyFactionState"],
        context: dict[str, Any],
    ) -> EffectResult:
        """
        Apply a modifier for the next faction cycle.

        Data fields:
        - action_id: Target action ID (or "all")
        - modifier: Integer modifier value
        - reason: Reason for the modifier
        """
        modifier_entry = {
            "action_id": effect.data.get("action_id", "all"),
            "modifier": effect.data.get("modifier", 0),
            "reason": effect.data.get("reason", "effect applied"),
        }

        faction_state.modifiers_next_cycle.append(modifier_entry)

        return EffectResult(
            success=True,
            effect_type="apply_modifier_next_turn",
            description=f"applied modifier {modifier_entry['modifier']:+d} to {modifier_entry['action_id']}",
            changes={"modifier": modifier_entry},
        )

    def _handle_adjust_standing(
        self,
        effect: "EffectCommand",
        faction_state: "FactionTurnState",
        party_state: Optional["PartyFactionState"],
        context: dict[str, Any],
    ) -> EffectResult:
        """
        Adjust party standing with a faction.

        Data fields:
        - faction: Faction or group ID
        - delta: Integer change
        """
        if not party_state:
            return EffectResult(
                success=False,
                effect_type="adjust_standing",
                description="No party state available",
                error="party_state required",
            )

        target_faction = effect.data.get("faction", faction_state.faction_id)
        delta = effect.data.get("delta", 0)

        old_standing = party_state.get_standing(target_faction)
        new_standing = party_state.adjust_standing(target_faction, delta)

        return EffectResult(
            success=True,
            effect_type="adjust_standing",
            description=f"adjusted standing with {target_faction}: {old_standing} -> {new_standing}",
            changes={
                "faction": target_faction,
                "old_standing": old_standing,
                "new_standing": new_standing,
                "delta": delta,
            },
        )

    def _handle_log_news(
        self,
        effect: "EffectCommand",
        faction_state: "FactionTurnState",
        party_state: Optional["PartyFactionState"],
        context: dict[str, Any],
    ) -> EffectResult:
        """
        Add a news item to the faction's news log.

        Data fields:
        - text: News text
        """
        text = effect.data.get("text", "")
        date = context.get("date", "")

        if date:
            news_entry = f"[{date}] {text}"
        else:
            news_entry = text

        faction_state.news.append(news_entry)

        return EffectResult(
            success=True,
            effect_type="log_news",
            description=f"logged news: {text[:50]}...",
            changes={"news": news_entry},
        )

    def _handle_complete_goal(
        self,
        effect: "EffectCommand",
        faction_state: "FactionTurnState",
        party_state: Optional["PartyFactionState"],
        context: dict[str, Any],
    ) -> EffectResult:
        """
        Mark a goal as complete.

        Data fields:
        - goal_id: The goal ID that was completed

        Note: This is primarily for logging. Goal completion may trigger
        other game effects that are handled at a higher level.
        """
        goal_id = effect.data.get("goal_id", "")
        date = context.get("date", "")

        news_entry = f"Goal completed: {goal_id}"
        if date:
            news_entry = f"[{date}] {news_entry}"
        faction_state.news.append(news_entry)

        return EffectResult(
            success=True,
            effect_type="complete_goal",
            description=f"completed goal: {goal_id}",
            changes={"goal_id": goal_id, "date": date},
        )
