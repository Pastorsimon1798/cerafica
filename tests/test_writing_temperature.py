"""Tests for writing temperature in caption generation functions."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "instagram" / "scripts" / "lib"))

import inspect
from caption_generator import generate_caption_with_ollama, generate_caption_with_openrouter


def test_ollama_caption_has_temperature():
    """Verify the Ollama caption function includes temperature=0.9 in its API call."""
    source = inspect.getsource(generate_caption_with_ollama)
    assert "temperature" in source, "Ollama caption function should reference temperature"
    assert "0.9" in source, "Ollama caption function should use temperature=0.9"


def test_openrouter_caption_has_temperature():
    """Verify the OpenRouter caption function includes temperature=0.9 in its API call."""
    source = inspect.getsource(generate_caption_with_openrouter)
    assert "temperature" in source, "OpenRouter caption function should reference temperature"
    assert "0.9" in source, "OpenRouter caption function should use temperature=0.9"
