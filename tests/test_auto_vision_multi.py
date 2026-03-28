#!/usr/bin/env python3
"""
Tests for multi-provider parallel execution in auto_vision.py
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, call
import pytest

# Add parent directory to path to import scripts
sys.path.insert(0, str(Path(__file__).parent.parent / "instagram" / "scripts"))

from auto_vision import MODELS, analyze_with_model, process_photo


class TestModelsConfig:
    """Test the MODELS configuration."""

    def test_models_config_has_three_providers(self):
        """MODELS list should have 3 providers with correct backends."""
        assert len(MODELS) == 3, f"Expected 3 models, got {len(MODELS)}"

        # Check first model (Ollama)
        assert MODELS[0]["name"] == "Kimi K2.5 (Ollama)"
        assert MODELS[0]["backend"] == "ollama"
        assert MODELS[0]["vision_model"] == "kimi-k2.5:cloud"

        # Check second model (OpenRouter)
        assert MODELS[1]["name"] == "Kimi K2.5 (OpenRouter)"
        assert MODELS[1]["backend"] == "openrouter"
        assert MODELS[1]["vision_model"] == "moonshotai/kimi-k2.5"

        # Check third model (OpenRouter)
        assert MODELS[2]["name"] == "Gemini 3 Flash"
        assert MODELS[2]["backend"] == "openrouter"
        assert MODELS[2]["vision_model"] == "google/gemini-3-flash-preview"

    def test_all_models_have_required_fields(self):
        """All models should have name, backend, and vision_model fields."""
        for model in MODELS:
            assert "name" in model, f"Model missing 'name' field: {model}"
            assert "backend" in model, f"Model missing 'backend' field: {model}"
            assert "vision_model" in model, f"Model missing 'vision_model' field: {model}"
            assert model["backend"] in ["ollama", "openrouter"], \
                f"Invalid backend: {model['backend']}"


class TestAnalyzeWithModel:
    """Test analyze_with_model routing by backend."""

    @patch('auto_vision.analyze_photo')
    @patch('auto_vision.set_ai_config')
    def test_analyze_with_model_routes_ollama(self, mock_set_ai_config, mock_analyze_photo):
        """Verify analyze_with_model sets ollama config for ollama backend."""
        # Setup
        mock_analysis = Mock()
        mock_analysis.piece_type = "Mug"
        mock_analysis.glaze_type = "Celadon"
        mock_analysis.primary_colors = ["blue"]
        mock_analysis.mood = "calm"
        mock_analyze_photo.return_value = mock_analysis

        config = {
            "backend": "ollama",
            "vision_model": "kimi-k2.5:cloud",
            "name": "Kimi K2.5 (Ollama)"
        }
        photo_path = Path("/fake/photo.jpg")

        # Execute
        result, reasoning, raw = analyze_with_model(photo_path, config)

        # Verify
        mock_set_ai_config.assert_called_once()
        call_args = mock_set_ai_config.call_args[0][0]

        assert call_args.backend == "ollama"
        assert call_args.ollama_vision_model == "kimi-k2.5:cloud"

        mock_analyze_photo.assert_called_once_with(str(photo_path))
        assert result == mock_analysis

    @patch('auto_vision.analyze_photo')
    @patch('auto_vision.set_ai_config')
    def test_analyze_with_model_routes_openrouter(self, mock_set_ai_config, mock_analyze_photo):
        """Verify analyze_with_model sets openrouter config for openrouter backend."""
        # Setup
        mock_analysis = Mock()
        mock_analysis.piece_type = "Bowl"
        mock_analysis.glaze_type = "Shino"
        mock_analysis.primary_colors = ["white"]
        mock_analysis.mood = "rustic"
        mock_analyze_photo.return_value = mock_analysis

        config = {
            "backend": "openrouter",
            "vision_model": "moonshotai/kimi-k2.5",
            "name": "Kimi K2.5 (OpenRouter)"
        }
        photo_path = Path("/fake/photo.jpg")

        # Execute
        result, reasoning, raw = analyze_with_model(photo_path, config)

        # Verify
        mock_set_ai_config.assert_called_once()
        call_args = mock_set_ai_config.call_args[0][0]

        assert call_args.backend == "openrouter"
        assert call_args.openrouter_vision_model == "moonshotai/kimi-k2.5"

        mock_analyze_photo.assert_called_once_with(str(photo_path))
        assert result == mock_analysis


class TestProcessPhoto:
    """Test process_photo with single model."""

    MOCK_MODEL = {"name": "Kimi K2.5 (Ollama)", "backend": "ollama", "vision_model": "kimi-k2.5:cloud"}

    @patch('auto_vision.has_vision_result')
    @patch('auto_vision.save_vision_result')
    @patch('auto_vision.analyze_with_model')
    @patch('auto_vision.get_photo_id')
    def test_process_photo_runs_successfully(self, mock_get_photo_id, mock_analyze_with_model,
                                             mock_save_vision_result, mock_has_vision_result):
        """Verify process_photo returns success result for a single model."""
        # Setup
        mock_get_photo_id.return_value = 123
        mock_has_vision_result.return_value = False

        mock_analysis = Mock()
        mock_analysis.piece_type = "Vase"
        mock_analysis.glaze_type = "Tenmoku"
        mock_analysis.primary_colors = ["brown"]
        mock_analysis.mood = "dramatic"

        mock_analyze_with_model.return_value = (mock_analysis, "", "")

        photo_path = Path("/fake/test_photo.jpg")

        # Execute
        result = process_photo(photo_path, model=self.MOCK_MODEL, force=False)

        # Verify structure
        assert result["photo"] == "test_photo.jpg"
        assert result["photo_id"] == 123
        assert result["model"] == "Kimi K2.5 (Ollama)"
        assert result["status"] == "success"
        assert result["piece_type"] == "Vase"
        assert result["glaze_type"] == "Tenmoku"

        # Verify analyze_with_model was called once
        assert mock_analyze_with_model.call_count == 1
        assert mock_save_vision_result.call_count == 1

    @patch('auto_vision.has_vision_result')
    @patch('auto_vision.save_vision_result')
    @patch('auto_vision.analyze_with_model')
    @patch('auto_vision.get_photo_id')
    def test_process_photo_skips_already_analyzed(self, mock_get_photo_id, mock_analyze_with_model,
                                                   mock_save_vision_result, mock_has_vision_result):
        """Verify process_photo skips model when result already exists."""
        # Setup
        mock_get_photo_id.return_value = 456
        mock_has_vision_result.return_value = True  # Already analyzed

        photo_path = Path("/fake/test_photo2.jpg")

        # Execute
        result = process_photo(photo_path, model=self.MOCK_MODEL, force=False)

        # Verify skipped — no analysis or save calls
        assert result["status"] == "skipped"
        assert mock_analyze_with_model.call_count == 0
        assert mock_save_vision_result.call_count == 0

    @patch('auto_vision.has_vision_result')
    @patch('auto_vision.save_vision_result')
    @patch('auto_vision.analyze_with_model')
    @patch('auto_vision.get_photo_id')
    def test_process_photo_handles_errors_gracefully(self, mock_get_photo_id, mock_analyze_with_model,
                                                      mock_save_vision_result, mock_has_vision_result):
        """Verify process_photo captures errors without crashing."""
        # Setup
        mock_get_photo_id.return_value = 789
        mock_has_vision_result.return_value = False

        mock_analyze_with_model.side_effect = Exception("API timeout")

        photo_path = Path("/fake/test_photo3.jpg")

        # Execute
        result = process_photo(photo_path, model=self.MOCK_MODEL, force=False)

        # Verify error was captured
        assert result["status"] == "error"
        assert "API timeout" in result["error"]
        assert mock_save_vision_result.call_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
