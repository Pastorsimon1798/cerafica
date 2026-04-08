"""
Caption generator module for Instagram posts.

Analyzes photos and generates captions in the user's voice using:
- Photo content analysis (piece type, colors, mood)
- Voice rules from brand/voice-rules.md
- Hashtags from shared/hashtag-library.md

AI Model Support (March 2026):
- TWO-MODEL ARCHITECTURE:
  - Vision: qwen3.5:cloud (Ollama) - multimodal ceramic identification
  - Writing: deepseek-v3.2:cloud (Ollama) - natural caption generation
- Fallback: OpenRouter API (paid)
"""

import os
import re
import base64
import json
import sqlite3
import subprocess
import tempfile
import time
import logging
from collections import Counter
import requests
from pathlib import Path
from typing import Optional, Literal
from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO

# Load environment variables from .env BEFORE any other imports
from dotenv import load_dotenv
_env_path = Path(__file__).parent.parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

# Import data loader for canonical ceramics-foundation data
try:
    from data_loader import load_colors, load_clay_bodies, load_colorants
except ImportError:
    load_colors = load_clay_bodies = load_colorants = lambda: []

# Try to import PIL for image compression
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# =============================================================================
# IMAGE COMPRESSION HELPER
# =============================================================================

def compress_image_for_api(photo_path: str, max_size_mb: float = 15.0, max_dimension: int = 4096, min_quality: int = 70) -> str:
    """
    Compress image to fit within API size limits.

    Args:
        photo_path: Path to the image file
        max_size_mb: Maximum size in megabytes (default 15MB for minimal compression)
        max_dimension: Maximum width or height in pixels
        min_quality: Minimum quality threshold (don't go below this)

    Returns:
        Base64 encoded image string
    """
    max_bytes = int(max_size_mb * 1024 * 1024)

    # Read original file
    with open(photo_path, "rb") as f:
        original_data = f.read()

    # If already small enough, return as-is
    if len(original_data) <= max_bytes:
        return base64.b64encode(original_data).decode("utf-8")

    # Need to compress - check if PIL is available
    if not HAS_PIL:
        print(f"Warning: Image {photo_path} is {len(original_data)/1024/1024:.1f}MB but PIL not available for compression")
        return base64.b64encode(original_data).decode("utf-8")

    # Open and compress with PIL
    img = Image.open(photo_path)

    # Convert to RGB if necessary (for PNG with transparency)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Resize if too large
    if max(img.size) > max_dimension:
        ratio = max_dimension / max(img.size)
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    # Try different quality levels, starting high for minimal compression
    for quality in [95, 85, 80, min_quality]:
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        compressed_size = buffer.tell()

        if compressed_size <= max_bytes:
            print(f"Compressed {photo_path}: {len(original_data)/1024/1024:.1f}MB -> {compressed_size/1024/1024:.1f}MB (quality={quality})")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

    # If still too large at min_quality, return as-is rather than destroy quality
    print(f"Warning: {photo_path} still too large at quality={min_quality}, sending original")
    return base64.b64encode(original_data).decode("utf-8")


# =============================================================================
# WORLDBUILDING DATA (Glaze Exploration Series)
# =============================================================================


@dataclass
class WorldbuildingData:
    """Planetary worldbuilding data for a ceramic vessel from the Glaze Exploration Series."""
    planet_name: str
    series_name: str
    series_description: str
    surface_geology: str
    orbital_data: str
    formation_history: str
    inhabitants: str
    generated_caption: Optional[str] = None


def get_worldbuilding_db_path() -> Path:
    """Get the worldbuilding feedback.db path."""
    return get_workspace_root() / "tools" / "feedback.db"


# =============================================================================
# CHARACTERISTIC-BASED PLANET MATCHING
# =============================================================================

_MATCH_THRESHOLD = 0.70  # Minimum similarity score to consider a planet match
_GLAZE_SERIES_ID = 1     # Default series_id for Glaze Exploration Series


def _extract_geological_terms(analysis) -> set[str]:
    """Extract geological terms from a piece's vision analysis.

    Uses COLOR_GEOLOGY, SURFACE_GEOLOGY, and MOOD_GEOLOGY dicts to map
    detected colors/surfaces/mood to individual geological words.

    Args:
        analysis: PhotoAnalysis or VideoAnalysis with detected characteristics

    Returns:
        Set of lowercase geological words describing the piece
    """
    from geology_vocabulary import COLOR_GEOLOGY, SURFACE_GEOLOGY, MOOD_GEOLOGY

    terms = set()
    all_text = ""

    # Extract from primary colors
    if hasattr(analysis, 'primary_colors') and analysis.primary_colors:
        all_text += " ".join(analysis.primary_colors).lower() + " "

    # Extract from secondary colors
    if hasattr(analysis, 'secondary_colors') and analysis.secondary_colors:
        all_text += " ".join(analysis.secondary_colors).lower() + " "

    # Extract from surface qualities
    if hasattr(analysis, 'surface_qualities') and analysis.surface_qualities:
        all_text += " ".join(analysis.surface_qualities).lower() + " "

    # Extract from mood
    if hasattr(analysis, 'mood') and analysis.mood:
        all_text += analysis.mood.lower() + " "

    # Map each detected word to its geological description, then split into individual terms
    for word in all_text.split():
        word_key = word.strip().replace(" ", "_")

        # Check color geology
        if word_key in COLOR_GEOLOGY:
            desc = COLOR_GEOLOGY[word_key].lower()
            terms.update(desc.split())

        # Check surface geology
        if word_key in SURFACE_GEOLOGY:
            desc = SURFACE_GEOLOGY[word_key].lower()
            terms.update(desc.split())

        # Check mood geology
        if word_key in MOOD_GEOLOGY:
            desc = MOOD_GEOLOGY[word_key].lower()
            terms.update(desc.split())

    # Filter to meaningful terms (remove stop words, very short words, and punctuation)
    _STOP_WORDS = {
        "the", "a", "an", "of", "and", "in", "to", "is", "it", "that", "on",
        "with", "as", "at", "by", "for", "from", "or", "be", "has", "had",
        "are", "been", "was", "were", "this", "not", "but", "its", "a",
        "only", "each", "every", "no", "under", "over", "where", "when",
        "how", "what", "which", "who", "can", "do", "did", "will", "may",
        "should", "would", "could", "still", "just", "very", "most",
        "across", "along", "entire", "specific", "create", "creates",
    }
    # Strip trailing punctuation from terms
    terms = {re.sub(r'[^a-z0-9-]', '', t) for t in terms}
    terms = {t for t in terms if len(t) > 2 and t not in _STOP_WORDS}

    return terms


def _score_planet_similarity(geo_terms: set[str], planet_surface_geology: str) -> float:
    """Score similarity between a piece's geological terms and a planet's geology.

    Args:
        geo_terms: Set of geological terms from the piece's vision analysis
        planet_surface_geology: The planet's surface_geology text from the DB

    Returns:
        Similarity score from 0.0 to 1.0
    """
    if not geo_terms or not planet_surface_geology:
        return 0.0

    planet_text = planet_surface_geology.lower()
    matching = sum(1 for term in geo_terms if term in planet_text)
    return matching / len(geo_terms)


def _load_all_planets() -> list[dict]:
    """Load all planets from the worldbuilding DB.

    Returns:
        List of dicts with keys: planet_name, surface_geology, orbital_data,
        formation_history, inhabitants, generated_caption, series_name,
        series_description, photo, series_id
    """
    db_path = get_worldbuilding_db_path()
    if not db_path.exists():
        return []

    try:
        conn = sqlite3.connect(str(db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT sp.planet_name, sp.surface_geology, sp.orbital_data,
                   sp.formation_history, sp.inhabitants, sp.generated_caption,
                   sp.photo, sp.series_id,
                   s.name AS series_name, s.description AS series_description
            FROM series_pieces sp
            JOIN series s ON sp.series_id = s.id
            WHERE sp.planet_name IS NOT NULL
        """)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        logging.warning(f"Failed to load planets from DB: {e}")
        return []


def _find_best_planet_match(analysis) -> Optional[tuple[str, float, dict]]:
    """Find the best matching planet for a piece based on geological characteristics.

    Args:
        analysis: PhotoAnalysis or VideoAnalysis with detected characteristics

    Returns:
        Tuple of (planet_name, score, planet_data) if match found above threshold,
        None otherwise
    """
    geo_terms = _extract_geological_terms(analysis)
    if not geo_terms:
        logging.debug("No geological terms extracted from analysis, skipping planet match")
        return None

    planets = _load_all_planets()
    if not planets:
        logging.debug("No planets in DB, skipping planet match")
        return None

    best_name = None
    best_score = 0.0
    best_data = None

    for planet in planets:
        score = _score_planet_similarity(geo_terms, planet["surface_geology"])
        if score > best_score:
            best_score = score
            best_name = planet["planet_name"]
            best_data = planet

    if best_score >= _MATCH_THRESHOLD and best_name:
        logging.info(f"Planet match: score={best_score:.2f} for {best_name} (threshold={_MATCH_THRESHOLD})")
        return (best_name, best_score, best_data)

    logging.info(f"No planet match (best={best_score:.2f} for {best_name or 'none'}).")
    return None


def _generate_planet_name(analysis, existing_names: list[str]) -> str:
    """Generate a unique planet name inspired by the piece's characteristics.

    Uses AI to generate a name following the convention RootWord-ix-Number
    or RootWord-os-Number. Falls back to deterministic name if AI fails.

    Args:
        analysis: PhotoAnalysis or VideoAnalysis with detected characteristics
        existing_names: List of planet names already in use

    Returns:
        A unique planet name string
    """
    colors = getattr(analysis, 'primary_colors', []) or []
    surfaces = getattr(analysis, 'surface_qualities', []) or []
    mood = getattr(analysis, 'mood', '') or ''

    # Build a prompt with the piece's characteristics
    characteristics = []
    if colors:
        characteristics.append(f"colors: {', '.join(colors)}")
    if surfaces:
        characteristics.append(f"surfaces: {', '.join(surfaces)}")
    if mood:
        characteristics.append(f"mood: {mood}")
    char_text = "; ".join(characteristics)

    existing_text = ", ".join(existing_names) if existing_names else "none"

    prompt = f"""Generate a single sci-fi planet name for an exoplanet with these visual characteristics: {char_text}

Rules:
- Follow the pattern: RootWord-ix-Number or RootWord-os-Number (e.g., "Ceruleix-2", "Pyr-os-8")
- The root should evoke the colors/surfaces listed above (use geological/scientific sounding roots)
- Use a number that isn't used by any existing planet
- Existing planet names to avoid: {existing_text}
- Output ONLY the planet name, nothing else — no quotes, no explanation"""

    try:
        config = get_ai_config()
        if config.backend == "ollama":
            model = config.ollama_writing_model
            is_cloud = model.endswith(":cloud")
            if is_cloud:
                # Cloud models use /api/chat with messages format
                # Note: thinking models (kimi-k2.5, qwen3.5) need high num_predict
                # because they spend tokens on reasoning before outputting content
                response = requests.post(
                    f"{config.ollama_base_url}/api/chat",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "options": {"temperature": 0.9, "num_predict": 4000},
                    },
                    timeout=300,
                )
                response.raise_for_status()
                result = response.json()
                name = result.get("message", {}).get("content", "").strip().strip('"').strip("'")
            else:
                # Local models use /api/generate
                response = requests.post(
                    f"{config.ollama_base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.9, "num_predict": 30},
                    },
                    timeout=30,
                )
                response.raise_for_status()
                name = response.json().get("response", "").strip().strip('"').strip("'")
        else:
            from openai import OpenAI
            api_key = os.environ.get("OPENROUTER_API_KEY")
            if not api_key:
                raise RuntimeError("OPENROUTER_API_KEY not set")
            client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")
            response = client.chat.completions.create(
                model=config.openrouter_caption_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=30,
                temperature=0.9,
            )
            name = response.choices[0].message.content.strip().strip('"').strip("'")

        # Validate: must match the pattern
        if re.match(r'^[A-Z][a-zA-Z]+(?:-[a-z]+)?-\d+$', name):
            logging.info(f"Generated planet name: {name}")
            return name
        else:
            raise RuntimeError(f"AI generated invalid planet name '{name}'. Stopping — no silent fallback to banned color names.")

    except Exception as e:
        raise RuntimeError(f"Planet name generation failed: {e}. Cannot continue without a valid planet name.")


def _create_new_planet(analysis, filename: str) -> Optional[WorldbuildingData]:
    """Create a new planet from a piece's vision analysis.

    Generates planet name, lore, and full worldbuilding data, then stores in DB.

    Args:
        analysis: PhotoAnalysis or VideoAnalysis with detected characteristics
        filename: Original media filename for DB storage

    Returns:
        WorldbuildingData with the new planet's data, or None if generation fails
    """
    if not os.environ.get("OPENROUTER_API_KEY"):
        logging.info("OPENROUTER_API_KEY not set, skipping planet auto-generation")
        return None

    try:
        from worldbuilding_generator import (
            generate_worldbuilding, generate_all_lore,
        )
        from geology_vocabulary import build_vocabulary_block

        # Load existing planet names for uniqueness check
        planets = _load_all_planets()
        existing_names = [p["planet_name"] for p in planets]

        # Generate planet name
        planet_name = _generate_planet_name(analysis, existing_names)

        # Extract characteristics for worldbuilding generation
        primary_colors = getattr(analysis, 'primary_colors', []) or []
        secondary_colors = getattr(analysis, 'secondary_colors', []) or []
        surface_qualities = getattr(analysis, 'surface_qualities', []) or []
        mood = getattr(analysis, 'mood', '') or ''
        technique = getattr(analysis, 'technique', None) or ''
        clay_type = getattr(analysis, 'clay_type', None) or ''
        firing_state = getattr(analysis, 'firing_state', None) or ''
        color_appearance = getattr(analysis, 'color_appearance', None) or ''
        form_attributes = getattr(analysis, 'form_attributes', []) or []
        hypotheses = getattr(analysis, 'hypotheses', []) or []

        # Build vocabulary block for the prompt
        vocab_block = build_vocabulary_block(primary_colors, surface_qualities, mood)

        # Generate lore line via batch lore (single piece)
        piece_vision = {
            "planet_name": planet_name,
            "colors": ", ".join(primary_colors) if primary_colors else "unknown",
            "textures": ", ".join(surface_qualities) if surface_qualities else "unknown",
            "mood": mood or "unknown",
            "form": getattr(analysis, 'piece_type', 'unknown'),
            "description": color_appearance or "",
            "hypotheses": "; ".join(hypotheses[:3]) if hypotheses else "",
        }
        lore_map = generate_all_lore([piece_vision])
        lore_line = lore_map.get(planet_name, "")

        # Generate full worldbuilding dossier
        wb_dict = generate_worldbuilding(
            hypotheses=hypotheses,
            surface_qualities=surface_qualities,
            primary_colors=primary_colors,
            secondary_colors=secondary_colors,
            form_attributes=form_attributes,
            mood=mood,
            technique=technique,
            clay_type=clay_type,
            firing_state=firing_state,
            color_appearance=color_appearance,
            planet_name=planet_name,
            lore_line=lore_line,
        )

        # Store in database
        db_path = get_worldbuilding_db_path()
        conn = sqlite3.connect(str(db_path), timeout=30)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO series_pieces
                (series_id, photo, planet_name, surface_geology, orbital_data,
                 formation_history, inhabitants, generated_caption)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            _GLAZE_SERIES_ID,
            filename,
            planet_name,
            wb_dict["surface_geology"],
            wb_dict["orbital_data"],
            wb_dict["formation_history"],
            wb_dict["inhabitants"],
            wb_dict["generated_caption"],
        ))
        conn.commit()
        conn.close()

        logging.info(f"Generated lore for {planet_name} (stored in DB)")

        # Get series info for WorldbuildingData
        series_data = next((p for p in planets if p.get("series_id") == _GLAZE_SERIES_ID), None)
        series_name = series_data["series_name"] if series_data else "Glaze Exploration Series"
        series_description = series_data["series_description"] if series_data else ""

        return WorldbuildingData(
            planet_name=planet_name,
            series_name=series_name,
            series_description=series_description,
            surface_geology=wb_dict["surface_geology"],
            orbital_data=wb_dict["orbital_data"],
            formation_history=wb_dict["formation_history"],
            inhabitants=wb_dict["inhabitants"],
            generated_caption=wb_dict["generated_caption"],
        )

    except Exception as e:
        # Close DB connection if it was opened before the error
        try:
            conn.close()
        except Exception:
            pass
        logging.error(f"Planet auto-generation failed: {e}")
        return None


def lookup_worldbuilding(filename: str, analysis=None) -> Optional[WorldbuildingData]:
    """Look up or generate worldbuilding data for a media file.

    Two paths:
    1. If analysis is provided (new path): characteristic-based matching or auto-generation
    2. If analysis is None (fallback): filename-based matching (backward compat)

    Args:
        filename: The media filename (just the filename, not full path)
        analysis: Optional PhotoAnalysis/VideoAnalysis for characteristic matching

    Returns:
        WorldbuildingData if found/generated, None otherwise
    """
    # --- NEW PATH: characteristic-based matching ---
    if analysis is not None:
        # Try matching to an existing planet
        match = _find_best_planet_match(analysis)
        if match:
            planet_name, score, planet_data = match
            return WorldbuildingData(
                planet_name=planet_data["planet_name"],
                series_name=planet_data["series_name"] or "Unknown Series",
                series_description=planet_data["series_description"] or "",
                surface_geology=planet_data["surface_geology"] or "",
                orbital_data=planet_data["orbital_data"] or "",
                formation_history=planet_data["formation_history"] or "",
                inhabitants=planet_data["inhabitants"] or "",
                generated_caption=planet_data["generated_caption"],
            )

        # No match found — try auto-generating a new planet
        logging.info("No planet match. Generating new planet...")
        new_planet = _create_new_planet(analysis, filename)
        if new_planet:
            return new_planet

        # Auto-generation failed (no API key, etc.) — fall through to filename matching
        logging.info("Planet auto-generation unavailable, falling back to filename matching")

    # --- FALLBACK PATH: filename-based matching (backward compat) ---
    db_path = get_worldbuilding_db_path()
    if not db_path.exists():
        return None

    try:
        conn = sqlite3.connect(str(db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Build query with series info
        query = """
            SELECT sp.planet_name, sp.surface_geology, sp.orbital_data,
                   sp.formation_history, sp.inhabitants, sp.generated_caption,
                   s.name AS series_name, s.description AS series_description
            FROM series_pieces sp
            JOIN series s ON sp.series_id = s.id
            WHERE 1=0
        """
        params = []

        # Strategy 1: Planet-name matching (e.g., "Ceruleix-2_rotating.mp4" -> "Ceruleix-2")
        stem = Path(filename).stem
        planet_match = re.match(r'^([A-Z][a-zA-Z]+(?:-[a-z]+)*-\d+)', stem)
        if planet_match:
            query += " OR sp.planet_name = ?"
            params.append(planet_match.group(1))

        # Strategy 2: Direct photo filename match (case-insensitive)
        query += " OR LOWER(sp.photo) = ?"
        params.append(filename.lower())

        # Also try just the stem without extension
        query += " OR LOWER(sp.photo) = ?"
        params.append(stem.lower())

        cursor.execute(query, params)
        row = cursor.fetchone()
        conn.close()

        if row and row["planet_name"]:
            return WorldbuildingData(
                planet_name=row["planet_name"],
                series_name=row["series_name"] or "Unknown Series",
                series_description=row["series_description"] or "",
                surface_geology=row["surface_geology"] or "",
                orbital_data=row["orbital_data"] or "",
                formation_history=row["formation_history"] or "",
                inhabitants=row["inhabitants"] or "",
                generated_caption=row["generated_caption"],
            )
        return None
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        logging.warning(f"Worldbuilding DB lookup failed: {e}")
        return None


# =============================================================================
# AI MODEL CONFIGURATION
# =============================================================================

# Backend selection: "ollama" (local, FREE) or "openrouter" (API, paid)
AI_BACKEND: Literal["ollama", "openrouter"] = "ollama"

# Ollama configuration (SINGLE-MODEL: Kimi K2.5)
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_VISION_MODEL = "kimi-k2.5:cloud"    # Multimodal - ceramic identification
OLLAMA_WRITING_MODEL = "kimi-k2.5:cloud"   # Text - natural caption generation

# OpenRouter configuration (API - PAID, fallback)
OPENROUTER_VISION_MODEL = "google/gemini-3-flash-preview"  # $0.50/M input
OPENROUTER_CAPTION_MODEL = "deepseek/deepseek-v3.2"  # $0.26/M input


@dataclass
class AIConfig:
    """Configuration for AI model usage."""
    backend: Literal["ollama", "openrouter"] = AI_BACKEND

    # Ollama settings (two-model architecture)
    ollama_base_url: str = OLLAMA_BASE_URL
    ollama_vision_model: str = OLLAMA_VISION_MODEL    # For photo analysis
    ollama_writing_model: str = OLLAMA_WRITING_MODEL  # For caption generation

    # OpenRouter settings (fallback)
    openrouter_vision_model: str = OPENROUTER_VISION_MODEL
    openrouter_caption_model: str = OPENROUTER_CAPTION_MODEL

    @property
    def is_local(self) -> bool:
        """Check if using local (free) models."""
        return self.backend == "ollama"

    @property
    def is_api(self) -> bool:
        """Check if using API (paid) models."""
        return self.backend == "openrouter"


# Global config instance (can be overridden)
_ai_config = AIConfig()


def get_ai_config() -> AIConfig:
    """Get the current AI configuration."""
    return _ai_config


def set_ai_config(config: AIConfig):
    """Set the AI configuration."""
    global _ai_config
    _ai_config = config


def configure_ai(
    backend: Literal["ollama", "openrouter"] = None,
    ollama_vision_model: str = None,
    ollama_writing_model: str = None,
    openrouter_vision_model: str = None,
    openrouter_caption_model: str = None
):
    """
    Configure AI settings.

    Args:
        backend: "ollama" (local, FREE) or "openrouter" (API, paid)
        ollama_vision_model: Vision model for Ollama (e.g., "qwen3.5:cloud")
        ollama_writing_model: Writing model for Ollama (e.g., "deepseek-v3.2:cloud")
        openrouter_vision_model: Vision model via OpenRouter
        openrouter_caption_model: Caption model via OpenRouter
    """
    global _ai_config
    config = AIConfig()

    if backend:
        config.backend = backend
    if ollama_vision_model:
        config.ollama_vision_model = ollama_vision_model
    if ollama_writing_model:
        config.ollama_writing_model = ollama_writing_model
    if openrouter_vision_model:
        config.openrouter_vision_model = openrouter_vision_model
    if openrouter_caption_model:
        config.openrouter_caption_model = openrouter_caption_model

    _ai_config = config


# =============================================================================
# DATA CLASSES
# =============================================================================


class ContentType(Enum):
    """Type of ceramic content in the media."""
    FINISHED_PIECE = "finished"
    PROCESS = "process"
    KILN_REVEAL = "kiln_reveal"
    STUDIO = "studio"
    DETAIL = "detail"
    # Video-specific types
    PROCESS_VIDEO = "process_video"      # Throwing, trimming, glazing videos
    KILN_REVEAL_VIDEO = "kiln_reveal_video"  # Kiln opening videos
    STUDIO_TOUR = "studio_tour"          # Studio walkthrough
    TIME_LAPSE = "time_lapse"            # Time-lapse pottery making
    SINGLE_PIECE_VIDEO = "single_piece_video"  # Video showcasing one piece
    COLLECTION_VIDEO = "collection_video"      # Video showing multiple pieces
    COMPARISON_VIDEO = "comparison_video"      # Video comparing pieces side-by-side


@dataclass
class PhotoAnalysis:
    """Analysis of a photo's content."""
    content_type: ContentType
    piece_type: str  # vase, bowl, mug, planter, sculpture, etc.
    primary_colors: list[str]
    secondary_colors: list[str]
    glaze_type: Optional[str]  # Technical: best-guess glaze IDs
    color_appearance: Optional[str]  # Visual: color description using taxonomy (what you SEE, not what glazes you think)
    technique: Optional[str]  # wheel-thrown, handbuilt, etc.
    mood: str  # warm, cool, earthy, modern, organic
    is_process: bool
    dimensions_visible: bool
    suggested_hook: str
    firing_state: Optional[str] = None  # "greenware", "bisque", "glazed", "finished"
    surface_qualities: list[str] = field(default_factory=list)  # visual surface phenomena
    piece_count: int = 1  # Number of pieces visible (1=single, 2-5=few, 6+=collection)
    # Taxonomy expansion (March 2026)
    clay_type: Optional[str] = None  # b_mix, death_valley, dark_brown, soldate_60, long_beach, half_half, stoney_white, recycled
    form_attributes: list[str] = field(default_factory=list)  # lidded, stackable, pourable, handheld
    purpose: Optional[str] = None  # functional, decorative, sculptural, hybrid
    product_family: Optional[str] = None  # dinnerware, serveware, drinkware, decor, garden, art
    # Hypothesis generation (March 2026)
    hypotheses: list[str] = field(default_factory=list)  # 3-5 initial hypotheses before concluding
    safety_flags: list[str] = field(default_factory=list)  # food_safe, microwave_safe, dishwasher_safe, outdoor_safe
    # Enhanced vision analysis (March 2026)
    lighting: Optional[dict] = None  # {"light_source": "...", "direction": "...", "quality": "...", "impact": "..."}
    photo_quality: Optional[dict] = None  # {"angle": "...", "obstructions": "...", "completeness": "..."}
    uncertainties: Optional[list] = None  # ["Foot in shadow", "Glare may mask surface"]
    color_distribution: Optional[str] = None  # "uniform", "breaking", "pooling", "variegated", "gradient", "banded"
    # Worldbuilding (Glaze Exploration Series)
    worldbuilding: Optional[WorldbuildingData] = None


@dataclass
class GeneratedCaption:
    """Generated caption with all components."""
    hook: str
    body: str
    cta: str
    hashtags: str
    full_caption: str
    alt_text: str = ""  # Accessibility description (max 100 chars)


@dataclass
class VideoAnalysis:
    """Analysis of a video's content."""
    content_type: ContentType
    video_type: str  # process, reveal, tour, timelapse
    duration_seconds: float
    primary_colors: list[str]
    activity: str  # throwing, trimming, glazing, etc.
    mood: str
    has_audio: bool
    suggested_hook: str
    is_reel_suitable: bool  # True if < 90s and vertical/square
    aspect_ratio_category: str = "horizontal"
    duration_warning: Optional[str] = None
    piece_type: Optional[str] = None
    technique: Optional[str] = None
    # Worldbuilding (Glaze Exploration Series)
    worldbuilding: Optional[WorldbuildingData] = None


@dataclass
class CarouselAnalysis:
    """Analysis for carousel posts."""
    content_types: list[ContentType]  # One per item
    firing_states: list[str] = field(default_factory=list)  # Per-slide firing state (greenware/bisque/glazed/finished)
    primary_theme: str = ""
    narrative_flow: str = ""  # How items connect
    hooks: list[str] = field(default_factory=list)
    cta: str = ""


@dataclass
class StoriesAnalysis:
    """Analysis for Instagram Stories (15s vertical videos)."""
    content_type: ContentType
    duration_seconds: float
    activity: str  # throwing, trimming, glazing, packing, etc.
    mood: str
    text_overlay_suggestions: list[str] = field(default_factory=list)
    sticker_suggestions: list[str] = field(default_factory=list)
    is_story_suitable: bool = True  # True if <= 15s and vertical


def is_video_file(filepath: str) -> bool:
    """Check if a file is a video based on extension."""
    video_extensions = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".wmv"}
    return Path(filepath).suffix.lower() in video_extensions


def get_video_duration(video_path: str) -> float:
    """
    Get video duration in seconds using ffprobe.

    Args:
        video_path: Path to the video file

    Returns:
        Duration in seconds, or 0.0 if detection fails
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path
            ],
            capture_output=True,
            text=True,
            check=True
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError):
        return 0.0


def extract_video_frames(video_path: str, max_frames: int = 5) -> list[str]:
    """
    Extract evenly-spaced frames from video using ffmpeg.

    Args:
        video_path: Path to the video file
        max_frames: Maximum number of frames to extract (default 5)

    Returns:
        List of temp frame file paths (PNG format).
        Caller is responsible for cleaning up these files.

    Notes:
        - For short videos, fewer frames will be extracted (min 1 second per frame)
        - Frames are distributed at 10%-90% of video duration to avoid edge cases

    Example cleanup:
        frames = extract_video_frames("video.mp4", max_frames=5)
        try:
            # use frames...
        finally:
            for frame in frames:
                os.unlink(frame)
    """
    # Get video duration
    duration = get_video_duration(video_path)
    if duration <= 0:
        return []

    # Adjust max_frames for short videos (at least 1 second between frames)
    # A 3-second video should get max 3 frames, not 5
    effective_max_frames = min(max_frames, max(1, int(duration)))

    # Create temp directory for frames
    temp_dir = tempfile.mkdtemp(prefix="video_frames_")

    # Calculate timestamps for evenly-spaced frames
    # Avoid extracting at exactly 0 or duration (potential edge cases)
    frames = []
    for i in range(effective_max_frames):
        # Distribute frames evenly: first at ~10%, last at ~90%
        progress = (i + 1) / (effective_max_frames + 1)
        timestamp = duration * progress

        output_path = os.path.join(temp_dir, f"frame_{i:02d}.png")

        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-ss", str(timestamp),
                    "-i", video_path,
                    "-vframes", "1",
                    "-q:v", "2",  # High quality PNG
                    output_path
                ],
                capture_output=True,
                check=True
            )
            if os.path.exists(output_path):
                frames.append(output_path)
        except subprocess.CalledProcessError:
            continue  # Skip failed frames

    return frames


def get_workspace_root() -> Path:
    """Get the workspace root directory."""
    return Path(__file__).parent.parent.parent.parent


def get_voice_rules_path() -> Path:
    """Get the voice rules file path."""
    return get_workspace_root() / "brand" / "voice-rules.md"


def get_hashtag_library_path() -> Path:
    """Get the hashtag library file path."""
    return get_workspace_root() / "shared" / "hashtag-library.md"


def load_voice_rules() -> str:
    """Load the voice rules markdown file."""
    path = get_voice_rules_path()
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def load_hashtag_library() -> str:
    """Load the hashtag library markdown file."""
    path = get_hashtag_library_path()
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def load_brand_identity() -> str:
    """Load the brand identity markdown file."""
    path = get_workspace_root() / "brand" / "identity.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def extract_few_shot_examples(voice_rules: str) -> str:
    """Extract the Top Performing Captions section from voice-rules.md for few-shot prompting."""
    if not voice_rules:
        return ""

    # Extract the Top Performing Captions section
    match = re.search(
        r'## Top Performing Captions.*?(?=## Lower Performing|\Z)',
        voice_rules,
        re.DOTALL
    )
    if match:
        return match.group(0).strip()
    return ""


def build_worldbuilding_block(wb: WorldbuildingData) -> str:
    """Build the PLANETARY WORLDBUILDING section for AI prompts."""
    sections = []
    sections.append(f"PLANETARY WORLDBUILDING — {wb.series_name}")
    sections.append(f"Series concept: {wb.series_description}")
    sections.append("")
    sections.append(f"Planet: {wb.planet_name}")
    sections.append(f"Surface Geology: {wb.surface_geology}")
    if wb.orbital_data:
        sections.append(f"Orbital Data: {wb.orbital_data}")
    if wb.formation_history:
        sections.append(f"Formation History: {wb.formation_history}")
    if wb.inhabitants:
        sections.append(f"Inhabitants: {wb.inhabitants}")
    sections.append("")
    sections.append("INSTRUCTION: This piece IS this planet. Write the caption in planetary exploration language:")
    sections.append("- Call the piece by its planet name (e.g., 'Ceruleix-2', not 'this vase')")
    sections.append("- Describe colors as geological features (e.g., 'cobalt-iron oxidation' not 'blue')")
    sections.append("- Reference the formation history and orbital data")
    sections.append("- Frame the viewer as an explorer discovering a new world")
    sections.append("- End with a question about the planet or the exploration")

    return "\n".join(sections)


def build_geological_vocab_block(analysis) -> str:
    """Build the GEOLOGICAL VOCABULARY section from detected colors and surfaces."""
    colors = getattr(analysis, 'primary_colors', []) or []
    surfaces = getattr(analysis, 'surface_qualities', []) or []
    mood = getattr(analysis, 'mood', None)

    if not colors and not surfaces:
        return ""

    try:
        from geology_vocabulary import build_vocabulary_block
        vocab = build_vocabulary_block(colors, surfaces, mood)
        if vocab:
            return f"GEOLOGICAL VOCABULARY (use these terms, NOT raw color names):\n{vocab}\n\nNO FOOD OR FABRIC METAPHORS. 'Chocolate' becomes 'deep iron-manganese oxide deposits.' 'Denim' becomes 'cobalt-iron oxidation under specific atmospheric pressure.'"
    except ImportError:
        pass
    return ""


def build_brand_identity_block(identity_md: str) -> str:
    """Extract key brand identity elements for prompt injection."""
    if not identity_md:
        return ""

    lines = ["BRAND IDENTITY"]

    # Extract CERAFICA etymology
    etymology_match = re.search(
        r'\*\*CERAFICA = (.+?)\*\*',
        identity_md
    )
    if etymology_match:
        lines.append(f"Brand: CERAFICA = {etymology_match.group(1)}")

    # Extract handle
    handle_match = re.search(r'\*\*Handle\*\*:\s*(@\S+)', identity_md)
    if handle_match:
        lines.append(f"Instagram: {handle_match.group(1)}")

    # Extract studio info
    studio_match = re.search(r'\*\*Where work is made\*\*:\s*(.+?)(?:\n|$)', identity_md)
    if studio_match:
        lines.append(f"Studio: {studio_match.group(1).strip()}")

    # Extract brand pillars
    pillars_match = re.search(
        r'## Brand Pillars\n\n((?:\d+\..+\n?)+)',
        identity_md
    )
    if pillars_match:
        lines.append("")
        lines.append("Brand Pillars:")
        for line in pillars_match.group(1).strip().split("\n"):
            line = line.strip()
            if line:
                # Clean up markdown bold
                line = re.sub(r'\*\*(.+?)\*\* —', r'\1:', line)
                lines.append(f"  {line}")

    return "\n".join(lines)


# Piece type keywords for detection
PIECE_KEYWORDS = {
    "vase": ["vase", "vessel", "tall", "slim"],
    "bowl": ["bowl", "round", "curved", "dish"],
    "mug": ["mug", "cup", "handle", "tumbler"],
    "planter": ["planter", "pot", "plant", "drainage"],
    "plate": ["plate", "platter", "dish", "flat"],
    "sculpture": ["sculpture", "sculptural", "abstract", "form"],
    "jar": ["jar", "container", "lidded", "canister"],
}

# Glaze keywords - Membership Studio cone 10 reduction glazes
GLAZE_KEYWORDS = {
    # === MEMBERSHIP STUDIO GLAZES (Cone 10 Reduction) ===

    # CLEARS
    "lucid_clear": ["lucid clear", "lucid"],
    "tom_coleman_clear": ["tom coleman clear", "tom coleman", "coleman clear"],

    # WHITES
    "choinard_white": ["choinard white", "choinard"],
    "white_crawl": ["white crawl", "crawl white"],
    "tighty_whitey": ["tighty whitey", "tighty", "whitey"],

    # NEUTRALS
    "long_beach_black": ["long beach black", "long beach", "lb black"],
    "larrys_grey": ["larry's grey", "larrys grey", "larry grey"],

    # GREENS
    "froggy": ["froggy", "frog"],
    "toady": ["toady", "toad"],
    "ming_green": ["ming green", "ming"],
    "celadon": ["celadon", "celadon green"],
    "amber_celadon": ["amber celadon", "amber celadon green"],

    # SHINOS
    "luster_shino": ["luster shino", "luster"],
    "malcoms_shino": ["malcom's shino", "malcoms shino", "malcom shino"],

    # BLUES
    "jensen_blue": ["jensen blue", "jensen"],
    "aegean_blue": ["aegean blue", "aegean"],
    "chun_blue": ["chun blue", "chun"],
    "blugr": ["blugr", "blue green", "blue-green"],

    # REDS
    "iron_red": ["iron red", "iron"],
    "johns_red": ["john's red", "johns red", "john red"],
    "pablos_red": ["pablo's red", "pablos red", "pablo red"],

    # PURPLES/PINKS
    "shocking_purple": ["shocking purple", "purple", "shocking"],
    "pinky": ["pinky", "pink"],
    "raspberry": ["raspberry", "raspberry pink"],

    # BROWNS/DARKS
    "cosmic_brown": ["cosmic brown", "cosmic"],
    "teadust": ["teadust", "tea dust"],
    "tenmoku": ["tenmoku", "temmoku"],

    # YELLOWS
    "mellow_yellow": ["mellow yellow", "mellow"],

    # LUSTERS
    "honey_luster": ["honey luster", "honey"],

    # CRYSTALS
    "strontium_crystal": ["strontium crystal", "strontium", "crystal"],

    # OTHERS
    "sun_valley": ["sun valley", "sunvalley"],
    "angel_eyes": ["angel eyes", "angel"],

    # === SURFACE TYPES (for AI vision fallback) ===
    "matte": ["matte", "flat", "satin matte"],
    "glossy": ["glossy", "shiny", "bright", "high gloss"],
    "satin": ["satin", "semi-gloss", "semi matte"],
    "speckled": ["speckle", "speckled", "dots", "spots"],

    # === GENERIC FALLBACKS ===
    "clear": ["clear", "transparent"],
    "white": ["white glaze", "opaque white"],
}

# Technique keywords
TECHNIQUE_KEYWORDS = {
    "wheel-thrown": ["wheel", "thrown", "spinning", "turning"],
    "handbuilt": ["handbuilt", "slab", "coil", "pinch"],
    "slip-cast": ["slip", "cast", "mold"],
}


# =============================================================================
# TEXTURE SYNONYMS - Human vocabulary, not thesaurus overdose
# =============================================================================

TEXTURE_SYNONYMS = {
    # Color variation (NOT just "variegation")
    "variegation": [
        "mottled", "patchy", "streaked", "cloudy", "blotchy",
        "uneven color", "shifting tones", "natural variation",
    ],

    # Breaking (edges/high points)
    "breaking": [
        "breaking at the edges", "darker at the rim", "lighter on the high points",
        "edge variation", "rim contrast", "thinner at the edges",
    ],

    # Pooling (glaze settling in low spots)
    "color_pooling": [
        "pooling in the grooves", "settling in the recesses", "gathering in the curves",
        "darker where it pools", "thicker in the low spots",
    ],

    # Crawling (glaze pulling back)
    "crawling": [
        "crawling texture", "pulling back", "beading up", "retreating",
        "that intentional crawling", "bare spots where the glaze pulled",
    ],

    # Crackle/craze
    "crackle": [
        "crackle pattern", "crazing", "tiny cracks", "spiderweb pattern",
        "network of lines", "crackled surface",
    ],

    # Crystalline
    "crystalline": [
        "crystal formations", "tiny crystals", "sparkling crystals",
        "frost-like patterns", "micro-crystals",
    ],

    # Running/rivulets
    "running": [
        "running down the sides", "drip marks", "flowing patterns",
        "rivulets", "streaks where it ran",
    ],

    # Carbon trapping
    "carbon_trapping": [
        "carbon trapping", "trapped carbon", "smoky patches", "dark flashes",
        "carbon marks", "reduction flashing",
    ],

    # Oil spot
    "oil_spot": [
        "oil spot pattern", "metallic spots", "iridescent dots",
        "shimmering spots", "oil spot effect",
    ],

    # Speckled
    "speckled": [
        "speckled", "flecked", "spotted", "peppered",
        "tiny dots", "freckled surface",
    ],

    # Surface sheen
    "matte": ["matte finish", "soft surface", "velvety", "flat finish"],
    "satin": ["satin sheen", "soft glow", "subtle shine", "semi-gloss"],
    "gloss": ["glossy", "glassy", "shiny", "reflective", "glass-like"],

    # General texture
    "texture": [
        "texture", "surface", "feel", "finish", "tactile quality",
        "hand", "surface quality",
    ],

    # Surface personality
    "reactive": [
        "unpredictable", "wild", "alive", "surprising", "each one unique",
        "does its own thing", "never the same twice",
    ],
}

# =============================================================================
# GLAZE COMBINATION VOCABULARY (March 2026)
# Artistic philosophy: "A piece is finished when it tells a story without trying"
# =============================================================================

GLAZE_COMBO_VOCABULARY = {
    # "Tells a story" language - for pieces that speak for themselves
    "story_phrases": [
        "Tells its own story",
        "Every angle has a chapter",
        "The surface speaks",
        "No explanation needed",
        "Reads like a sentence you can't improve",
        "The glaze does the talking",
        "Self-evident",
        "Doesn't need me to explain it",
    ],

    # Layering language - for pieces with multiple glazes or firings
    "layering": [
        "Built in layers, reads as one",
        "Each firing added a sentence",
        "The strata of this piece",
        "Archaeology of glaze",
        "Three layers, one voice",
        "Stacked glazes, unified result",
        "The history is in the surface",
    ],

    # Process-as-collaborator - the kiln did the work
    "process_collaborator": [
        "The kiln and I agreed on this one",
        "Fire's contribution",
        "Let the materials speak",
        "Found the beauty, didn't force it",
        "The process revealed this",
        "The kiln knew what it was doing",
        "I just put it in the kiln. The rest happened on its own.",
    ],

    # Raw/primal language - for gestural, energetic work
    "raw_primal": [
        "Urgent marks, quiet result",
        "Raw edges, refined feeling",
        "Nothing overworked here",
        "First impulse, final form",
        "Gestural glaze application",
        "Captured the moment",
        "Alive in a way I didn't plan",
    ],

    # Copper flashing specific - for copper shavings/wire in clay
    "copper_flashing": [
        "Those copper moments",
        "The copper did its thing",
        "Blood chest marks from copper shavings",
        "Copper flashing where I needed it",
        "The copper found its way through",
    ],
}

def get_glaze_combo_phrase(category: str = "story_phrases") -> str:
    """
    Get a random phrase from the glaze combination vocabulary.

    Args:
        category: One of "story_phrases", "layering", "process_collaborator",
                  "raw_primal", "copper_flashing"

    Returns:
        A randomly selected phrase
    """
    import random
    phrases = GLAZE_COMBO_VOCABULARY.get(category, GLAZE_COMBO_VOCABULARY["story_phrases"])
    return random.choice(phrases)

# =============================================================================
# HOOK PATTERNS - First line of captions that stop the scroll
# ==============================================================================

HOOK_PATTERNS = {
    # Curiosity hooks - spark interest
    "curiosity": [
        "The kiln gods were kind today.",
        "This glaze combination shouldn't work. But it does.",
        "Three months of work. One kiln opening.",
        "What I thought would happen vs what actually happened.",
        "The before and after on this one is wild.",
    ],

    # Specific-value hooks - immediate clarity on what this is
    "specific_value": [
        "{glaze} on {clay}. The combo I didn't know I needed.",
        "{piece}. {technique}. {one_detail}.",
        "{piece} with {glaze}. The {surface_quality} gets me every time.",
        "One of one. Won't make another exactly like this.",
        "{glaze}. That's it. That's the caption.",
    ],

    # Vulnerability hooks - human, relatable
    "vulnerability": [
        "This one was supposed to be a bowl.",
        "Attempt #{number}. Finally didn't wobble.",
        "Did not expect it to turn out this good.",
        "The crack happened during drying. I kept it anyway.",
        "Not my best work but it's got personality.",
        "That kiln opening feeling when you're not sure what you'll get.",
    ],

    # Process hooks - for making content
    "process": [
        "From {start} to {finish} in {time}.",
        "{technique} demo. {one_tip}.",
        "The {part} is always the hardest part.",
        "Watch this {time_in_real} (actually {real_time}).",
        "Messy hands. Clean result.",
    ],

    # Engagement hooks - invite interaction
    "engagement": [
        "Matte or gloss on this one? Can't decide.",
        "Rate this glaze combo 1-10, be honest.",
        "Drop a 🔥 if this glaze variation is your vibe.",
        "Which one's your favorite? Left or right?",
        "Tag someone who needs to see this glaze.",
    ],

    # Minimal hooks - sometimes less is more
    "minimal": [
        "Just a {piece}. A really good one though.",
        "{glaze}.",
        "Made this today.",
        "Kiln opening day.",
        "Fresh from the kiln.",
    ],

    # Sales hooks - for available pieces
    "sales": [
        "Looking for its forever home.",
        "Available. DM to claim.",
        "One available. First to claim gets it.",
        "Shop update: {piece} is listed.",
    ],
}

def get_hook(category: str, **kwargs) -> str:
    """
    Get a random hook from a category, with optional variable substitution.

    Args:
        category: Hook category (curiosity, specific_value, vulnerability, etc.)
        **kwargs: Variables to substitute (glaze, piece, technique, etc.)

    Returns:
        A hook string with variables filled in
    """
    import random
    hooks = HOOK_PATTERNS.get(category, HOOK_PATTERNS["specific_value"])
    hook = random.choice(hooks)

    # Substitute variables
    for key, value in kwargs.items():
        hook = hook.replace(f"{{{key}}}", str(value))

    # Clean up any remaining placeholders
    import re
    hook = re.sub(r'\{[^}]+\}', '', hook).strip()
    hook = re.sub(r'\s+', ' ', hook)  # Clean up multiple spaces

    return hook


def get_texture_synonym(quality: str, context: str = "neutral") -> str:
    """
    Get a random synonym for a texture quality.

    Args:
        quality: The texture quality (e.g., "variegation", "breaking")
        context: "neutral", "descriptive", or "enthusiastic"

    Returns:
        A randomly selected synonym
    """
    import random
    synonyms = TEXTURE_SYNONYMS.get(quality, [quality])
    return random.choice(synonyms)

# =============================================================================
# TAXONOMY EXPANSION (March 2026)
# =============================================================================

# Clay body taxonomy (Laguna Cone 10) — loaded from ceramics-foundation or hardcoded fallback
_loaded_clays = load_clay_bodies()
if _loaded_clays:
    CLAY_BODY_TAXONOMY = {
        body['name'].lower().replace(' ', '_'): {
            'properties': body['properties'],
            'visual_cues': body['visual_cues'],
            'best_glazes': body['best_glazes'],
            'avoid_glazes': body.get('avoid_glazes', []),
        } for body in _loaded_clays['clay_bodies']
    }
else:
    CLAY_BODY_TAXONOMY = {
        "b_mix": {
            "properties": ["cream-white raw", "smooth porcelain", "fires gray/white", "true glaze color"],
            "visual_cues": ["very smooth surface", "white/cream color", "clean lines", "no speckling"],
            "best_glazes": ["celadon", "clear", "blue", "white"],
            "avoid_glazes": ["shino"],  # Shinos give pink/tan on B-Mix
        },
        "death_valley": {
            "properties": ["reddish raw", "dark brown fired", "iron speckling", "rustic"],
            "visual_cues": ["iron speckles visible", "warm undertone", "rustic texture"],
            "best_glazes": ["shino", "tenmoku", "iron_red"],
        },
        "dark_brown": {
            "properties": ["strong warm undertone", "dramatic with light glazes"],
            "visual_cues": ["dark visible through glaze", "warm showing at edges"],
        },
        "soldate_60": {
            "properties": ["60 mesh sand", "textured", "yellow/brown in reduction"],
            "visual_cues": ["visible sand texture", "warm undertones"],
        },
        "long_beach": {
            "properties": ["brownish-pink raw", "light brown reduction", "warm fluid throwing"],
            "visual_cues": ["warm pink undertone", "smooth throw"],
        },
        "half_half": {
            "properties": ["gray/white", "porcelain + stoneware mix", "versatile"],
            "visual_cues": ["white to gray range", "smooth"],
        },
        "stoney_white": {
            "properties": ["white stoneware", "mottled in reduction", "rustic"],
            "visual_cues": ["white with variation", "rustic character"],
        },
        "recycled": {
            "properties": ["variable", "unpredictable"],
            "visual_cues": ["inconsistent color", "mixed textures"],
        },
    }

# Form attributes by piece type (expanded taxonomy from ceramics education)
# These are DESCRIPTIVE vocabulary, not filtering rules - accept whatever the AI returns
FORM_ATTRIBUTES = {
    # Functional
    "lidded": ["jar", "canister", "casserole", "teapot"],
    "stackable": ["bowl", "plate", "mug", "cup"],
    "pourable": ["pitcher", "ewer", "teapot", "creamer"],
    "handheld": ["mug", "cup", "tumbler", "bowl"],
    "nested": ["bowl", "plate"],

    # Body Profile (anatomical shape terms taught in ceramics)
    "cylindrical": [],      # straight parallel sides
    "spherical": [],        # ball-shaped
    "ovoid": [],            # egg-shaped
    "conical": [],          # tapering to point
    "bell_shaped": [],      # flared at bottom, narrow at top
    "shouldered": [],       # distinct shoulder where body curves outward
    "necked": [],           # has a narrow neck below rim
    "waisted": [],          # narrow in middle (hourglass)
    "bulbous": [],          # round, swollen body
    "elongated": [],        # stretched tall
    "squat": [],            # short and wide

    # Rim/Lip Treatment
    "flared": [],           # widens at rim
    "tapered": [],          # narrows gradually
    "rolled": [],           # thickened rolled rim
    "rounded": [],          # soft rounded edge
    "squared": [],          # sharp 90-degree edge

    # Foot/Base
    "footed": [],           # has distinct foot ring
    "trimmed": [],          # trimmed foot (leather-hard)
    "flat_base": [],        # sits flat without foot ring

    # Character/Aesthetic
    "organic": [],          # natural, flowing curves
    "geometric": [],        # angular, precise
    "asymmetrical": [],     # intentionally off-balance
    "sculptural": [],       # artistic, non-functional emphasis
    "refined": [],          # smooth, polished
    "rustic": [],           # rough, natural texture
    "bold": [],             # strong presence
    "delicate": [],         # fine, fragile appearance

    # Surface Form (3D texture)
    "faceted": [],          # flat geometric planes cut into surface
    "fluted": [],           # concave vertical grooves
    "ribbed": [],           # raised ridges
    "carved": [],           # cut/incised decoration
    "textured": [],         # general surface texture
    "smooth": [],           # no texture
}

# Color taxonomy for cone 10 reduction firing — loaded from ceramics-foundation or hardcoded fallback
# These are GUIDANCE vocabulary - accept any color the AI returns, don't filter
_loaded_colors = load_colors()
if _loaded_colors:
    COLOR_TAXONOMY = {name: info['family'] for name, info in _loaded_colors.items()}
else:
    COLOR_TAXONOMY = {
        # BROWNS (cone 10 nuance - most common in reduction firing)
        "toast": "brown", "pyrolusite": "brown", "bituminous": "brown", "anthracite": "brown",
        "ferruginous": "brown", "mahogany": "brown", "tannin": "brown", "lignite": "brown",
        "tobacco": "brown", "sienna": "brown", "umber": "brown", "ochre": "brown",
        "russet": "brown", "bronze": "brown", "copper": "brown", "tan": "brown",
        "fawn": "brown", "siderite": "brown", "jarosite": "brown", "gilsonite": "brown",

        # REDS (reduction reds are muted, not bright)
        "rust": "red", "brick": "red", "garnet": "red", "burgundy": "red",
        "maroon": "red", "realgar": "red", "oxblood": "red", "terracotta": "red",
        "dried_rose": "red", "clay_red": "red", "spinel": "red", "rhodochrosite": "red",

        # GRAYS (atmospheric reduction grays)
        "slate": "gray", "charcoal": "gray", "dove": "gray", "stone": "gray",
        "ash": "gray", "smoke": "gray", "pewter": "gray", "graphite": "gray",
        "flint": "gray", "steel": "gray", "smoky": "gray",

        # WHITES/PALE MINERALS (warm cone 10 whites)
        "bone": "white", "ivory": "white", "calcite": "white", "gypsum": "white",
        "parchment": "white", "argillite": "white", "bisque": "white", "porcelain": "white",

        # GREENS (reduction greens)
        "celadon": "green", "sage": "green", "serpentine": "green", "moss": "green",
        "seafoam": "green", "oribe": "green", "glauconite": "green",

        # BLUES
        "chun_blue": "blue", "teal": "blue", "slate_blue": "blue",
        "ice_blue": "blue", "chalcedony": "blue",

        # ORANGES/YELLOWS
        "shino": "orange", "amber": "orange", "retinite": "yellow",
        "wulfenite": "orange", "mimetite": "orange", "gold": "yellow",

        # FALLBACKS (common color names)
        "white": "white", "black": "black", "brown": "brown", "red": "red",
        "orange": "orange", "yellow": "yellow", "green": "green", "blue": "blue",
        "purple": "purple", "pink": "pink", "grey": "gray", "gray": "gray",
    }

# Context-aware hashtag generation (March 2026 — Instagram hard-limits to 5 hashtags)
# Sources: IQHashtags.com, Viraly.io, EvergreenFeed, Social Media Today, Instagram Help Center
#
# Strategy: 5-slot framework — each slot serves a distinct purpose
#   Slot 1: Niche (what is this) — 50K-500K posts
#   Slot 2: Technique (how was it made) — 50K-200K posts
#   Slot 3: Audience (who is this for) — 100K-500K posts
#   Slot 4: Content type (what format) — 50K-200K posts
#   Slot 5: Local (where) — 10K-50K posts (always included)
#
# Key rules:
#   - No glaze-specific tags (too small, nobody searches them)
#   - No tags over 5M posts (too competitive for nano account)
#   - No generic tags (#love, #instagood, #reels — Instagram warns these hurt)
#   - Each slot = different purpose, no overlap
HASHTAG_TAXONOMY = {
    # SLOT 1: NICHE (what is this — puts post in a specific community)
    # Target: 50K-500K posts. These are the primary discovery tags.
    "niche": {
        "finished": ["#handmadepottery"],  # 456K posts, strong community
        "glaze_focus": ["#glazepottery"],  # ~80K, glaze exploration content
        "studio": ["#studiopottery"],  # ~150K, studio/workshop content
        "process": ["#potteryprocess"],  # ~100K, process/behind-the-scenes
        "functional": ["#functionalpottery"],  # ~120K, functional ware
        "contemporary": ["#contemporaryceramics"],  # ~100K, art-focused
        "default": ["#handmadepottery"],  # fallback
    },

    # SLOT 2: TECHNIQUE (how was it made — reaches process-interested people)
    "technique_to_hashtag": {
        "wheel-thrown": ["#wheelthrown"],
        "wheel_thrown": ["#wheelthrown"],
        "handbuilt": ["#handbuilt"],
        "hand-built": ["#handbuilt"],
        "slab_built": ["#handbuilt"],
        "coil_built": ["#handbuilt"],
        "slip-cast": ["#handbuilt"],
    },

    # SLOT 3: AUDIENCE (who should see this — connects with target buyers/community)
    "audience": {
        "collector": ["#ceramicart"],  # 5.7M but high engagement, reaches buyers
        "home_decor": ["#ceramichomedecor"],
        "pottery_community": ["#pottersofinstagram"],
        "art_collector": ["#contemporaryceramics"],
        "process_lover": ["#potteryprocess"],
        "default": ["#ceramicart"],
    },

    # SLOT 4: CONTENT TYPE (what format — helps algorithm categorize)
    "content_type": {
        "reel": ["#potteryreels"],
        "video": ["#potteryreels"],
        "carousel": ["#potteryoftheday"],
        "process_video": ["#potteryprocess"],
        "photo": [],  # no format tag for photos — save the slot
        "default": [],
    },

    # SLOT 5: LOCAL (always include 1 — IRL connections matter)
    "local": ["#longbeachartist", "#longbeachca", "#longbeachcalifornia", "#socalpottery", "#socalartist"],
}

# Maximum hashtags (Instagram hard-limits to 5 as of Jan 2026)
MAX_HASHTAGS = 5


# Purpose inference rules
PURPOSE_RULES = {
    "functional": ["mug", "bowl", "plate", "pitcher", "teapot", "jar", "tumbler", "cup"],
    "decorative": ["vase", "bud_vase", "planter"],
    "sculptural": ["sculpture"],
}

# Product family mapping
PRODUCT_FAMILY_MAP = {
    "dinnerware": ["plate", "bowl"],
    "serveware": ["platter", "serving_bowl", "pitcher"],
    "drinkware": ["mug", "cup", "tumbler", "teapot"],
    "decor": ["vase", "bud_vase", "sculpture"],
    "garden": ["planter", "cover_pot"],
    "art": ["sculpture"],
}

# Safety flag inference
SAFETY_FLAG_RULES = {
    "food_safe": {
        "implies": ["mug", "bowl", "plate", "pitcher", "teapot", "jar", "tumbler", "cup"],
        "excludes": ["sculpture", "incense_burner"],
    },
    "microwave_safe": {
        "requires": ["food_safe"],
        "excludes_luster": True,
    },
    "dishwasher_safe": {
        "requires": ["food_safe"],
    },
    "outdoor_safe": {
        "implies": ["planter", "garden_piece"],
    },
}


def infer_purpose(piece_type: str) -> Optional[str]:
    """Infer purpose from piece type."""
    if piece_type in PURPOSE_RULES["functional"]:
        return "functional"
    elif piece_type in PURPOSE_RULES["decorative"]:
        return "decorative"
    elif piece_type in PURPOSE_RULES["sculptural"]:
        return "sculptural"
    return None


def infer_product_family(piece_type: str) -> Optional[str]:
    """Infer product family from piece type."""
    for family, types in PRODUCT_FAMILY_MAP.items():
        if piece_type in types:
            return family
    return None


def infer_safety_flags(piece_type: str, glaze_type: Optional[str]) -> list[str]:
    """Infer safety flags from piece type and glaze."""
    flags = []
    rules = SAFETY_FLAG_RULES["food_safe"]

    if piece_type in rules["implies"] and piece_type not in rules["excludes"]:
        flags.append("food_safe")

    if "food_safe" in flags:
        if glaze_type and "luster" not in glaze_type.lower():
            flags.append("microwave_safe")
            flags.append("dishwasher_safe")

    if piece_type in SAFETY_FLAG_RULES["outdoor_safe"]["implies"]:
        flags.append("outdoor_safe")

    return flags


def infer_form_attributes(piece_type: str) -> list[str]:
    """Infer form attributes from piece type."""
    attrs = []
    for attr, types in FORM_ATTRIBUTES.items():
        if piece_type in types:
            attrs.append(attr)
    return attrs


# =============================================================================
# FEW-SHOT LEARNING (March 2026)
# Load verified examples from feedback database to improve predictions
# =============================================================================

def build_few_shot_examples() -> list[dict]:
    """
    Load verified examples from feedback database for few-shot learning.

    Returns high-quality examples (score >= 2.5) sorted by most recent first.
    Maximum 10 examples to avoid prompt overflow.
    """
    feedback_path = Path(__file__).parent.parent.parent / "data" / "vision-feedback.json"

    if not feedback_path.exists():
        return []

    try:
        with open(feedback_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return []

    # Extract high-quality examples (overall_score >= 2.5)
    examples = []
    for entry in data.get("feedback_entries", []):
        if entry.get("overall_score", 0) >= 2.5:
            correction = entry.get("human_correction", {})
            examples.append({
                "piece_type": correction.get("piece_type", "unknown"),
                "glaze_type": correction.get("glaze_type", "unknown"),
                "surface_qualities": correction.get("surface_qualities", []),
                "color_appearance": correction.get("color_appearance", "unknown"),
                "technique": correction.get("technique", "unknown"),
                "clay_type": correction.get("clay_type") or "unknown"
            })

    # Sort by timestamp (most recent first) and limit to 10
    if examples:
        # Add timestamps for sorting
        entries_with_ts = []
        for entry, example in zip(data.get("feedback_entries", []), examples):
            if entry.get("overall_score", 0) >= 2.5:
                example_with_ts = {**example, "_timestamp": entry.get("timestamp", "")}
                entries_with_ts.append(example_with_ts)

        entries_with_ts.sort(key=lambda x: x["_timestamp"], reverse=True)
        # Remove timestamp before returning
        return [{k: v for k, v in ex.items() if k != "_timestamp"} for ex in entries_with_ts[:10]]

    return []


def format_few_shot_examples(examples: list[dict]) -> str:
    """
    Format few-shot examples for inclusion in vision prompt.

    Returns a formatted string with verified examples to guide AI identification.
    """
    if not examples:
        return ""

    section = """

## REFERENCE EXAMPLES (From Verified Pieces)
Study these verified examples from your artist's actual collection to guide your identification:

"""
    for i, ex in enumerate(examples[:5], 1):  # Limit to 5 in prompt to save space
        surface = ", ".join(ex["surface_qualities"]) if ex["surface_qualities"] else "none"
        section += f"""Example {i}:
- Form: {ex['piece_type']}
- Glaze: {ex['glaze_type']}
- Surface qualities: {surface}
- Color appearance: {ex['color_appearance']}
- Technique: {ex['technique']}
- Clay: {ex['clay_type']}

"""

    return section


# =============================================================================
# CONSOLIDATED VISION PROMPT (March 2026)
# Single template used by both Ollama and OpenRouter backends
# =============================================================================

def _build_color_sections() -> str:
    """Build color vocabulary sections for vision prompt from loaded taxonomy."""
    families: dict[str, list[str]] = {}
    for color, family in COLOR_TAXONOMY.items():
        # Skip fallback generic colors (they map to themselves)
        if color == family:
            continue
        families.setdefault(family, []).append(color)

    # Canonical ordering with section labels
    family_labels = [
        ('brown', 'BROWNS (most nuanced)'),
        ('red', 'REDS (muted reduction reds)'),
        ('gray', 'GRAYS'),
        ('white', 'WHITES/CREAMS'),
        ('green', 'GREENS'),
        ('blue', 'BLUES'),
        ('orange', 'ORANGES/YELLOWS'),
        ('purple', 'PURPLES/VIOLETS'),
        ('black', 'BLACKS'),
    ]

    lines = []
    for family, label in family_labels:
        colors = families.get(family, [])
        if colors:
            lines.append(f'  * {label}: {", ".join(colors)}')

    return '\n'.join(lines)


def _build_chemistry_section() -> str:
    """Build studio glaze chemistry reference from colorants.json or hardcoded."""
    _loaded_colorants = load_colorants()
    if _loaded_colorants and 'colorants' in _loaded_colorants:
        lines = []
        for key, colorant in _loaded_colorants['colorants'].items():
            name = colorant['name']
            ranges = colorant.get('percentage_ranges', {})
            for effect, info in ranges.items():
                pct_min = info['min']
                pct_max = info['max']
                atmo = info.get('atmosphere', '')
                color = info.get('color', '')
                atmo_str = f' in {atmo}' if atmo != 'any' else ''
                lines.append(
                    f'  * {name.upper()}: {name.split("(")[0].strip()} ({pct_min}-{pct_max}%){atmo_str} — {color}'
                )
        return '\n'.join(lines)

    # Hardcoded fallback matching original prompt
    return """  * COBALT BLUES: cobalt oxide (0.5-2%) — Jensen Blue, Aegean Blue
  * COPPER REDUCTION BLUE: copper oxide in reduction — Chun Blue
  * IRON+COBALT: iron + cobalt oxide blend — Blugr
  * IRON REDUCTION GREENS: iron oxide (1-2%) in reduction — Celadon, Ming Green, Toady, Froggy
  * AMBER CELADON: iron oxide (3-4%) in reduction — Amber Celadon
  * HIGH IRON BROWNS: iron oxide (5-10%) — Tenmoku, Cosmic Brown
  * IRON+MANGANESE: iron oxide + manganese dioxide — Long Beach Black, Larry's Grey
  * COPPER REDUCTION REDS: copper oxide (0.5-1%) in heavy reduction — John's Red, Pablo's Red, Iron Red
  * CHROME-TIN PINKS: chrome oxide (0.5%) + tin oxide (12%) — Pinky, Raspberry
  * MANGANESE PURPLE: manganese dioxide (5-8%) + cobalt oxide — Shocking Purple
  * REDUCTION LUSTER: reduction-sensitive metallic luster — Honey Luster
  * STRONTIUM CRYSTAL: strontium carbonate + zinc oxide, slow-cool crystals — Strontium Crystal
  * HIGH-SODA SHINO: high-soda feldspar, carbon trapping, subtle iridescence — Luster Shino, Malcom's Shino
  * OPACIFIED WHITES: tin or zirconium opacified — Choinard White, Tighty Whitey
  * MAGNESIUM CRAWL: high magnesium, intentional crawling texture — White Crawl
  * TRANSPARENT CLEARS: transparent silica glass, no colorants — Lucid Clear, Tom Coleman Clear
  * RUTILE YELLOW: rutile (5-10%) or iron yellow — Mellow Yellow
  * UNDOCUMENTED: studio-specific formulation, chemistry unknown — Angel Eyes, Sun Valley"""

# Pre-build dynamic sections at module load time
_COLOR_SECTIONS = _build_color_sections()
_CHEMISTRY_SECTION = _build_chemistry_section()

VISION_PROMPT_TEMPLATE = """Analyze this ceramic pottery photo and provide a structured analysis.
{idea_seed_section}

SURFACE EFFECTS COMMON IN THIS STUDIO (cone 10 reduction):
- Carbon trapping and crackle networks (Shino-family glazes)
- Blue pooling in recesses, color breaking at thin spots (Chun-family)
- Warm luster and honey tones with copper flashing (layered glazes)
- Iron speckling and dark surface variation (iron-saturated glazes)
Your job is to DESCRIBE what you see, not identify glazes.

Respond with a JSON object with these fields:

- hypotheses: Array of 3-5 initial hypotheses about the piece
  Format: "description [confidence] - visual evidence"
  Confidence levels: high, medium, low
  Example: "Bud vase with Shino glaze [high] - crackle texture visible, carbon trapping at shoulder"
  For multi-piece photos (3+ different types), lead with "Collection of mixed forms [high] - ..."

- piece_type: Classify using these STANDARD CERAMICS TERMINOLOGY definitions:

  MULTI-PIECE PHOTOS (CHECK FIRST):
  * collection: Multiple DIFFERENT pieces in one shot (e.g., 3 bowls + 2 vases + 1 mug)
    Use this when pieces are not all the same type - do NOT force one category.
  * If all pieces ARE the same type (e.g., 5 bud vases), still use the singular form (bud_vase)
    and set piece_count to the number visible.

  BUD VASE vs VASE (critical distinction):
  * bud_vase: SMALLEST vase category. Designed for ONE flower stem. Narrow neck, usually < 6" tall.
             Key: opening barely wide enough for single stem, proportionally small overall.
  * vase: For multiple flowers/arrangements. Wider opening than bud vase, typically 6"+ tall.
          Key: opening can hold several stems, larger body.

  JAR vs BOWL (critical distinction):
  * jar: Opening is NARROWER than the widest part of body (constricted lip).
         Often has lid-seating rim even if no lid present. Storage form.
  * bowl: Opening is WIDER than or equal to body width. Open, accessible form.
          Depth typically less than width.

  OTHER FORMS:
  * mug: Has handle, cylindrical or tapered body, for drinking hot beverages
  * cup: Smaller than mug, may or may not have handle, for drinking
  * tumbler: Cylindrical drinking vessel WITHOUT handle
  * planter: Container for plants, often with drainage considerations
  * plate: Flat, shallow, for serving food
  * pitcher: Has SPOUT and handle, for pouring liquids
  * teapot: Has LID, spout, AND handle, for brewing tea
  * sculpture: Non-functional artistic form

  UNCERTAINTY: Use "piece" if uncertain (prefer this over wrong classification)

- content_type: One of (finished, process, kiln_reveal, studio, detail)
- firing_state: CRITICAL - What stage of firing is this piece?
  * "greenware" - NEVER fired. Raw clay, fresh off wheel, still drying. Soft, can be scratched with fingernail.
  * "bisque" - FIRED ONCE (bisque fire ~ cone 06). Porous, matte, no glaze. Clay has changed color from raw (gray/pink → white/terracotta). LOOKS FIRED, not raw.
  * "glazed" - Glaze applied (shiny or matte coating visible), may be unfired or fired
  * "finished" - Fully fired and glazed, ready to use
  * null if unclear

  KEY DISTINCTION: Greenware vs Bisque
  * Greenware = raw, unfired clay (grayish-pink or cream, looks "wet" or "leather hard")
  * Bisque = has been through kiln once (white or terracotta, looks "dry" and "fired", no shine but definitely transformed)

- primary_colors: Array of 1-2 main colors. Use CONE 10 REDUCTION vocabulary:
{color_sections}
  * Or any color you see - unexpected combinations are welcome!
- secondary_colors: Array of accent colors (same vocabulary)

- glaze_type: null always. Do NOT write brand names (e.g., "Shino", "Tenmoku").
  Instead, in hypotheses you may reference chemistry from the STUDIO GLAZE CHEMISTRY table below.
  Describe what the chemistry IS (oxide compounds), not brand names.
  null always.

STUDIO GLAZE CHEMISTRY (use these aliases in hypotheses — describe compounds, never brand names):
{chemistry_section}

- color_appearance: VIVID VISUAL DESCRIPTION of the surface. This is the PRIMARY field for describing glaze effects.
  Use pottery chemistry vocabulary: breaking, pooling, running, carbon trapping, flashing, crawling, rivulets.
  Use emotional/sensory language: "velvety matte," "glassy depth," "warm radiance," "cool luminosity."
  Make at least 3 distinct observations about this specific piece. Be specific — no generic descriptions.
  Minimum 15 words, ideally 25-40 words. Each description must be UNIQUE to this piece.
  Examples: "chalcedony blue pooling in recesses with calcite breaking at the rim, carbon trapping visible at shoulder creating speckled iron deposits over the raw clay"
             "slate and pyrolusite flowing in variegated waves across the belly, a prominent crackle network catching light along the shoulder where the glaze thins to reveal bisque beneath"
             "deep denim pooling at the neck, transitioning through a metallic slate-gray midsection into bronze luster highlights near the foot where crawling exposes the warm B-Mix body"
  null if unglazed/unfired

- surface_qualities: Array of visible surface phenomena (max 5, only if finished/fired):

  REQUIREMENTS:
  - Always include a SHEEN LEVEL (matte, satin, or gloss) — actually LOOK at the reflectivity
  - Include at least one QUALITY CATEGORY beyond sheen
  - Each quality must be a DISTINCT phenomenon — no listing 3 variations of the same thing

  SHEEN LEVELS (judge by reflectivity):
  * matte: No reflection, flat finish. Looks absorbent, like raw clay.
  * satin: Subtle reflection, soft glow. Semi-reflective, like eggshell.
  * gloss: Clear reflection, mirror-like highlights. Glassy, wet-looking.

  QUALITY CATEGORIES:
  * SHEEN: matte, satin, gloss
  * COLOR EFFECTS: variegation (mottled), breaking (color change at edges), color_pooling, flashing (localized kiln-atmosphere color), blush, halo, mottling
  * MOVEMENT: crawling (glaze pulls back), running, rivulets, dripping, cascading, pinholing, running_thin
  * CRYSTALLINE: crystalline (visible crystals), oil_spot (metallic spots on dark), crackle (fine crack network), waxy (micro-crystalline sheen), micro_crystal
  * REDUCTION: carbon_trapping (dark speckles in lighter glaze), luster (metallic sheen), reduction_shadow, wadding_mark, flame_mark
  * TEXTURE: smooth, speckled (visible particles), leather_hard (if unfired), raw, waxy, sandy, gritty
  * PATTERN: striped, banded, spotted, dappled, feathered
  * EDGE EFFECTS: dry_foot (unglazed base), lip_mark, thumbprint
  null if none visible or unclear

- clay_type: Identify clay body if visible at unglazed areas or foot:
  * "b_mix" - Smooth white/cream porcelain
  * "death_valley" - Iron speckling visible, rustic look
  * "porcelain" - Pure white, translucent when thin
  * "stoneware" - Generic gray/tan stoneware
  * "sculptural_raku" - Blackened, crackled surface from raku firing
  * "earthenware" - Low-fire red/brown clay
  * null if fully glazed (can't see clay)

- form_attributes: Array of structural/aesthetic features. Use ceramics education vocabulary:
  * Functional: lidded, stackable, pourable, handheld, nested
  * Body Profile: cylindrical, spherical, ovoid, conical, bell_shaped, shouldered, necked, waisted, bulbous, elongated, squat, tall_slender, balanced, short_wide, heavy_bottomed, top_heavy, s_curve, tapered_bottom, wide_mouth, trumpet, barrel, drum, mushroom, pagoda, kidney, crescent, pod
  * Rim/Lip: flared, tapered, rolled, rounded, squared, pinched, cut, split, everted, collared
  * Foot/Base: footed, trimmed, flat_base, pedestal, foot_ring, wide_foot, unglazed_foot, triple_foot
  * Character: organic, geometric, asymmetrical, sculptural, refined, rustic, bold, delicate, playful, dramatic, serene, intimate, industrial, minimal, ornate, monumental, whimsical
  * Surface Form: faceted, fluted, ribbed, carved, textured, smooth, pierced, incised, stamped, combed, paddled, slip_trail, sgraffito, wax_resist, impressed
  * Or any descriptor you see - unusual combinations are welcome!

- purpose: "functional"|"decorative"|"sculptural"|"hybrid"|null
- product_family: "dinnerware"|"serveware"|"drinkware"|"decor"|"garden"|"art"|null
- technique: One of (wheel-thrown, handbuilt, slip-cast, coil_built, pinch_pot, slab_built, wheel_altered, extruded, press_molded, or null)
- mood: One of (warm, cool, earthy, modern, organic, dramatic, serene, bold, intimate, playful, minimal, moody, vibrant, rustic, luminous)
- dimensions_visible: Boolean - can you estimate size?
- piece_count: Integer - how many pieces are visible? (1=single, 2-5=few, 6+=collection)
- brief_description: 5-10 word description for the hook

- uncertainties: Array of things you CANNOT determine. Be specific about WHAT and WHY. Use [] if highly confident.

- color_distribution: How colors are distributed across the piece surface
  Options: "uniform" (even), "breaking" (color shifts at edges/thin spots), "pooling" (darker in recesses),
           "variegated" (mottled/patchy), "gradient" (smooth transition), "banded" (horizontal/vertical bands),
           "dappled" (spotted color variation), "streaked" (directional lines of color), "speckled" (fine dots),
           "ombre" (gradual fade between colors), "feathered" (soft blended edges), "mottled" (irregular patches)
  Example: "breaking"

DIVERSITY RULES — Read carefully:
- Do NOT use "earth tones" as a color. That is not a color. Use specific taxonomy words from the color vocabulary above.
- Do NOT default to "earthy" for mood. Consider: warm, cool, modern, organic, dramatic, serene, bold, intimate.
- Do NOT always say "gloss" for sheen. Actually LOOK at the reflectivity. Satin and matte are equally valid.
- Each surface quality should be a DISTINCT phenomenon. Don't list 3 variations of the same thing.
- color_appearance MUST be unique to this specific piece. No generic descriptions.
- Vary your sentence structure. Do not start every description the same way.

Example response:
{{"piece_type": "bud_vase", "content_type": "finished", "firing_state": "finished", "primary_colors": ["sienna", "copper"], "secondary_colors": ["bronze"], "glaze_type": null, "color_appearance": "chalcedony blue pooling in recesses with calcite breaking at the rim over exposed ferruginous clay, carbon trapping visible at shoulder creating speckled iron deposits", "surface_qualities": ["waxy", "crawling", "luster", "color_pooling"], "clay_type": "b_mix", "form_attributes": ["necked", "organic", "delicate"], "purpose": "decorative", "product_family": "decor", "technique": "wheel-thrown", "mood": "warm", "dimensions_visible": true, "piece_count": 1, "brief_description": "Lustrous bud vase with warm sienna and copper tones", "hypotheses": ["Bud vase with Shino glaze [high] - crackle texture visible, carbon trapping", "Small pitcher [low] - no handle visible but form could accommodate"], "uncertainties": [], "color_distribution": "breaking"}}"""


def analyze_photo_basic(photo_path: str) -> PhotoAnalysis:
    """
    Basic photo analysis without AI (uses filename and metadata).

    For full AI-powered analysis, use analyze_photo() which calls
    Claude API for image understanding.
    """
    filename = Path(photo_path).stem.lower()

    # Detect content type from filename
    is_process = any(kw in filename for kw in ["process", "wip", "making", "wheel", "throwing", "trimming"])
    is_kiln = any(kw in filename for kw in ["kiln", "reveal", "unload", "firing"])

    if is_kiln:
        content_type = ContentType.KILN_REVEAL
    elif is_process:
        content_type = ContentType.PROCESS
    else:
        content_type = ContentType.FINISHED_PIECE

    # Detect piece type from filename
    piece_type = "piece"
    for ptype, keywords in PIECE_KEYWORDS.items():
        if any(kw in filename for kw in keywords):
            piece_type = ptype
            break

    # Detect glaze from filename
    glaze_type = None
    for gtype, keywords in GLAZE_KEYWORDS.items():
        if any(kw in filename for kw in keywords):
            glaze_type = gtype
            break

    # Detect technique from filename
    technique = None
    for ttype, keywords in TECHNIQUE_KEYWORDS.items():
        if any(kw in filename for kw in keywords):
            technique = ttype
            break

    # Default colors based on common ceramics
    primary_colors = ["earth tones"]
    secondary_colors = []

    return PhotoAnalysis(
        content_type=content_type,
        piece_type=piece_type,
        primary_colors=primary_colors,
        secondary_colors=secondary_colors,
        glaze_type=glaze_type,
        color_appearance=None,  # Not available without AI vision
        technique=technique,
        mood="warm" if "warm" in filename else "modern",
        is_process=is_process,
        dimensions_visible=False,
        suggested_hook=f"Handmade ceramic {piece_type}",
        surface_qualities=[]
    )


def analyze_photo(photo_path: str, use_ai: bool = True) -> PhotoAnalysis:
    """
    Analyze a photo to understand its content.

    Uses AI for rich analysis, falls back to basic filename analysis.
    Routes to Ollama (local, FREE) or OpenRouter (API, paid) based on config.

    Args:
        photo_path: Path to the photo file
        use_ai: Whether to use AI for analysis (default True)

    Returns:
        PhotoAnalysis object with detected content
    """
    if not use_ai:
        analysis = analyze_photo_basic(photo_path)
    else:
        config = get_ai_config()

        # Try AI analysis with configured backend
        try:
            if config.backend == "ollama":
                analysis = analyze_photo_with_ollama(photo_path)
            else:
                analysis = analyze_photo_with_ai(photo_path)  # OpenRouter
        except Exception as e:
            print(f"AI analysis failed ({config.backend}): {e}")
            analysis = analyze_photo_basic(photo_path)

    # Attach worldbuilding data if available
    filename = Path(photo_path).name
    analysis.worldbuilding = lookup_worldbuilding(filename, analysis=analysis)
    if analysis.worldbuilding:
        logging.info(f"Worldbuilding matched: {analysis.worldbuilding.planet_name} for {filename}")

    return analysis


def analyze_video_basic(video_path: str, duration: float = 0.0, width: int = 0, height: int = 0) -> VideoAnalysis:
    """
    Basic video analysis without AI (uses filename and metadata).

    Args:
        video_path: Path to the video file
        duration: Video duration in seconds (if known)
        width: Video width (if known)
        height: Video height (if known)

    Returns:
        VideoAnalysis object with detected content
    """
    filename = Path(video_path).stem.lower()

    # Detect video type from filename
    is_throwing = any(kw in filename for kw in ["throw", "wheel", "spinning"])
    is_trimming = any(kw in filename for kw in ["trim", "trimming"])
    is_glazing = any(kw in filename for kw in ["glaze", "glazing", "dip"])
    is_kiln = any(kw in filename for kw in ["kiln", "reveal", "unload", "opening"])
    is_tour = any(kw in filename for kw in ["tour", "studio", "walkthrough", "space"])
    is_timelapse = any(kw in filename for kw in ["timelapse", "time-lapse", "time lapse"])

    # Determine activity and content type
    if is_kiln:
        video_type = "reveal"
        activity = "kiln reveal"
        content_type = ContentType.KILN_REVEAL_VIDEO
    elif is_tour:
        video_type = "tour"
        activity = "studio tour"
        content_type = ContentType.STUDIO_TOUR
    elif is_timelapse:
        video_type = "timelapse"
        activity = "pottery making"
        content_type = ContentType.TIME_LAPSE
    elif is_throwing:
        video_type = "process"
        activity = "wheel throwing"
        content_type = ContentType.PROCESS_VIDEO
    elif is_trimming:
        video_type = "process"
        activity = "trimming"
        content_type = ContentType.PROCESS_VIDEO
    elif is_glazing:
        video_type = "process"
        activity = "glazing"
        content_type = ContentType.PROCESS_VIDEO
    else:
        video_type = "process"
        activity = "pottery process"
        content_type = ContentType.PROCESS_VIDEO

    # Calculate aspect ratio category
    aspect_ratio_category = "horizontal"
    if width > 0 and height > 0:
        if height > width:
            ratio = height / width
            if 1.7 <= ratio <= 1.9:
                aspect_ratio_category = "vertical_9_16"
            else:
                aspect_ratio_category = "vertical"
        elif abs(height - width) / max(height, width) < 0.1:
            aspect_ratio_category = "square"

    # Check if suitable for Reels (< 90 seconds, vertical or square)
    is_reel_suitable = 0 < duration <= 90 and aspect_ratio_category in ["vertical", "vertical_9_16", "square"]

    # Duration warning for videos that don't meet Reels criteria
    duration_warning = None
    if duration > 90:
        duration_warning = f"Video is {duration:.1f}s, exceeds 90s Reels limit"
    elif duration > 0 and aspect_ratio_category == "horizontal":
        duration_warning = f"Video is horizontal, not suitable for Reels"

    return VideoAnalysis(
        content_type=content_type,
        video_type=video_type,
        duration_seconds=duration,
        primary_colors=["earth tones"],
        activity=activity,
        mood="warm",
        has_audio=False,  # Unknown without processing
        suggested_hook=f"{activity.capitalize()} video",
        is_reel_suitable=is_reel_suitable,
        aspect_ratio_category=aspect_ratio_category,
        duration_warning=duration_warning
    )


# =============================================================================
# STORIES ANALYSIS
# =============================================================================

# Story text overlay templates by activity
STORY_OVERLAY_TEMPLATES = {
    "wheel throwing": ["Studio day 🎨", "Centering...", "Mud on the wheel", "In the zone"],
    "trimming": ["Trimming session", "Details matter ✨", "Refining the form"],
    "glazing": ["Glaze time!", "Dipping day", "The magic step ✨", "Glazing ritual"],
    "kiln reveal": ["Wait for it...", "Kiln opening day!", "The reveal 🎉", "Nervous excitement"],
    "studio tour": ["Studio vibes", "My happy place", "Behind the scenes", "Where the magic happens"],
    "pottery making": ["Making today", "Clay therapy", "Process shot", "Work in progress"],
    "packing": ["Order packing 📦", "Off to new homes", "Shipping day"],
    "default": ["Studio life", "Clay days", "Pottery in progress", "Making things"],
}

# Story sticker suggestions by activity
STORY_STICKER_SUGGESTIONS = {
    "wheel throwing": ["🎨", "🫖", "💪", "🔥"],
    "trimming": ["✨", "🔪", "📏"],
    "glazing": ["🌈", "🪣", "✨", "🔥"],
    "kiln reveal": ["😱", "🎉", "🔥", "❤️"],
    "studio tour": ["🏠", "❤️", "✨", "📍"],
    "pottery making": ["🎨", "💪", "✨"],
    "packing": ["📦", "💌", "✈️"],
    "default": ["❤️", "✨", "🔥"],
}


def analyze_story_basic(video_path: str, duration: float = 0.0, width: int = 0, height: int = 0) -> StoriesAnalysis:
    """
    Basic analysis for Instagram Stories from filename and metadata.

    Stories are 15-second vertical videos with text overlays.
    Must be <= 15s and vertical (9:16 aspect ratio) to be suitable.

    Args:
        video_path: Path to the video file
        duration: Video duration in seconds (if known)
        width: Video width (if known)
        height: Video height (if known)

    Returns:
        StoriesAnalysis object with text overlay and sticker suggestions
    """
    filename = Path(video_path).stem.lower()

    # Detect activity from filename
    is_throwing = any(kw in filename for kw in ["throw", "wheel", "spinning"])
    is_trimming = any(kw in filename for kw in ["trim", "trimming"])
    is_glazing = any(kw in filename for kw in ["glaze", "glazing", "dip"])
    is_kiln = any(kw in filename for kw in ["kiln", "reveal", "unload", "opening"])
    is_tour = any(kw in filename for kw in ["tour", "studio", "walkthrough"])
    is_packing = any(kw in filename for kw in ["pack", "ship", "order"])

    # Determine activity
    if is_kiln:
        activity = "kiln reveal"
        content_type = ContentType.KILN_REVEAL_VIDEO
    elif is_tour:
        activity = "studio tour"
        content_type = ContentType.STUDIO_TOUR
    elif is_throwing:
        activity = "wheel throwing"
        content_type = ContentType.PROCESS_VIDEO
    elif is_trimming:
        activity = "trimming"
        content_type = ContentType.PROCESS_VIDEO
    elif is_glazing:
        activity = "glazing"
        content_type = ContentType.PROCESS_VIDEO
    elif is_packing:
        activity = "packing"
        content_type = ContentType.PROCESS_VIDEO
    else:
        activity = "pottery making"
        content_type = ContentType.PROCESS_VIDEO

    # Check if suitable for Stories (<= 15s and vertical)
    is_vertical = height > width if width > 0 and height > 0 else True
    is_story_suitable = duration <= 15 and is_vertical

    # Generate text overlay suggestions
    overlay_templates = STORY_OVERLAY_TEMPLATES.get(activity, STORY_OVERLAY_TEMPLATES["default"])
    text_overlays = overlay_templates.copy()

    # Add time-based overlays for longer videos
    if duration > 5:
        text_overlays.append(f"{int(duration)}s of magic")

    # Get sticker suggestions
    sticker_suggestions = STORY_STICKER_SUGGESTIONS.get(activity, STORY_STICKER_SUGGESTIONS["default"])

    return StoriesAnalysis(
        content_type=content_type,
        duration_seconds=duration,
        activity=activity,
        mood="warm",
        text_overlay_suggestions=text_overlays,
        sticker_suggestions=sticker_suggestions,
        is_story_suitable=is_story_suitable
    )


def generate_caption_for_stories(analysis: StoriesAnalysis) -> str:
    """
    Generate text overlay suggestions for Instagram Stories.

    Stories don't have traditional captions - instead they have
    text overlays and stickers. This returns suggested text overlays.

    Args:
        analysis: StoriesAnalysis object

    Returns:
        Newline-separated text overlay suggestions
    """
    lines = ["📝 TEXT OVERLAY SUGGESTIONS:"]
    lines.append("─" * 30)

    for i, overlay in enumerate(analysis.text_overlay_suggestions[:4], 1):
        lines.append(f"{i}. {overlay}")

    lines.append("")
    lines.append("🏷️ STICKER SUGGESTIONS:")
    lines.append("─" * 30)
    lines.append(" ".join(analysis.sticker_suggestions))

    if not analysis.is_story_suitable:
        lines.append("")
        lines.append("⚠️ NOTE: This video may not be suitable for Stories.")
        if analysis.duration_seconds > 15:
            lines.append(f"   Duration ({analysis.duration_seconds:.1f}s) exceeds 15s limit.")

    return "\n".join(lines)


def analyze_video_frames(video_path: str, max_frames: int = 5, duration: float = 0.0, width: int = 0, height: int = 0) -> VideoAnalysis:
    """
    Extract multiple frames, analyze each, and aggregate results.

    Detects whether video shows:
    - Single piece (consistent detections across frames)
    - Collection (multiple pieces, varying types/colors)
    - Comparison (same piece from different angles or similar pieces side-by-side)

    Args:
        video_path: Path to the video file
        max_frames: Maximum frames to extract (default 5)
        duration: Video duration in seconds (if known)
        width: Video width (if known)
        height: Video height (if known)

    Returns:
        VideoAnalysis with aggregated content detection
    """
    frames = extract_video_frames(video_path, max_frames=max_frames)
    if not frames:
        return analyze_video_basic(video_path, duration, width, height)

    try:
        # Analyze each frame — use raw vision analysis WITHOUT worldbuilding lookup
        # (worldbuilding is done ONCE after aggregation, not per-frame)
        frame_analyses = []
        for frame in frames:
            try:
                if use_ai:
                    analysis = analyze_photo_with_ollama(frame) if get_ai_config().backend == "ollama" else analyze_photo_with_ai(frame)
                else:
                    analysis = analyze_photo_basic(frame)
                frame_analyses.append(analysis)
            except Exception:
                continue  # Skip failed frames

        if not frame_analyses:
            return analyze_video_basic(video_path, duration, width, height)

        # Get video metadata
        if duration == 0.0:
            duration = get_video_duration(video_path)

        # Calculate aspect ratio category
        aspect_ratio_category = "horizontal"
        if width > 0 and height > 0:
            if height > width:
                ratio = height / width
                if 1.7 <= ratio <= 1.9:
                    aspect_ratio_category = "vertical_9_16"
                else:
                    aspect_ratio_category = "vertical"
            elif abs(height - width) / max(height, width) < 0.1:
                aspect_ratio_category = "square"

        # Aggregate results
        all_piece_types = [a.piece_type for a in frame_analyses]
        all_colors = []
        for a in frame_analyses:
            all_colors.extend(a.primary_colors)
        all_glazes = [a.glaze_type for a in frame_analyses if a.glaze_type]

        # Count unique piece types and colors
        unique_piece_types = set(all_piece_types)
        unique_colors = set(all_colors)

        # Determine video content type based on consistency
        if len(unique_piece_types) == 1:
            # Same piece type across all frames - single piece showcase
            content_type = ContentType.SINGLE_PIECE_VIDEO
            activity = f"showcasing {all_piece_types[0]}"
        elif len(frame_analyses) >= 3 and len(unique_piece_types) >= 3:
            # Multiple different pieces - likely a collection
            content_type = ContentType.COLLECTION_VIDEO
            activity = f"collection of {len(unique_piece_types)} piece types"
        elif len(unique_piece_types) > 1:
            # Multiple pieces, could be comparison
            content_type = ContentType.COMPARISON_VIDEO
            activity = f"comparing {' and '.join(list(unique_piece_types)[:2])}"
        else:
            # Default to process video
            content_type = ContentType.PROCESS_VIDEO
            activity = "pottery process"

        # Aggregate colors (most common)
        color_counts = Counter(all_colors)
        primary_colors = [c for c, _ in color_counts.most_common(3)]

        # Use the most common mood
        mood_counts = Counter(a.mood for a in frame_analyses)
        mood = mood_counts.most_common(1)[0][0] if mood_counts else "warm"

        # Generate hook based on aggregated content
        if content_type == ContentType.SINGLE_PIECE_VIDEO:
            piece_desc = all_piece_types[0]
            glaze_desc = all_glazes[0] if all_glazes else None
            if glaze_desc:
                suggested_hook = f"{piece_desc.capitalize()} with {glaze_desc}"
            else:
                suggested_hook = f"{piece_desc.capitalize()} showcase"
        elif content_type == ContentType.COLLECTION_VIDEO:
            suggested_hook = f"Collection of {len(unique_piece_types)} ceramic pieces"
        else:
            suggested_hook = f"{activity.capitalize()}"

        # Reel suitability
        is_reel_suitable = 0 < duration <= 90 and aspect_ratio_category in ["vertical", "vertical_9_16", "square"]

        # Duration warning
        duration_warning = None
        if duration > 90:
            duration_warning = f"Video is {duration:.1f}s, exceeds 90s Reels limit"
        elif duration > 0 and aspect_ratio_category == "horizontal":
            duration_warning = "Video is horizontal, not suitable for Reels"

        # Video type from content type
        video_type_map = {
            ContentType.SINGLE_PIECE_VIDEO: "showcase",
            ContentType.COLLECTION_VIDEO: "collection",
            ContentType.COMPARISON_VIDEO: "comparison",
            ContentType.PROCESS_VIDEO: "process",
            ContentType.KILN_REVEAL_VIDEO: "reveal",
            ContentType.STUDIO_TOUR: "tour",
            ContentType.TIME_LAPSE: "timelapse",
        }

        return VideoAnalysis(
            content_type=content_type,
            video_type=video_type_map.get(content_type, "process"),
            duration_seconds=duration,
            primary_colors=primary_colors,
            activity=activity,
            mood=mood,
            has_audio=False,
            suggested_hook=suggested_hook,
            is_reel_suitable=is_reel_suitable,
            aspect_ratio_category=aspect_ratio_category,
            duration_warning=duration_warning
        )
    finally:
        # Clean up all extracted frames
        for frame in frames:
            try:
                os.unlink(frame)
            except OSError:
                pass
        # Try to clean up temp directory
        if frames:
            try:
                temp_dir = os.path.dirname(frames[0])
                if os.path.exists(temp_dir):
                    os.rmdir(temp_dir)
            except OSError:
                pass


def analyze_video(video_path: str, use_ai: bool = True, duration: float = 0.0, width: int = 0, height: int = 0) -> VideoAnalysis:
    """
    Analyze a video to understand its content.

    Uses AI for rich analysis via multi-frame extraction, falls back to basic filename analysis.

    Args:
        video_path: Path to the video file
        use_ai: Whether to use AI for analysis (default True)
        duration: Video duration in seconds (if known)
        width: Video width (if known)
        height: Video height (if known)

    Returns:
        VideoAnalysis object with detected content
    """
    if not use_ai:
        analysis = analyze_video_basic(video_path, duration, width, height)
    else:
        # Use multi-frame analysis for richer content detection
        analysis = analyze_video_frames(video_path, max_frames=5, duration=duration, width=width, height=height)

    # Attach worldbuilding data if available
    filename = Path(video_path).name
    analysis.worldbuilding = lookup_worldbuilding(filename, analysis=analysis)
    if analysis.worldbuilding:
        logging.info(f"Worldbuilding matched: {analysis.worldbuilding.planet_name} for {filename}")

    return analysis


def analyze_carousel(media_paths: list[str], use_ai: bool = True) -> CarouselAnalysis:
    """
    Analyze multiple images for carousel caption.

    Args:
        media_paths: List of paths to media files
        use_ai: Whether to use AI for analysis (default True)

    Returns:
        CarouselAnalysis object with narrative flow and unified caption info
    """
    # Analyze each item
    analyses = []
    for path in media_paths:
        if is_video_file(path):
            analyses.append(analyze_video(path, use_ai=use_ai))
        else:
            analyses.append(analyze_photo(path, use_ai=use_ai))

    # Determine primary theme
    piece_types = set()
    content_types = []
    for a in analyses:
        if hasattr(a, 'piece_type'):
            piece_types.add(a.piece_type)
        content_types.append(a.content_type)

    # Determine narrative flow
    if len(set(content_types)) == 1:
        narrative_flow = "collection"  # Same type of content
    elif ContentType.PROCESS in content_types and ContentType.FINISHED_PIECE in content_types:
        narrative_flow = "story"  # Process to result
    elif ContentType.DETAIL in content_types:
        narrative_flow = "details"  # Close-ups
    else:
        narrative_flow = "mixed"

    # Generate hooks for each item
    hooks = []
    for i, a in enumerate(analyses):
        if hasattr(a, 'suggested_hook'):
            hooks.append(f"Slide {i+1}: {a.suggested_hook}")
        else:
            hooks.append(f"Slide {i+1}")

    # Generate CTA based on flow
    cta_templates = {
        "collection": "Which one's your favorite? Let me know below!",
        "story": "From start to finish - the full journey of this piece.",
        "details": "Swipe to see all the details of this piece.",
        "mixed": "Swipe through to see more!",
    }
    cta = cta_templates.get(narrative_flow, "Swipe for more!")

    # Primary theme
    if piece_types:
        primary_theme = " and ".join(sorted(piece_types)[:2])
    else:
        primary_theme = "ceramic pieces"

    return CarouselAnalysis(
        content_types=content_types,
        primary_theme=primary_theme,
        narrative_flow=narrative_flow,
        hooks=hooks,
        cta=cta
    )


# =============================================================================
# API RETRY HELPER
# =============================================================================

_log = logging.getLogger(__name__)

def _api_post_with_retry(url, json_data, timeout=300, max_retries=3):
    """POST with exponential backoff on transient failures."""
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(url, json=json_data, timeout=timeout)
            if response.status_code < 500:
                return response
            _log.warning("API returned %s (attempt %d/%d)", response.status_code, attempt, max_retries)
            last_exc = RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            _log.warning("API request failed (attempt %d/%d): %s", attempt, max_retries, e)
            last_exc = e
        if attempt < max_retries:
            time.sleep(2 ** attempt)  # 2s, 4s, 8s
    raise last_exc


# =============================================================================
# OLLAMA (LOCAL - FREE)
# =============================================================================

def check_ollama_available(base_url: str = OLLAMA_BASE_URL) -> bool:
    """Check if Ollama is running and accessible."""
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def analyze_photo_with_ollama(
    photo_path: str,
    model: str = None,
    base_url: str = None,
    idea_seed: str = None
) -> PhotoAnalysis:
    """
    Analyze photo using Ollama model (supports both local and cloud models).

    Cloud models (e.g., qwen3.5:cloud, kimi-k2.5:cloud) use /api/chat endpoint.
    Local models use /api/generate endpoint.

    Args:
        photo_path: Path to the photo file
        model: Ollama model name (default: from config)
        base_url: Ollama server URL (default: http://localhost:11434)
        idea_seed: Optional creative association from the potter (e.g., "reminds me of basalt")

    Returns:
        PhotoAnalysis object with detected content
    """
    config = get_ai_config()
    model = model or config.ollama_vision_model
    base_url = base_url or config.ollama_base_url

    # Check Ollama is available
    if not check_ollama_available(base_url):
        raise ConnectionError(
            f"Ollama not available at {base_url}. "
            "Run 'ollama serve' or install from ollama.com"
        )

    # Compress and encode image (handles large files automatically)
    image_b64 = compress_image_for_api(photo_path)

    # Build idea seed section if provided
    if idea_seed:
        idea_seed_section = f"""

POTTER'S CREATIVE LENS: The potter noted this piece reminds them of "{idea_seed}"
Consider this perspective while analyzing - does it reveal anything about the form, surface, or mood?
This is ONE lens among many - still explore all possibilities in your hypotheses.
"""
    else:
        idea_seed_section = ""

    # Build vision prompt with few-shot examples from feedback
    few_shot_examples = build_few_shot_examples()
    examples_section = format_few_shot_examples(few_shot_examples)
    prompt = VISION_PROMPT_TEMPLATE.format(idea_seed_section=idea_seed_section, color_sections=_COLOR_SECTIONS, chemistry_section=_CHEMISTRY_SECTION) + examples_section

    # Cloud models need /api/chat endpoint with messages format
    is_cloud_model = model.endswith(":cloud")

    if is_cloud_model:
        # Use /api/chat for cloud models
        response = _api_post_with_retry(
            f"{base_url}/api/chat",
            json_data={
                "model": model,
                "messages": [{
                    "role": "user",
                    "content": prompt,
                    "images": [image_b64]
                }],
                "stream": False,
                "options": {"temperature": 0.9}
            },
            timeout=180
        )

        if response.status_code != 200:
            raise RuntimeError(f"Ollama cloud error: {response.text}")

        result = response.json()
        response_text = result.get("message", {}).get("content", "")
    else:
        # Use /api/generate for local models
        response = _api_post_with_retry(
            f"{base_url}/api/generate",
            json_data={
                "model": model,
                "prompt": prompt,
                "images": [image_b64],
                "stream": False
            },
            timeout=300
        )

        if response.status_code != 200:
            raise RuntimeError(f"Ollama error: {response.text}")

        result = response.json()
        response_text = result.get("response", "")

    # Parse JSON from response
    try:
        # Try direct parse
        analysis = json.loads(response_text)
    except json.JSONDecodeError:
        import re
        # Try to find JSON in markdown code block
        code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if code_block_match:
            analysis = json.loads(code_block_match.group(1))
        else:
            # Try greedy match for outermost braces
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
            else:
                raise ValueError(f"Could not parse Ollama response as JSON: {response_text[:200]}")

    # Filter banned food and fabric words from vision output
    from geology_vocabulary import BANNED_FOOD_WORDS, BANNED_FABRIC_WORDS
    _BANNED = set(BANNED_FOOD_WORDS) | set(BANNED_FABRIC_WORDS)

    def _filter_banned(word_list: list) -> list:
        """Remove banned food/fabric words from a list, logging each removal."""
        filtered = []
        for w in word_list:
            if w.lower().strip() in _BANNED:
                logging.warning(f"Filtered banned word from vision output: '{w}'")
            else:
                filtered.append(w)
        return filtered

    def _filter_banned_text(text: str) -> str:
        """Remove banned food/fabric words from a text string, replacing with geological equivalents."""
        if not text:
            return text
        import re
        for word in _BANNED:
            pattern = r'\b' + re.escape(word) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                logging.warning(f"Filtered banned word from color_appearance: '{word}'")
                text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        # Clean up double spaces and dangling commas from removals
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r',\s*,', ',', text)
        text = re.sub(r'^,\s*', '', text)
        text = re.sub(r',\s*$', '', text)
        return text

    raw_primary = analysis.get("primary_colors", ["earth tones"])
    raw_secondary = analysis.get("secondary_colors", [])
    raw_surfaces = analysis.get("surface_qualities", [])

    return PhotoAnalysis(
        content_type=ContentType(analysis.get("content_type", "finished")),
        piece_type=analysis.get("piece_type", "piece"),
        primary_colors=_filter_banned(raw_primary),
        secondary_colors=_filter_banned(raw_secondary),
        glaze_type=analysis.get("glaze_type"),
        color_appearance=_filter_banned_text(analysis.get("color_appearance")),
        technique=analysis.get("technique"),
        mood=analysis.get("mood", "warm"),
        is_process=analysis.get("content_type") in ["process", "kiln_reveal"],
        dimensions_visible=analysis.get("dimensions_visible", False),
        suggested_hook=analysis.get("brief_description", "Handmade ceramic piece"),
        firing_state=analysis.get("firing_state"),
        surface_qualities=_filter_banned(raw_surfaces),
        piece_count=analysis.get("piece_count", 1),
        clay_type=analysis.get("clay_type"),
        form_attributes=analysis.get("form_attributes", []),
        purpose=analysis.get("purpose") or infer_purpose(analysis.get("piece_type", "piece")),
        product_family=analysis.get("product_family") or infer_product_family(analysis.get("piece_type", "piece")),
        safety_flags=infer_safety_flags(analysis.get("piece_type"), analysis.get("glaze_type")),
        hypotheses=analysis.get("hypotheses", []),
        lighting=analysis.get("lighting"),
        photo_quality=analysis.get("photo_quality"),
        uncertainties=analysis.get("uncertainties"),
        color_distribution=analysis.get("color_distribution"),
    )


def generate_caption_with_ollama(
    analysis: PhotoAnalysis,
    voice_rules: str = None,
    model: str = None,
    base_url: str = None
) -> str:
    """
    Generate caption using Ollama writing model (DeepSeek).

    Two-model architecture: Vision (Qwen3.5) -> Writing (DeepSeek)

    Args:
        analysis: PhotoAnalysis object
        voice_rules: Optional brand voice guidelines
        model: Ollama model name (default: from config.ollama_writing_model)
        base_url: Ollama server URL

    Returns:
        Generated caption text
    """
    config = get_ai_config()
    model = model or config.ollama_writing_model
    base_url = base_url or config.ollama_base_url

    # Load voice rules if not provided
    if voice_rules is None:
        voice_rules = load_voice_rules()

    # Build enrichment blocks
    worldbuilding_block = ""
    geo_vocab_block = build_geological_vocab_block(analysis)
    few_shot_block = ""
    brand_identity_block = ""

    if analysis.worldbuilding:
        worldbuilding_block = build_worldbuilding_block(analysis.worldbuilding)
    else:
        # For non-worldbuilding pieces, add few-shot examples and brand identity
        few_shot_examples = extract_few_shot_examples(voice_rules)
        if few_shot_examples:
            few_shot_block = f"FEW-SHOT EXAMPLES (study these patterns — process education + specific technique + emotional expression + questions):\n{few_shot_examples}"

        identity_md = load_brand_identity()
        if identity_md:
            brand_identity_block = build_brand_identity_block(identity_md)

    # Detect if this is a process shot (unfired or in-progress)
    _firing_state = getattr(analysis, 'firing_state', None)
    _glaze_type = getattr(analysis, 'glaze_type', None)
    is_process_shot = (
        _firing_state in ["greenware", "bisque"] or
        analysis.content_type in [ContentType.PROCESS, ContentType.KILN_REVEAL, ContentType.STUDIO, ContentType.PROCESS_VIDEO] or
        (_glaze_type is None and _firing_state != "finished")
    )

    if is_process_shot:
        # PROCESS SHOT - focus on making, not selling
        enrichment_sections = ""
        if worldbuilding_block:
            enrichment_sections += f"\n\n{worldbuilding_block}"
        if geo_vocab_block:
            enrichment_sections += f"\n\n{geo_vocab_block}"
        if few_shot_block:
            enrichment_sections += f"\n\n{few_shot_block}"
        if brand_identity_block:
            enrichment_sections += f"\n\n{brand_identity_block}"

        prompt = f"""You are a creative copywriter for a pottery Instagram account.

PIECE DETAILS:
- Type: {analysis.piece_type}
- Stage: {getattr(analysis, 'firing_state', None) or 'work in progress'}
- Colors: {', '.join(analysis.primary_colors)}
- Technique: {analysis.technique or 'handmade'}
- Mood: {analysis.mood}

IMPORTANT: This is a PROCESS shot showing work in progress (unfired or in-progress clay).
{enrichment_sections}

BRAND VOICE:
{voice_rules if voice_rules else 'Warm, authentic, process-focused artist voice.'}

=== STEP 1: BRAINSTORM 7 CAPTION IDEAS ===
Generate 7 distinct caption ideas. Each should:
- Have a different hook angle (emotional, technical, playful, poetic, etc.)
- Focus on the making process or studio moment
- End with a question about pottery making

DO NOT:
- Ask about displaying the piece or where to put it
- Treat it like a finished piece available for purchase
- Ask "what would you put in this vase/bowl?"

Format: Just list 7 ideas, numbered 1-7, each with hook + body + question.

=== STEP 2: SELECT 3 FINAL CAPTIONS ===
From your 7 ideas, select 3 that are:
1. Most distinct from each other (different tones/angles)
2. Most interesting and scroll-stopping
3. Under 300 characters each

Output format:
```
CAPTIONS:
1. [caption 1]
2. [caption 2]
3. [caption 3]
```"""
    else:
        # FINISHED PIECE - can include sales elements
        surface_qualities = getattr(analysis, 'surface_qualities', [])
        surface_note = ""
        if surface_qualities:
            # Use synonyms for varied, natural language
            notes = [get_texture_synonym(sq) for sq in surface_qualities[:2]]
            surface_note = f"\n- Surface Qualities: {', '.join(notes)}"

        enrichment_sections = ""
        if worldbuilding_block:
            enrichment_sections += f"\n\n{worldbuilding_block}"
        if geo_vocab_block:
            enrichment_sections += f"\n\n{geo_vocab_block}"
        if few_shot_block:
            enrichment_sections += f"\n\n{few_shot_block}"
        if brand_identity_block:
            enrichment_sections += f"\n\n{brand_identity_block}"

        prompt = f"""You are a creative copywriter for a pottery Instagram account.

PIECE DETAILS:
- Type: {analysis.piece_type}
- Surface Chemistry: {analysis.color_appearance or 'unknown'}
- Colors: {', '.join(analysis.primary_colors)}
- Technique: {analysis.technique or 'handmade'}
- Mood: {analysis.mood}{surface_note}
{enrichment_sections}

BRAND VOICE:
{voice_rules if voice_rules else 'Warm, authentic, process-focused artist voice.'}

=== STEP 1: BRAINSTORM 7 CAPTION IDEAS ===
Generate 7 distinct caption ideas. Each should:
- Have a different hook angle (emotional, technical, playful, poetic, minimal, story-driven, etc.)
- Mention surface qualities naturally if listed (e.g., "love the carbon trapping")
- End with a question

AVOID redundant phrasing - if glaze already contains "glaze", don't add "glaze" again.

Format: Just list 7 ideas, numbered 1-7, each with hook + body + question.

=== STEP 2: SELECT 3 FINAL CAPTIONS ===
From your 7 ideas, select 3 that are:
1. Most distinct from each other (different tones/angles)
2. Most interesting and scroll-stopping
3. Under 300 characters each

Output format:
```
CAPTIONS:
1. [caption 1]
2. [caption 2]
3. [caption 3]
```"""

    # Call Ollama API
    response = _api_post_with_retry(
        f"{base_url}/api/generate",
        json_data={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.9}
        },
        timeout=300
    )

    if response.status_code != 200:
        raise RuntimeError(f"Ollama error: {response.text}")

    result = response.json()
    # DeepSeek returns content in 'thinking' field, not 'response'
    caption = result.get("response") or result.get("thinking", "")
    return caption.strip()


# =============================================================================
# OPENROUTER (API - PAID)
# =============================================================================

def analyze_photo_with_ai(photo_path: str, idea_seed: str = None) -> PhotoAnalysis:
    """
    Use AI to analyze photo content via OpenRouter.

    Requires OPENROUTER_API_KEY environment variable.
    Falls back to basic analysis if not available.

    Args:
        photo_path: Path to the photo file
        idea_seed: Optional creative association from the potter (e.g., "reminds me of basalt")
    """
    import os
    from openai import OpenAI

    # Check for API key
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("OPENROUTER_API_KEY not set, using basic analysis")
        return analyze_photo_basic(photo_path)

    # Compress and encode image (handles large files automatically)
    # Note: After compression, image is always JPEG
    base64_image = compress_image_for_api(photo_path)
    media_type = "image/jpeg"  # Compression always outputs JPEG

    # Use OpenRouter with OpenAI SDK
    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1"
    )

    # Build idea seed section if provided
    if idea_seed:
        idea_seed_section = f"""

POTTER'S CREATIVE LENS: The potter noted this piece reminds them of "{idea_seed}"
Consider this perspective while analyzing - does it reveal anything about the form, surface, or mood?
This is ONE lens among many - still explore all possibilities in your hypotheses.
"""
    else:
        idea_seed_section = ""

    # Build vision prompt with few-shot examples from feedback
    few_shot_examples = build_few_shot_examples()
    examples_section = format_few_shot_examples(few_shot_examples)
    prompt = VISION_PROMPT_TEMPLATE.format(idea_seed_section=idea_seed_section, color_sections=_COLOR_SECTIONS, chemistry_section=_CHEMISTRY_SECTION) + examples_section

    # Use configurable vision model via OpenRouter
    config = get_ai_config()
    response = client.chat.completions.create(
        model=config.openrouter_vision_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{base64_image}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ],
        max_tokens=2000,
        temperature=0.9
    )

    # Parse response
    import json
    response_text = response.choices[0].message.content

    # Extract JSON from response (handle markdown code blocks, extra text)
    try:
        # Try direct parse
        result = json.loads(response_text)
    except json.JSONDecodeError:
        import re
        # Try to find JSON in markdown code block
        code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if code_block_match:
            result = json.loads(code_block_match.group(1))
        else:
            # Try greedy match for outermost braces
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                raise ValueError("Could not parse AI response as JSON")

    return PhotoAnalysis(
        content_type=ContentType(result.get("content_type", "finished")),
        piece_type=result.get("piece_type", "piece"),
        primary_colors=result.get("primary_colors", ["earth tones"]),
        secondary_colors=result.get("secondary_colors", []),
        glaze_type=result.get("glaze_type"),
        color_appearance=result.get("color_appearance"),
        technique=result.get("technique"),
        mood=result.get("mood", "warm"),
        is_process=result.get("content_type") in ["process", "kiln_reveal"],
        dimensions_visible=result.get("dimensions_visible", False),
        suggested_hook=result.get("brief_description", "Handmade ceramic piece"),
        firing_state=result.get("firing_state"),
        surface_qualities=result.get("surface_qualities", []),
        piece_count=result.get("piece_count", 1),
        clay_type=result.get("clay_type"),
        form_attributes=result.get("form_attributes", []),
        purpose=result.get("purpose") or infer_purpose(result.get("piece_type", "piece")),
        product_family=result.get("product_family") or infer_product_family(result.get("piece_type", "piece")),
        safety_flags=infer_safety_flags(result.get("piece_type"), result.get("glaze_type")),
        hypotheses=result.get("hypotheses", []),
        lighting=result.get("lighting"),
        photo_quality=result.get("photo_quality"),
        uncertainties=result.get("uncertainties"),
        color_distribution=result.get("color_distribution"),
    )


def generate_hook(analysis: PhotoAnalysis) -> str:
    """Generate the first line hook based on analysis."""
    parts = []

    # Add technique if known
    if analysis.technique:
        parts.append(analysis.technique.replace("-", " "))

    # Determine if we need plural form
    # Use plural for: studio shots, multiple pieces (piece_count > 1)
    use_plural = (
        analysis.content_type == ContentType.STUDIO or
        getattr(analysis, 'piece_count', 1) > 1
    )

    # Add piece type (pluralize if needed)
    piece_type = analysis.piece_type
    if use_plural and piece_type == "piece":
        piece_type = "pieces"
    parts.append(piece_type)

    # Add glaze if known (avoid redundant "glaze" if already in glaze_type)
    if analysis.glaze_type:
        if "glaze" in analysis.glaze_type.lower():
            parts.append(f"with {analysis.glaze_type}")
        else:
            parts.append(f"with {analysis.glaze_type} glaze")

    # Add color if distinctive
    if analysis.primary_colors and analysis.primary_colors[0] != "earth tones":
        parts.append(f"in {analysis.primary_colors[0]} tones")

    hook = " ".join(parts)
    return hook.capitalize()


def generate_body(analysis: PhotoAnalysis) -> str:
    """Generate the caption body based on content type."""
    templates = {
        ContentType.FINISHED_PIECE: [
            "This piece came out of the kiln with such beautiful {colors}. {glaze_note}{surface_note}",
            "Love how this {glaze_desc} interacts with the clay on this {piece}.{surface_note}",
            "The {colors} on this {piece} are exactly what I was hoping for.{surface_note}",
        ],
        ContentType.PROCESS: [
            "Working on some new {piece}s at the studio today. {technique_note}",
            "Here's a peek at the process behind these {piece}s.",
            "Always love the feeling of clay in my hands, especially when making {piece}s.",
        ],
        ContentType.KILN_REVEAL: [
            "Kiln reveal day! These {piece}s came out even better than expected.{surface_note}",
            "The moment of truth - opening the kiln to see these {piece}s.{surface_note}",
            "Nothing beats the surprise of a kiln opening. {glaze_note}{surface_note}",
        ],
        ContentType.STUDIO: [
            "A day in the studio. Working on some new pieces.",
            "Studio vibes today - surrounded by clay and creativity.",
            "Behind the scenes at my Long Beach pottery studio.",
        ],
        ContentType.DETAIL: [
            "A closer look at the {glaze} on this {piece}.{surface_note}",
            "The details on this {piece} make it special.{surface_note}",
            "Zooming in on the texture of this {piece}.{surface_note}",
        ],
        # Video-specific templates
        ContentType.PROCESS_VIDEO: [
            "Behind the scenes in today's studio session. There's something so meditative about the process.",
            "A glimpse into my pottery process. Each piece tells a story from start to finish.",
            "POV: You're watching a pottery session. The best part is seeing the form come to life.",
        ],
        ContentType.KILN_REVEAL_VIDEO: [
            "The moment you've been waiting for - kiln reveal! The anticipation never gets old.",
            "Watch me open the kiln and see how these pieces turned out. Spoiler: I'm obsessed!",
            "Kiln reveal day is always full of surprises. Watch until the end to see my favorite piece!",
        ],
        ContentType.STUDIO_TOUR: [
            "Come take a tour of my pottery studio in Long Beach. This is where the magic happens!",
            "A look around my creative space. Every corner has a story.",
            "Welcome to my studio! This is where I spend most of my days making ceramics.",
        ],
        ContentType.TIME_LAPSE: [
            "Hours of work condensed into seconds. Watch this {activity} from start to finish!",
            "From lump of clay to finished form in under a minute. The process is so satisfying.",
            "Time-lapse of my latest pottery session. Can you spot the transformation?",
        ],
    }

    # Get template for content type
    options = templates.get(analysis.content_type, templates[ContentType.FINISHED_PIECE])

    # Pick first option (could randomize later)
    template = options[0]

    # Build replacements
    colors = " and ".join(analysis.primary_colors[:2]) if analysis.primary_colors else "colors"
    glaze_type = getattr(analysis, 'glaze_type', None)

    # Build glaze description that avoids redundant "glaze" repetition
    if glaze_type:
        # If glaze_type already contains "glaze", don't add it again
        if "glaze" in glaze_type.lower():
            glaze_desc = glaze_type
            glaze_note = f"The {glaze_type} creates such unique patterns."
        else:
            glaze_desc = f"{glaze_type} glaze"
            glaze_note = f"The {glaze_type} glaze creates such unique patterns."
    else:
        glaze_desc = "glaze"
        glaze_note = "The glaze created some beautiful surprises."

    technique = getattr(analysis, 'technique', None)
    technique_note = f"Using {technique} technique." if technique else "Handmade with care."

    # Build surface quality note if available (uses synonym bank for variety)
    surface_qualities = getattr(analysis, 'surface_qualities', [])
    surface_note = ""
    if surface_qualities:
        # Use synonyms for natural, varied language
        # Ensure grammar works by treating single-word adjectives differently from phrases
        notes = []
        for sq in surface_qualities[:2]:
            synonym = get_texture_synonym(sq)
            # If it's a single adjective (no spaces), add a noun
            if ' ' not in synonym and not synonym.endswith('ing'):
                synonym = f"{synonym} quality"
            notes.append(synonym)
        if notes:
            surface_note = f" Love the {notes[0]}" + (f" and {notes[1]}." if len(notes) > 1 else ".")

    # Handle VideoAnalysis
    activity = getattr(analysis, 'activity', 'pottery making') if hasattr(analysis, 'activity') else 'pottery making'

    body = template.format(
        piece=getattr(analysis, 'piece_type', 'piece'),
        colors=colors,
        glaze=getattr(analysis, 'glaze_type', None) or "glaze",
        glaze_desc=glaze_desc,
        glaze_note=glaze_note,
        technique_note=technique_note,
        activity=activity,
        surface_note=surface_note,
    )

    return body


def generate_cta(analysis) -> str:
    """Generate a call-to-action based on content type.

    Includes @cerafica_design handle in 80%+ of posts.
    Uses DM sales template for finished pieces.
    """
    import hashlib

    # Determine if this is a worldbuilding piece (planetary CTA)
    has_worldbuilding = (
        hasattr(analysis, 'worldbuilding')
        and analysis.worldbuilding is not None
    )
    is_video = isinstance(analysis, VideoAnalysis)
    is_reel = is_video and getattr(analysis, 'is_reel_suitable', False)

    # Tag @cerafica_design in ~80% of posts
    tag_handle = int(hashlib.md5(str(getattr(analysis, 'piece_type', '') + str(time.time())).encode()).hexdigest(), 16) % 5 != 0

    handle_tag = "\n@cerafica_design" if tag_handle else ""

    # Studio shot detection for @clayonfirst
    is_studio_shot = (
        hasattr(analysis, 'content_type')
        and analysis.content_type in [ContentType.STUDIO, ContentType.STUDIO_TOUR]
    )
    studio_tag = "\n@clayonfirst" if is_studio_shot else ""

    if has_worldbuilding:
        # Worldbuilding/planetary pieces get special CTAs
        planet_ctas = [
            "Would you explore this world?",
            "Which planet calls to you?",
            "Follow for more planetary explorations",
        ]
        cta = planet_ctas[0] + handle_tag
    elif is_reel or (is_video and getattr(analysis, 'is_reel_suitable', False)):
        # Videos/Reels — reach + engagement
        reel_ctas = [
            "Follow @cerafica_design for more planetary explorations",
            "Save this for later",
            "Drop a comment if this was satisfying",
        ]
        cta = reel_ctas[0]  # Already has handle
    else:
        cta_options = {
            ContentType.FINISHED_PIECE: [
                "DM to purchase — I respond within 4 hours! Details, dimensions, pricing, shipping, local pickup in Long Beach.",
                "Available at cerafica.etsy.com or DM to purchase",
                "Available in Long Beach or DM to purchase",
                "Send me a message if you'd like to bring this home",
            ],
            ContentType.PROCESS: [
                "Follow @cerafica_design for more process reveals",
                "Save this for inspiration",
                "What type of ceramics content do you enjoy seeing most?",
            ],
            ContentType.KILN_REVEAL: [
                "What's your favorite part of the pottery process?",
                "Do you love kiln reveal surprises as much as I do?",
                "Save this if you're a pottery lover",
            ],
            ContentType.STUDIO: [
                "Do you have a creative space that inspires you?",
                "Tag a friend who would love this studio",
                "Where do you create?",
            ],
            ContentType.DETAIL: [
                "Do you prefer matte or glossy finishes?",
                "What draws you to a piece — the form or the glaze?",
                "Save this for glaze inspiration",
            ],
            ContentType.PROCESS_VIDEO: [
                "Save this for when you need pottery ASMR",
                "What's your favorite part of the pottery process?",
                "Drop a comment if you love watching pottery being made",
            ],
            ContentType.KILN_REVEAL_VIDEO: [
                "What was your favorite piece from this kiln load?",
                "Do you love kiln reveal videos as much as I do?",
                "Watch until the end to see my favorite piece!",
            ],
            ContentType.STUDIO_TOUR: [
                "Do you have a creative space? Tell me about it!",
                "Tag someone who would love this studio setup",
                "What would you add to your dream pottery studio?",
            ],
            ContentType.TIME_LAPSE: [
                "Save this for satisfying pottery content",
                "What should I make next? Drop your ideas below!",
                "From clay to form in seconds. What do you think?",
            ],
        }

        options = cta_options.get(
            analysis.content_type if hasattr(analysis, 'content_type') else None,
            cta_options[ContentType.FINISHED_PIECE]
        )
        cta = options[0] + handle_tag

    # Append studio tag if applicable
    if studio_tag and "@clayonfirst" not in cta:
        cta += studio_tag

    return cta


# =============================================================================
# ALT TEXT GENERATION (Accessibility)
# =============================================================================

def generate_alt_text(analysis) -> str:
    """
    Generate an accessibility alt text description from existing PhotoAnalysis fields.

    No AI call needed — builds structurally from already-detected data.

    Rules:
    - Finished pieces: "{technique} {piece_type} with {glaze} in {colors}"
    - Process shots (greenware/bisque): "{technique} {piece_type}, work in progress"
    - Videos: "Pottery process video showing {activity}"
    - Colors: Skip generic "earth tones", use top 2 primary colors
    - Surface qualities: Add one notable quality if space allows
    - Hard truncate at 100 chars (Instagram limit), break at word boundary

    Args:
        analysis: PhotoAnalysis or VideoAnalysis object

    Returns:
        Alt text string (max 100 chars)
    """
    is_video = isinstance(analysis, VideoAnalysis)

    if is_video:
        activity = getattr(analysis, 'activity', 'pottery process')
        text = f"Pottery process video showing {activity}"
        return _truncate_alt_text(text, 100)

    # Determine firing state
    firing_state = getattr(analysis, 'firing_state', None)
    is_process_shot = firing_state in ("greenware", "bisque")

    technique = getattr(analysis, 'technique', None) or ""
    piece_type = getattr(analysis, 'piece_type', 'ceramic piece') or "ceramic piece"
    glaze_type = getattr(analysis, 'glaze_type', None)
    primary_colors = getattr(analysis, 'primary_colors', [])
    surface_qualities = getattr(analysis, 'surface_qualities', [])

    # Build base description
    if technique:
        base = f"{technique} {piece_type}"
    else:
        base = piece_type

    if is_process_shot:
        # No glaze mention on unfired work
        text = f"{base}, work in progress"
    elif glaze_type:
        text = f"{base} with {glaze_type}"
    else:
        text = base

    # Add colors (skip generic "earth tones")
    display_colors = [c for c in primary_colors[:2] if c.lower() not in ("earth tones",)]
    if display_colors:
        color_str = " and ".join(display_colors)
        text = f"{text} in {color_str}"

    # Add one surface quality if space allows
    if surface_qualities and len(text) < 80:
        quality = surface_qualities[0]
        candidate = f"{text} with {quality} surface"
        if len(candidate) <= 100:
            text = candidate

    return _truncate_alt_text(text, 100)


def _truncate_alt_text(text: str, max_len: int) -> str:
    """Truncate text at word boundary to fit within max_len characters."""
    if len(text) <= max_len:
        return text
    # Find last space before max_len
    truncated = text[:max_len]
    last_space = truncated.rfind(" ")
    if last_space > max_len * 0.6:  # Don't cut too aggressively
        return truncated[:last_space]
    return truncated


# =============================================================================
# CAPTION VALIDATION (Voice Rule Enforcement)
# =============================================================================

BANNED_WORDS = [
    "delve", "tapestry", "realm", "embrace", "elevate",
    "navigate", "foster", "groundbreaking", "invaluable",
    "relentless", "furthermore", "moreover", "additionally",
]


def validate_caption(caption: GeneratedCaption, analysis=None) -> tuple[bool, list[str]]:
    """
    Validate a generated caption against voice rules.

    Checks:
    - Banned words (from brand/voice-rules.md)
    - Em dash count (max 1)
    - Length (warn if < 100 or > 800 chars, sweet spot 300-500)
    - Question check (warn if missing question on finished pieces)

    Args:
        caption: GeneratedCaption object
        analysis: Optional PhotoAnalysis for context-aware checks

    Returns:
        Tuple of (is_valid: bool, issues: list[str])
    """
    issues = []
    full = caption.full_caption.lower()

    # 1. Banned words
    for word in BANNED_WORDS:
        if word in full:
            issues.append(f"Banned word: '{word}'")

    # 2. Em dash count (max 1)
    em_dash_count = caption.full_caption.count("\u2014") + caption.full_caption.count("--")
    if em_dash_count > 1:
        issues.append(f"Too many em dashes ({em_dash_count}), max 1")

    # 3. Length checks
    length = len(caption.full_caption)
    if length < 100:
        issues.append(f"Caption too short ({length} chars, recommend 300-500)")
    elif length > 800:
        issues.append(f"Caption too long ({length} chars, recommend 300-500)")
    elif length < 300:
        # Soft warning — not invalid, just guidance
        logging.warning(f"Caption validation: on the short side ({length} chars, sweet spot is 300-500)")

    # 4. Question check on finished pieces (soft warning)
    is_finished = (
        analysis
        and hasattr(analysis, 'content_type')
        and analysis.content_type == ContentType.FINISHED_PIECE
    )
    if is_finished and "?" not in caption.full_caption:
        logging.warning("Caption validation: finished piece missing a question (recommended 80%+)")

    # 5. Geological banned words (food/fabric metaphors that should be planetary terms)
    # Only flag when the piece has worldbuilding data — planetary language should be used instead
    has_worldbuilding = (
        analysis
        and hasattr(analysis, 'worldbuilding')
        and analysis.worldbuilding is not None
    )
    if has_worldbuilding:
        try:
            from geology_vocabulary import check_banned_words
            geo_violations = check_banned_words(caption.full_caption)
            for word in geo_violations:
                issues.append(f"Food/fabric metaphor (use geological term): '{word}'")
        except ImportError:
            pass

    is_valid = len(issues) == 0

    # Log warnings (don't block generation)
    if issues:
        for issue in issues:
            logging.warning(f"Caption validation: {issue}")

    return is_valid, issues


def select_hashtags(analysis, is_reel: bool = False, is_carousel: bool = False, max_tags: int = MAX_HASHTAGS) -> str:
    """
    Generate context-aware hashtags based on detected content.

    Strategy (March 2026 — Instagram hard-limits to 5 hashtags):
    5-slot framework — each slot serves a distinct purpose:
      Slot 1: Niche (what is this) — e.g. #handmadepottery
      Slot 2: Technique (how was it made) — e.g. #wheelthrown
      Slot 3: Audience (who is this for) — e.g. #ceramicart
      Slot 4: Content type (what format) — e.g. #potteryreels
      Slot 5: Local (where) — e.g. #longbeachartist (always included)

    No glaze-specific tags (too small). No tags over 5M posts (too competitive).

    Args:
        analysis: PhotoAnalysis or VideoAnalysis object with detected content
        is_reel: Whether this is a Reel
        is_carousel: Whether this is a carousel
        max_tags: Maximum tags (default 5, Instagram hard cap)

    Returns:
        String of hashtags
    """
    import hashlib

    tags = []

    piece_type = getattr(analysis, 'piece_type', None) or ''
    technique = getattr(analysis, 'technique', None) or ''
    firing_state = getattr(analysis, 'firing_state', None)
    is_finished = firing_state == "finished"
    is_process = firing_state in ("greenware", "bisque")

    is_video = is_reel or is_carousel or (
        hasattr(analysis, 'content_type') and analysis.content_type in [
            ContentType.PROCESS_VIDEO, ContentType.KILN_REVEAL_VIDEO,
            ContentType.STUDIO_TOUR, ContentType.TIME_LAPSE
        ]
    )

    # Slot 1: Niche (what is this post about)
    niche_pool = HASHTAG_TAXONOMY["niche"]
    if is_process:
        niche_tag = niche_pool.get("process", niche_pool["default"])[0]
    elif hasattr(analysis, 'glaze_type') and analysis.glaze_type:
        niche_tag = niche_pool.get("glaze_focus", niche_pool["default"])[0]
    else:
        niche_tag = niche_pool["default"][0]
    tags.append(niche_tag)

    # Slot 2: Technique (how was it made)
    if technique:
        tech_key = technique.lower().replace("-", "_")
        tech_tags = HASHTAG_TAXONOMY["technique_to_hashtag"].get(tech_key, [])
        if tech_tags:
            tags.append(tech_tags[0])

    # Slot 3: Audience (who should see this)
    audience_pool = HASHTAG_TAXONOMY["audience"]
    if piece_type in ("sculpture",):
        audience_tag = audience_pool.get("art_collector", audience_pool["default"])[0]
    elif piece_type in ("planter",):
        audience_tag = audience_pool.get("home_decor", audience_pool["default"])[0]
    elif is_process:
        audience_tag = audience_pool.get("pottery_community", audience_pool["default"])[0]
    else:
        audience_tag = audience_pool["default"][0]
    tags.append(audience_tag)

    # Slot 4: Content type (what format — skip for photos to save the slot)
    ct_pool = HASHTAG_TAXONOMY["content_type"]
    if is_video:
        if is_reel or hasattr(analysis, 'is_reel_suitable') and analysis.is_reel_suitable:
            ct_tags = ct_pool.get("reel", ct_pool.get("video", []))
        elif is_process:
            ct_tags = ct_pool.get("process_video", ct_pool.get("video", []))
        else:
            ct_tags = ct_pool.get("video", [])
        if ct_tags:
            tags.append(ct_tags[0])
    elif is_carousel:
        ct_tags = ct_pool.get("carousel", [])
        if ct_tags:
            tags.append(ct_tags[0])

    # Slot 5: Local (always include — rotate through pool)
    local_pool = HASHTAG_TAXONOMY["local"]
    local_idx = int(hashlib.md5((piece_type or 'x').encode()).hexdigest(), 16) % len(local_pool)
    tags.append(local_pool[local_idx])

    # Warn if fewer than 3 tags (indicates missing analysis data)
    if len(tags) < 3:
        logging.warning(
            f"Only {len(tags)} hashtags generated — missing analysis data? "
            f"technique={technique}, "
            f"piece={piece_type}, "
            f"firing_state={firing_state}"
        )

    return " ".join(tags[:max_tags])


def generate_caption_for_carousel(
    analysis: CarouselAnalysis,
    voice_rules: str = None,
    include_cta: bool = True
) -> GeneratedCaption:
    """
    Generate a complete caption for a carousel post.

    Args:
        analysis: CarouselAnalysis object
        voice_rules: Optional voice rules content
        include_cta: Whether to include call-to-action

    Returns:
        GeneratedCaption with all components
    """
    # Carousel hooks based on narrative flow
    hook_templates = {
        "collection": f"Fresh from the kiln! {analysis.primary_theme.capitalize()} - swipe to see them all",
        "story": f"From lump of clay to finished {analysis.primary_theme} - the full journey",
        "details": f"The little details make this {analysis.primary_theme} special",
        "mixed": f"{analysis.primary_theme.capitalize()} - {len(analysis.content_types)} slides of pottery goodness",
    }

    hook = hook_templates.get(analysis.narrative_flow, f"Swipe to see more {analysis.primary_theme}")

    # Body based on narrative flow
    body_templates = {
        "collection": "Each piece has its own personality. Which one speaks to you?",
        "story": "Every piece tells a story from start to finish. This is the journey of creation.",
        "details": "Sometimes you need to zoom in to really appreciate the glaze and texture.",
        "mixed": "A mix of process and finished pieces from the studio.",
    }

    body = body_templates.get(analysis.narrative_flow, "Swipe through for more!")

    # CTA
    cta = analysis.cta if include_cta else ""

    # Hashtags for carousel
    hashtags = select_hashtags(
        PhotoAnalysis(
            content_type=ContentType.FINISHED_PIECE,
            piece_type=analysis.primary_theme,
            primary_colors=["earth tones"],
            secondary_colors=[],
            glaze_type=None,
            color_appearance=None,
            technique=None,
            mood="warm",
            is_process=False,
            dimensions_visible=False,
            suggested_hook=hook
        ),
        is_carousel=True
    )

    # Assemble
    parts = [hook, "", body]
    if cta:
        parts.extend(["", cta])
    parts.extend(["", ".", hashtags])

    full_caption = "\n".join(parts)

    return GeneratedCaption(
        hook=hook,
        body=body,
        cta=cta,
        hashtags=hashtags,
        full_caption=full_caption,
        alt_text=generate_alt_text(analysis)
    )


# =============================================================================
# AI RESPONSE PARSING
# =============================================================================

def _parse_ai_caption_response(caption_text: str, return_options: bool = False) -> dict:
    """
    Parse structured AI caption response into hook, body, CTA components.

    The AI prompt generates 3 numbered captions in this format:
        CAPTIONS:
        1. Hook line
           Body lines here
           CTA line?
        2. ...

    Args:
        caption_text: Raw AI response text
        return_options: If True, return all 3 caption options as list

    Returns:
        dict with "hook", "body", "cta" keys (first caption by default)
        If return_options=True, also includes "options" with list of dicts
    """
    import re

    # Extract the CAPTIONS section (everything after CAPTIONS: header)
    captions_match = re.search(r'CAPTIONS:\s*\n(.*)', caption_text, re.DOTALL)
    if captions_match:
        captions_block = captions_match.group(1).strip()
    else:
        # Fallback: use entire text if no CAPTIONS header found
        captions_block = caption_text.strip()

    # Split on numbered list items (including at start of block)
    items = re.split(r'(?:^|\n)\s*\d+\.\s*', captions_block)

    # Filter out empty items and strip
    items = [item.strip() for item in items if item.strip()]

    def _parse_single(item_text: str) -> dict:
        """Parse a single caption item into hook, body, cta."""
        lines = [l.strip() for l in item_text.strip().split("\n") if l.strip()]
        if not lines:
            return {"hook": "", "body": "", "cta": ""}

        hook = lines[0]
        body_lines = []
        cta = ""

        for line in lines[1:]:
            if "?" in line or line.startswith("DM") or "comment" in line.lower():
                cta = line
            elif not cta:  # Only collect body lines before CTA
                body_lines.append(line)

        body = " ".join(body_lines).strip()
        return {"hook": hook, "body": body, "cta": cta}

    options = [_parse_single(item) for item in items]

    if not options:
        # Last resort fallback: treat whole text as one caption
        lines = caption_text.strip().split("\n")
        return {"hook": lines[0] if lines else "", "body": "", "cta": ""}

    result = options[0]
    if return_options:
        result["options"] = options
    return result


def generate_caption_with_ai(
    analysis: PhotoAnalysis,
    voice_rules: str = None
) -> GeneratedCaption:
    """
    Generate caption using AI for more natural, brand-aligned text.

    Uses configured backend (Ollama local or OpenRouter API).

    Args:
        analysis: PhotoAnalysis object
        voice_rules: Optional voice rules content

    Returns:
        GeneratedCaption with AI-generated content
    """
    config = get_ai_config()

    # Load voice rules if not provided
    if voice_rules is None:
        voice_rules = load_voice_rules()

    # Generate caption using configured backend
    if config.backend == "ollama":
        caption_text = generate_caption_with_ollama(analysis, voice_rules)
    else:
        # Use OpenRouter for caption generation
        caption_text = generate_caption_with_openrouter(analysis, voice_rules)

    # Parse the AI response (structured CAPTIONS format)
    parsed = _parse_ai_caption_response(caption_text)
    hook = parsed["hook"]
    body = parsed["body"]
    cta = parsed["cta"]
    hashtags = select_hashtags(analysis)

    # Assemble full caption
    parts = [hook]
    if body:
        parts.extend(["", body])
    if cta:
        parts.extend(["", cta])
    parts.extend(["", ".", hashtags])

    full_caption = "\n".join(parts)

    return GeneratedCaption(
        hook=hook,
        body=body,
        cta=cta,
        hashtags=hashtags,
        full_caption=full_caption,
        alt_text=generate_alt_text(analysis)
    )


def generate_caption_with_openrouter(
    analysis: PhotoAnalysis,
    voice_rules: str = None
) -> str:
    """
    Generate caption using OpenRouter API.

    Args:
        analysis: PhotoAnalysis object
        voice_rules: Optional brand voice guidelines

    Returns:
        Generated caption text
    """
    from openai import OpenAI

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set")

    config = get_ai_config()

    # Load voice rules if not provided
    if voice_rules is None:
        voice_rules = load_voice_rules()

    # Build enrichment blocks
    worldbuilding_block = ""
    geo_vocab_block = build_geological_vocab_block(analysis)
    few_shot_block = ""
    brand_identity_block = ""

    if analysis.worldbuilding:
        worldbuilding_block = build_worldbuilding_block(analysis.worldbuilding)
    else:
        few_shot_examples = extract_few_shot_examples(voice_rules)
        if few_shot_examples:
            few_shot_block = f"FEW-SHOT EXAMPLES (study these patterns — process education + specific technique + emotional expression + questions):\n{few_shot_examples}"

        identity_md = load_brand_identity()
        if identity_md:
            brand_identity_block = build_brand_identity_block(identity_md)

    # Detect if this is a process shot (unfired or in-progress)
    _firing_state = getattr(analysis, 'firing_state', None)
    _glaze_type = getattr(analysis, 'glaze_type', None)
    is_process_shot = (
        _firing_state in ["greenware", "bisque"] or
        analysis.content_type in [ContentType.PROCESS, ContentType.KILN_REVEAL, ContentType.STUDIO, ContentType.PROCESS_VIDEO] or
        (_glaze_type is None and _firing_state != "finished")
    )

    if is_process_shot:
        # PROCESS SHOT - focus on making, not selling
        enrichment_sections = ""
        if worldbuilding_block:
            enrichment_sections += f"\n\n{worldbuilding_block}"
        if geo_vocab_block:
            enrichment_sections += f"\n\n{geo_vocab_block}"
        if few_shot_block:
            enrichment_sections += f"\n\n{few_shot_block}"
        if brand_identity_block:
            enrichment_sections += f"\n\n{brand_identity_block}"

        prompt = f"""You are a creative copywriter for a pottery Instagram account.

PIECE DETAILS:
- Type: {analysis.piece_type}
- Stage: {getattr(analysis, 'firing_state', None) or 'work in progress'}
- Colors: {', '.join(analysis.primary_colors)}
- Technique: {analysis.technique or 'handmade'}
- Mood: {analysis.mood}

IMPORTANT: This is a PROCESS shot showing work in progress (unfired or in-progress clay).
{enrichment_sections}

BRAND VOICE:
{voice_rules if voice_rules else 'Warm, authentic, process-focused artist voice.'}

=== STEP 1: BRAINSTORM 7 CAPTION IDEAS ===
Generate 7 distinct caption ideas. Each should:
- Have a different hook angle (emotional, technical, playful, poetic, etc.)
- Focus on the making process or studio moment
- End with a question about pottery making

DO NOT:
- Ask about displaying the piece or where to put it
- Treat it like a finished piece available for purchase
- Ask "what would you put in this vase/bowl?"

Format: Just list 7 ideas, numbered 1-7, each with hook + body + question.

=== STEP 2: SELECT 3 FINAL CAPTIONS ===
From your 7 ideas, select 3 that are:
1. Most distinct from each other (different tones/angles)
2. Most interesting and scroll-stopping
3. Under 300 characters each

Output format:
```
CAPTIONS:
1. [caption 1]
2. [caption 2]
3. [caption 3]
```"""
    else:
        # FINISHED PIECE - can include sales elements
        surface_qualities = getattr(analysis, 'surface_qualities', [])
        surface_note = ""
        if surface_qualities:
            # Use synonyms for varied, natural language
            notes = [get_texture_synonym(sq) for sq in surface_qualities[:2]]
            surface_note = f"\n- Surface Qualities: {', '.join(notes)}"

        enrichment_sections = ""
        if worldbuilding_block:
            enrichment_sections += f"\n\n{worldbuilding_block}"
        if geo_vocab_block:
            enrichment_sections += f"\n\n{geo_vocab_block}"
        if few_shot_block:
            enrichment_sections += f"\n\n{few_shot_block}"
        if brand_identity_block:
            enrichment_sections += f"\n\n{brand_identity_block}"

        prompt = f"""You are a creative copywriter for a pottery Instagram account.

PIECE DETAILS:
- Type: {analysis.piece_type}
- Surface Chemistry: {analysis.color_appearance or 'unknown'}
- Colors: {', '.join(analysis.primary_colors)}
- Technique: {analysis.technique or 'handmade'}
- Mood: {analysis.mood}{surface_note}
{enrichment_sections}

BRAND VOICE:
{voice_rules if voice_rules else 'Warm, authentic, process-focused artist voice.'}

=== STEP 1: BRAINSTORM 7 CAPTION IDEAS ===
Generate 7 distinct caption ideas. Each should:
- Have a different hook angle (emotional, technical, playful, poetic, minimal, story-driven, etc.)
- Mention surface qualities naturally if listed (e.g., "love the carbon trapping")
- End with a question

AVOID redundant phrasing - if glaze already contains "glaze", don't add "glaze" again.

Format: Just list 7 ideas, numbered 1-7, each with hook + body + question.

=== STEP 2: SELECT 3 FINAL CAPTIONS ===
From your 7 ideas, select 3 that are:
1. Most distinct from each other (different tones/angles)
2. Most interesting and scroll-stopping
3. Under 300 characters each

Output format:
```
CAPTIONS:
1. [caption 1]
2. [caption 2]
3. [caption 3]
```"""

    client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")

    response = client.chat.completions.create(
        model=config.openrouter_caption_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800,
        temperature=0.9
    )

    return response.choices[0].message.content.strip()


def generate_caption(
    analysis: PhotoAnalysis,
    voice_rules: str = None,
    include_cta: bool = True,
    is_reel: bool = False,
    use_ai: bool = True
) -> GeneratedCaption:
    """
    Generate a complete caption from photo/video analysis.

    Args:
        analysis: PhotoAnalysis or VideoAnalysis object
        voice_rules: Optional voice rules content (loaded from file if not provided)
        include_cta: Whether to include call-to-action
        is_reel: Whether this is a Reel (shorter, punchier style)
        use_ai: Whether to use AI for caption generation (default: True)

    Returns:
        GeneratedCaption with all components
    """
    # Check if it's a video analysis
    is_video = isinstance(analysis, VideoAnalysis)

    # Videos with worldbuilding data get AI-generated captions (planetary lore)
    if is_video and getattr(analysis, 'worldbuilding', None):
        # Override content type — this is a finished piece showcase, not process
        analysis.content_type = ContentType.FINISHED_PIECE
        if not analysis.piece_type:
            analysis.piece_type = "vase"
        if not analysis.technique:
            analysis.technique = "wheel-thrown"
        try:
            result = generate_caption_with_ai(analysis, voice_rules)
            result.hashtags = select_hashtags(analysis, is_reel=is_reel)
            full_caption = result.full_caption
            # Replace hashtags in assembled caption
            if result.hashtags:
                parts = full_caption.rsplit(".", 1)
                if len(parts) == 2:
                    full_caption = parts[0] + ".\n" + result.hashtags
                else:
                    full_caption = full_caption.rstrip() + "\n.\n" + result.hashtags
                result = GeneratedCaption(
                    hook=result.hook,
                    body=result.body,
                    cta=result.cta,
                    hashtags=result.hashtags,
                    full_caption=full_caption,
                    alt_text=result.alt_text,
                )
            validate_caption(result, analysis)
            return result
        except Exception as e:
            print(f"AI caption generation failed for worldbuilding video, using templates: {e}")

    if is_video:
        return generate_caption_for_video(analysis, voice_rules, include_cta, is_reel)

    # Use AI for caption generation if requested
    if use_ai:
        try:
            result = generate_caption_with_ai(analysis, voice_rules)
            validate_caption(result, analysis)
            return result
        except Exception as e:
            print(f"AI caption generation failed, using templates: {e}")
            # Fall through to template-based generation

    # Generate components for photo (template-based)
    hook = generate_hook(analysis)
    body = generate_body(analysis)
    cta = generate_cta(analysis) if include_cta else ""
    hashtags = select_hashtags(analysis)

    # Assemble full caption
    parts = [hook]

    if body:
        parts.append("")
        parts.append(body)

    if cta:
        parts.append("")
        parts.append(cta)

    # Hashtags at the end with separator
    parts.append("")
    parts.append(".")
    parts.append(hashtags)

    full_caption = "\n".join(parts)

    result = GeneratedCaption(
        hook=hook,
        body=body,
        cta=cta,
        hashtags=hashtags,
        full_caption=full_caption,
        alt_text=generate_alt_text(analysis)
    )
    validate_caption(result, analysis)
    return result


def generate_caption_for_video(
    analysis: VideoAnalysis,
    voice_rules: str = None,
    include_cta: bool = True,
    is_reel: bool = False
) -> GeneratedCaption:
    """
    Generate a complete caption from video analysis.

    Args:
        analysis: VideoAnalysis object
        voice_rules: Optional voice rules content
        include_cta: Whether to include call-to-action
        is_reel: Whether this is a Reel (shorter, punchier style)

    Returns:
        GeneratedCaption with all components
    """
    # Reels get shorter, punchier hooks
    if is_reel or analysis.is_reel_suitable:
        reel_hooks = [
            f"Wait for it... {analysis.activity}",
            f"POV: {analysis.activity}",
            f"{analysis.activity.capitalize()} in real time",
            f"The most satisfying part of pottery",
            f"Pottery ASMR: {analysis.activity}",
        ]
        hook = reel_hooks[0]  # Could randomize later
    else:
        # For feed videos, create a better hook that's not redundant
        activity = analysis.activity if analysis.activity else "pottery"
        suggested = analysis.suggested_hook if analysis.suggested_hook else "studio session"

        # Avoid redundant "pottery process - pottery process video" pattern
        if suggested.lower() in activity.lower() or activity.lower() in suggested.lower():
            # They overlap, so just use one
            hook = activity.capitalize() if activity else "Studio session"
        else:
            hook = f"{activity.capitalize()} - {suggested}"

    # Generate body using shared function
    body = generate_body(analysis)

    # Generate CTA (Reels get different CTAs)
    if is_reel or analysis.is_reel_suitable:
        reel_ctas = [
            "Save this for later",
            "Drop a 🎨 if this was satisfying",
            "Follow for more pottery content",
            "What should I make next?",
        ]
        cta = reel_ctas[0] if include_cta else ""
    else:
        cta = generate_cta(analysis) if include_cta else ""

    # Select hashtags (Reels get Reels-specific tags)
    hashtags = select_hashtags(analysis, is_reel=(is_reel or analysis.is_reel_suitable))

    # Assemble full caption
    parts = [hook]

    # Add duration note for longer videos
    if analysis.duration_seconds > 60:
        mins = int(analysis.duration_seconds // 60)
        secs = int(analysis.duration_seconds % 60)
        parts.append(f"({mins}:{secs:02d})")

    if body:
        parts.append("")
        parts.append(body)

    if cta:
        parts.append("")
        parts.append(cta)

    # Hashtags at the end with separator
    parts.append("")
    parts.append(".")
    parts.append(hashtags)

    full_caption = "\n".join(parts)

    return GeneratedCaption(
        hook=hook,
        body=body,
        cta=cta,
        hashtags=hashtags,
        full_caption=full_caption,
        alt_text=generate_alt_text(analysis)
    )


def caption_length_ok(caption: str) -> bool:
    """Check if caption length is in optimal range (300-500 chars)."""
    length = len(caption)
    return 300 <= length <= 800  # Allow up to 800 for hashtags


def test_module(photo_path: str = None, test_ai: bool = False):
    """Test the caption generator module."""
    config = get_ai_config()

    print("=" * 60)
    print("Caption Generator Module Test")
    print("=" * 60)

    # 0. Show AI configuration
    print(f"\n0. AI Configuration:")
    print(f"   Backend: {config.backend}")
    if config.backend == "ollama":
        print(f"   Vision Model: {config.ollama_vision_model}")
        print(f"   Writing Model: {config.ollama_writing_model}")
        print(f"   Ollama URL: {config.ollama_base_url}")
        ollama_ok = check_ollama_available(config.ollama_base_url)
        print(f"   Ollama available: {'✓' if ollama_ok else '✗'}")
    else:
        print(f"   Vision Model: {config.openrouter_vision_model}")
        print(f"   Caption Model: {config.openrouter_caption_model}")
        print(f"   API Key set: {'✓' if os.environ.get('OPENROUTER_API_KEY') else '✗'}")

    # 1. Test basic analysis
    print("\n1. Testing basic photo analysis...")
    if photo_path and Path(photo_path).exists():
        analysis = analyze_photo(photo_path, use_ai=False)
        print(f"   Piece type: {analysis.piece_type}")
        print(f"   Content type: {analysis.content_type.value}")
        print(f"   Technique: {analysis.technique or 'not detected'}")
        print(f"   Glaze: {analysis.glaze_type or 'not detected'}")
    else:
        # Use mock analysis
        analysis = PhotoAnalysis(
            content_type=ContentType.FINISHED_PIECE,
            piece_type="vase",
            primary_colors=["orange", "grey"],
            secondary_colors=["brown"],
            glaze_type="shino",
            color_appearance=None,
            technique="wheel-thrown",
            mood="earthy",
            is_process=False,
            dimensions_visible=True,
            suggested_hook="Carbon trap shino vase"
        )
        print("   Using mock analysis (no photo provided)")
        print(f"   Piece type: {analysis.piece_type}")
        print(f"   Glaze: {analysis.glaze_type}")

    # 2. Test caption generation (template-based)
    print("\n2. Testing caption generation (templates)...")
    caption = generate_caption(analysis, use_ai=False)

    print(f"\n   Hook: {caption.hook}")
    print(f"\n   Body: {caption.body}")
    print(f"\n   CTA: {caption.cta}")
    print(f"\n   Hashtags: {caption.hashtags[:50]}...")

    print("\n3. Full caption (template):")
    print("-" * 40)
    print(caption.full_caption)
    print("-" * 40)

    print(f"\n   Caption length: {len(caption.full_caption)} chars")
    print(f"   Length OK: {'✓' if caption_length_ok(caption.full_caption) else '✗'}")

    # 4. Test with AI if requested
    if test_ai or (photo_path and Path(photo_path).exists()):
        print(f"\n4. Testing AI-powered analysis ({config.backend})...")
        if photo_path and Path(photo_path).exists():
            try:
                ai_analysis = analyze_photo(photo_path, use_ai=True)
                print(f"   AI detected piece type: {ai_analysis.piece_type}")
                print(f"   AI detected glaze: {ai_analysis.glaze_type or 'none'}")
                print(f"   AI detected technique: {ai_analysis.technique or 'none'}")

                # 5. Test AI caption generation
                print(f"\n5. Testing AI caption generation ({config.backend})...")
                ai_caption = generate_caption(ai_analysis, use_ai=True)
                print("\n   AI Caption:")
                print("-" * 40)
                print(ai_caption.full_caption)
                print("-" * 40)

            except Exception as e:
                print(f"   AI analysis failed: {e}")
        else:
            print("   Skipping AI analysis (no photo provided)")

    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    import sys

    photo_path = None
    test_ai = False
    backend = None
    model = None

    args = sys.argv[1:]

    # Parse arguments
    if "--test" in args or "--test-ai" in args:
        test_ai = "--test-ai" in args

        # Check for --photo argument
        try:
            photo_idx = args.index("--photo")
            if photo_idx + 1 < len(args):
                photo_path = args[photo_idx + 1]
        except ValueError:
            pass

        # Check for --backend argument
        try:
            backend_idx = args.index("--backend")
            if backend_idx + 1 < len(args):
                backend = args[backend_idx + 1]
        except ValueError:
            pass

        # Check for --model argument
        try:
            model_idx = args.index("--model")
            if model_idx + 1 < len(args):
                model = args[model_idx + 1]
        except ValueError:
            pass

        # Configure if backend or model specified
        if backend or model:
            configure_ai(
                backend=backend if backend in ["ollama", "openrouter"] else None,
                ollama_vision_model=model if backend == "ollama" or (backend is None and model) else None,
                ollama_writing_model=model if backend == "ollama" or (backend is None and model) else None
            )

        test_module(photo_path, test_ai=test_ai)
    else:
        print("Caption Generator Module")
        print("")
        print("Usage:")
        print("  python caption_generator.py --test [--photo PATH]")
        print("      Test with template-based captions")
        print("")
        print("  python caption_generator.py --test-ai [--photo PATH] [--backend ollama|openrouter] [--model MODEL]")
        print("      Test with AI-powered analysis and captions")
        print("")
        print("Options:")
        print("  --photo PATH    Path to photo file for analysis")
        print("  --backend       AI backend: ollama (local, FREE) or openrouter (API, paid)")
        print("  --model         Model name (e.g., qwen3.5:9b, qwen3.5:35b)")
        print("")
        print("Examples:")
        print("  python caption_generator.py --test --photo vase.jpg")
        print("  python caption_generator.py --test-ai --photo vase.jpg --backend ollama")
        print("  python caption_generator.py --test-ai --photo vase.jpg --model qwen3.5:35b")
