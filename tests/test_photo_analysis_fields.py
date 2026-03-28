"""
Test PhotoAnalysis new fields for enhanced vision analysis.

Task 1.1: Add 4 new optional fields to PhotoAnalysis dataclass.
"""
import sys
import os
from pathlib import Path

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent / "instagram" / "scripts" / "lib"
sys.path.insert(0, str(project_root))

from caption_generator import PhotoAnalysis, ContentType


def test_photo_analysis_new_fields():
    """Test that PhotoAnalysis accepts and stores the 4 new optional fields."""
    a = PhotoAnalysis(
        content_type=ContentType.FINISHED_PIECE,
        piece_type="bud_vase",
        primary_colors=["sienna"],
        secondary_colors=[],
        glaze_type=None,
        color_appearance=None,
        technique=None,
        mood="warm",
        is_process=False,
        dimensions_visible=True,
        suggested_hook="test hook",
        lighting={"light_source": "studio_natural", "direction": "front", "quality": "diffuse", "impact": "Even lighting"},
        photo_quality={"angle": "profile", "obstructions": "none", "completeness": "full_piece_visible"},
        uncertainties=["Foot in shadow"],
        color_distribution="breaking",
    )
    assert a.lighting["light_source"] == "studio_natural"
    assert a.uncertainties == ["Foot in shadow"]
    assert a.color_distribution == "breaking"
    assert a.photo_quality["angle"] == "profile"


def test_photo_analysis_defaults_none():
    """Test that new fields default to None when not provided."""
    a = PhotoAnalysis(
        content_type=ContentType.FINISHED_PIECE,
        piece_type="piece",
        primary_colors=[],
        secondary_colors=[],
        glaze_type=None,
        color_appearance=None,
        technique=None,
        mood="warm",
        is_process=False,
        dimensions_visible=False,
        suggested_hook="test",
    )
    assert a.lighting is None
    assert a.photo_quality is None
    assert a.uncertainties is None
    assert a.color_distribution is None
