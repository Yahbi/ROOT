"""
Skill Engine — HERMES-style procedural memory for ROOT.

Skills are SKILL.md files with YAML frontmatter stored in data/skills/.
ROOT can create, improve, and invoke skills based on experience.
Skills are injected into context when relevant to a task.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from backend.config import ROOT_DIR

logger = logging.getLogger("root.skills")

SKILLS_DIR = ROOT_DIR / "data" / "skills"


@dataclass(frozen=True)
class Skill:
    """Immutable skill loaded from a SKILL.md file."""

    name: str
    category: str
    description: str
    version: str
    tags: list[str]
    content: str
    path: str
    author: str = "ROOT"
    platforms: list[str] = field(default_factory=lambda: ["darwin", "linux", "win32"])


class SkillEngine:
    """Manages ROOT's skill library — load, search, create, improve."""

    def __init__(self, skills_dir: Optional[Path] = None) -> None:
        self._dir = skills_dir or SKILLS_DIR
        self._skills: dict[str, Skill] = {}
        self._dir.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> int:
        """Scan skills directory and load all SKILL.md files."""
        self._skills.clear()
        count = 0
        for skill_file in self._dir.rglob("SKILL.md"):
            skill = self._parse_skill(skill_file)
            if skill:
                self._skills[f"{skill.category}/{skill.name}"] = skill
                count += 1
        logger.info("Loaded %d skills from %s", count, self._dir)
        return count

    def get(self, key: str) -> Optional[Skill]:
        """Get a skill by category/name key."""
        return self._skills.get(key)

    def list_all(self) -> list[Skill]:
        """List all loaded skills."""
        return list(self._skills.values())

    def list_categories(self) -> dict[str, list[Skill]]:
        """Group skills by category."""
        cats: dict[str, list[Skill]] = {}
        for skill in self._skills.values():
            cats.setdefault(skill.category, []).append(skill)
        return cats

    def search(self, query: str, limit: int = 5) -> list[Skill]:
        """Simple keyword search across skills."""
        query_lower = query.lower()
        scored = []
        for skill in self._skills.values():
            score = 0
            if query_lower in skill.name.lower():
                score += 10
            if query_lower in skill.description.lower():
                score += 5
            for tag in skill.tags:
                if query_lower in tag.lower():
                    score += 3
            if query_lower in skill.content.lower():
                score += 1
            if score > 0:
                scored.append((score, skill))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s for _, s in scored[:limit]]

    def create_skill(
        self,
        name: str,
        category: str,
        description: str,
        content: str,
        tags: Optional[list[str]] = None,
        version: str = "1.0.0",
    ) -> Skill:
        """Create a new skill file on disk."""
        cat_dir = self._dir / category
        cat_dir.mkdir(parents=True, exist_ok=True)
        skill_dir = cat_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)

        frontmatter = f"""---
name: {name}
description: {description}
version: {version}
author: ROOT
tags: [{', '.join(tags or [])}]
platforms: [darwin, linux, win32]
---"""

        full_content = f"{frontmatter}\n\n{content}"
        skill_path = skill_dir / "SKILL.md"
        skill_path.write_text(full_content)

        skill = Skill(
            name=name,
            category=category,
            description=description,
            version=version,
            tags=tags or [],
            content=content,
            path=str(skill_path),
        )
        self._skills[f"{category}/{name}"] = skill
        logger.info("Created skill: %s/%s", category, name)
        return skill

    def build_context(self, relevant_skills: list[Skill]) -> str:
        """Build context string from relevant skills for injection into prompts."""
        if not relevant_skills:
            return ""
        parts = ["## Available Skills"]
        for skill in relevant_skills:
            parts.append(f"\n### {skill.category}/{skill.name}")
            parts.append(f"*{skill.description}*\n")
            # Truncate content to keep context manageable
            content = skill.content[:3000]
            if len(skill.content) > 3000:
                content += "\n...(truncated)"
            parts.append(content)
        return "\n".join(parts)

    def build_index(self) -> str:
        """Build a skill index for the system prompt."""
        categories = self.list_categories()
        if not categories:
            return ""
        parts = ["## Skill Index"]
        for cat, skills in sorted(categories.items()):
            parts.append(f"\n**{cat}/**")
            for s in skills:
                tags = f" [{', '.join(s.tags)}]" if s.tags else ""
                parts.append(f"  - {s.name}: {s.description}{tags}")
        return "\n".join(parts)

    def stats(self) -> dict:
        """Skill statistics."""
        categories = self.list_categories()
        return {
            "total": len(self._skills),
            "categories": {cat: len(skills) for cat, skills in categories.items()},
        }

    # ── internals ──────────────────────────────────────────────

    @staticmethod
    def _parse_skill(path: Path) -> Optional[Skill]:
        """Parse a SKILL.md file with YAML frontmatter."""
        try:
            text = path.read_text(errors="replace")
        except Exception:
            return None

        # Extract frontmatter
        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
        if not fm_match:
            return None

        fm_text = fm_match.group(1)
        content = text[fm_match.end():]

        # Simple YAML parsing (no dependency)
        def _get(key: str, default: str = "") -> str:
            m = re.search(rf"^{key}:\s*(.+)$", fm_text, re.MULTILINE)
            return m.group(1).strip() if m else default

        def _get_list(key: str) -> list[str]:
            m = re.search(rf"^{key}:\s*\[(.+?)\]", fm_text, re.MULTILINE)
            if m:
                return [t.strip().strip("'\"") for t in m.group(1).split(",")]
            return []

        name = _get("name")
        if not name:
            name = path.parent.name

        category = path.parent.parent.name if path.parent.parent != SKILLS_DIR else "general"

        return Skill(
            name=name,
            category=category,
            description=_get("description", "No description"),
            version=_get("version", "1.0.0"),
            tags=_get_list("tags"),
            content=content.strip(),
            path=str(path),
            author=_get("author", "ROOT"),
            platforms=_get_list("platforms") or ["darwin", "linux", "win32"],
        )
