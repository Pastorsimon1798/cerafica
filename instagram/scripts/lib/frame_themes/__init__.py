"""
Frame Theme System

Provides post-processing themes for product photos.
Each theme applies overlays, borders, watermarks, and text to product images.

Usage:
    from frame_themes import load_theme
    theme = load_theme("clean")  # or "minimal"
    result = theme.generate(photo_path, output_path, product_name="My Product")
"""

from .base import FrameTheme
from .clean import CleanFrameTheme
from .minimal import MinimalFrameTheme

# Registry of built-in themes
THEMES = {
    "clean": CleanFrameTheme,
    "minimal": MinimalFrameTheme,
}


def load_theme(theme_name: str, **kwargs) -> FrameTheme:
    """Load a frame theme by name.

    Args:
        theme_name: Name of built-in theme ("clean", "minimal") or
                    a dotted path to a custom theme class.
        **kwargs: Passed to theme constructor.

    Returns:
        Instantiated FrameTheme.
    """
    if theme_name in THEMES:
        return THEMES[theme_name](**kwargs)

    # Try loading as a module path (e.g., "packs.ceramics.frame_theme.PlanetaryTheme")
    try:
        parts = theme_name.rsplit(".", 1)
        if len(parts) == 2:
            import importlib
            module = importlib.import_module(parts[0])
            theme_class = getattr(module, parts[1])
            return theme_class(**kwargs)
    except (ImportError, AttributeError):
        pass

    raise ValueError(f"Unknown frame theme: {theme_name}. Available: {list(THEMES.keys())}")
