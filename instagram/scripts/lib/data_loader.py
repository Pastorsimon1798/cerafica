"""Data loader for ceramics-foundation submodule data.

Reads canonical ceramic data from JSON/markdown files in the ceramics-foundation
submodule. Falls back to None if submodule is not present, allowing callers to
use hardcoded defaults.

Same pattern as openglaze/core/chemistry/data_loader.py.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# ceramics-foundation submodule location relative to this file
# scripts/lib/data_loader.py -> ../../ceramics-foundation/
_FOUNDATION_DIR = Path(__file__).resolve().parent.parent.parent / 'ceramics-foundation'


def _find_foundation_dir() -> Optional[Path]:
    """Find the ceramics-foundation submodule root directory."""
    if _FOUNDATION_DIR.is_dir():
        return _FOUNDATION_DIR
    return None


def _load_json(path: Path) -> Optional[object]:
    """Load a JSON file, returning None on any error."""
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        logger.debug(f'Could not load {path}: {e}')
        return None


def load_colors() -> Optional[Dict[str, Dict[str, str]]]:
    """Parse colors.md markdown table into {color_name: {family, visual_id}}.

    Returns dict keyed by lowercase color name, or None if file unavailable.
    """
    foundation = _find_foundation_dir()
    if foundation is None:
        return None

    colors_path = foundation / 'taxonomies' / 'colors.md'
    try:
        text = colors_path.read_text()
    except OSError as e:
        logger.debug(f'Could not read {colors_path}: {e}')
        return None

    # Parse family headings and table rows
    colors = {}
    current_family = None

    # Map section headings to canonical family names
    family_map = {
        'browns': 'brown',
        'reds': 'red',
        'grays': 'gray',
        'whites': 'white',
        'whites & creams': 'white',
        'greens': 'green',
        'blues': 'blue',
        'oranges': 'orange',
        'oranges & yellows': 'orange',
        'yellows': 'yellow',
        'purples': 'purple',
        'purples/violets': 'purple',
        'blacks': 'black',
        'fallback colors': None,  # skip fallbacks section
    }

    for line in text.splitlines():
        # Detect section headings: ## Browns (28 terms)
        heading_match = re.match(r'^##\s+(.+?)(?:\s*\(\d+)', line)
        if heading_match:
            heading = heading_match.group(1).strip().lower()
            current_family = family_map.get(heading)
            continue

        if current_family is None:
            continue

        # Parse table rows: | **Color Name** | Visual description |
        row_match = re.match(r'\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|', line)
        if row_match:
            color_name = row_match.group(1).strip()
            visual_id = row_match.group(2).strip()
            key = color_name.lower().replace(' ', '_')
            colors[key] = {
                'family': current_family,
                'visual_id': visual_id,
            }

    return colors if colors else None


def load_clay_bodies() -> Optional[Dict]:
    """Load clay body database from clay-bodies.json.

    Returns dict with 'clay_bodies' key or None if unavailable.
    """
    foundation = _find_foundation_dir()
    if foundation is None:
        return None

    data = _load_json(foundation / 'data' / 'clay-bodies.json')
    if data and 'clay_bodies' in data:
        return data
    return None


def load_colorants() -> Optional[Dict]:
    """Load colorant data from colorants.json.

    Returns dict with 'colorants' key or None if unavailable.
    """
    foundation = _find_foundation_dir()
    if foundation is None:
        return None

    data = _load_json(foundation / 'data' / 'colorants.json')
    if data and 'colorants' in data:
        return data
    return None


def load_layering_rules() -> Optional[Dict]:
    """Load layering compatibility rules from layering-rules.json.

    Returns the full rules dict or None if unavailable.
    """
    foundation = _find_foundation_dir()
    if foundation is None:
        return None

    data = _load_json(foundation / 'data' / 'layering-rules.json')
    if data:
        return data
    return None
