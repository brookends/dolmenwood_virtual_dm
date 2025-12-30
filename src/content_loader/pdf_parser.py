"""
PDF Parser for Dolmenwood Virtual DM.

Parses content from Dolmenwood rulebooks (Player's Book, Campaign Book, Monster Book).
Extracts structured data including hex descriptions, NPC profiles, monster statistics,
and rules text.

Note: This parser is designed to work with the official Dolmenwood book format.
Actual PDF parsing requires PyMuPDF (fitz) or pdfplumber packages.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Generator, Optional
import logging

from src.data_models import (
    SourceType,
    ContentSource,
    SourceReference,
    HexLocation,
    NPC,
    StatBlock,
    Feature,
    Lair,
    Landmark,
    Season,
)


logger = logging.getLogger(__name__)


class BookType(str, Enum):
    """Types of Dolmenwood books."""

    PLAYERS_BOOK = "players_book"
    CAMPAIGN_BOOK = "campaign_book"
    MONSTER_BOOK = "monster_book"


@dataclass
class ParsedPage:
    """A parsed page from a PDF."""

    page_number: int
    text: str
    sections: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ParsedSection:
    """A parsed section from a book."""

    title: str
    content: str
    page_start: int
    page_end: int
    subsections: list["ParsedSection"] = field(default_factory=list)
    section_type: str = "general"


@dataclass
class ParseResult:
    """Result of parsing a PDF."""

    success: bool
    source: ContentSource
    pages: list[ParsedPage] = field(default_factory=list)
    sections: list[ParsedSection] = field(default_factory=list)
    hexes: list[HexLocation] = field(default_factory=list)
    npcs: list[NPC] = field(default_factory=list)
    monsters: list[dict[str, Any]] = field(default_factory=list)
    rules: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class PDFParser:
    """
    Parser for Dolmenwood PDF rulebooks.

    Extracts structured content from:
    - Player's Book: Character options, spells, equipment, rules
    - Campaign Book: Hexes, settlements, NPCs, factions
    - Monster Book: Monster statistics and descriptions

    The parser uses regex patterns to identify and extract specific
    content types based on the formatting conventions in the books.
    """

    # Regex patterns for content extraction
    PATTERNS = {
        # Hex header: e.g., "0709 The Witch's Knoll"
        "hex_header": re.compile(r"^(\d{4})\s+(.+)$", re.MULTILINE),
        # NPC name with title: e.g., "Lady Harrowmoor, Baroness of..."
        "npc_header": re.compile(r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s*(.+)?$", re.MULTILINE),
        # Monster header: e.g., "Woodgrue" or "WOODGRUE"
        "monster_header": re.compile(r"^([A-Z][A-Z\s]+)$", re.MULTILINE),
        # Stat block patterns
        "armor_class": re.compile(r"AC[:\s]+(\d+)", re.IGNORECASE),
        "hit_dice": re.compile(r"HD[:\s]+(\d+d\d+(?:[+-]\d+)?|\d+)", re.IGNORECASE),
        "hit_points": re.compile(r"HP[:\s]+(\d+)", re.IGNORECASE),
        "movement": re.compile(r"MV[:\s]+(\d+)", re.IGNORECASE),
        "morale": re.compile(r"ML[:\s]+(\d+)", re.IGNORECASE),
        "attacks": re.compile(r"Att?[:\s]+(.+?)(?=\n|$)", re.IGNORECASE),
        "damage": re.compile(r"Dmg?[:\s]+(.+?)(?=\n|$)", re.IGNORECASE),
        "save": re.compile(r"Save[:\s]+(.+?)(?=\n|$)", re.IGNORECASE),
        # Section headers
        "chapter": re.compile(r"^Chapter\s+(\d+)[:\s]+(.+)$", re.MULTILINE | re.IGNORECASE),
        "section": re.compile(r"^#{1,3}\s+(.+)$", re.MULTILINE),
        # Table patterns
        "table_header": re.compile(r"^Table\s+(\d+)[:\s]+(.+)$", re.MULTILINE | re.IGNORECASE),
        # Terrain types
        "terrain": re.compile(
            r"\b(forest|deep forest|moor|swamp|hills?|mountains?|river|lake|road|trail|farmland)\b",
            re.IGNORECASE,
        ),
        # Fairy/Drune markers
        "fairy": re.compile(r"\b(fairy|fae|faerie|enchanted|glamour)\b", re.IGNORECASE),
        "drune": re.compile(r"\b(drune|stone|standing stone|dolmen|menhir)\b", re.IGNORECASE),
    }

    def __init__(self):
        """Initialize the PDF parser."""
        self._pdf_lib_available = self._check_pdf_library()

    def _check_pdf_library(self) -> bool:
        """Check if PDF parsing libraries are available."""
        try:
            import fitz  # PyMuPDF

            return True
        except ImportError:
            pass

        try:
            import pdfplumber

            return True
        except ImportError:
            pass

        logger.warning("No PDF parsing library available (install PyMuPDF or pdfplumber)")
        return False

    def parse_pdf(self, file_path: Path, book_type: BookType, version: str = "1.0") -> ParseResult:
        """
        Parse a Dolmenwood PDF rulebook.

        Args:
            file_path: Path to the PDF file
            book_type: Type of book being parsed
            version: Version string for the content

        Returns:
            ParseResult with extracted content
        """
        if not file_path.exists():
            return ParseResult(
                success=False,
                source=self._create_source(file_path, book_type, version),
                errors=[f"File not found: {file_path}"],
            )

        source = self._create_source(file_path, book_type, version)

        if not self._pdf_lib_available:
            # Return a result that indicates PDF parsing isn't available
            # but include the source registration
            return ParseResult(
                success=False,
                source=source,
                errors=["PDF parsing libraries not available. Install PyMuPDF or pdfplumber."],
            )

        try:
            # Extract pages
            pages = self._extract_pages(file_path)

            result = ParseResult(
                success=True,
                source=source,
                pages=pages,
            )

            # Parse based on book type
            if book_type == BookType.CAMPAIGN_BOOK:
                result.hexes = self._parse_hexes(pages)
                result.npcs = self._parse_npcs(pages)
                result.sections = self._parse_sections(pages)

            elif book_type == BookType.MONSTER_BOOK:
                result.monsters = self._parse_monsters(pages)

            elif book_type == BookType.PLAYERS_BOOK:
                result.rules = self._parse_rules(pages)
                result.tables = self._parse_tables(pages)

            return result

        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            return ParseResult(success=False, source=source, errors=[str(e)])

    def _create_source(self, file_path: Path, book_type: BookType, version: str) -> ContentSource:
        """Create a ContentSource for the parsed book."""
        book_names = {
            BookType.PLAYERS_BOOK: "Dolmenwood Player's Book",
            BookType.CAMPAIGN_BOOK: "Dolmenwood Campaign Book",
            BookType.MONSTER_BOOK: "Dolmenwood Monster Book",
        }

        # Calculate file hash if file exists
        file_hash = None
        page_count = None
        if file_path.exists():
            import hashlib

            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            file_hash = sha256_hash.hexdigest()

        return ContentSource(
            source_id=f"dolmenwood_{book_type.value}_{version}",
            source_type=SourceType.CORE_RULEBOOK,
            book_name=book_names.get(book_type, "Unknown Book"),
            book_code=book_type.value,
            version=version,
            file_path=str(file_path),
            file_hash=file_hash,
            page_count=page_count,
            imported_at=datetime.now(),
        )

    def _extract_pages(self, file_path: Path) -> list[ParsedPage]:
        """Extract text from all pages of the PDF."""
        pages = []

        try:
            import fitz  # PyMuPDF

            doc = fitz.open(str(file_path))
            for page_num, page in enumerate(doc, start=1):
                text = page.get_text()
                pages.append(
                    ParsedPage(
                        page_number=page_num,
                        text=text,
                    )
                )
            doc.close()

        except ImportError:
            try:
                import pdfplumber

                with pdfplumber.open(file_path) as pdf:
                    for page_num, page in enumerate(pdf.pages, start=1):
                        text = page.extract_text() or ""
                        pages.append(
                            ParsedPage(
                                page_number=page_num,
                                text=text,
                            )
                        )

            except ImportError:
                logger.error("No PDF library available")

        return pages

    def _parse_hexes(self, pages: list[ParsedPage]) -> list[HexLocation]:
        """Parse hex locations from Campaign Book pages."""
        hexes = []
        full_text = "\n".join(page.text for page in pages)

        # Find all hex headers
        for match in self.PATTERNS["hex_header"].finditer(full_text):
            hex_id = match.group(1)
            name = match.group(2).strip()

            # Get the content following this hex until the next hex
            start_pos = match.end()
            next_match = self.PATTERNS["hex_header"].search(full_text, start_pos)
            end_pos = next_match.start() if next_match else len(full_text)

            content = full_text[start_pos:end_pos].strip()

            # Parse hex details
            hex_loc = self._parse_hex_content(hex_id, name, content)
            if hex_loc:
                hexes.append(hex_loc)

        return hexes

    def _parse_hex_content(self, hex_id: str, name: str, content: str) -> Optional[HexLocation]:
        """Parse the content of a hex description."""
        # Determine terrain
        terrain = "forest"  # Default
        terrain_match = self.PATTERNS["terrain"].search(content)
        if terrain_match:
            terrain = terrain_match.group(1).lower()

        # Check for fairy influence
        fairy_influence = None
        if self.PATTERNS["fairy"].search(content):
            fairy_influence = "Present"

        # Check for Drune presence
        drune_presence = bool(self.PATTERNS["drune"].search(content))

        # Extract features (simplified - would need more sophisticated parsing)
        features = []
        landmarks = []
        lairs = []

        # Look for numbered or bulleted items as features
        feature_pattern = re.compile(r"(?:^|\n)[\d•\-\*]+\.?\s*([A-Z][^.]+\.)", re.MULTILINE)
        for i, match in enumerate(feature_pattern.finditer(content)):
            features.append(
                Feature(
                    feature_id=f"{hex_id}_feature_{i+1}",
                    name=f"Feature {i+1}",
                    description=match.group(1).strip(),
                )
            )

        return HexLocation(
            hex_id=hex_id,
            terrain=terrain,
            name=name if name else None,
            description=content[:500] if content else "",  # Truncate for storage
            features=features,
            lairs=lairs,
            landmarks=landmarks,
            fairy_influence=fairy_influence,
            drune_presence=drune_presence,
        )

    def _parse_npcs(self, pages: list[ParsedPage]) -> list[NPC]:
        """Parse NPC profiles from Campaign Book pages."""
        npcs = []
        # NPC parsing would require more sophisticated pattern matching
        # based on the actual book format
        return npcs

    def _parse_monsters(self, pages: list[ParsedPage]) -> list[dict[str, Any]]:
        """Parse monster entries from Monster Book pages."""
        monsters = []
        full_text = "\n".join(page.text for page in pages)

        # Find monster headers (all caps names)
        for match in self.PATTERNS["monster_header"].finditer(full_text):
            monster_name = match.group(1).strip().title()

            # Get content following this monster
            start_pos = match.end()
            next_match = self.PATTERNS["monster_header"].search(full_text, start_pos)
            end_pos = next_match.start() if next_match else min(start_pos + 2000, len(full_text))

            content = full_text[start_pos:end_pos].strip()

            # Parse stat block
            monster_data = self._parse_monster_stats(monster_name, content)
            if monster_data:
                monsters.append(monster_data)

        return monsters

    def _parse_monster_stats(self, name: str, content: str) -> Optional[dict[str, Any]]:
        """Parse monster statistics from content block."""
        monster = {
            "monster_id": name.lower().replace(" ", "_"),
            "name": name,
            "description": "",
            "stat_block": {},
        }

        # Extract stat block values
        ac_match = self.PATTERNS["armor_class"].search(content)
        if ac_match:
            monster["stat_block"]["armor_class"] = int(ac_match.group(1))

        hd_match = self.PATTERNS["hit_dice"].search(content)
        if hd_match:
            monster["stat_block"]["hit_dice"] = hd_match.group(1)

        hp_match = self.PATTERNS["hit_points"].search(content)
        if hp_match:
            monster["stat_block"]["hp_max"] = int(hp_match.group(1))
            monster["stat_block"]["hp_current"] = int(hp_match.group(1))

        mv_match = self.PATTERNS["movement"].search(content)
        if mv_match:
            monster["stat_block"]["movement"] = int(mv_match.group(1))

        ml_match = self.PATTERNS["morale"].search(content)
        if ml_match:
            monster["stat_block"]["morale"] = int(ml_match.group(1))

        att_match = self.PATTERNS["attacks"].search(content)
        if att_match:
            monster["stat_block"]["attacks"] = [
                {"name": "Attack", "description": att_match.group(1).strip()}
            ]

        save_match = self.PATTERNS["save"].search(content)
        if save_match:
            monster["stat_block"]["save_as"] = save_match.group(1).strip()

        # Get description (first paragraph after stats)
        lines = content.split("\n")
        desc_lines = []
        in_stats = True
        for line in lines:
            if not line.strip():
                in_stats = False
                continue
            if not in_stats and line.strip():
                desc_lines.append(line.strip())
                if len(" ".join(desc_lines)) > 200:
                    break

        monster["description"] = " ".join(desc_lines)

        # Only return if we found at least some stats
        if monster["stat_block"]:
            return monster
        return None

    def _parse_rules(self, pages: list[ParsedPage]) -> list[dict[str, Any]]:
        """Parse rules sections from Player's Book."""
        rules = []
        # Would parse chapter headings and rule text
        return rules

    def _parse_tables(self, pages: list[ParsedPage]) -> list[dict[str, Any]]:
        """Parse tables from the books."""
        tables = []
        full_text = "\n".join(page.text for page in pages)

        for match in self.PATTERNS["table_header"].finditer(full_text):
            table_num = match.group(1)
            table_name = match.group(2).strip()

            tables.append(
                {
                    "table_id": f"table_{table_num}",
                    "name": table_name,
                    "entries": [],  # Would need to parse table contents
                }
            )

        return tables

    def _parse_sections(self, pages: list[ParsedPage]) -> list[ParsedSection]:
        """Parse major sections from pages."""
        sections = []
        full_text = "\n".join(page.text for page in pages)

        for match in self.PATTERNS["chapter"].finditer(full_text):
            chapter_num = match.group(1)
            chapter_name = match.group(2).strip()

            sections.append(
                ParsedSection(
                    title=f"Chapter {chapter_num}: {chapter_name}",
                    content="",  # Would extract chapter content
                    page_start=0,
                    page_end=0,
                    section_type="chapter",
                )
            )

        return sections


class TextParser:
    """
    Parser for plain text or markdown content.

    Used for manually transcribed or cleaned-up content that doesn't
    require PDF parsing.
    """

    def __init__(self):
        """Initialize the text parser."""
        pass

    def parse_hex_file(self, file_path: Path) -> list[HexLocation]:
        """
        Parse hex data from a JSON or text file.

        Expected JSON format:
        {
            "hexes": [
                {
                    "hex_id": "0709",
                    "name": "The Witch's Knoll",
                    "terrain": "forest",
                    "description": "...",
                    "features": [...],
                    "lairs": [...],
                    "landmarks": [...]
                }
            ]
        }
        """
        import json

        hexes = []

        with open(file_path, "r") as f:
            data = json.load(f)

        for hex_data in data.get("hexes", []):
            hex_loc = HexLocation(
                hex_id=hex_data["hex_id"],
                terrain=hex_data.get("terrain", "forest"),
                name=hex_data.get("name"),
                description=hex_data.get("description", ""),
                features=[
                    Feature(
                        feature_id=f.get("feature_id", f"{hex_data['hex_id']}_f_{i}"),
                        name=f.get("name", f"Feature {i+1}"),
                        description=f.get("description", ""),
                        searchable=f.get("searchable", False),
                        hidden=f.get("hidden", False),
                    )
                    for i, f in enumerate(hex_data.get("features", []))
                ],
                lairs=[
                    Lair(
                        lair_id=l.get("lair_id", f"{hex_data['hex_id']}_l_{i}"),
                        monster_type=l.get("monster_type", "Unknown"),
                        monster_count=l.get("monster_count", "1d6"),
                        treasure_type=l.get("treasure_type"),
                    )
                    for i, l in enumerate(hex_data.get("lairs", []))
                ],
                landmarks=[
                    Landmark(
                        landmark_id=lm.get("landmark_id", f"{hex_data['hex_id']}_lm_{i}"),
                        name=lm.get("name", f"Landmark {i+1}"),
                        description=lm.get("description", ""),
                        visible_from_adjacent=lm.get("visible_from_adjacent", True),
                    )
                    for i, lm in enumerate(hex_data.get("landmarks", []))
                ],
                fairy_influence=hex_data.get("fairy_influence"),
                drune_presence=hex_data.get("drune_presence", False),
                seasonal_variations={
                    Season(k): v for k, v in hex_data.get("seasonal_variations", {}).items()
                },
                encounter_table=hex_data.get("encounter_table"),
                adjacent_hexes=hex_data.get("adjacent_hexes", {}),
                roads=hex_data.get("roads", []),
                rivers=hex_data.get("rivers", []),
            )
            hexes.append(hex_loc)

        return hexes

    def parse_npc_file(self, file_path: Path) -> list[NPC]:
        """
        Parse NPC data from a JSON file.

        Expected JSON format:
        {
            "npcs": [
                {
                    "npc_id": "lady_harrowmoor",
                    "name": "Lady Harrowmoor",
                    "title": "Baroness of Harrowmoor",
                    "location": "Castle Harrowmoor",
                    "faction": "High Wold Nobility",
                    "personality": "Cold and calculating",
                    "goals": ["Expand territory", "Find the lost heir"],
                    "secrets": ["Is actually a changeling"],
                    "dialogue_hooks": ["Speaks of the old days"],
                    "relationships": {"Lord Blackwood": "Rival"}
                }
            ]
        }
        """
        import json

        npcs = []

        with open(file_path, "r") as f:
            data = json.load(f)

        for npc_data in data.get("npcs", []):
            stat_block = None
            if npc_data.get("stat_block"):
                sb = npc_data["stat_block"]
                stat_block = StatBlock(
                    armor_class=sb.get("armor_class", 9),
                    hit_dice=sb.get("hit_dice", "1d8"),
                    hp_current=sb.get("hp_current", 4),
                    hp_max=sb.get("hp_max", 4),
                    movement=sb.get("movement", 120),
                    attacks=sb.get("attacks", []),
                    morale=sb.get("morale", 7),
                    save_as=sb.get("save_as", ""),
                    special_abilities=sb.get("special_abilities", []),
                )

            npc = NPC(
                npc_id=npc_data["npc_id"],
                name=npc_data["name"],
                title=npc_data.get("title"),
                location=npc_data.get("location", ""),
                faction=npc_data.get("faction"),
                personality=npc_data.get("personality", ""),
                goals=npc_data.get("goals", []),
                secrets=npc_data.get("secrets", []),
                stat_block=stat_block,
                dialogue_hooks=npc_data.get("dialogue_hooks", []),
                relationships=npc_data.get("relationships", {}),
                disposition=npc_data.get("disposition", 0),
            )
            npcs.append(npc)

        return npcs

    def parse_monster_file(self, file_path: Path) -> list[dict[str, Any]]:
        """Parse monster data from a JSON file."""
        import json

        with open(file_path, "r") as f:
            data = json.load(f)

        return data.get("monsters", [])
