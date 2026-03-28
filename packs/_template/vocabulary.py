"""
Domain vocabulary for content generation.

This is a template — customize for your product domain.
The vocabulary is injected into AI prompts to guide language
that matches your brand and product type.

For ceramics, this would contain geological descriptions.
For jewelry, it might contain gemstone and metalwork vocabulary.
For art, it might contain art theory and technique vocabulary.
"""

# Color name -> descriptive language for your domain
# Example: {"blue": "Deep sapphire tones reminiscent of..."}
COLOR_VOCABULARY = {}

# Surface/texture -> descriptive language
# Example: {"polished": "Mirror-finish surface reflecting..."}
SURFACE_VOCABULARY = {}

# Mood -> flavor text for captions
# Example: {"elegant": "Refined simplicity that speaks to..."}
MOOD_VOCABULARY = {}

# Words to AVOID in captions (domain-specific overuse)
BANNED_WORDS = []


def lookup_colors(color_list):
    """Look up descriptive vocabulary for detected colors."""
    if not color_list:
        return {}
    return {c: COLOR_VOCABULARY[c] for c in color_list if c in COLOR_VOCABULARY}


def lookup_surfaces(surface_list):
    """Look up descriptive vocabulary for surface qualities."""
    if not surface_list:
        return {}
    return {s: SURFACE_VOCABULARY[s] for s in surface_list if s in SURFACE_VOCABULARY}


def build_vocabulary_block(colors, surfaces, mood=None):
    """Build a vocabulary reference block to inject into AI prompts."""
    lines = []

    color_descs = lookup_colors(colors)
    if color_descs:
        lines.append("COLOR DESCRIPTIONS (use these, NOT raw color names):")
        for color, desc in color_descs.items():
            lines.append(f"  - {color}: {desc}")

    surface_descs = lookup_surfaces(surfaces)
    if surface_descs:
        lines.append("SURFACE DESCRIPTIONS:")
        for surface, desc in surface_descs.items():
            lines.append(f"  - {surface}: {desc}")

    if mood and mood in MOOD_VOCABULARY:
        lines.append(f"TONE: {MOOD_VOCABULARY[mood]}")

    return "\n".join(lines)


def check_banned_words(text):
    """Check text for banned words. Returns list of violations."""
    import re
    text_lower = text.lower()
    return [w for w in BANNED_WORDS if re.search(r'\b' + re.escape(w) + r'\b', text_lower)]
