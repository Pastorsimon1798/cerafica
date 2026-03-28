"""Tests for OpenRouter response parsing — new fields extraction."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "instagram" / "scripts" / "lib"))

from caption_generator import PhotoAnalysis, ContentType


def test_openrouter_parsing_new_fields():
    """Verify PhotoAnalysis can be constructed with all new fields from OpenRouter JSON."""
    mock_result = {
        "piece_type": "jar",
        "content_type": "finished",
        "primary_colors": ["slate", "charcoal"],
        "secondary_colors": ["graphite"],
        "lighting": {"light_source": "window", "direction": "side", "quality": "mixed", "impact": "Strong shadows"},
        "photo_quality": {"angle": "front", "obstructions": "glare", "completeness": "partial"},
        "uncertainties": ["Foot in shadow", "Glare masks texture"],
        "color_distribution": "pooling",
        "hypotheses": ["Storage jar [medium] - dark surface but no clay visible"],
    }

    result = PhotoAnalysis(
        content_type=ContentType(mock_result.get("content_type", "finished")),
        piece_type=mock_result.get("piece_type", "piece"),
        primary_colors=mock_result.get("primary_colors", []),
        secondary_colors=mock_result.get("secondary_colors", []),
        glaze_type=mock_result.get("glaze_type"),
        color_appearance=mock_result.get("color_appearance"),
        technique=mock_result.get("technique"),
        mood=mock_result.get("mood", "warm"),
        is_process=False,
        dimensions_visible=mock_result.get("dimensions_visible", False),
        suggested_hook=mock_result.get("brief_description", "test"),
        hypotheses=mock_result.get("hypotheses", []),
        lighting=mock_result.get("lighting"),
        photo_quality=mock_result.get("photo_quality"),
        uncertainties=mock_result.get("uncertainties"),
        color_distribution=mock_result.get("color_distribution"),
    )

    assert result.lighting["light_source"] == "window"
    assert result.photo_quality["obstructions"] == "glare"
    assert result.uncertainties == ["Foot in shadow", "Glare masks texture"]
    assert result.color_distribution == "pooling"


def test_openrouter_parsing_backward_compat():
    """Old OpenRouter responses without new fields should still work."""
    mock_result = {
        "piece_type": "mug",
        "content_type": "finished",
        "primary_colors": ["toast"],
        "secondary_colors": [],
    }

    result = PhotoAnalysis(
        content_type=ContentType(mock_result.get("content_type", "finished")),
        piece_type=mock_result.get("piece_type", "piece"),
        primary_colors=mock_result.get("primary_colors", []),
        secondary_colors=mock_result.get("secondary_colors", []),
        glaze_type=mock_result.get("glaze_type"),
        color_appearance=mock_result.get("color_appearance"),
        technique=mock_result.get("technique"),
        mood="warm",
        is_process=False,
        dimensions_visible=False,
        suggested_hook="test",
    )

    assert result.lighting is None
    assert result.photo_quality is None
    assert result.uncertainties is None
    assert result.color_distribution is None
