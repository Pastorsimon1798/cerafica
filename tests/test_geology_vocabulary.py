"""
Tests for instagram/scripts/lib/geology_vocabulary.py

Covers: lookup_colors, lookup_surfaces, build_vocabulary_block, check_banned_words
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "instagram" / "scripts" / "lib"))

from geology_vocabulary import (
    lookup_colors,
    lookup_surfaces,
    build_vocabulary_block,
    check_banned_words,
    COLOR_GEOLOGY,
    SURFACE_GEOLOGY,
    BANNED_FOOD_WORDS,
    BANNED_FABRIC_WORDS,
)


# ---------------------------------------------------------------------------
# lookup_colors
# ---------------------------------------------------------------------------

class TestLookupColors:
    def test_empty_list_returns_empty_dict(self):
        assert lookup_colors([]) == {}

    def test_none_equivalent_empty(self):
        # Callers may pass empty; guard already handled
        assert lookup_colors([]) == {}

    def test_known_color_returns_description(self):
        result = lookup_colors(["blue"])
        assert "blue" in result
        assert result["blue"] == COLOR_GEOLOGY["blue"]

    def test_multiple_known_colors(self):
        result = lookup_colors(["blue", "rust", "teal"])
        assert set(result.keys()) == {"blue", "rust", "teal"}

    def test_unknown_color_excluded(self):
        result = lookup_colors(["nonexistent_color_xyz"])
        assert result == {}

    def test_mixed_known_and_unknown(self):
        result = lookup_colors(["blue", "fakemadeupcolor"])
        assert "blue" in result
        assert "fakemadeupcolor" not in result

    def test_case_insensitive_lookup(self):
        result = lookup_colors(["BLUE"])
        assert "blue" in result

    def test_strips_leading_trailing_spaces(self):
        result = lookup_colors(["  blue  "])
        assert "blue" in result

    def test_space_replaced_with_underscore(self):
        # "earth tones" should map via underscore normalisation
        result = lookup_colors(["earth tones"])
        assert "earth tones" in result or "earth_tones" in result

    def test_underscore_key_name(self):
        # "chun_blue" is stored with underscore
        result = lookup_colors(["chun_blue"])
        assert "chun_blue" in result

    def test_returns_dict_not_list(self):
        result = lookup_colors(["blue"])
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# lookup_surfaces
# ---------------------------------------------------------------------------

class TestLookupSurfaces:
    def test_empty_list_returns_empty_dict(self):
        assert lookup_surfaces([]) == {}

    def test_known_surface_returns_description(self):
        result = lookup_surfaces(["crackle"])
        assert "crackle" in result
        assert result["crackle"] == SURFACE_GEOLOGY["crackle"]

    def test_multiple_known_surfaces(self):
        result = lookup_surfaces(["crackle", "luster", "pinholing"])
        assert set(result.keys()) == {"crackle", "luster", "pinholing"}

    def test_unknown_surface_excluded(self):
        result = lookup_surfaces(["notarealusurface"])
        assert result == {}

    def test_case_insensitive(self):
        result = lookup_surfaces(["CRACKLE"])
        assert "crackle" in result

    def test_strips_whitespace(self):
        result = lookup_surfaces([" luster "])
        assert "luster" in result


# ---------------------------------------------------------------------------
# build_vocabulary_block
# ---------------------------------------------------------------------------

class TestBuildVocabularyBlock:
    def test_empty_inputs_returns_empty_string(self):
        result = build_vocabulary_block([], [])
        assert result == ""

    def test_known_color_appears_in_output(self):
        result = build_vocabulary_block(["blue"], [])
        assert "blue" in result
        assert "COLOR ORIGINS" in result

    def test_known_surface_appears_in_output(self):
        result = build_vocabulary_block([], ["crackle"])
        assert "crackle" in result
        assert "SURFACE ORIGINS" in result

    def test_mood_appears_when_known(self):
        result = build_vocabulary_block([], [], mood="dramatic")
        assert "ATMOSPHERIC NOTE" in result

    def test_unknown_mood_excluded(self):
        result = build_vocabulary_block([], [], mood="unknownmood")
        assert "ATMOSPHERIC NOTE" not in result

    def test_banned_food_word_filtered_from_colors(self):
        # "chocolate" is a banned food word; should be stripped before lookup
        result = build_vocabulary_block(["chocolate"], [])
        # chocolate is in COLOR_GEOLOGY but also in BANNED_FOOD_WORDS,
        # so it should be filtered out before lookup
        assert "chocolate" not in result

    def test_banned_fabric_word_filtered_from_surfaces(self):
        result = build_vocabulary_block([], ["silk"])
        assert "silk" not in result

    def test_combined_colors_and_surfaces(self):
        result = build_vocabulary_block(["rust"], ["crackle"])
        assert "COLOR ORIGINS" in result
        assert "SURFACE ORIGINS" in result

    def test_unknown_color_produces_no_color_section(self):
        result = build_vocabulary_block(["unknowncolor"], [])
        assert "COLOR ORIGINS" not in result


# ---------------------------------------------------------------------------
# check_banned_words
# ---------------------------------------------------------------------------

class TestCheckBannedWords:
    def test_clean_text_returns_empty_list(self):
        text = "Iron silicate compressed under extreme tectonic pressure."
        assert check_banned_words(text) == []

    def test_food_word_detected(self):
        violations = check_banned_words("The surface has a chocolate hue.")
        assert "chocolate" in violations

    def test_fabric_word_detected(self):
        violations = check_banned_words("Reminds me of denim fabric patterns.")
        assert "denim" in violations

    def test_multiple_violations(self):
        violations = check_banned_words("honey-colored silk surface")
        assert "honey" in violations
        assert "silk" in violations

    def test_case_insensitive_detection(self):
        violations = check_banned_words("HONEY COLORED GLAZE")
        assert "honey" in violations

    def test_partial_word_not_flagged(self):
        # "olive" is banned but "olivine" is a real mineral — should NOT be flagged
        violations = check_banned_words("The surface contains olivine crystals.")
        assert "olive" not in violations

    def test_empty_string_returns_empty(self):
        assert check_banned_words("") == []

    def test_all_banned_food_words_are_checked(self):
        # Ensure BANNED_FOOD_WORDS list is non-empty (sanity)
        assert len(BANNED_FOOD_WORDS) > 10

    def test_all_banned_fabric_words_are_checked(self):
        assert len(BANNED_FABRIC_WORDS) > 5

    def test_returns_list(self):
        assert isinstance(check_banned_words("clean text"), list)
