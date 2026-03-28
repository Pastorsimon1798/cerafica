#!/usr/bin/env python3
"""
Frame Generator for Ceramics Instagram

Creates stylized frames/overlays for pottery photos.
First use case: Planetary Exploration series with sci-fi HUD/Terminal aesthetic.

Architecture:
- FrameGenerator: Base class with common functionality
- PlanetaryFrameGenerator: HUD/Terminal style for planetary exploration
- SpaceBackground: Procedural star field + nebula generator
"""

import os
import random
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps, ImageChops

# Background removal
try:
    from rembg import remove, new_session
    REMBG_AVAILABLE = True
except ImportError:
    REMBG_AVAILABLE = False


# ============================================================================
# CONFIGURATION
# ============================================================================

# Canvas dimensions (4:5 Instagram portrait) — 2x for high quality
OUTPUT_WIDTH = 2160
OUTPUT_HEIGHT = 2700

# Color palette
COLORS = {
    "cyan_glow": (30, 195, 210),      # #1EC3D2 — matched from CeraficaIcon Gradient
    "cyan_dim": (15, 130, 155),       # #0F829B — dimmer variant of logo cyan
    "amber": (255, 170, 0),           # #FFAA00
    "white_soft": (255, 255, 255),    # #FFFFFF (used at 60% opacity)
    "space_black": (10, 10, 18),      # #0A0A12
    "nebula_purple": (42, 26, 58),    # #2A1A3A
    "nebula_teal": (10, 42, 42),      # #0A2A2A
}

# Typography
HEADER_HEIGHT = 100
FOOTER_HEIGHT = 620  # Scaled for 1920px height: lore + stats + brand
MARGIN = 40
LOGO_PATH = Path("/Users/simongonzalezdecruz/Library/Mobile Documents/com~apple~CloudDocs/Cerafica Design/PNGs/CeraficaIcon Gradient@4x.png")

# Font paths — fallback chain: JetBrains Mono → Fira Code → Menlo → default
_FONT_CANDIDATES = [
    # JetBrains Mono Nerd Font (user-installed)
    str(Path.home() / "Library/Fonts/JetBrainsMonoNerdFontMono-Regular.ttf"),
    str(Path.home() / "Library/Fonts/JetBrainsMonoNerdFontMono-Bold.ttf"),
    # Fira Code (user-installed)
    str(Path.home() / "Library/Fonts/FiraCode-Regular.ttf"),
    str(Path.home() / "Library/Fonts/FiraCode-Bold.ttf"),
    # Menlo (system)
    "Menlo.ttc",
    "/System/Library/Fonts/Menlo.ttc",
]


def _find_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a monospace font from the fallback chain."""
    # Try JetBrains Mono Bold or Fira Code Bold if bold requested
    bold_candidates = [
        str(Path.home() / "Library/Fonts/JetBrainsMonoNerdFontMono-Bold.ttf"),
        str(Path.home() / "Library/Fonts/FiraCode-Bold.ttf"),
    ]
    candidates = bold_candidates if bold else _FONT_CANDIDATES
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()

# Frame storage
FRAMED_OUTPUT_DIR = Path(__file__).parent.parent.parent.parent / "output" / "framed"

# Chemistry mappings (from validated planetary caption system)
COLOR_TO_CHEMISTRY = {
    "blue": "CuSO₄ (copper sulfate)",
    "green": "CuCO₃ (copper carbonate)",
    "green-blue": "CuCO₃·Cu(OH)₂ (malachite)",
    "rust": "Fe₂O₃ (iron oxide)",
    "brown": "Fe₂O₃·nH₂O (hydrated iron oxide)",
    "black": "C (carbon deposits)",
    "charcoal": "C (elemental carbon)",
    "purple": "MnO₂ (manganese dioxide)",
    "plum": "Mn₂O₃ (manganese oxide)",
    "bronze": "Cu (metallic copper)",
    "copper": "Cu (native copper)",
    "ochre": "FeO(OH)·nH₂O (limonite)",
    "gold": "FeO(OH) (goethite)",
    "white": "SiO₂ (silica)",
    "cream": "Al₂Si₂O₅(OH)₄ (kaolinite)",
    "tan": "Fe₂O₃ + SiO₂ (iron-stained silica)",
}

SURFACE_TO_GEOLOGY = {
    "crawling": "tectonic displacement",
    "variegation": "mineral stratification",
    "luster": "metallic crystallization",
    "speckled": "meteoritic inclusions",
    "rivulets": "volcanic flow channels",
    "crackle": "thermal shock fractures",
    "gloss": "rapid vitrification",
    "satin": "aeolian erosion",
    "matte": "unweathered surface",
    "crystalline": "slow-crystal formation",
}

# Map vision color vocabulary to chemistry keys
COLOR_FAMILY_MAP = {
    # Browns → brown/ochre/tan
    "toast": "brown", "cocoa": "brown", "chocolate": "brown",
    "espresso": "brown", "chestnut": "brown", "mahogany": "brown",
    "walnut": "brown", "pecan": "brown", "tobacco": "brown",
    "sienna": "ochre", "umber": "brown", "russet": "rust",
    "bronze": "bronze", "copper": "copper", "tan": "tan",
    "fawn": "tan", "molasses": "brown",
    "loam": "brown", "raw_umber": "ochre",
    "burnt_sienna": "ochre", "ochre": "ochre",
    "tenmoku": "brown", "oil-spot": "brown",
    "goethite": "ochre", "limonite": "ochre",
    # Reds → rust
    "rust": "rust", "brick": "rust", "garnet": "rust",
    "burgundy": "rust", "maroon": "rust", "oxblood": "rust",
    "terracotta": "rust", "dried_rose": "rust", "clay_red": "rust",
    "cranberry": "rust", "persimmon": "rust", "copper_red": "rust",
    "iron_red": "rust", "hematite": "rust", "cinnabar": "rust",
    "laterite": "rust", "bauxite": "rust",
    # Grays → charcoal
    "slate": "charcoal", "charcoal": "charcoal", "dove": "charcoal",
    "stone": "charcoal", "ash": "charcoal", "smoke": "charcoal",
    "pewter": "charcoal", "graphite": "charcoal", "flint": "charcoal",
    "steel": "charcoal", "pearl": "charcoal", "silver": "charcoal",
    "iron_gray": "charcoal", "smoky": "charcoal",
    "basalt": "charcoal", "pumice": "charcoal",
    "rhyolite": "charcoal", "diorite": "charcoal",
    "wad": "charcoal", "diatomite": "charcoal",
    # Whites/Creams → white/cream
    "bone": "white", "ivory": "cream", "cream": "cream",
    "buttermilk": "cream", "parchment": "cream", "oatmeal": "cream",
    "bisque": "cream", "porcelain": "white", "snow": "white",
    "alabaster": "white", "ecru": "cream", "chalk": "white",
    # Greens → green
    "celadon": "green", "sage": "green", "olive": "green",
    "moss": "green", "seafoam": "green", "oribe": "green",
    "jade": "green", "pine": "green", "eucalyptus": "green",
    "sea_green": "green", "matcha": "green", "lichen": "green",
    "malachite": "green", "verdigris": "green",
    # Blues → blue
    "chun_blue": "blue", "teal": "blue", "slate_blue": "blue",
    "ice_blue": "blue", "denim": "blue", "navy": "blue",
    "cerulean": "blue", "azure": "blue", "midnight": "blue",
    "powder_blue": "blue", "cobalt": "blue", "indigo": "blue",
    "azurite": "blue", "chrysocolla": "blue",
    # Oranges/Yellows → gold/ochre
    "shino": "ochre", "amber": "gold", "honey": "gold",
    "gold": "gold", "tangerine": "gold", "maize": "gold",
    "kaki": "gold", "chamois": "gold",
    "naples_yellow": "gold", "raw_sienna": "gold",
    "crocoite": "gold",
    # Purples → purple/plum
    "plum": "plum", "purple": "purple", "lilac": "purple",
    "lavender": "purple", "mauve": "purple", "wisteria": "purple",
    "aubergine": "plum",
    # Blacks → black/charcoal
    "black": "black", "obsidian": "black", "jet": "black",
    "onyx": "black", "raven": "black",
}


def normalize_vision_color(color: str) -> str | None:
    """Convert vision color name to chemistry key."""
    return COLOR_FAMILY_MAP.get(color.lower().replace(" ", "_"))


def colors_to_chemistry_string(colors: list) -> str | None:
    """Convert primary colors to chemistry formula string."""
    formulas = []
    seen = set()
    for color in colors[:3]:  # Max 3
        key = normalize_vision_color(color)
        if key and key not in seen:
            formulas.append(COLOR_TO_CHEMISTRY[key])
            seen.add(key)
    return " | ".join(formulas) if formulas else None


def surface_to_geology_string(qualities: list) -> str | None:
    """Convert surface qualities to geology description."""
    terms = []
    for q in qualities[:2]:  # Max 2
        if q in SURFACE_TO_GEOLOGY:
            terms.append(SURFACE_TO_GEOLOGY[q])
    return ", ".join(terms) if terms else None


def hypotheses_to_chemistry_string(hypotheses) -> str | None:
    """
    Extract chemistry language from vision analysis hypotheses.

    Parses hypothesis text for oxide/compound references (e.g.,
    "copper oxide in reduction", "iron oxide (5-10%)") and formats
    them for the frame's COMPOSITION field.

    Falls back to None if no chemistry language is found.
    """
    import re

    if not hypotheses:
        return None

    # Normalize to list of strings
    if isinstance(hypotheses, str):
        texts = [hypotheses]
    elif isinstance(hypotheses, list):
        texts = [str(h) for h in hypotheses if h]
    else:
        return None

    # Extract oxide/compound references from hypothesis text
    # Match patterns like "copper oxide", "iron oxide (5-10%)", "manganese dioxide", etc.
    compound_pattern = re.compile(
        r'((?:iron|copper|manganese|cobalt|chromium|nickel|titanium|zinc|'
        r'vanadium|barium|tin|lead|silicon|aluminum|calcium|magnesium|potassium|sodium|'
        r'lithium|strontium|cerium|copper|carbon)\s+\w+\s*(?:\([^)]*\))?)',
        re.IGNORECASE
    )

    compounds = []
    seen = set()
    for text in texts[:2]:  # Check first 2 hypotheses
        matches = compound_pattern.findall(text)
        for match in matches:
            key = match.lower().rstrip('.,;')
            if key not in seen:
                compounds.append(match.strip())
                seen.add(key)

    if compounds:
        # Capitalize first letter of each compound
        formatted = [c[0].upper() + c[1:] if c else c for c in compounds[:3]]
        return " | ".join(formatted)

    return None


def extract_chemistry_from_hypotheses(hypotheses) -> str | None:
    """
    Extract just the chemistry-relevant portion from hypotheses for ANOMALIES field.

    Scans all hypotheses, picks the one with the most chemistry references,
    and returns a focused excerpt (80 chars max).
    """
    import re

    if not hypotheses:
        return None

    if isinstance(hypotheses, list):
        texts = [str(h) for h in hypotheses if h]
    else:
        texts = [str(hypotheses)]

    if not texts:
        return None

    # Pattern to find chemistry-relevant text segments
    chemistry_pattern = re.compile(
        r'((?:iron|copper|manganese|cobalt|carbon|oxide|reduction|'
        r'oxidation|sodium|silica|ash|wood.fired|kiln|ash.glaze|'
        r'shino|wadding|sagger|salt.fired)[^.]*)',
        re.IGNORECASE
    )

    # Score each hypothesis by number of oxide/compound references (weighted higher)
    oxide_pattern = re.compile(r'(?:iron|copper|manganese|cobalt|nickel|titanium|zinc)\s+oxide', re.IGNORECASE)

    best_text = None
    best_score = 0
    for text in texts:
        matches = chemistry_pattern.findall(text)
        oxide_matches = oxide_pattern.findall(text)
        # Score: oxide references worth 3x, general chemistry references worth 1x
        score = len(oxide_matches) * 3 + len(matches)
        if score > best_score:
            best_score = score
            best_text = text

    if best_text and best_score > 0:
        matches = chemistry_pattern.findall(best_text)
        combined = " ".join(m.strip() for m in matches[:2])
        combined = combined.strip(' ,;.')
        if len(combined) > 80:
            combined = combined[:77] + "..."
        return combined if combined else None

    # No chemistry found — return truncated first hypothesis as fallback
    truncated = texts[0].strip()[:80]
    if len(texts[0].strip()) > 80:
        truncated = truncated[:77] + "..."
    return truncated if truncated else None


def wrap_text(text: str, font, max_width: int, draw: ImageDraw.Draw) -> list[str]:
    """Wrap text to fit within max_width pixels, returning list of lines."""
    if not text:
        return []
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


# ============================================================================
# SPACE BACKGROUND GENERATOR
# ============================================================================

class SpaceBackground:
    """Generates procedural space backgrounds with stars and nebulae."""

    def __init__(self, width: int, height: int, seed: Optional[int] = None,
                 accent_color: Optional[Tuple[int, int, int]] = None):
        self.width = width
        self.height = height
        self.accent_color = accent_color
        if seed is not None:
            random.seed(seed)

    def generate(self) -> Image.Image:
        """Generate a complete space background."""
        bg = self._generate_base()
        bg = self._add_stars(bg)
        return bg

    def _generate_base(self) -> Image.Image:
        """Generate space background without stars (for per-frame twinkling)."""
        # Start with deep black
        bg = Image.new('RGB', (self.width, self.height), COLORS["space_black"])

        # Add nebula gradients
        bg = self._add_nebula(bg)

        # Add vignette for card-frame depth
        bg = self._add_vignette(bg)

        # Add scan lines
        bg = self._add_scan_lines(bg)

        return bg

    def _add_nebula(self, bg: Image.Image) -> Image.Image:
        """Add visible, colorful nebula gradients. Uses accent color from piece palette if available."""
        # Create nebula layer
        nebula = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(nebula)

        # Build nebula color palette — bright enough to be visible on black
        if self.accent_color:
            r, g, b = self.accent_color
            # Boost accent to vivid nebula color
            piece_nebula = (
                min(255, r + 80),
                min(255, g + 40),
                min(255, b + 80),
            )
            nebula_colors = [piece_nebula, (140, 70, 180), (40, 130, 130)]
        else:
            nebula_colors = [(140, 70, 180), (40, 130, 130)]

        # Soft, blurry nebulae — fewer, more transparent
        num_nebulae = random.randint(3, 6)
        for _ in range(num_nebulae):
            x = random.randint(-100, self.width + 100)
            y = random.randint(-100, self.height + 100)
            radius = random.randint(200, 500)

            # Choose color from palette
            color = random.choice(nebula_colors)

            # Draw radial gradient with soft, low alpha
            for r in range(radius, 0, -12):
                alpha = int(45 * (1 - r / radius))
                rgba = (*color, alpha)
                draw.ellipse(
                    [x - r, y - r, x + r, y + r],
                    fill=rgba
                )

        # Subtle accent glow near center for depth
        cx, cy = self.width // 2, self.height // 2
        accent_radius = random.randint(300, 450)
        accent_color = self.accent_color or (80, 40, 120)
        for r in range(accent_radius, 0, -10):
            alpha = int(25 * (1 - r / accent_radius))
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*accent_color, alpha))

        # Blur the nebula layer for softness
        nebula = nebula.filter(ImageFilter.GaussianBlur(radius=40))

        # Composite
        bg.paste(Image.alpha_composite(bg.convert('RGBA'), nebula).convert('RGB'))
        return bg

    def _add_vignette(self, bg: Image.Image) -> Image.Image:
        """Add subtle darkening at edges for card-frame depth using layered ellipses."""
        vig = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(vig)

        cx, cy = self.width // 2, self.height // 2
        max_radius = int((cx ** 2 + cy ** 2) ** 0.5)

        # Draw concentric ellipses from outside in, each slightly less opaque
        for r in range(max_radius, int(max_radius * 0.5), -20):
            t = (r - max_radius * 0.5) / (max_radius * 0.5)
            alpha = int(100 * t * t)  # Quadratic falloff — subtle in center, stronger at edges
            alpha = min(alpha, 100)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(0, 0, 0, alpha), width=22)

        return Image.alpha_composite(bg.convert('RGBA'), vig).convert('RGB')

    def _add_stars(self, bg: Image.Image) -> Image.Image:
        """Add random star field."""
        draw = ImageDraw.Draw(bg)
        self._draw_stars_on(draw, self.width, self.height)
        return bg

    @staticmethod
    def generate_star_layer(width: int, height: int, seed: int) -> Image.Image:
        """Generate a single star layer as RGBA for twinkling compositing."""
        layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        SpaceBackground._draw_stars_on(draw, width, height, seed=seed)
        return layer

    @staticmethod
    def _draw_stars_on(draw, width: int, height: int, seed: int | None = None) -> None:
        """Draw stars onto a given ImageDraw object."""
        rng = random.Random(seed)
        num_stars = int((width * height) / 800)

        for _ in range(num_stars):
            x = rng.randint(0, width)
            y = rng.randint(0, height)

            size = rng.choices([1, 1, 1, 2, 2, 3], weights=[50, 30, 10, 5, 3, 2])[0]
            brightness = rng.randint(150, 255)

            if rng.random() < 0.1:
                r = min(255, brightness + rng.randint(0, 30))
                g = brightness
                b = min(255, brightness + rng.randint(0, 50))
            elif rng.random() < 0.1:
                r = min(255, brightness + rng.randint(0, 50))
                g = min(255, brightness + rng.randint(0, 30))
                b = brightness
            else:
                r = g = b = brightness

            if size == 1:
                draw.point((x, y), fill=(r, g, b))
            else:
                draw.ellipse([x - size, y - size, x + size, y + size], fill=(r, g, b))

    def _add_scan_lines(self, bg: Image.Image) -> Image.Image:
        """Add subtle CRT-style scan lines."""
        scan = Image.new('RGBA', (self.width, self.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(scan)

        # Horizontal lines every 2px
        for y in range(0, self.height, 2):
            draw.line([(0, y), (self.width, y)], fill=(0, 0, 0, 12))  # 5% opacity

        return Image.alpha_composite(bg.convert('RGBA'), scan).convert('RGB')


# ============================================================================
# BASE FRAME GENERATOR
# ============================================================================

class FrameGenerator:
    """Base class for frame generators."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or FRAMED_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_frame(self, image_path: str, data: Dict[str, Any]) -> Image.Image:
        """
        Main pipeline - override in subclasses.

        Args:
            image_path: Path to source image
            data: Series-specific data for frame content

        Returns:
            Framed PIL Image
        """
        raise NotImplementedError("Subclasses must implement generate_frame")

    def _normalize_orientation(self, image: Image.Image,
                                accent_color: Optional[Tuple[int, int, int]] = None,
                                website: bool = False) -> Tuple[Image.Image, Image.Image, Tuple[int, int, int, int]]:
        """
        Normalize image to 4:5 orientation with space background.

        All outputs: 1080 x 1350px
        The source image is scaled to ~92% for dominant visual presence.
        Background is removed and replaced with space.

        Args:
            image: Source image
            accent_color: Optional accent color for color-aware nebulae
            website: If True, center pottery and use full canvas (no header/footer offsets)

        Returns:
            Tuple of (composited_image, alpha_mask, bounding_box)
            bounding_box is (x, y, width, height) of the placed piece on canvas
        """
        # Create space background with accent color for color-aware nebulae
        space = SpaceBackground(OUTPUT_WIDTH, OUTPUT_HEIGHT, accent_color=accent_color).generate()

        # Remove background using rembg
        if REMBG_AVAILABLE:
            try:
                # Create session with isnet-general-use model - better for objects
                session = new_session(model_name='isnet-general-use')
                # rembg returns RGBA with transparent background
                image_no_bg = remove(image, session=session, post_process_mask=True)
                image = image_no_bg
            except Exception as e:
                print(f"Warning: Background removal with isnet failed, trying default: {e}")
                try:
                    # Fall back to default model (no session = u2net)
                    image_no_bg = remove(image, post_process_mask=True)
                    image = image_no_bg
                except Exception as e2:
                    print(f"Warning: Background removal failed, using original: {e2}")
                    if image.mode != 'RGBA':
                        image = image.convert('RGBA')

        if website:
            # Website mode: centered, full canvas, no HUD chrome
            margin_ratio = 0.85
            max_width = int(OUTPUT_WIDTH * margin_ratio)
            max_height = int(OUTPUT_HEIGHT * margin_ratio)
            x_offset = 0  # centered
            y_offset = 0  # full vertical space
        else:
            # Instagram mode: offset left, account for header/footer
            margin_ratio = 0.82
            max_width = int(OUTPUT_WIDTH * margin_ratio)
            usable_height = OUTPUT_HEIGHT - HEADER_HEIGHT - FOOTER_HEIGHT
            max_height = int(usable_height * margin_ratio)
            x_offset = -100  # shift left to balance zoom panels on right
            y_offset = HEADER_HEIGHT  # start below header

        # Calculate scale to fit within max dimensions
        img_ratio = image.width / image.height
        max_ratio = max_width / max_height

        if img_ratio > max_ratio:
            # Image is wider - fit to width
            new_width = max_width
            new_height = int(max_width / img_ratio)
        else:
            # Image is taller - fit to height
            new_height = max_height
            new_width = int(max_height * img_ratio)

        # Resize image (preserve alpha channel if present)
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Ensure RGBA for compositing
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        # Convert space to RGBA for alpha compositing
        space_rgba = space.convert('RGBA')

        if website:
            x = (OUTPUT_WIDTH - new_width) // 2
            y = (OUTPUT_HEIGHT - new_height) // 2
        else:
            x = (OUTPUT_WIDTH - new_width) // 2 + x_offset
            usable_height = OUTPUT_HEIGHT - HEADER_HEIGHT - FOOTER_HEIGHT
            y = y_offset + (usable_height - new_height) // 2

        # Extract alpha mask for rim light and reticle
        alpha_mask = image.split()[3]  # Get alpha channel

        # Composite image onto space background using alpha channel
        space_rgba.paste(image, (x, y), image)  # Third arg is mask

        # Convert back to RGB
        composite = space_rgba.convert('RGB')
        bbox = (x, y, new_width, new_height)
        return composite, alpha_mask, bbox

    def _smart_blur_background(self, image: Image.Image, blur_radius: int = 40) -> Image.Image:
        """
        Apply Gaussian blur to background while keeping subject sharp.

        This is a simplified version - for better results, implement
        subject detection/masking.
        """
        # For now, apply a subtle overall blur to soften edges
        # Full subject detection would require ML model
        return image.filter(ImageFilter.GaussianBlur(radius=2))

    def save_frame(self, image: Image.Image, original_path: str, series: str = "frame") -> str:
        """
        Save framed image to output directory.

        Args:
            image: Framed PIL Image
            original_path: Original image path (used for naming)
            series: Series name for subdirectory

        Returns:
            Path to saved framed image
        """
        from datetime import datetime
        date_dir = self.output_dir / datetime.now().strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)

        original_name = Path(original_path).stem
        output_name = f"{original_name}_{series}.jpg"
        output_path = date_dir / output_name

        image.save(output_path, "JPEG", quality=98, subsampling=0)

        return str(output_path)


# ============================================================================
# PLANETARY FRAME GENERATOR
# ============================================================================

class PlanetaryFrameGenerator(FrameGenerator):
    """
    HUD/Terminal style frame for planetary exploration series.

    Visual style: Retro-futuristic sci-fi data display
    """

    def generate_frame(self, image_path: str, planet_data: Dict[str, Any]) -> Image.Image:
        """
        Generate planetary exploration frame.

        Args:
            image_path: Path to pottery photo
            planet_data: Dict with keys:
                - planet_name: Name of the planet
                - sector: Sector designation
                - surface_geology: Description of surface
                - log_number: Exploration log number (optional, auto-generated if missing)
                - light_direction: Optional str ("top", "side", "bottom") for directional glow

        Returns:
            Framed 1080x1350 PIL Image
        """
        # Load source image
        source = Image.open(image_path)

        # Apply EXIF orientation (fixes iPhone rotation issues)
        source = ImageOps.exif_transpose(source)

        # Subtle enhancement: make pottery pop against dark space
        source = ImageEnhance.Contrast(source).enhance(1.1)
        source = ImageEnhance.Color(source).enhance(1.15)

        if source.mode != 'RGB':
            source = source.convert('RGB')

        # Sample accent color from source for color-aware nebulae
        accent_color = self._sample_accent_color(source)

        # Step 1: Normalize to 4:5 with space background
        canvas, alpha_mask, bbox = self._normalize_orientation(source, accent_color=accent_color)

        # Step 2: Add glow around center (where piece should be)
        light_direction = planet_data.get('light_direction', None)
        canvas = self._add_center_glow(canvas, source, light_direction=light_direction)

        # Step 3: Add rim light on pottery edges
        canvas = self._add_rim_light(canvas, alpha_mask, bbox, light_direction=light_direction)

        # Step 4: Apply HUD overlay
        canvas = self._apply_hud_overlay(canvas, planet_data)

        # Step 6: Add satellite zoom panels to footer area (after HUD so they overlay)
        canvas = self._add_zoom_panels(canvas, alpha_mask, bbox)

        return canvas

    def generate_website_frame(self, image_path: str, planet_data: Dict[str, Any] = None) -> Image.Image:
        """
        Generate website product frame — pottery + space bg + glow + zoom panels, no HUD.

        The website IS the frame, so we skip all HUD chrome (header, footer, targeting
        reticle, chemistry formulas, logo). The pottery is centered on the space background
        with rim lighting and zoom panels repositioned to corners.

        Args:
            image_path: Path to pottery photo
            planet_data: Optional dict (used for light_direction)

        Returns:
            2160x2700 PIL Image
        """
        if planet_data is None:
            planet_data = {}

        source = Image.open(image_path)
        source = ImageOps.exif_transpose(source)

        # Subtle enhancement
        source = ImageEnhance.Contrast(source).enhance(1.1)
        source = ImageEnhance.Color(source).enhance(1.15)

        if source.mode != 'RGB':
            source = source.convert('RGB')

        accent_color = self._sample_accent_color(source)

        # Step 1: Normalize with website=True (centered, no header/footer offsets)
        canvas, alpha_mask, bbox = self._normalize_orientation(source, accent_color=accent_color, website=True)

        # Step 2: Center glow
        light_direction = planet_data.get('light_direction', None)
        canvas = self._add_center_glow(canvas, source, light_direction=light_direction)

        # Step 3: Rim light
        canvas = self._add_rim_light(canvas, alpha_mask, bbox, light_direction=light_direction)

        # Step 4: Zoom panels (website layout — positioned at corners)
        canvas = self._add_zoom_panels(canvas, alpha_mask, bbox, website=True)

        # NO HUD overlay, NO targeting reticle — the website is the frame
        return canvas

    def _sample_accent_color(self, image: Image.Image) -> Tuple[int, int, int]:
        """Sample dominant color from image center for color-aware effects."""
        sample = image.resize((50, 50))
        return sample.getpixel((25, 25))

    def _add_center_glow(self, canvas: Image.Image, source: Image.Image,
                          light_direction: Optional[str] = None) -> Image.Image:
        """Add soft glow around the center area, offset by light direction."""
        # Create glow layer
        glow = Image.new('RGBA', (OUTPUT_WIDTH, OUTPUT_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(glow)

        # Center point with light-aware offset
        cx, cy = OUTPUT_WIDTH // 2, OUTPUT_HEIGHT // 2
        offset_x, offset_y = 0, -30  # Default slight upward offset

        if light_direction:
            if light_direction == "side":
                offset_x = random.choice([-80, 80])  # Random left or right
                offset_y = -10
            elif light_direction == "top":
                offset_x = 0
                offset_y = -80
            elif light_direction == "bottom":
                offset_x = 0
                offset_y = 40

        # Get dominant color from source (simplified - use center pixel)
        sample = source.resize((50, 50))
        center_color = sample.getpixel((25, 25))

        # Create radial glow
        max_radius = min(OUTPUT_WIDTH, OUTPUT_HEIGHT) // 2 - 50
        for r in range(max_radius, 0, -5):
            alpha = int(15 * (1 - r / max_radius))
            rgba = (*center_color, alpha)
            draw.ellipse(
                [cx + offset_x - r, cy + offset_y - r,
                 cx + offset_x + r, cy + offset_y + r],
                fill=rgba
            )

        # Apply blur to glow
        glow = glow.filter(ImageFilter.GaussianBlur(radius=60))

        return Image.alpha_composite(canvas.convert('RGBA'), glow).convert('RGB')

    def _add_rim_light(self, canvas: Image.Image, alpha_mask: Image.Image,
                        bbox: Tuple[int, int, int, int],
                        light_direction: Optional[str] = None) -> Image.Image:
        """Add subtle rim light along pottery edges for studio-lit floating effect."""
        if not REMBG_AVAILABLE or alpha_mask is None:
            return canvas

        bx, by, bw, bh = bbox

        # Detect edges from alpha mask
        edges = alpha_mask.filter(ImageFilter.FIND_EDGES)

        # Create rim light layer
        rim = Image.new('RGBA', (OUTPUT_WIDTH, OUTPUT_HEIGHT), (0, 0, 0, 0))

        # Determine rim light offset based on light direction
        shift_x, shift_y = 3, -3  # Default: top-left light
        if light_direction == "side":
            shift_x, shift_y = -4, 0
        elif light_direction == "bottom":
            shift_x, shift_y = 0, 4
        elif light_direction == "top":
            shift_x, shift_y = 0, -4

        # Shift edges toward light source for directional rim
        shifted_edges = ImageChops.offset(edges, shift_x, shift_y)

        # Color the edges with cyan glow
        edge_rgba = Image.new('RGBA', edges.size, (0, 0, 0, 0))
        edge_rgba = Image.composite(
            Image.new('RGBA', edges.size, (*COLORS["cyan_glow"], 60)),
            edge_rgba,
            edges
        )

        # Also add shifted edge for directional feel
        shifted_rgba = Image.new('RGBA', shifted_edges.size, (0, 0, 0, 0))
        shifted_rgba = Image.composite(
            Image.new('RGBA', shifted_edges.size, (*COLORS["cyan_glow"], 35)),
            shifted_rgba,
            shifted_edges
        )

        # Place on full canvas
        rim.paste(edge_rgba, (bx, by))
        rim.paste(shifted_rgba, (bx, by))

        # Blur for soft glow
        rim = rim.filter(ImageFilter.GaussianBlur(radius=2))

        return Image.alpha_composite(canvas.convert('RGBA'), rim).convert('RGB')

    def _add_targeting_reticle(self, canvas: Image.Image, alpha_mask: Image.Image,
                                bbox: Tuple[int, int, int, int]) -> Image.Image:
        """Add targeting reticle brackets around the pottery piece."""
        if not REMBG_AVAILABLE or alpha_mask is None:
            return canvas

        bx, by, bw, bh = bbox

        # Find actual bounding box from alpha mask (tighter than image bbox)
        alpha_bbox = alpha_mask.getbbox()
        if not alpha_bbox:
            return canvas

        # Map alpha bbox to canvas coordinates
        padding = 20
        rx = bx + alpha_bbox[0] - padding
        ry = by + alpha_bbox[1] - padding
        rx2 = bx + alpha_bbox[2] + padding
        ry2 = by + alpha_bbox[3] + padding

        reticle = Image.new('RGBA', (OUTPUT_WIDTH, OUTPUT_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(reticle)

        bracket_len = min(40, (rx2 - rx) // 4, (ry2 - ry) // 4)
        color = (*COLORS["cyan_glow"], 160)

        # Corner brackets
        # Top-left
        draw.line([(rx, ry), (rx + bracket_len, ry)], fill=color, width=1)
        draw.line([(rx, ry), (rx, ry + bracket_len)], fill=color, width=1)
        # Top-right
        draw.line([(rx2, ry), (rx2 - bracket_len, ry)], fill=color, width=1)
        draw.line([(rx2, ry), (rx2, ry + bracket_len)], fill=color, width=1)
        # Bottom-left
        draw.line([(rx, ry2), (rx + bracket_len, ry2)], fill=color, width=1)
        draw.line([(rx, ry2), (rx, ry2 - bracket_len)], fill=color, width=1)
        # Bottom-right
        draw.line([(rx2, ry2), (rx2 - bracket_len, ry2)], fill=color, width=1)
        draw.line([(rx2, ry2), (rx2, ry2 - bracket_len)], fill=color, width=1)

        # Crosshair lines extending from brackets (with gap near center)
        mid_x = (rx + rx2) // 2
        mid_y = (ry + ry2) // 2
        gap = min(30, (rx2 - rx) // 6)
        crosshair_color = (*COLORS["cyan_glow"], 80)

        # Horizontal crosshair
        draw.line([(rx + bracket_len + 5, mid_y), (mid_x - gap, mid_y)], fill=crosshair_color, width=1)
        draw.line([(mid_x + gap, mid_y), (rx2 - bracket_len - 5, mid_y)], fill=crosshair_color, width=1)
        # Vertical crosshair
        draw.line([(mid_x, ry + bracket_len + 5), (mid_x, mid_y - gap)], fill=crosshair_color, width=1)
        draw.line([(mid_x, mid_y + gap), (mid_x, ry2 - bracket_len - 5)], fill=crosshair_color, width=1)

        # Small tick marks along top bracket
        tick_len = 6
        for i in range(1, 4):
            tx = rx + bracket_len * i // 4
            draw.line([(tx, ry - tick_len), (tx, ry)], fill=(*COLORS["cyan_glow"], 100), width=1)

        return Image.alpha_composite(canvas.convert('RGBA'), reticle).convert('RGB')

    def _add_zoom_panels(self, canvas: Image.Image, alpha_mask: Image.Image,
                          bbox: Tuple[int, int, int, int],
                          website: bool = False) -> Image.Image:
        """Add satellite imagery zoom panels with detail-scoring magnification.

        Args:
            canvas: The composited image
            alpha_mask: Alpha mask of the pottery piece
            bbox: Bounding box (x, y, width, height) on canvas
            website: If True, position panels at corners instead of top-right sidebar
        """
        if not REMBG_AVAILABLE or alpha_mask is None:
            return canvas

        bx, by, bw, bh = bbox

        # Find tight bounding box from alpha mask
        alpha_bbox = alpha_mask.getbbox()
        if not alpha_bbox or (alpha_bbox[2] - alpha_bbox[0]) < 40 or (alpha_bbox[3] - alpha_bbox[1]) < 40:
            return canvas

        panel_width = 300
        panel_border = 4
        panel_gap = 36
        num_panels = 3

        ax1, ay1, ax2, ay2 = alpha_bbox
        piece_w = ax2 - ax1
        piece_h = ay2 - ay1

        # --- Detail scoring: find most interesting regions via color + texture ---
        # Work on the alpha mask region to find textured areas
        piece_region = alpha_mask.crop((ax1, ay1, ax2, ay2))
        piece_color = canvas.crop((bx + ax1, by + ay1, bx + ax2, by + ay2)).convert('HSV')
        piece_gray = canvas.crop((bx + ax1, by + ay1, bx + ax2, by + ay2)).convert('L')

        grid_rows, grid_cols = 4, 4
        cell_w = piece_w / grid_cols
        cell_h = piece_h / grid_rows

        # Score each cell by blended color richness + edge texture
        raw_scores = []  # (row, col, color_score, texture_score)
        for row in range(grid_rows):
            for col in range(grid_cols):
                cx1 = int(col * cell_w)
                cy1 = int(row * cell_h)
                cx2 = int((col + 1) * cell_w)
                cy2 = int((row + 1) * cell_h)
                cx2 = min(cx2, piece_color.width)
                cy2 = min(cy2, piece_color.height)

                cell_color = piece_color.crop((cx1, cy1, cx2, cy2))
                cell_gray = piece_gray.crop((cx1, cy1, cx2, cy2))
                if cell_color.width < 3 or cell_color.height < 3:
                    raw_scores.append((row, col, 0, 0))
                    continue

                # Check alpha coverage in this cell
                cell_alpha = piece_region.crop((cx1, cy1, cx2, cy2))
                alpha_pixels = list(cell_alpha.getdata())
                coverage = sum(1 for p in alpha_pixels if p > 128) / max(len(alpha_pixels), 1)
                if coverage < 0.6:
                    raw_scores.append((row, col, 0, 0))
                    continue

                # Color score: saturation + hue diversity
                hsv_pixels = list(cell_color.getdata())
                saturations = [s for _, s, _ in hsv_pixels]
                hues = [h for h, _, _ in hsv_pixels]
                avg_sat = sum(saturations) / len(saturations)
                if len(hues) > 1:
                    hue_mean = sum(hues) / len(hues)
                    hue_var = sum((h - hue_mean) ** 2 for h in hues) / len(hues)
                else:
                    hue_var = 0
                color_score = hue_var * 3 + avg_sat

                # Texture score: gradient magnitude
                gray_pixels = list(cell_gray.getdata())
                w = cell_gray.width
                tex_score = 0
                for py in range(cell_gray.height):
                    for px in range(w):
                        idx = py * w + px
                        if px < w - 1:
                            tex_score += abs(gray_pixels[idx] - gray_pixels[idx + 1])
                        if py < cell_gray.height - 1:
                            tex_score += abs(gray_pixels[idx] - gray_pixels[idx + w])

                raw_scores.append((row, col, color_score, tex_score))

        # Normalize each metric to 0-1, then blend
        max_color = max((s[2] for s in raw_scores), default=1) or 1
        max_tex = max((s[3] for s in raw_scores), default=1) or 1
        cell_scores = []
        for row, col, cs, ts in raw_scores:
            norm_color = cs / max_color
            norm_tex = ts / max_tex
            score = norm_color * 0.6 + norm_tex * 0.4
            # Penalize bottom rows (foot region) — prefer glazed upper areas
            vertical_ratio = row / max(grid_rows - 1, 1)
            if vertical_ratio > 0.7:
                score *= 0.05  # near-total block on bottom 30% (foot ring)
            elif vertical_ratio > 0.4:
                score *= 0.5  # moderate penalty on lower-middle rows
            cell_scores.append((row, col, score))

        # Sort by score descending
        cell_scores.sort(key=lambda x: x[2], reverse=True)
        active = [(r, c, s) for r, c, s in cell_scores if s > 0]

        # Select cells with horizontal diversity — guarantee picks from both sides
        selected = []

        def is_adjacent(row, col):
            return any(abs(row - sr) <= 1 and abs(col - sc) <= 1
                       for sr, sc in selected)

        if active:
            # 1) Best cell overall
            selected.append((active[0][0], active[0][1]))

            # 2) Best cell from opposite horizontal half
            first_zone = active[0][1] // 2  # 0=left, 1=right
            for row, col, score in active:
                if not is_adjacent(row, col) and col // 2 != first_zone:
                    selected.append((row, col))
                    break

            # 3) Best remaining cell (any zone, non-adjacent)
            for row, col, score in active:
                if not is_adjacent(row, col):
                    selected.append((row, col))
                if len(selected) >= num_panels:
                    break

        # Fallback: if fewer than 3 selected, pick remaining top-scored
        if len(selected) < num_panels:
            for row, col, score in cell_scores:
                if score == 0:
                    break
                if (row, col) not in selected:
                    selected.append((row, col))
                if len(selected) >= num_panels:
                    break

        # Build crop regions from selected cells
        # Fixed crop size: 150px → 300px panel = exactly 2x zoom every time
        crop_pixels = 200  # 300 / 1.5 = 1.5x zoom
        regions = []
        for idx, (row, col) in enumerate(selected):
            center_x = ax1 + (col + 0.5) * cell_w
            center_y = ay1 + (row + 0.5) * cell_h
            half_size = crop_pixels // 2
            rx1 = int(center_x - half_size)
            ry1 = int(center_y - half_size)
            rx2 = int(center_x + half_size)
            ry2 = int(center_y + half_size)
            regions.append((rx1, ry1, rx2, ry2))

        overlay = Image.new('RGBA', (OUTPUT_WIDTH, OUTPUT_HEIGHT), (0, 0, 0, 0))

        # Sort regions by vertical center so connector lines never intersect
        regions.sort(key=lambda r: (r[1] + r[3]) / 2)

        if website:
            # Website mode: distribute panels to corners/edges of canvas
            # Use smaller panels for corner placement
            panel_width_web = 240
            corner_gap = 30
            # Pre-compute positions: bottom-left, bottom-right, top-right
            corner_positions = [
                (corner_gap, OUTPUT_HEIGHT - panel_width_web - corner_gap),           # bottom-left
                (OUTPUT_WIDTH - panel_width_web - corner_gap,
                 OUTPUT_HEIGHT - panel_width_web - corner_gap),                        # bottom-right
                (OUTPUT_WIDTH - panel_width_web - corner_gap, corner_gap),             # top-right
            ]
        else:
            # Instagram mode: position panels at top-right of art frame area
            sidebar_x = OUTPUT_WIDTH - panel_width - MARGIN
            start_y = HEADER_HEIGHT + 30

        for i, (rx1, ry1, rx2, ry2) in enumerate(regions):
            # Clamp to mask bounds
            rx1, ry1 = max(0, int(rx1)), max(0, int(ry1))
            rx2, ry2 = min(alpha_mask.width, int(rx2)), min(alpha_mask.height, int(ry2))

            if rx2 - rx1 < 5 or ry2 - ry1 < 5:
                continue

            # Crop region from canvas
            crop_region = canvas.crop((
                bx + rx1, by + ry1,
                bx + rx2, by + ry2
            )).convert('RGBA')

            # Resize to panel size (square)
            if website:
                crop_resized = crop_region.resize((panel_width_web, panel_width_web), Image.Resampling.LANCZOS)
            else:
                crop_resized = crop_region.resize((panel_width, panel_width), Image.Resampling.LANCZOS)

            # Panel position
            draw = ImageDraw.Draw(overlay)

            if website:
                if i >= len(corner_positions):
                    continue
                px, py = corner_positions[i]
                draw.rectangle(
                    [px - panel_border, py - panel_border,
                     px + panel_width_web + panel_border, py + panel_width_web + panel_border],
                    fill=(*COLORS["cyan_dim"], 140)
                )
                overlay.paste(crop_resized, (px, py))
                # No ZOOM label in website mode — cleaner look
            else:
                py = start_y + i * (panel_width + panel_gap)
                draw.rectangle(
                    [sidebar_x - panel_border, py - panel_border,
                     sidebar_x + panel_width + panel_border, py + panel_width + panel_border],
                    fill=(*COLORS["cyan_dim"], 180)
                )
                overlay.paste(crop_resized, (sidebar_x, py))
                # Label
                font_label = _find_font(20)
                label = f"ZOOM-{i + 1}"
                draw.text((sidebar_x + 4, py - panel_border - 28), label,
                         font=font_label, fill=(*COLORS["cyan_glow"], 200))

        return Image.alpha_composite(canvas.convert('RGBA'), overlay).convert('RGB')

    def _apply_hud_overlay(self, canvas: Image.Image, planet_data: Dict[str, Any]) -> Image.Image:
        """Apply HUD frame, text, and decorative elements."""
        # Convert to RGBA for overlay
        hud = canvas.convert('RGBA')
        draw = ImageDraw.Draw(hud)

        # Get or generate log number
        log_number = planet_data.get('log_number', random.randint(1, 999))

        # Load fonts via fallback chain
        font_header = _find_font(56, bold=True)
        font_data = _find_font(36)
        font_small = _find_font(28)

        # ========== HEADER BAR ==========
        # Header background
        draw.rectangle([0, 0, OUTPUT_WIDTH, HEADER_HEIGHT], fill=(0, 0, 0, 200))

        # Header text — planet name
        planet_name = planet_data.get('planet_name', None)
        draw.text((MARGIN, 24), "Cerafica Exploration Log", font=font_header, fill=COLORS["cyan_glow"])
        if planet_name:
            name_text = planet_name.title()
            name_w = font_header.getlength(name_text)
            draw.text((OUTPUT_WIDTH - MARGIN - int(name_w), 24), name_text, font=font_header, fill=COLORS["cyan_glow"])

        # Hexagon icon (simplified)

        # Header line
        draw.line([(0, HEADER_HEIGHT), (OUTPUT_WIDTH, HEADER_HEIGHT)],
                  fill=COLORS["white_soft"], width=2)

        # ========== FOOTER (redesigned: lore + compact stats) ==========
        footer_y = OUTPUT_HEIGHT - FOOTER_HEIGHT

        # Footer background
        draw.rectangle([0, footer_y, OUTPUT_WIDTH, OUTPUT_HEIGHT], fill=(0, 0, 0, 220))

        # Footer top border — cyan accent line
        draw.line([(0, footer_y), (OUTPUT_WIDTH, footer_y)],
                  fill=(*COLORS["cyan_glow"], 200), width=4)

        font_label = _find_font(26)
        font_value = _find_font(34)
        font_lore = _find_font(30)

        # --- 1. Full-width lore quote ---
        lore = planet_data.get('lore')
        y = footer_y + 20
        if lore:
            lines = wrap_text(str(lore), font_lore, OUTPUT_WIDTH - 2 * MARGIN, draw)
            for line in lines[:3]:
                draw.text((MARGIN, y), line, font=font_lore, fill=(*COLORS["white_soft"], 180))
                y += 40
        y += 8  # spacing after lore

        # --- 2. Cyan divider line ---
        draw.line([(MARGIN, y), (OUTPUT_WIDTH - MARGIN, y)],
                  fill=(*COLORS["cyan_glow"], 120), width=2)
        y += 40

        # --- 3. Two-column compact stats ---
        col_width = (OUTPUT_WIDTH - 3 * MARGIN) // 2
        right_x = MARGIN * 2 + col_width

        # --- LEFT COLUMN ---
        ly = y

        # SURFACE
        surface = planet_data.get('surface_qualities') or planet_data.get('surface_geology') or 'Unknown'
        draw.text((MARGIN, ly), "SURFACE", font=font_label, fill=COLORS["cyan_dim"])
        ly += 30
        lines = wrap_text(str(surface)[:60], font_value, col_width - 20, draw)
        for line in lines[:1]:
            draw.text((MARGIN, ly), line, font=font_value, fill=COLORS["cyan_glow"])
            ly += 44

        # ORIGIN
        origin = planet_data.get('origin')
        if origin:
            draw.text((MARGIN, ly), "ORIGIN", font=font_label, fill=COLORS["cyan_dim"])
            ly += 30
            lines = wrap_text(str(origin)[:50], font_value, col_width - 20, draw)
            for line in lines[:1]:
                draw.text((MARGIN, ly), line, font=font_value, fill=COLORS["cyan_glow"])
                ly += 44

        # FIRING STATE
        firing = planet_data.get('firing_state')
        if firing and firing not in ['work in progress', 'work_in_progress', None]:
            draw.text((MARGIN, ly), "FIRING STATE", font=font_label, fill=COLORS["cyan_dim"])
            ly += 30
            lines = wrap_text(str(firing), font_value, col_width - 20, draw)
            for line in lines[:1]:
                draw.text((MARGIN, ly), line, font=font_value, fill=COLORS["cyan_glow"])
                ly += 44

        # --- RIGHT COLUMN ---
        ry = y

        # COMPOSITION — one compound per line, amber highlighted
        chemistry = planet_data.get('chemistry')
        if chemistry:
            draw.text((right_x, ry), "COMPOSITION", font=font_label, fill=COLORS["amber"])
            ry += 30
            # Split on pipe/bar separator for one compound per line
            compounds = [c.strip() for c in str(chemistry).split('|')]
            for compound in compounds:
                draw.text((right_x, ry), compound, font=font_value, fill=COLORS["amber"])
                ry += 44
            ry += 4
        else:
            colors = planet_data.get('primary_colors', [])
            if colors:
                comp = colors_to_chemistry_string(colors)
                if comp:
                    draw.text((right_x, ry), "COMPOSITION", font=font_label, fill=COLORS["amber"])
                    ry += 30
                    compounds = [c.strip() for c in comp.split('|')]
                    for compound in compounds:
                        draw.text((right_x, ry), compound, font=font_value, fill=COLORS["amber"])
                        ry += 44
                    ry += 4

        # ANOMALIES — amber highlighted
        anomalies = planet_data.get('anomalies')
        if anomalies:
            draw.text((right_x, ry), "ANOMALIES", font=font_label, fill=COLORS["amber"])
            ry += 30
            lines = wrap_text(str(anomalies)[:100], font_value, col_width - 20, draw)
            for line in lines[:2]:
                draw.text((right_x, ry), line, font=font_value, fill=COLORS["amber"])
                ry += 44
            ry += 4

        # SUBSTRATE (clay type)
        clay = planet_data.get('clay_type')
        if clay:
            draw.text((right_x, ry), "SUBSTRATE", font=font_label, fill=COLORS["cyan_dim"])
            ry += 30
            lines = wrap_text(str(clay).replace('_', ' ').title(), font_value, col_width - 20, draw)
            for line in lines[:1]:
                draw.text((right_x, ry), line, font=font_value, fill=COLORS["cyan_glow"])
                ry += 44

        # --- 4. Logo overlay — bottom-right of art frame (opposite zoom panels) ---
        if LOGO_PATH.exists():
            logo = Image.open(LOGO_PATH).convert('RGBA')
            # Scale icon larger (was 120, now 240 for better visibility)
            target_h = 240
            ratio = target_h / logo.height
            logo_w = int(logo.width * ratio)
            logo_h = target_h
            logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
            # Position in bottom-right of the art frame area
            border_pad = 24
            art_bottom = footer_y - border_pad
            art_right = OUTPUT_WIDTH - border_pad
            logo_x = art_right - logo_w - 10   # 10px from right border
            logo_y = art_bottom - logo_h - 10   # 10px from bottom border
            hud.paste(logo, (logo_x, logo_y), logo)
        else:
            brand_text = "CERAFICA"
            brand_font = _find_font(38, bold=True)
            brand_x = (OUTPUT_WIDTH - len(brand_text) * 24) // 2
            brand_y = OUTPUT_HEIGHT - 80
            draw.text((brand_x, brand_y), f"\u25C8 {brand_text} \u25C8", font=brand_font, fill=COLORS["amber"])

        # ========== CARD FRAME BORDERS ==========
        # Thin inner border rectangle around art frame area (between header and footer)
        border_pad = 24
        art_top = HEADER_HEIGHT + border_pad
        art_bottom = footer_y - border_pad
        art_left = border_pad
        art_right = OUTPUT_WIDTH - border_pad

        draw.rectangle(
            [art_left, art_top, art_right, art_bottom],
            outline=(*COLORS["cyan_dim"], 160), width=2
        )

        # Subtle corner brackets — smaller and more refined
        corner_size = 24
        cs = corner_size
        # Top-left
        draw.line([(art_left, art_top), (art_left + cs, art_top)], fill=COLORS["cyan_glow"], width=4)
        draw.line([(art_left, art_top), (art_left, art_top + cs)], fill=COLORS["cyan_glow"], width=4)
        # Top-right
        draw.line([(art_right, art_top), (art_right - cs, art_top)], fill=COLORS["cyan_glow"], width=4)
        draw.line([(art_right, art_top), (art_right, art_top + cs)], fill=COLORS["cyan_glow"], width=4)
        # Bottom-left
        draw.line([(art_left, art_bottom), (art_left + cs, art_bottom)], fill=COLORS["cyan_glow"], width=4)
        draw.line([(art_left, art_bottom), (art_left, art_bottom - cs)], fill=COLORS["cyan_glow"], width=4)
        # Bottom-right
        draw.line([(art_right, art_bottom), (art_right - cs, art_bottom)], fill=COLORS["cyan_glow"], width=4)
        draw.line([(art_right, art_bottom), (art_right, art_bottom - cs)], fill=COLORS["cyan_glow"], width=4)

        # ========== SCAN LINES (subtle overlay) ==========
        # Already added in SpaceBackground, but add extra in HUD areas
        for y in range(0, HEADER_HEIGHT, 4):
            draw.line([(0, y), (OUTPUT_WIDTH, y)], fill=(0, 0, 0, 8))

        for y in range(footer_y, OUTPUT_HEIGHT, 4):
            draw.line([(0, y), (OUTPUT_WIDTH, y)], fill=(0, 0, 0, 8))

        return hud.convert('RGB')


# ============================================================================
# MINIMAL FRAME GENERATOR
# ============================================================================

class MinimalFrameGenerator(FrameGenerator):
    """
    Clean, adaptable frame for any series.

    Visual style: Minimalist gallery aesthetic with brand mark.
    Works for any series topic — not tied to planetary/space theme.
    """

    def generate_frame(self, image_path: str, data: Dict[str, Any]) -> Image.Image:
        """
        Generate a clean framed image.

        Args:
            image_path: Path to source image
            data: Dict with optional keys:
                - series_name: Name of the series (subtle overlay)
                - piece_description: Description from vision analysis (footer)
                - accent_color: Optional (r, g, b) tuple, auto-detected if missing

        Returns:
            Framed 1080x1350 PIL Image
        """
        source = Image.open(image_path)
        source = ImageOps.exif_transpose(source)
        if source.mode != 'RGB':
            source = source.convert('RGB')

        # Detect accent color from image center
        accent = data.get('accent_color') or self._detect_accent_color(source)

        # Create canvas
        canvas = Image.new('RGB', (OUTPUT_WIDTH, OUTPUT_HEIGHT), (248, 245, 240))  # warm off-white

        # Calculate photo placement with padding
        padding = 40
        header_space = 60
        footer_space = 80
        max_w = OUTPUT_WIDTH - 2 * padding
        max_h = OUTPUT_HEIGHT - header_space - footer_space - 2 * padding

        img_ratio = source.width / source.height
        frame_ratio = max_w / max_h

        if img_ratio > frame_ratio:
            new_w = max_w
            new_h = int(max_w / img_ratio)
        else:
            new_h = max_h
            new_w = int(max_h * img_ratio)

        photo = source.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # Center photo
        x = (OUTPUT_WIDTH - new_w) // 2
        y = header_space + (OUTPUT_HEIGHT - header_space - footer_space - new_h) // 2

        # Draw subtle border around photo
        draw = ImageDraw.Draw(canvas)
        border = 2
        border_color = (200, 195, 188)
        draw.rectangle(
            [x - padding//2, y - padding//2, x + new_w + padding//2, y + new_h + padding//2],
            outline=border_color, width=border
        )

        canvas.paste(photo, (x, y))

        # Brand mark in top-right corner
        font_brand = _find_font(13)
        font_series = _find_font(16, bold=True)
        font_footer = _find_font(12)

        # Brand mark
        brand = "CERAFICA"
        brand_w = len(brand) * 8  # approximate monospace width
        draw.text((OUTPUT_WIDTH - brand_w - 20, 20), brand, font=font_brand, fill=(160, 155, 148))

        # Accent line under brand
        draw.line(
            [(OUTPUT_WIDTH - brand_w - 20, 38), (OUTPUT_WIDTH - 20, 38)],
            fill=accent, width=2
        )

        # Series name as subtle overlay (top-left)
        series_name = data.get('series_name', '')
        if series_name:
            draw.text((20, 20), series_name.upper(), font=font_series, fill=(180, 175, 168))

        # Footer with piece description
        description = data.get('piece_description', '')
        if description:
            # Truncate to fit
            max_chars = 80
            if len(description) > max_chars:
                description = description[:max_chars - 3] + "..."
            draw.text((20, OUTPUT_HEIGHT - 45), description, font=font_footer, fill=(160, 155, 148))

        return canvas

    def _detect_accent_color(self, image: Image.Image) -> Tuple[int, int, int]:
        """Detect dominant color from image center region."""
        # Sample center 20% of image
        w, h = image.size
        cx, cy = w // 2, h // 2
        sample_w, sample_h = w // 5, h // 5
        region = image.crop((cx - sample_w, cy - sample_h, cx + sample_w, cy + sample_h))

        # Resize to small for averaging
        small = region.resize((10, 10))
        pixels = list(small.getdata())

        # Average RGB
        avg_r = sum(p[0] for p in pixels) // len(pixels)
        avg_g = sum(p[1] for p in pixels) // len(pixels)
        avg_b = sum(p[2] for p in pixels) // len(pixels)

        # Saturate slightly for a more vivid accent
        max_val = max(avg_r, avg_g, avg_b)
        if max_val > 0:
            factor = 0.7  # Pull toward middle for subtlety
            avg_r = int(avg_r * factor + 255 * (1 - factor) * (avg_r / max_val) * 0.3)
            avg_g = int(avg_g * factor + 255 * (1 - factor) * (avg_g / max_val) * 0.3)
            avg_b = int(avg_b * factor + 255 * (1 - factor) * (avg_b / max_val) * 0.3)

        return (min(255, avg_r), min(255, avg_g), min(255, avg_b))

def generate_planetary_frame(image_path: str, planet_data: Dict[str, Any],
                             save: bool = True, output_name: str = None) -> Tuple[Image.Image, Optional[str]]:
    """
    Convenience function to generate a planetary frame.

    Args:
        image_path: Path to source image
        planet_data: Planet data dict
        save: Whether to save to output directory
        output_name: Optional filename override (without extension) for the saved file

    Returns:
        Tuple of (framed Image, saved_path or None)
    """
    generator = PlanetaryFrameGenerator()
    framed = generator.generate_frame(image_path, planet_data)

    if save:
        name_for_save = output_name if output_name else image_path
        saved_path = generator.save_frame(framed, name_for_save, series="planetary")
        return framed, saved_path

    return framed, None


def generate_minimal_frame(image_path: str, data: Dict[str, Any],
                           save: bool = True, output_name: str = None) -> Tuple[Image.Image, Optional[str]]:
    """
    Convenience function to generate a minimal frame.

    Args:
        image_path: Path to source image
        data: Dict with series_name, piece_description, accent_color
        save: Whether to save to output directory
        output_name: Optional filename override (without extension) for the saved file

    Returns:
        Tuple of (framed Image, saved_path or None)
    """
    generator = MinimalFrameGenerator()
    framed = generator.generate_frame(image_path, data)

    if save:
        name_for_save = output_name if output_name else image_path
        saved_path = generator.save_frame(framed, name_for_save, series="minimal")
        return framed, saved_path

    return framed, None


# ============================================================================
# TEST FUNCTION
# ============================================================================

def test_generator():
    """Test the frame generator with a sample image."""
    print("=" * 60)
    print("Frame Generator Test")
    print("=" * 60)

    # Look for test images
    test_dirs = [
        Path(__file__).parent.parent.parent.parent / "instagram" / "ab_test_photos",
        Path(__file__).parent.parent.parent.parent / "instagram" / "vision_exports",
    ]

    test_image = None
    for test_dir in test_dirs:
        if test_dir.exists():
            for ext in ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG"]:
                matches = list(test_dir.glob(ext))
                if matches:
                    test_image = str(matches[0])
                    break
        if test_image:
            break

    if not test_image:
        print("No test images found. Creating a test image...")
        # Create a simple test image
        test_img = Image.new('RGB', (1000, 1200), (139, 90, 43))  # Brown ceramic color
        test_dir = Path(__file__).parent.parent.parent.parent / "output" / "framed" / "test"
        test_dir.mkdir(parents=True, exist_ok=True)
        test_image = str(test_dir / "test_piece.jpg")
        test_img.save(test_image)

    print(f"\nUsing test image: {test_image}")

    # Sample planet data
    planet_data = {
        "planet_name": "Pallth-7",
        "sector": "Obsidian Cluster",
        "surface_geology": "Volcanic glass plains with copper oxide deposits",
        "log_number": 47
    }

    print(f"Planet data: {planet_data}")

    # Generate frame
    print("\nGenerating frame...")
    generator = PlanetaryFrameGenerator()
    framed = generator.generate_frame(test_image, planet_data)

    # Save to test directory
    test_output_dir = FRAMED_OUTPUT_DIR / "test"
    saved_path = generator.save_frame(framed, test_image)

    print(f"\nFramed image saved to: {saved_path}")
    print(f"Dimensions: {framed.size[0]}x{framed.size[1]}")

    # Verify dimensions
    assert framed.size == (OUTPUT_WIDTH, OUTPUT_HEIGHT), \
        f"Expected {OUTPUT_WIDTH}x{OUTPUT_HEIGHT}, got {framed.size}"

    print("\n" + "=" * 60)
    print("Test passed! Open the image to verify visual output.")
    print("=" * 60)

    return saved_path


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        test_generator()
    else:
        print("Usage: python frame_generator.py --test")
        print("       Tests the frame generator module")
