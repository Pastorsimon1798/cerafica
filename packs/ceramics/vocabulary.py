"""
Geological vocabulary for worldbuilding generation.

Extracted from human-door/pipeline.html color/surface origins mapping.
Provides the authoritative geological descriptions for colors and surfaces
detected in ceramic vision analysis.

When the AI sees "denim" it should write "Cobalt-iron oxidation under
specific atmospheric pressure" — NOT "denim atmosphere".
"""

# Color name -> geological origin description
COLOR_GEOLOGY = {
    "blue": "Deep water + silica deposits + depth pressure.",
    "chun_blue": "Rare chun crystallization — a geological fluke that should not exist at this scale.",
    "denim": "Cobalt-iron oxidation under specific atmospheric pressure. The blue deepens with age.",
    "ice_blue": "Suspended ice micro-crystals refracting light through a thin atmosphere.",
    "seafoam": "Biological mineral processing — organisms concentrate calcium and copper in their shells.",
    "green": "Copper oxidation in a reducing atmosphere.",
    "olive": "Iron-magnesium silicates exposed by tectonic uplift. Olives only appear on geological fault lines.",
    "brown": "Iron and organic decay. Layers of composted biological material compressed over millennia.",
    "tan": "Dried seabeds and evaporite deposits.",
    "oatmeal": "Calcium-rich sedimentary deposits from ancient shallow seas.",
    "cream": "Volcanic ash + calcium deposits.",
    "white": "Pure calcium carbonate crystallization from thermal vent precipitation.",
    "rust": "Iron oxide exposure. This world was wounded repeatedly.",
    "terracotta": "Iron-rich clay substrate oxidized by sustained atmospheric exposure.",
    "mahogany": "Deep iron-manganese oxide deposits. The color of old blood baked into stone.",
    "oxblood": "Extreme iron oxidation under high-pressure conditions. Rare — only found near impact sites.",
    "burgundy": "Manganese-iron interaction in reducing zones. The chemistry is still not fully understood.",
    "garnet": "Aluminum-silicate metamorphism at extreme depth. Brought to surface by volcanic upwelling.",
    "walnut": "Organic tannin compounds leached from deep soil layers. The smell carries for kilometers.",
    "chestnut": "Iron-rich clay deposits stained by millennia of organic interaction.",
    "chocolate": "Dense organic matter compressed with iron oxides. This is decay, fossilized.",
    "cocoa": "Manganese-iron carbonate deposits with biological signatures.",
    "bronze": "Copper + tin + oxidation state. The metallic sheen comes from crystal alignment.",
    "teal": "Transitional chemistry. Colors still reacting.",
    "slate": "Iron-silicate compression. The grey comes from pressure, not composition.",
    "pewter": "Tin-lead alloy deposits from ancient volcanic activity.",
    "charcoal": "Carbon-rich deposits from prolonged reduction atmosphere events.",
    "earth tones": "Mixed geological strata — each layer a different epoch of this world's history.",
    "amber": "Iron-oxide and organic polymerization over millennia. The amber glow comes from fossilized biological resin.",
    "honey": "Biological amber deposits — ancient tree resin fossilized under pressure. The color is warmth, trapped.",
    "taupe": "Iron-manganese silicates in a specific oxidation state. Taupe only appears where geological stability has persisted for billions of years.",
    "slate_blue": "Iron-silicate compression with copper mineral traces.",
    "dark_blue": "Deep water + silica deposits at extreme depth pressure.",
}

# Surface quality -> geological description
SURFACE_GEOLOGY = {
    "crackle": "Fracture networks from the Late Heavy Bombardment. Mineral deposits bleed color along fault lines.",
    "luster": "Metallic crystallization creates reflective ore veins across the surface.",
    "carbon_trapping": "Carbon sequestration in surface fractures darkens entire geological zones.",
    "speckled": "Impact debris scatters foreign minerals across the surface.",
    "color_pooling": "Mineral pooling concentrates pigments in low-lying areas — the color runs and collects.",
    "pinholing": "Gas vent emissions create localized plumes and pitting across the surface.",
    "breaking": "Debris from contraction events lingers in ridges and valleys.",
    "running": "Mineral runoff creates low-lying chemical mists along drainage paths.",
    "flashing": "Intermittent plasma discharge ionizes the air, leaving transient surface marks.",
    "crawling": "Tectonic displacement — geological or biological origin debated.",
    "variegation": "Mineral stratification — each band a different epoch.",
    "crazing": "Micro-fracture networks from thermal cycling over millennia.",
    "shino": "Oxide reduction zones where atmospheric conditions shifted suddenly.",
    "wood_firing": "Organic carbon deposits from prolonged biomass combustion events.",
}

# Mood -> geological flavor
MOOD_GEOLOGY = {
    "dramatic": "Colors compete for dominance. No single mineral won.",
    "organic": "Colors emerged from biological processes — the geology is alive.",
    "moody": "Colors shift with the light. By evening, the whole world looks different.",
    "vibrant": "Unusually saturated — the mineral chemistry here favors vivid expression.",
    "earthy": "Colors settled slowly. What you see is millions of years of patience.",
}

# Words the AI must NEVER use — these are food/fabric metaphors
# that leak in when the AI doesn't have geological vocabulary
BANNED_FOOD_WORDS = [
    "chocolate", "honey", "oatmeal", "cocoa", "walnut", "chestnut",
    "mocha", "caramel", "vanilla", "cinnamon", "peanut", "butter",
    "cream", "berry", "cherry", "plum", "olive", "maple", "sugar",
    "toffee", "butterscotch", "marmalade", "jam", "citrus",
    "pecan", "molasses", "buttermilk", "tangerine", "maize",
    "persimmon", "cranberry", "matcha", "espresso", "tomato",
    "apricot", "peach", "chamois",
]

BANNED_FABRIC_WORDS = [
    "denim", "canvas", "silk", "velvet", "linen", "suede", "leather",
    "lace", "satin", "wool", "cotton", "corduroy", "tweed", "flannel",
]


def lookup_colors(color_list):
    """Look up geological descriptions for a list of detected colors.

    Args:
        color_list: list of color name strings (e.g., ["denim", "seafoam"])

    Returns:
        dict mapping color name -> geological description (only for matches)
    """
    if not color_list:
        return {}
    results = {}
    for color in color_list:
        name = color.lower().strip().replace(" ", "_")
        if name in COLOR_GEOLOGY:
            results[name] = COLOR_GEOLOGY[name]
        # Also try the raw form
        elif color.lower().strip() in COLOR_GEOLOGY:
            results[color.lower().strip()] = COLOR_GEOLOGY[color.lower().strip()]
    return results


def lookup_surfaces(surface_list):
    """Look up geological descriptions for a list of surface qualities.

    Args:
        surface_list: list of surface name strings (e.g., ["crackle", "luster"])

    Returns:
        dict mapping surface name -> geological description (only for matches)
    """
    if not surface_list:
        return {}
    results = {}
    for surface in surface_list:
        name = surface.lower().strip().replace(" ", "_")
        if name in SURFACE_GEOLOGY:
            results[name] = SURFACE_GEOLOGY[name]
    return results


def build_vocabulary_block(colors, surfaces, mood=None):
    """Build a vocabulary reference block to inject into AI prompts.

    Args:
        colors: list of detected color strings
        surfaces: list of detected surface quality strings
        mood: optional mood string

    Returns:
        Formatted string with geological descriptions for this piece
    """
    # Filter out banned food and fabric words BEFORE building the block
    _ALL_BANNED = set(BANNED_FOOD_WORDS) | set(BANNED_FABRIC_WORDS)
    colors = [c for c in colors if c.lower().strip() not in _ALL_BANNED]
    surfaces = [s for s in surfaces if s.lower().strip() not in _ALL_BANNED]

    lines = []

    color_descs = lookup_colors(colors)
    if color_descs:
        lines.append("COLOR ORIGINS (use these geological descriptions, NOT the raw color names):")
        for color, desc in color_descs.items():
            lines.append(f"  - {color}: {desc}")

    surface_descs = lookup_surfaces(surfaces)
    if surface_descs:
        lines.append("SURFACE ORIGINS (use these geological descriptions):")
        for surface, desc in surface_descs.items():
            lines.append(f"  - {surface}: {desc}")

    if mood and mood.lower().strip() in MOOD_GEOLOGY:
        lines.append(f"ATMOSPHERIC NOTE: {MOOD_GEOLOGY[mood.lower().strip()]}")

    return "\n".join(lines)


def check_banned_words(text):
    """Check text for banned food/fabric words. Returns list of violations found."""
    text_lower = text.lower()
    violations = []

    for word in BANNED_FOOD_WORDS:
        # Check as whole word to avoid false positives (e.g., "olive" in "olivine")
        import re
        if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
            violations.append(word)

    for word in BANNED_FABRIC_WORDS:
        import re
        if re.search(r'\b' + re.escape(word) + r'\b', text_lower):
            violations.append(word)

    return violations
