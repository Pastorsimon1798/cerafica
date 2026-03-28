"""Tests for Ollama response parsing — new fields extraction."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "instagram" / "scripts" / "lib"))

from caption_generator import PhotoAnalysis, ContentType


def test_ollama_parsing_new_fields():
    """Verify PhotoAnalysis can be constructed with all new fields from Ollama JSON."""
    mock_analysis = {
        "piece_type": "bud_vase",
        "content_type": "finished",
        "primary_colors": ["sienna", "copper"],
        "secondary_colors": ["bronze"],
        "lighting": {"light_source": "studio", "direction": "front", "quality": "diffuse", "impact": "good"},
        "photo_quality": {"angle": "profile", "obstructions": "none", "completeness": "full_piece_visible"},
        "uncertainties": ["Foot obscured"],
        "color_distribution": "breaking",
        "hypotheses": ["Bud vase with Shino glaze [high] - crackle visible"],
    }

    result = PhotoAnalysis(
        content_type=ContentType(mock_analysis.get("content_type", "finished")),
        piece_type=mock_analysis.get("piece_type", "piece"),
        primary_colors=mock_analysis.get("primary_colors", []),
        secondary_colors=mock_analysis.get("secondary_colors", []),
        glaze_type=mock_analysis.get("glaze_type"),
        color_appearance=mock_analysis.get("color_appearance"),
        technique=mock_analysis.get("technique"),
        mood=mock_analysis.get("mood", "warm"),
        is_process=False,
        dimensions_visible=mock_analysis.get("dimensions_visible", False),
        suggested_hook=mock_analysis.get("brief_description", "test"),
        hypotheses=mock_analysis.get("hypotheses", []),
        lighting=mock_analysis.get("lighting"),
        photo_quality=mock_analysis.get("photo_quality"),
        uncertainties=mock_analysis.get("uncertainties"),
        color_distribution=mock_analysis.get("color_distribution"),
    )

    assert result.lighting["light_source"] == "studio"
    assert result.photo_quality["angle"] == "profile"
    assert result.uncertainties == ["Foot obscured"]
    assert result.color_distribution == "breaking"


def test_ollama_parsing_backward_compat():
    """Old responses without new fields should still work (defaults to None)."""
    mock_analysis = {
        "piece_type": "bowl",
        "content_type": "finished",
        "primary_colors": ["cream"],
        "secondary_colors": [],
    }

    result = PhotoAnalysis(
        content_type=ContentType(mock_analysis.get("content_type", "finished")),
        piece_type=mock_analysis.get("piece_type", "piece"),
        primary_colors=mock_analysis.get("primary_colors", []),
        secondary_colors=mock_analysis.get("secondary_colors", []),
        glaze_type=mock_analysis.get("glaze_type"),
        color_appearance=mock_analysis.get("color_appearance"),
        technique=mock_analysis.get("technique"),
        mood="warm",
        is_process=False,
        dimensions_visible=False,
        suggested_hook="test",
    )

    assert result.lighting is None
    assert result.photo_quality is None
    assert result.uncertainties is None
    assert result.color_distribution is None
