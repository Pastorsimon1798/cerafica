"""
Geological vocabulary for worldbuilding generation.

BACKWARD COMPATIBILITY SHIM — the canonical source is now packs/ceramics/vocabulary.py.
This file re-exports everything so existing imports continue to work.
"""
import sys
from pathlib import Path

# Add packs/ceramics to path so we can import from the domain pack
_pack_path = Path(__file__).parent.parent.parent.parent / "packs" / "ceramics"
if _pack_path.exists() and str(_pack_path) not in sys.path:
    sys.path.insert(0, str(_pack_path))

try:
    from vocabulary import (  # noqa: F401
        COLOR_GEOLOGY, SURFACE_GEOLOGY, MOOD_GEOLOGY,
        BANNED_FOOD_WORDS, BANNED_FABRIC_WORDS,
        lookup_colors, lookup_surfaces, build_vocabulary_block,
        check_banned_words,
    )
except ImportError:
    # Fallback: if pack not found, define empty defaults
    COLOR_GEOLOGY = {}
    SURFACE_GEOLOGY = {}
    MOOD_GEOLOGY = {}
    BANNED_FOOD_WORDS = []
    BANNED_FABRIC_WORDS = []

    def lookup_colors(color_list):
        return {}

    def lookup_surfaces(surface_list):
        return {}

    def build_vocabulary_block(colors, surfaces, mood=None):
        return ""

    def check_banned_words(text):
        return []
