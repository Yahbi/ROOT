"""Tests for SkillEngine — loading, searching, creating, and context building."""

from __future__ import annotations

import pytest
from pathlib import Path

from backend.core.skill_engine import Skill, SkillEngine


@pytest.fixture
def skills_dir(tmp_path: Path) -> Path:
    """Provide a temporary skills directory."""
    d = tmp_path / "skills"
    d.mkdir()
    return d


@pytest.fixture
def engine(skills_dir: Path) -> SkillEngine:
    """Provide a SkillEngine with a temp directory."""
    return SkillEngine(skills_dir=skills_dir)


def _write_skill(
    skills_dir: Path,
    category: str,
    name: str,
    description: str = "A test skill",
    tags: str = "test, demo",
    content: str = "Skill body content here.",
) -> Path:
    """Helper to write a SKILL.md file on disk."""
    cat_dir = skills_dir / category / name
    cat_dir.mkdir(parents=True, exist_ok=True)
    skill_path = cat_dir / "SKILL.md"
    skill_path.write_text(
        f"---\n"
        f"name: {name}\n"
        f"description: {description}\n"
        f"version: 1.0.0\n"
        f"author: ROOT\n"
        f"tags: [{tags}]\n"
        f"platforms: [darwin, linux, win32]\n"
        f"---\n\n"
        f"{content}\n"
    )
    return skill_path


class TestSkillDataclass:
    def test_frozen(self):
        skill = Skill(
            name="x", category="c", description="d",
            version="1.0.0", tags=[], content="body", path="/tmp/x",
        )
        with pytest.raises(AttributeError):
            skill.name = "y"  # type: ignore[misc]

    def test_defaults(self):
        skill = Skill(
            name="x", category="c", description="d",
            version="1.0.0", tags=[], content="body", path="/tmp/x",
        )
        assert skill.author == "ROOT"
        assert "darwin" in skill.platforms


class TestLoadAll:
    def test_empty_directory(self, engine: SkillEngine):
        count = engine.load_all()
        assert count == 0
        assert engine.list_all() == []

    def test_loads_single_skill(self, engine: SkillEngine, skills_dir: Path):
        _write_skill(skills_dir, "coding", "python_debug")
        count = engine.load_all()
        assert count == 1
        assert len(engine.list_all()) == 1

    def test_loads_multiple_skills(self, engine: SkillEngine, skills_dir: Path):
        _write_skill(skills_dir, "coding", "python_debug")
        _write_skill(skills_dir, "coding", "js_debug")
        _write_skill(skills_dir, "trading", "signal_scan")
        count = engine.load_all()
        assert count == 3

    def test_reload_clears_old(self, engine: SkillEngine, skills_dir: Path):
        _write_skill(skills_dir, "coding", "python_debug")
        engine.load_all()
        assert len(engine.list_all()) == 1
        # Remove old, add new
        import shutil
        shutil.rmtree(skills_dir / "coding")
        _write_skill(skills_dir, "ops", "deploy")
        engine.load_all()
        assert len(engine.list_all()) == 1
        assert engine.list_all()[0].name == "deploy"

    def test_skips_invalid_files(self, engine: SkillEngine, skills_dir: Path):
        # File without frontmatter
        bad_dir = skills_dir / "bad" / "broken"
        bad_dir.mkdir(parents=True)
        (bad_dir / "SKILL.md").write_text("No frontmatter here.")
        _write_skill(skills_dir, "good", "valid")
        count = engine.load_all()
        assert count == 1


class TestGet:
    def test_get_existing(self, engine: SkillEngine, skills_dir: Path):
        _write_skill(skills_dir, "coding", "python_debug")
        engine.load_all()
        skill = engine.get("coding/python_debug")
        assert skill is not None
        assert skill.name == "python_debug"

    def test_get_missing(self, engine: SkillEngine):
        assert engine.get("nonexistent/skill") is None


class TestListCategories:
    def test_groups_by_category(self, engine: SkillEngine, skills_dir: Path):
        _write_skill(skills_dir, "coding", "python_debug")
        _write_skill(skills_dir, "coding", "js_debug")
        _write_skill(skills_dir, "trading", "signal_scan")
        engine.load_all()
        cats = engine.list_categories()
        assert "coding" in cats
        assert len(cats["coding"]) == 2
        assert "trading" in cats
        assert len(cats["trading"]) == 1


class TestSearch:
    def test_search_by_name(self, engine: SkillEngine, skills_dir: Path):
        _write_skill(skills_dir, "coding", "python_debug", description="Debug Python code")
        _write_skill(skills_dir, "trading", "signal_scan", description="Scan market signals")
        engine.load_all()
        results = engine.search("python")
        assert len(results) == 1
        assert results[0].name == "python_debug"

    def test_search_by_description(self, engine: SkillEngine, skills_dir: Path):
        _write_skill(skills_dir, "trading", "signal_scan", description="Scan market signals")
        engine.load_all()
        results = engine.search("market")
        assert len(results) == 1

    def test_search_by_tag(self, engine: SkillEngine, skills_dir: Path):
        _write_skill(skills_dir, "coding", "python_debug", tags="python, debug")
        engine.load_all()
        results = engine.search("debug")
        assert len(results) >= 1

    def test_search_by_content(self, engine: SkillEngine, skills_dir: Path):
        _write_skill(skills_dir, "ops", "deploy", content="Use kubectl to deploy to k8s.")
        engine.load_all()
        results = engine.search("kubectl")
        assert len(results) == 1

    def test_search_limit(self, engine: SkillEngine, skills_dir: Path):
        for i in range(10):
            _write_skill(skills_dir, "cat", f"skill_{i}", content="common keyword")
        engine.load_all()
        results = engine.search("common", limit=3)
        assert len(results) == 3

    def test_search_no_results(self, engine: SkillEngine, skills_dir: Path):
        _write_skill(skills_dir, "coding", "python_debug")
        engine.load_all()
        results = engine.search("zzzznonexistent")
        assert results == []


class TestCreateSkill:
    def test_creates_on_disk(self, engine: SkillEngine, skills_dir: Path):
        skill = engine.create_skill(
            name="new_skill",
            category="testing",
            description="A brand new skill",
            content="Step 1: do the thing.",
            tags=["new", "test"],
        )
        assert skill.name == "new_skill"
        assert skill.category == "testing"
        path = Path(skill.path)
        assert path.exists()
        assert "new_skill" in path.read_text()

    def test_created_skill_is_retrievable(self, engine: SkillEngine, skills_dir: Path):
        engine.create_skill(
            name="retrievable",
            category="testing",
            description="Can be retrieved",
            content="body",
        )
        assert engine.get("testing/retrievable") is not None

    def test_create_with_defaults(self, engine: SkillEngine, skills_dir: Path):
        skill = engine.create_skill(
            name="minimal",
            category="general",
            description="Minimal skill",
            content="body",
        )
        assert skill.version == "1.0.0"
        assert skill.tags == []


class TestBuildContext:
    def test_empty_skills(self, engine: SkillEngine):
        assert engine.build_context([]) == ""

    def test_formats_skills(self, engine: SkillEngine):
        skill = Skill(
            name="test", category="cat", description="desc",
            version="1.0.0", tags=[], content="body content", path="/tmp",
        )
        ctx = engine.build_context([skill])
        assert "## Available Skills" in ctx
        assert "cat/test" in ctx
        assert "desc" in ctx
        assert "body content" in ctx

    def test_truncates_long_content(self, engine: SkillEngine):
        long_content = "x" * 5000
        skill = Skill(
            name="long", category="cat", description="d",
            version="1.0.0", tags=[], content=long_content, path="/tmp",
        )
        ctx = engine.build_context([skill])
        assert "...(truncated)" in ctx


class TestBuildIndex:
    def test_empty_index(self, engine: SkillEngine):
        assert engine.build_index() == ""

    def test_index_with_skills(self, engine: SkillEngine, skills_dir: Path):
        _write_skill(skills_dir, "coding", "python_debug", tags="python, debug")
        engine.load_all()
        index = engine.build_index()
        assert "## Skill Index" in index
        assert "coding" in index
        assert "python_debug" in index


class TestStats:
    def test_empty_stats(self, engine: SkillEngine):
        stats = engine.stats()
        assert stats["total"] == 0
        assert stats["categories"] == {}

    def test_stats_with_skills(self, engine: SkillEngine, skills_dir: Path):
        _write_skill(skills_dir, "coding", "python_debug")
        _write_skill(skills_dir, "trading", "signal_scan")
        engine.load_all()
        stats = engine.stats()
        assert stats["total"] == 2
        assert stats["categories"]["coding"] == 1
        assert stats["categories"]["trading"] == 1
