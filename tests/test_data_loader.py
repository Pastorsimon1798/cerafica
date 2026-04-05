"""
Tests for instagram/scripts/lib/data_loader.py

Covers: _load_json, load_colors (markdown parsing), load_clay_bodies,
load_colorants, load_layering_rules — using tmp files and monkeypatching
to avoid dependence on the ceramics-foundation submodule being present.
"""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "instagram" / "scripts" / "lib"))

import data_loader


# ---------------------------------------------------------------------------
# _load_json
# ---------------------------------------------------------------------------

class TestLoadJson:
    def test_valid_json_file(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text('{"key": "value", "num": 42}')
        result = data_loader._load_json(f)
        assert result == {"key": "value", "num": 42}

    def test_missing_file_returns_none(self, tmp_path):
        result = data_loader._load_json(tmp_path / "nonexistent.json")
        assert result is None

    def test_malformed_json_returns_none(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{not valid json}")
        result = data_loader._load_json(f)
        assert result is None

    def test_empty_file_returns_none(self, tmp_path):
        f = tmp_path / "empty.json"
        f.write_text("")
        result = data_loader._load_json(f)
        assert result is None

    def test_json_list_returned_correctly(self, tmp_path):
        f = tmp_path / "list.json"
        f.write_text('[1, 2, 3]')
        result = data_loader._load_json(f)
        assert result == [1, 2, 3]


# ---------------------------------------------------------------------------
# _find_foundation_dir
# ---------------------------------------------------------------------------

class TestFindFoundationDir:
    def test_returns_none_when_dir_missing(self, tmp_path):
        with patch.object(data_loader, "_FOUNDATION_DIR", tmp_path / "does_not_exist"):
            assert data_loader._find_foundation_dir() is None

    def test_returns_path_when_dir_exists(self, tmp_path):
        real_dir = tmp_path / "ceramics-foundation"
        real_dir.mkdir()
        with patch.object(data_loader, "_FOUNDATION_DIR", real_dir):
            result = data_loader._find_foundation_dir()
            assert result == real_dir


# ---------------------------------------------------------------------------
# load_colors  (markdown table parsing)
# ---------------------------------------------------------------------------

SAMPLE_COLORS_MD = """\
# Ceramic Color Taxonomy

## Browns (2 terms)

| **Walnut Brown** | Mid-warm brown |
| **Chocolate** | Dark brown |

## Blues (1 terms)

| **Cobalt Blue** | Deep vivid blue |
"""

SAMPLE_COLORS_MD_NO_ROWS = """\
## Blues (0 terms)

| Header | Description |
"""


class TestLoadColors:
    def _make_foundation(self, tmp_path, content):
        foundation = tmp_path / "ceramics-foundation"
        taxonomies = foundation / "taxonomies"
        taxonomies.mkdir(parents=True)
        (taxonomies / "colors.md").write_text(content)
        return foundation

    def test_returns_none_when_foundation_missing(self):
        with patch.object(data_loader, "_FOUNDATION_DIR", Path("/nonexistent/path")):
            assert data_loader.load_colors() is None

    def test_parses_color_names_to_lowercase_keys(self, tmp_path):
        foundation = self._make_foundation(tmp_path, SAMPLE_COLORS_MD)
        with patch.object(data_loader, "_FOUNDATION_DIR", foundation):
            result = data_loader.load_colors()
        assert result is not None
        assert "walnut_brown" in result
        assert "chocolate" in result

    def test_parses_family_from_section_heading(self, tmp_path):
        foundation = self._make_foundation(tmp_path, SAMPLE_COLORS_MD)
        with patch.object(data_loader, "_FOUNDATION_DIR", foundation):
            result = data_loader.load_colors()
        assert result["walnut_brown"]["family"] == "brown"
        assert result["cobalt_blue"]["family"] == "blue"

    def test_parses_visual_id(self, tmp_path):
        foundation = self._make_foundation(tmp_path, SAMPLE_COLORS_MD)
        with patch.object(data_loader, "_FOUNDATION_DIR", foundation):
            result = data_loader.load_colors()
        assert result["walnut_brown"]["visual_id"] == "Mid-warm brown"

    def test_space_replaced_with_underscore_in_key(self, tmp_path):
        foundation = self._make_foundation(tmp_path, SAMPLE_COLORS_MD)
        with patch.object(data_loader, "_FOUNDATION_DIR", foundation):
            result = data_loader.load_colors()
        # "Cobalt Blue" -> "cobalt_blue"
        assert "cobalt_blue" in result

    def test_returns_none_when_colors_file_missing(self, tmp_path):
        foundation = tmp_path / "ceramics-foundation"
        foundation.mkdir()
        # No taxonomies directory or file
        with patch.object(data_loader, "_FOUNDATION_DIR", foundation):
            assert data_loader.load_colors() is None

    def test_skips_fallback_colors_section(self, tmp_path):
        md = """\
## Fallback Colors (1 terms)

| **Generic** | Fallback |

## Blues (1 terms)

| **Sky Blue** | Light blue |
"""
        foundation = self._make_foundation(tmp_path, md)
        with patch.object(data_loader, "_FOUNDATION_DIR", foundation):
            result = data_loader.load_colors()
        # "generic" should be excluded (fallback section skipped)
        assert result is not None
        assert "generic" not in result
        assert "sky_blue" in result


# ---------------------------------------------------------------------------
# load_clay_bodies
# ---------------------------------------------------------------------------

CLAY_BODIES_DATA = {"clay_bodies": [{"name": "Stoneware", "cone": "6-10"}]}
MISSING_KEY_DATA = {"other_key": []}


class TestLoadClaybodies:
    def _make_foundation_with_json(self, tmp_path, filename, content):
        foundation = tmp_path / "ceramics-foundation"
        data_dir = foundation / "data"
        data_dir.mkdir(parents=True)
        (data_dir / filename).write_text(json.dumps(content))
        return foundation

    def test_returns_none_when_foundation_missing(self):
        with patch.object(data_loader, "_FOUNDATION_DIR", Path("/nope")):
            assert data_loader.load_clay_bodies() is None

    def test_returns_data_when_file_valid(self, tmp_path):
        foundation = self._make_foundation_with_json(tmp_path, "clay-bodies.json", CLAY_BODIES_DATA)
        with patch.object(data_loader, "_FOUNDATION_DIR", foundation):
            result = data_loader.load_clay_bodies()
        assert result is not None
        assert "clay_bodies" in result

    def test_returns_none_when_key_missing(self, tmp_path):
        foundation = self._make_foundation_with_json(tmp_path, "clay-bodies.json", MISSING_KEY_DATA)
        with patch.object(data_loader, "_FOUNDATION_DIR", foundation):
            assert data_loader.load_clay_bodies() is None

    def test_returns_none_when_file_missing(self, tmp_path):
        foundation = tmp_path / "ceramics-foundation"
        (foundation / "data").mkdir(parents=True)
        with patch.object(data_loader, "_FOUNDATION_DIR", foundation):
            assert data_loader.load_clay_bodies() is None


# ---------------------------------------------------------------------------
# load_colorants
# ---------------------------------------------------------------------------

class TestLoadColorants:
    def _make_foundation(self, tmp_path, content):
        foundation = tmp_path / "ceramics-foundation"
        data_dir = foundation / "data"
        data_dir.mkdir(parents=True)
        (data_dir / "colorants.json").write_text(json.dumps(content))
        return foundation

    def test_returns_none_when_foundation_missing(self):
        with patch.object(data_loader, "_FOUNDATION_DIR", Path("/nope")):
            assert data_loader.load_colorants() is None

    def test_returns_data_with_colorants_key(self, tmp_path):
        foundation = self._make_foundation(tmp_path, {"colorants": [{"name": "Iron Oxide"}]})
        with patch.object(data_loader, "_FOUNDATION_DIR", foundation):
            result = data_loader.load_colorants()
        assert result is not None
        assert "colorants" in result

    def test_returns_none_when_colorants_key_absent(self, tmp_path):
        foundation = self._make_foundation(tmp_path, {"wrong": []})
        with patch.object(data_loader, "_FOUNDATION_DIR", foundation):
            assert data_loader.load_colorants() is None


# ---------------------------------------------------------------------------
# load_layering_rules
# ---------------------------------------------------------------------------

class TestLoadLayeringRules:
    def _make_foundation(self, tmp_path, content):
        foundation = tmp_path / "ceramics-foundation"
        data_dir = foundation / "data"
        data_dir.mkdir(parents=True)
        (data_dir / "layering-rules.json").write_text(json.dumps(content))
        return foundation

    def test_returns_none_when_foundation_missing(self):
        with patch.object(data_loader, "_FOUNDATION_DIR", Path("/nope")):
            assert data_loader.load_layering_rules() is None

    def test_returns_dict_when_file_valid(self, tmp_path):
        data = {"rules": [{"base": "shino", "compatible": ["celadon"]}]}
        foundation = self._make_foundation(tmp_path, data)
        with patch.object(data_loader, "_FOUNDATION_DIR", foundation):
            result = data_loader.load_layering_rules()
        assert result == data

    def test_returns_none_when_file_missing(self, tmp_path):
        foundation = tmp_path / "ceramics-foundation"
        (foundation / "data").mkdir(parents=True)
        with patch.object(data_loader, "_FOUNDATION_DIR", foundation):
            assert data_loader.load_layering_rules() is None
