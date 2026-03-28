#!/usr/bin/env python3
"""
Glaze Exploration Series — Teaser + Dynamic Captions Generator.

Commands:
    python3 scripts/generate_campaign.py --teaser     # regenerate teaser image
    python3 scripts/generate_campaign.py --captions   # generate posting_guide.md from DB
"""

import argparse
import json
import random
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from frame_generator import (
    SpaceBackground,
    COLORS,
    OUTPUT_WIDTH,
    OUTPUT_HEIGHT,
    HEADER_HEIGHT,
    FOOTER_HEIGHT,
    MARGIN,
    LOGO_PATH,
    wrap_text,
    _find_font,
)
from PIL import Image, ImageDraw, ImageFilter

DB_PATH = Path(__file__).parent.parent.parent / "tools" / "feedback.db"
CAMPAIGN_DIR = Path(__file__).parent.parent.parent / "output" / "campaign"

# Voice rules path
VOICE_RULES_PATH = Path(__file__).parent.parent.parent / "brand" / "voice-rules.md"


# ============================================================================
# Music mood → track mapping (free / royalty-free sources)
# ============================================================================

MUSIC_TRACKS = {
    "warm_acoustic": {
        "moods": {"warm", "rustic"},
        "color_families": {"red", "brown", "rust", "amber", "honey", "oatmeal",
                          "copper", "mahogany", "russet", "chestnut", "ochre"},
        "genre": "Ambient Acoustic / Warm Drone",
        "tracks": [
            {"name": "Light Awash", "artist": "Kevin MacLeod",
             "source": "Incompetech (CC BY)", "url": "https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100289"},
            {"name": "Movement Proposition", "artist": "Kevin MacLeod",
             "source": "Incompetech (CC BY)", "url": "https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1200083"},
        ],
    },
    "cool_space": {
        "moods": {"cool", "moody"},
        "color_families": {"blue", "teal", "denim", "slate", "chun_blue",
                          "seafoam", "cobalt", "peanut"},
        "genre": "Space Ambient / Dark Ambient",
        "tracks": [
            {"name": "Ultra Deep Field", "artist": "Stellardrone",
             "source": "Free Music Archive (CC BY)", "url": "https://freemusicarchive.org/music/Stellardrone/Light_Years/"},
            {"name": "Light Years", "artist": "Stellardrone",
             "source": "Free Music Archive (CC BY)", "url": "https://freemusicarchive.org/music/Stellardrone/Light_Years/"},
        ],
    },
    "cinematic_epic": {
        "moods": {"dramatic", "bold"},
        "color_families": {"oxblood", "garnet", "burgundy", "deep", "dark"},
        "genre": "Cinematic / Epic Ambient",
        "tracks": [
            {"name": "Memories", "artist": "Bensound",
             "source": "Bensound (Free License)", "url": "https://www.bensound.com/royalty-free-music/acoustic-folk"},
            {"name": "Emotional Piano", "artist": "Bensound",
             "source": "Bensound (Free License)", "url": "https://www.bensound.com/royalty-free-music/piano"},
        ],
    },
    "ethereal_soundscape": {
        "moods": {"organic", "earthy"},
        "color_families": {"mixed", "earth tones", "multi"},
        "genre": "Ethereal Soundscape",
        "tracks": [
            {"name": "Eternity", "artist": "Stellardrone",
             "source": "Free Music Archive (CC BY)", "url": "https://freemusicarchive.org/music/Stellardrone/Eternity/"},
            {"name": "Billions and Billions", "artist": "Stellardrone",
             "source": "Free Music Archive (CC BY)", "url": "https://freemusicarchive.org/music/Stellardrone/Eternity/"},
        ],
    },
    "uplifting_ambient": {
        "moods": {"vibrant", "modern"},
        "color_families": {"blue", "teal", "denim"},
        "genre": "Uplifting Ambient",
        "tracks": [
            {"name": "Night Sky Travel", "artist": "Pixabay Music",
             "source": "Pixabay (Free)", "url": "https://pixabay.com/music/"},
            {"name": "Ambient Space", "artist": "Pixabay Music",
             "source": "Pixabay (Free)", "url": "https://pixabay.com/music/"},
        ],
    },
}


def match_music_track(mood: str, primary_colors_raw: str) -> dict:
    """Match a piece's mood + colors to a music recommendation."""
    # Parse primary_colors from JSON string if needed
    try:
        colors = json.loads(primary_colors_raw) if primary_colors_raw else []
    except (json.JSONDecodeError, TypeError):
        colors = []

    # Build color family set (lowercased, simplified)
    color_text = " ".join(colors).lower()
    color_families = set()
    for color in colors:
        c = color.lower().replace(" ", "_")
        color_families.add(c)
    # Also add broad family keywords
    if any(w in color_text for w in ["red", "rust", "amber", "honey", "copper", "brown"]):
        color_families.update({"red", "brown", "warm"})
    if any(w in color_text for w in ["blue", "teal", "denim", "cobalt", "seafoam"]):
        color_families.update({"blue", "cool"})
    if any(w in color_text for w in ["earth", "chestnut", "walnut", "caramel"]):
        color_families.add("earth tones")

    mood_lower = (mood or "").lower()

    # Score each music category
    best_match = None
    best_score = -1
    for key, info in MUSIC_TRACKS.items():
        score = 0
        if mood_lower in info["moods"]:
            score += 2
        # Check color family overlap
        overlap = color_families & info["color_families"]
        score += len(overlap)
        if score > best_score:
            best_score = score
            best_match = (key, info)

    if best_match is None:
        # Fallback to ethereal
        best_match = ("ethereal_soundscape", MUSIC_TRACKS["ethereal_soundscape"])

    key, info = best_match
    track = random.choice(info["tracks"])
    return {
        "genre": info["genre"],
        "track_name": track["name"],
        "artist": track["artist"],
        "source": track["source"],
        "url": track["url"],
    }


def generate_teaser(seed: int = 42) -> str:
    """
    Generate teaser post — pure space + mystery text, no pottery photo.
    """
    random.seed(seed)
    bg = Image.new('RGB', (OUTPUT_WIDTH, OUTPUT_HEIGHT), COLORS["space_black"])
    nebula = Image.new('RGBA', (OUTPUT_WIDTH, OUTPUT_HEIGHT), (0, 0, 0, 0))
    ndraw = ImageDraw.Draw(nebula)

    # Extra-dense nebulae for drama
    nebula_colors = [(140, 70, 180), (40, 130, 130), (60, 20, 100), (20, 80, 100)]
    for _ in range(8):
        x = random.randint(-200, OUTPUT_WIDTH + 200)
        y = random.randint(-200, OUTPUT_HEIGHT + 200)
        radius = random.randint(250, 600)
        color = random.choice(nebula_colors)
        for r in range(radius, 0, -10):
            alpha = int(55 * (1 - r / radius))
            ndraw.ellipse([x - r, y - r, x + r, y + r], fill=(*color, alpha))

    nebula = nebula.filter(ImageFilter.GaussianBlur(radius=50))
    bg.paste(Image.alpha_composite(bg.convert('RGBA'), nebula).convert('RGB'))

    # Add stars
    bg = SpaceBackground(OUTPUT_WIDTH, OUTPUT_HEIGHT, seed=seed)._add_stars(bg)
    bg = SpaceBackground(OUTPUT_WIDTH, OUTPUT_HEIGHT, seed=seed)._add_vignette(bg)
    bg = SpaceBackground(OUTPUT_WIDTH, OUTPUT_HEIGHT, seed=seed)._add_scan_lines(bg)

    # Convert to RGBA for overlays
    canvas = bg.convert('RGBA')
    draw = ImageDraw.Draw(canvas)

    # ========== HEADER ==========
    draw.rectangle([0, 0, OUTPUT_WIDTH, HEADER_HEIGHT], fill=(0, 0, 0, 200))
    font_header = _find_font(56, bold=True)
    draw.text((MARGIN, 24), "Cerafica Exploration Log", font=font_header, fill=COLORS["cyan_glow"])

    # Encrypted planet name block
    font_cipher = _find_font(40)
    cipher = "\u2588" * 12
    cipher_w = int(font_cipher.getlength(cipher))
    draw.text((OUTPUT_WIDTH - MARGIN - cipher_w, 30), cipher, font=font_cipher,
              fill=(*COLORS["cyan_dim"], 180))

    draw.line([(0, HEADER_HEIGHT), (OUTPUT_WIDTH, HEADER_HEIGHT)],
              fill=COLORS["white_soft"], width=2)

    # ========== CENTER TEXT ==========
    font_big = _find_font(112, bold=True)
    font_sub = _find_font(56, bold=True)
    font_series = _find_font(40)
    font_lore_small = _find_font(26)
    font_lore_tiny = _find_font(22)

    cx, cy = OUTPUT_WIDTH // 2, (OUTPUT_HEIGHT + HEADER_HEIGHT - FOOTER_HEIGHT) // 2
    footer_y = OUTPUT_HEIGHT - FOOTER_HEIGHT

    text1 = "SOMETHING"
    text2 = "IS OUT THERE"
    text3 = "GLAZE EXPLORATION SERIES"

    for text, font, color, y_off in [
        (text1, font_big, COLORS["cyan_glow"], -220),
        (text2, font_big, COLORS["cyan_glow"], -80),
        (text3, font_series, COLORS["cyan_dim"], 60),
    ]:
        w = int(font.getlength(text))
        x = (OUTPUT_WIDTH - w) // 2
        y = cy + y_off
        draw.text((x, y), text, font=font, fill=color)

    # Targeting reticle — big enough to enclose all text + logo
    reticle_color = (*COLORS["cyan_dim"], 60)
    ring_r = 520
    draw.ellipse([cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r],
                 outline=reticle_color, width=2)
    # Inner ring
    inner_r = 480
    draw.ellipse([cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
                 outline=(*COLORS["cyan_dim"], 30), width=1)
    # Crosshair lines — reach from inner ring to outer
    gap = 40
    line_len = ring_r - 10
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
        draw.line([(cx + dx * gap, cy + dy * gap), (cx + dx * line_len, cy + dy * line_len)],
                  fill=reticle_color, width=2)
    # Tick marks on outer ring at 45-degree angles
    import math
    for angle_deg in [45, 135, 225, 315]:
        angle = math.radians(angle_deg)
        x1 = cx + int((ring_r - 20) * math.cos(angle))
        y1 = cy + int((ring_r - 20) * math.sin(angle))
        x2 = cx + int((ring_r + 20) * math.cos(angle))
        y2 = cy + int((ring_r + 20) * math.sin(angle))
        draw.line([(x1, y1), (x2, y2)], fill=reticle_color, width=2)

    # Lore text — scattered inside reticle above and below center text
    lore_fragments = [
        ("SURVEY TEAM ALPHA-7 // DEEP FIELD SCAN", cy - 350),
        ("ANOMALY DETECTED: UNKNOWN SPECTRAL SIGNATURE", cy - 320),
        ("FIRST CONTACT PROTOCOL INITIATED", cy + 140),
        ("CLASSIFICATION: PENDING REVIEW", cy + 170),
        ("MULTIPLE WORLDS CONFIRMED // SEE DOSSIER", cy + 200),
    ]
    for text, y_pos in lore_fragments:
        w = int(font_lore_small.getlength(text))
        x = (OUTPUT_WIDTH - w) // 2
        draw.text((x, y_pos), text, font=font_lore_small, fill=(*COLORS["cyan_dim"], 100))

    # Corner coordinates inside reticle
    coords = [
        (f"X:{random.randint(100,999):03d}.{random.randint(0,9)} Y:{random.randint(100,999):03d}.{random.randint(0,9)}",
         MARGIN + 20, HEADER_HEIGHT + 20),
        (f"RA: {random.randint(10,23)}h {random.randint(0,59)}m",
         OUTPUT_WIDTH - MARGIN - 220, HEADER_HEIGHT + 20),
        (f"DEC: {random.choice(['+','-'])}{random.randint(10,89)}.{random.randint(0,99)}",
         MARGIN + 20, footer_y - 50),
        (f"DIST: {random.randint(100,9999)}.{random.randint(0,9)} LY",
         OUTPUT_WIDTH - MARGIN - 240, footer_y - 50),
    ]
    for text, x, y in coords:
        draw.text((x, y), text, font=font_lore_tiny, fill=(*COLORS["cyan_dim"], 80))

    # Logo centered below series text
    if LOGO_PATH.exists():
        logo = Image.open(LOGO_PATH).convert('RGBA')
        target_h = 160
        ratio = target_h / logo.height
        logo = logo.resize((int(logo.width * ratio), target_h), Image.Resampling.LANCZOS)
        logo_x = (OUTPUT_WIDTH - logo.width) // 2
        logo_y = cy + 230
        canvas.paste(logo, (logo_x, logo_y), logo)

    # ========== FOOTER ==========
    draw.rectangle([0, footer_y, OUTPUT_WIDTH, OUTPUT_HEIGHT], fill=(0, 0, 0, 220))
    draw.line([(0, footer_y), (OUTPUT_WIDTH, footer_y)],
              fill=(*COLORS["cyan_glow"], 200), width=4)

    font_quote = _find_font(32)
    font_label = _find_font(30)
    font_lore_footer = _find_font(24)
    y = footer_y + 20

    quote = '"The universe is vast and mostly empty. Until now."'
    lines = wrap_text(quote, font_quote, OUTPUT_WIDTH - 2 * MARGIN, draw)
    for line in lines:
        draw.text((MARGIN, y), line, font=font_quote, fill=(*COLORS["white_soft"], 180))
        y += 38

    y += 10
    draw.line([(MARGIN, y), (OUTPUT_WIDTH - MARGIN, y)],
              fill=(*COLORS["cyan_glow"], 120), width=2)
    y += 30

    # Lore block — mission briefing flavor text
    lore_lines = [
        "MISSION BRIEFING // CERAFICA DEEP SPACE INITIATIVE",
        "Long-range spectral analysis has identified anomalous mineral signatures",
        "across multiple uncharted sectors. These readings match no known geological",
        "formation in our catalog. Preliminary data suggests the presence of worlds",
        "shaped by forces we do not yet understand. Full dossier pending review.",
    ]
    for line in lore_lines:
        draw.text((MARGIN, y), line, font=font_lore_footer, fill=(*COLORS["white_soft"], 120))
        y += 30

    y += 8
    draw.line([(MARGIN, y), (OUTPUT_WIDTH - MARGIN, y)],
              fill=(*COLORS["cyan_glow"], 80), width=1)
    y += 25

    # Classification fields — two columns
    fields_left = [
        ("CLASSIFICATION", "UNKNOWN"),
        ("SECTOR", "UNCHARTED"),
    ]
    fields_right = [
        ("STATUS", "FIRST CONTACT PENDING"),
        ("WORLDS DETECTED", "10+"),
    ]

    for label, value in fields_left:
        draw.text((MARGIN, y), label, font=font_label, fill=COLORS["cyan_dim"])
        draw.text((MARGIN + 280, y), value, font=font_label, fill=COLORS["cyan_glow"])
        y += 40

    ry = y - 80  # right column starts at same y as left
    for label, value in fields_right:
        right_x = OUTPUT_WIDTH // 2 + 40
        draw.text((right_x, ry), label, font=font_label, fill=COLORS["cyan_dim"])
        draw.text((right_x + 280, ry), value, font=font_label, fill=COLORS["cyan_glow"])
        ry += 40

    # Scan lines
    for y in range(0, HEADER_HEIGHT, 4):
        draw.line([(0, y), (OUTPUT_WIDTH, y)], fill=(0, 0, 0, 8))
    for y in range(footer_y, OUTPUT_HEIGHT, 4):
        draw.line([(0, y), (OUTPUT_WIDTH, y)], fill=(0, 0, 0, 8))

    # Save
    CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)
    out = CAMPAIGN_DIR / "01_teaser.jpg"
    canvas.convert('RGB').save(out, "JPEG", quality=98, subsampling=0)
    return str(out)


# ============================================================================
# Captions + Music from DB
# ============================================================================

def load_voice_rules() -> str:
    """Load voice rules for caption generation context."""
    if VOICE_RULES_PATH.exists():
        return VOICE_RULES_PATH.read_text()
    return ""


def query_series_pieces() -> list:
    """
    Query all series_pieces with vision_results (preferring Kimi Ollama model).
    Returns list of dicts with ALL available fields for rich caption generation.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all series_pieces with full data
    cursor.execute("""
        SELECT sp.id, sp.photo, sp.planet_name, sp.orbital_data,
               sp.surface_geology, sp.formation_history, sp.inhabitants, sp.order_index
        FROM series_pieces sp
        ORDER BY sp.order_index
    """)
    pieces = [dict(row) for row in cursor.fetchall()]
    conn.close()

    # For each piece, get the best vision result (prefer Kimi Ollama)
    for piece in pieces:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        base_name = Path(piece["photo"]).stem

        cursor.execute("""
            SELECT vr.mood, vr.primary_colors, vr.color_appearance,
                   vr.surface_qualities, vr.form_attributes, vr.technique,
                   vr.clay_type, vr.hypotheses, vr.model
            FROM vision_results vr
            JOIN photos p ON vr.photo_id = p.id
            WHERE p.filename LIKE ?
            ORDER BY
                CASE WHEN vr.model LIKE '%Kimi%2.5%Ollama%' THEN 0
                     WHEN vr.model LIKE '%Kimi%' THEN 1
                     WHEN vr.model LIKE '%Ollama%' THEN 2
                     ELSE 3 END
            LIMIT 1
        """, (f"%{base_name}%",))

        vr_row = cursor.fetchone()
        if vr_row:
            piece["mood"] = vr_row["mood"]
            piece["primary_colors"] = vr_row["primary_colors"]
            piece["color_appearance"] = vr_row["color_appearance"]
            piece["surface_qualities"] = vr_row["surface_qualities"]
            piece["form_attributes"] = vr_row["form_attributes"]
            piece["technique"] = vr_row["technique"]
            piece["clay_type"] = vr_row["clay_type"]
            piece["hypotheses"] = vr_row["hypotheses"]
        else:
            for key in ["mood", "primary_colors", "color_appearance",
                        "surface_qualities", "form_attributes", "technique",
                        "clay_type", "hypotheses"]:
                piece[key] = None

        # Query idea seeds for this photo
        cursor.execute(
            'SELECT seed_text FROM idea_seeds WHERE photo = ? AND deleted_at IS NULL',
            (piece["photo"],)
        )
        piece["idea_seeds"] = [r[0] for r in cursor.fetchall()]

        conn.close()

    return pieces


def _split_sentences(text: str) -> list:
    """Split text into sentences, handling decimal numbers like '2.1 billion'."""
    import re
    parts = re.split(r'(?<!\d)\.\s+(?!\d)', text)
    return [p.strip() for p in parts if p.strip()]


def _parse_json_list(raw: str) -> list:
    """Safely parse a JSON list string, returning empty list on failure."""
    if not raw:
        return []
    try:
        import json
        result = json.loads(raw)
        if isinstance(result, list):
            return result
        return []
    except (json.JSONDecodeError, TypeError):
        return []


def _generate_hashtags(piece: dict) -> str:
    """Generate 5 targeted hashtags per piece for dual audience reach."""
    tags = []

    # 1. Ceramics community tag (always 1 — pick best fit)
    mood = (piece.get("mood") or "").lower()
    if mood in ("dramatic", "bold", "cool", "moody"):
        tags.append("#ceramicart")  # 5.7M, art-focused crowd
    else:
        tags.append("#clay")  # 14.6M, highest reach score

    # 2. Aesthetic/mood tag (reach sci-fi/art audience)
    mood_tags = {
        "dramatic": "#darkaesthetic",
        "cool": "#moodygrams",
        "warm": "#warmtones",
        "modern": "#minimalart",
        "earthy": "#earthtones",
    }
    if mood in mood_tags:
        tags.append(mood_tags[mood])

    # 3. Piece type tag (discoverable by item)
    form_attrs = _parse_json_list(piece.get("form_attributes") or "")
    form_text = " ".join(form_attrs).lower() if form_attrs else ""
    piece_type = (piece.get("piece_type") or "").lower()
    piece_tags = {
        "vase": "#ceramicvase", "bud_vase": "#ceramicvase",
        "bowl": "#ceramicbowl", "mug": "#ceramicmug", "cup": "#ceramiccup",
        "planter": "#ceramicplanter", "sculpture": "#ceramicsculpture",
        "jar": "#ceramicjar", "plate": "#ceramicplate",
    }
    for ptype, tag in piece_tags.items():
        if ptype in piece_type or ptype.replace("_", " ") in form_text:
            tags.append(tag)
            break

    # 4. Crossover tag (bridges ceramics + art audiences)
    tags.append("#studiopottery")  # maker community, recognizes craft

    # 5. Local tag (always)
    tags.append("#longbeachartist")

    return " ".join(tags[:5])


def _extract_inhabitants_lore(inhabitants: str) -> str:
    """
    Extract the best lore from the inhabitants field.
    Prioritizes unique content, especially 'WHAT IT FEELS LIKE TO BE THERE'.
    Always tries to get the feelings section even if other sections are boilerplate.
    """
    if not inhabitants:
        return ""

    lines = inhabitants.strip().split("\n")
    sections = {}
    current_section = "_preamble"
    sections[current_section] = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("===") and stripped.endswith("==="):
            section_name = stripped.replace("=", "").strip().lower()
            current_section = section_name
            sections[current_section] = []
        elif current_section in sections:
            sections[current_section].append(stripped)

    # Always grab "what it feels like" first — it's the richest unique content
    feelings_key = None
    for key in sections:
        if "what it feels like" in key:
            feelings_key = key
            break
    if feelings_key:
        text = " ".join(sections[feelings_key]).strip()
        if text:
            return text

    # Then look for sections with real content (not "None" boilerplate)
    for name in ["intelligent life", "animal life", "plant life", "_preamble"]:
        if name in sections:
            text = " ".join(sections[name]).strip()
            if text and not text.startswith("None") and not text.startswith("No civilization"):
                return text

    return ""


def _extract_orbital_detail(orbital_data: str) -> str:
    """
    Extract the most evocative detail from orbital_data.
    Picks sensory/atmospheric lines (scent, temperature, breathability) over
    classification/surface data that's already on the framed image.
    Returns a clean sentence without the label prefix.
    """
    if not orbital_data:
        return ""
    lines = orbital_data.strip().split("\n")

    # Prioritize sensory details — strip the label prefix
    sensory_keywords = ["scent", "temperature", "breathability", "suit required"]
    priority_lines = []
    other_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip stuff that duplicates frame HUD
        if stripped.startswith("Classification:") or stripped.startswith("Surface features:"):
            continue
        if stripped.startswith("Primary terrain:"):
            continue
        # Check if it's a sensory line
        if any(kw in stripped.lower() for kw in sensory_keywords):
            # Strip label prefix ("Scent: " → just the value)
            if ":" in stripped:
                value = stripped.split(":", 1)[1].strip()
                priority_lines.append(value)
            else:
                priority_lines.append(stripped)
        else:
            # Strip label for non-sensory lines too
            if ":" in stripped:
                value = stripped.split(":", 1)[1].strip()
                other_lines.append(value)
            else:
                other_lines.append(stripped)

    # Use sensory lines first, then fall back to other orbital data
    chosen = priority_lines if priority_lines else other_lines
    if not chosen:
        return ""

    # Take first 1-2 lines
    text = ". ".join(chosen[:2])
    if len(text) > 250:
        text = text[:250].rsplit(" ", 1)[0]
    return text


def _extract_hypothesis(hypotheses_raw: str) -> str:
    """Extract the first (highest confidence) hypothesis."""
    hypotheses = _parse_json_list(hypotheses_raw)
    if not hypotheses:
        return ""
    first = hypotheses[0]
    # Strip the confidence tag like " [high]" or " [medium]"
    import re
    cleaned = re.sub(r'\s*\[(?:high|medium|low)\]', '', first).strip()
    # Clean up any leading dash
    cleaned = re.sub(r'^[-–]\s*', '', cleaned)
    return cleaned.strip()


def generate_caption(piece: dict) -> str:
    """
    Generate an Instagram caption COMPLEMENTARY to the framed image.

    The image already shows: surface geology, composition/colors, formation lore.
    The caption provides: atmosphere/sensory details, inhabitants lore,
    glaze hypotheses, and emotional hooks. No duplication.
    """
    planet = (piece.get("planet_name") or "Unknown Planet").title()

    # === DATA SOURCES (all complementary to image) ===
    inhabitants_lore = _extract_inhabitants_lore(piece.get("inhabitants") or "")
    orbital_detail = _extract_orbital_detail(piece.get("orbital_data") or "")
    hypothesis = _extract_hypothesis(piece.get("hypotheses") or "")
    technique = piece.get("technique") or ""
    clay_type = piece.get("clay_type") or ""

    # === HOOK ===
    # Planet name + most evocative orbital detail
    if orbital_detail:
        # Take first sentence
        first_orbital = _split_sentences(orbital_detail)
        detail = first_orbital[0] if first_orbital else orbital_detail[:120]
        # Don't use breathability/suit details as the hook — too clinical
        if any(kw in detail for kw in ["MARGINAL", "UNKNOWN", "SURVIVABLE", "TOXIC", "DEADLY", "Respirator", "Suit Required"]):
            # Try second sentence if available
            if len(first_orbital) > 1:
                detail = first_orbital[1]
            else:
                detail = None
        if detail and not any(kw in detail for kw in ["MARGINAL", "UNKNOWN", "SURVIVABLE", "TOXIC", "DEADLY"]):
            hook = f"Planet {planet}. {detail}"
        else:
            hook = f"Planet {planet}."
    else:
        hook = f"Planet {planet}."

    # === BODY — stack complementary content ===
    body_lines = []

    banned = {"delve", "delving", "tapestry", "realm", "embrace", "elevate",
              "navigate", "embark", "foster", "groundbreaking", "invaluable",
              "relentless", "furthermore", "moreover", "additionally"}

    # Idea seeds (user-provided creative direction — highest priority)
    idea_seeds = piece.get("idea_seeds") or []
    if idea_seeds:
        for seed in idea_seeds:
            seed_text = seed.strip()
            if seed_text and seed_text[-1] not in ".!?":
                seed_text += "."
            if not any(b in seed_text.lower() for b in banned):
                body_lines.append(seed_text)

    # Inhabitants lore (the unique per-planet storytelling)
    if inhabitants_lore:
        sentences = _split_sentences(inhabitants_lore)
        body_lines.extend(sentences[:5])

    # Fallback: if no inhabitants lore, use color_appearance and formation
    # (these are visual/geological, different from the stats on the frame)
    if not inhabitants_lore:
        color_appearance = piece.get("color_appearance") or ""
        formation = piece.get("formation_history") or ""
        if color_appearance:
            truncated = color_appearance[:300]
            if len(color_appearance) > 300:
                truncated = truncated.rsplit(" ", 1)[0]
            body_lines.append(truncated)
        if formation:
            # Skip first sentence (that's the lore on the frame), take second+
            sentences = _split_sentences(formation)
            if len(sentences) > 1:
                body_lines.extend(sentences[1:3])

    # Hypothesis (what the glaze actually might be — bridges pottery reality)
    if hypothesis:
        body_lines.append(hypothesis[:250])

    # === ENGAGEMENT ===
    engagement_options = [
        "What would you do if you found this world? Save this for your collection.",
        "Could you survive here? Tag someone who needs to see this.",
        "This is a one-of-one world. Once claimed, it's gone. DM to inquire.",
        "Send this to someone who loves weird planets.",
    ]
    engagement = engagement_options[hash(planet) % len(engagement_options)]

    # === ASSEMBLE ===
    parts = [hook]
    for line in body_lines:
        clean = line.strip()
        if not clean:
            continue
        if clean[-1] not in ".!?":
            clean += "."
        if not any(b in clean.lower() for b in banned):
            parts.append(clean)
    parts.append(engagement)

    caption = "\n\n".join(parts)

    # Instagram limit is 2200 chars; keep under 1500 for readability
    if len(caption) > 1500:
        # Trim body lines from the end (before engagement)
        parts_trimmed = parts[:-1]  # remove engagement
        while len("\n\n".join(parts_trimmed + [engagement])) > 1500 and len(parts_trimmed) > 1:
            parts_trimmed.pop()
        caption = "\n\n".join(parts_trimmed + [engagement])

    return caption


def generate_posting_guide() -> str:
    """
    Generate posting_guide.md with captions + music for every framed piece.
    """
    pieces = query_series_pieces()

    if not pieces:
        print("No series pieces found in DB.")
        sys.exit(1)

    print(f"Found {len(pieces)} series pieces.")

    lines = [
        "# Glaze Exploration Series — Posting Guide",
        "",
        f"Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d')}",
        f"Total pieces: {len(pieces)}",
        "",
        "---",
        "",
    ]

    for i, piece in enumerate(pieces, 1):
        planet = (piece.get("planet_name") or "Unknown Planet").title()
        photo = piece.get("photo", "unknown")
        mood = piece.get("mood") or "unknown"
        colors_raw = piece.get("primary_colors") or "[]"

        # Caption
        caption = generate_caption(piece)

        # Music
        music = match_music_track(mood, colors_raw)

        # Per-piece hashtags
        hashtags = _generate_hashtags(piece)

        lines.append(f"## {i}. {planet}")
        lines.append(f"")
        lines.append(f"**Photo:** `{photo}`")
        lines.append(f"**Mood:** {mood}")
        lines.append(f"")
        lines.append(f"### Caption")
        lines.append(f"")
        lines.append(f"{caption}")
        lines.append(f"")
        lines.append(f"{hashtags}")
        lines.append(f"")
        lines.append(f"### Music Recommendation")
        lines.append(f"")
        lines.append(f"**Genre:** {music['genre']}")
        lines.append(f"**Track:** \"{music['track_name']}\" by {music['artist']}")
        lines.append(f"**Source:** {music['source']}")
        lines.append(f"**Link:** {music['url']}")
        lines.append(f"")
        lines.append("---")
        lines.append("")

    guide = "\n".join(lines)

    # Save
    CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CAMPAIGN_DIR / "posting_guide.md"
    out_path.write_text(guide)

    return str(out_path)


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Glaze Exploration Series — teaser + dynamic captions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/generate_campaign.py --teaser
  python3 scripts/generate_campaign.py --captions
"""
    )

    parser.add_argument("--teaser", action="store_true",
                        help="Regenerate the teaser image")
    parser.add_argument("--captions", action="store_true",
                        help="Generate posting_guide.md with captions + music for all pieces")

    args = parser.parse_args()

    if args.teaser:
        print("Generating teaser...")
        out = generate_teaser()
        print(f"Saved: {out}")

    elif args.captions:
        print("Generating captions + music guide...")
        out = generate_posting_guide()
        print(f"Saved: {out}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
