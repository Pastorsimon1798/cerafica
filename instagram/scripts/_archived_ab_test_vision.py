#!/usr/bin/env python3
"""
================================================================================
ARCHIVED: 2026-03-16
================================================================================
This file is no longer active. A/B testing is complete and we now use Kimi K2.5
exclusively. Kept for reference - contains useful model comparison code that may
be useful for future A/B testing.

To unarchive: Rename _archived_ab_test_vision.py back to ab_test_vision.py
================================================================================

A/B Test: Compare vision + caption models on photos in "To Post" album.

Single-model E2E test: Each model does BOTH vision analysis AND caption generation.

Supports multi-backend testing: OpenRouter API + Ollama Cloud.
With --cot flag: Shows chain of thought reasoning for both vision and caption.
"""

import os
import sys
import json
import base64
import sqlite3
import tempfile
import argparse
import requests
from pathlib import Path
from datetime import datetime
from dataclasses import asdict

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from photo_export import get_media_from_album, export_media_by_index, MediaType
from caption_generator import (
    analyze_photo_with_ollama,
    analyze_photo_with_ai,
    PhotoAnalysis,
    generate_caption_with_ollama,
    generate_caption_with_openrouter,
    set_ai_config,
    AIConfig,
    load_voice_rules,
    GeneratedCaption,
    VISION_PROMPT_TEMPLATE,
    select_hashtags,
    ContentType,
)

# Model configuration with backend routing
# Single-model E2E: Same model for BOTH vision + caption
# Model A: Gemini 3 Flash via OpenRouter (requires OPENROUTER_API_KEY)
# Model B: Kimi K 2.5 via Ollama Cloud

# Standardized model name constants (use these everywhere)
MODEL_GEMINI = "Gemini"
MODEL_KIMI = "Kimi"

def normalize_model_name(model_name: str) -> str:
    """Normalize model name to standard constant."""
    if not model_name:
        return model_name
    if "gemini" in model_name.lower():
        return MODEL_GEMINI
    if "kimi" in model_name.lower():
        return MODEL_KIMI
    return model_name

MODEL_A = {
    "backend": "openrouter",
    "vision_model": "google/gemini-3-flash-preview",
    "caption_model": "google/gemini-3-flash-preview",  # SAME model for E2E test
    "name": MODEL_GEMINI  # Use constant
}
MODEL_B = {
    "backend": "ollama",
    "vision_model": "kimi-k2.5:cloud",
    "caption_model": "kimi-k2.5:cloud",  # SAME model for E2E test
    "name": MODEL_KIMI  # Use constant
}
BASE_URL = "http://localhost:11434"  # Ollama localhost


def load_voice_rules() -> str:
    """Load voice rules from file."""
    voice_path = Path(__file__).parent.parent.parent / "brand" / "voice-rules.md"
    if voice_path.exists():
        return voice_path.read_text()
    return ""


def analyze_with_backend(photo_path: Path, config: dict) -> PhotoAnalysis:
    """Route to correct analysis function based on backend."""
    if config["backend"] == "openrouter":
        if not os.environ.get("OPENROUTER_API_KEY"):
            raise ValueError("OPENROUTER_API_KEY not set. Create .env file with your key.")
        # Set OpenRouter config to use this model for vision
        set_ai_config(AIConfig(
            backend="openrouter",
            openrouter_vision_model=config["vision_model"],
            openrouter_caption_model=config["caption_model"]
        ))
        return analyze_photo_with_ai(str(photo_path))
    else:
        return analyze_photo_with_ollama(
            photo_path=str(photo_path),
            model=config["vision_model"],
            base_url=BASE_URL
        )


def generate_caption_with_backend(analysis: PhotoAnalysis, config: dict) -> dict:
    """Generate caption using the same model as vision analysis.

    Returns a dict with caption components for easy comparison.
    """
    voice_rules = load_voice_rules()

    if config["backend"] == "openrouter":
        # Config already set in analyze_with_backend
        caption_text = generate_caption_with_openrouter(analysis, voice_rules)
    else:
        # Ollama - pass model explicitly
        caption_text = generate_caption_with_ollama(
            analysis,
            voice_rules=voice_rules,
            model=config["caption_model"],
            base_url=BASE_URL
        )

    # Parse into components for comparison
    lines = caption_text.strip().split("\n")
    hook = lines[0] if lines else ""

    # Find body and CTA
    body_lines = []
    cta = ""
    for line in lines[1:]:
        if "?" in line or line.strip().startswith("DM") or "comment" in line.lower():
            cta = line.strip()
            break
        if line.strip():
            body_lines.append(line.strip())

    # Generate hashtags based on analysis
    hashtags = select_hashtags(analysis)

    return {
        "hook": hook,
        "body": " ".join(body_lines),
        "cta": cta,
        "hashtags": hashtags,
        "full_caption": caption_text
    }


# =============================================================================
# CHAIN OF THOUGHT FUNCTIONS
# =============================================================================

VISION_COT_PROMPT = """Analyze this ceramic pottery photo.

FIRST, write your reasoning process step by step:
1. What shape do you see? Consider the form proportions
2. What surface qualities are visible (gloss, matte, crawling, crackle)?
3. What colors dominate?
4. Based on the surface qualities, what glaze family might this be?
5. Is this finished or in-progress?

THEN provide structured JSON with these fields:
- piece_type: (collection, bud_vase, vase, jar, bowl, mug, cup, tumbler, planter, plate, pitcher, teapot, sculpture, piece)
  * Use "collection" when multiple DIFFERENT piece types are visible (e.g., bowls + vases + jars together)
  * If all pieces are the same type, use that singular type and set piece_count
- content_type: (finished, process, kiln_reveal, studio, detail)
- glaze_type: Best guess at glaze name or description
- primary_colors: List of 2 main colors
- secondary_colors: List of 2 accent colors
- surface_qualities: List visible qualities (gloss, matte, satin, crawling, crackle, variegation, color_pooling, speckled)
- firing_state: (finished, bisque, greenware)
- technique: (wheel-thrown, hand-built, slip-cast)
- mood: (earthy, organic, rustic, modern, playful, elegant)
- form_attributes: List 3-4 shape descriptors (ovoid, bulbous, squat, cylindrical, etc)
- piece_count: Number of distinct pieces visible

Format your response as:
<reasoning>
[YOUR STEP BY STEP REASONING HERE]
</reasoning>

<json>
{JSON OBJECT HERE}
</json>
"""

CAPTION_COT_PROMPT = """You are a creative copywriter for a pottery Instagram account.

PHOTO ANALYSIS:
{analysis_summary}

BRAND VOICE:
{voice_rules}

{idea_seed_section}

=== STEP 1: GENERATE 7 CAPTION IDEAS ===
Generate 7 distinct caption ideas. Each should:
- Have a different hook angle (emotional, technical, playful, poetic, minimal, story-driven, sensory)
- Mention surface qualities naturally if listed
- End with a question
- Be under 300 characters each

IMPORTANT: If an "Idea Seed" was provided above, ONE of your 7 ideas can explore that creative association - but this is OPTIONAL. The other 6 ideas should still explore completely different angles. The seed is inspiration, not a requirement.

=== STEP 2: SELECT TOP 3 ===
From your 7 ideas, select the TOP 3 based on:
- Hook strength (does it stop the scroll?)
- Authenticity (sounds like a real potter, not marketing copy)
- Engagement potential (invites response/comment)
- Distinctness (each offers something different)

Explain why you picked each.

=== STEP 3: COMBINE INTO ONE FINAL CAPTION ===
From your top 3, create ONE combined caption that:
- Uses the strongest hook
- Weaves in the best descriptive language
- Includes the most engaging question/CTA
- Flows naturally as a single cohesive caption

Format your response as:
<reasoning>
[YOUR 7 IDEAS]
[SELECTION: Which 3 made the cut and why]
[COMBINATION: How you're blending them]
</reasoning>

<final_caption>
[THE COMBINED CAPTION - ONE COMPLETE CAPTION]
</final_caption>
"""


def analyze_with_cot_openrouter(photo_path: str, model: str) -> dict:
    """Analyze photo with chain of thought via OpenRouter."""
    from openai import OpenAI

    # Read and encode image
    with open(photo_path, "rb") as f:
        image_data = f.read()

    import mimetypes
    media_type = mimetypes.guess_type(photo_path)[0] or "image/jpeg"
    base64_image = base64.b64encode(image_data).decode("utf-8")

    client = OpenAI(
        api_key=os.environ.get("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{base64_image}"}},
                {"type": "text", "text": VISION_COT_PROMPT}
            ]
        }],
        max_tokens=1500
    )

    response_text = response.choices[0].message.content
    return parse_cot_response(response_text)


def analyze_with_cot_ollama(photo_path: str, model: str, base_url: str) -> dict:
    """Analyze photo with chain of thought via Ollama Cloud."""
    # Read and encode image
    with open(photo_path, "rb") as f:
        image_data = f.read()

    base64_image = base64.b64encode(image_data).decode("utf-8")

    # Use /api/chat for cloud models
    is_cloud = model.endswith(":cloud")
    endpoint = "/api/chat" if is_cloud else "/api/generate"

    payload = {"model": model, "stream": False}

    if is_cloud:
        payload["messages"] = [{
            "role": "user",
            "content": VISION_COT_PROMPT,
            "images": [base64_image]
        }]
    else:
        payload["prompt"] = VISION_COT_PROMPT
        payload["images"] = [base64_image]

    response = requests.post(f"{base_url}{endpoint}", json=payload, timeout=180)

    if response.status_code != 200:
        raise RuntimeError(f"Ollama error: {response.text}")

    result = response.json()
    if is_cloud:
        response_text = result.get("message", {}).get("content", "")
    else:
        response_text = result.get("response", "")

    return parse_cot_response(response_text)


def generate_caption_with_cot_openrouter(analysis, model: str, voice_rules: str, idea_seed: str = None, creative_director: str = None) -> dict:
    """Generate caption with chain of thought via OpenRouter.


Args:
        analysis: PhotoAnalysis object OR dict with analysis fields
        model: OpenRouter model name
        voice_rules: Brand voice guidelines
        idea_seed: Optional creative association - gentle inspiration (one of 7 ideas)
        creative_director: Optional strong direction - shapes ALL outputs around a theme/series

    """
    from openai import OpenAI

    # Build creative direction section (stronger than idea seed)
    if creative_director:
        idea_seed_section = f"""🎬 CREATIVE DIRECTOR MODE - ACTIVE
The potter has set a specific creative direction for this piece:

"{creative_director}"

ALL 7 of your caption ideas should align with this theme/concept while still varying in tone (emotional, technical, playful, etc.).
This is NOT optional - the potter wants outputs that serve this vision.
"""
    elif idea_seed:
        idea_seed_section = f"""IDEA SEED (optional inspiration):
The potter noted: "{idea_seed}"
One of your 7 ideas MAY explore this creative angle, but don't force it. The other 6 should be completely different approaches.
"""
    else:
        idea_seed_section = ""

    # Support both PhotoAnalysis and dict
    if hasattr(analysis, 'piece_type'):
        piece_type = analysis.piece_type
        glaze_type = analysis.glaze_type
        primary_colors = analysis.primary_colors
        surface_qualities = getattr(analysis, 'surface_qualities', [])
        technique = analysis.technique
        mood = analysis.mood
        firing_state = analysis.firing_state
    else:
        piece_type = analysis.get("piece_type", "piece")
        glaze_type = analysis.get("glaze_type")
        primary_colors = analysis.get("primary_colors", [])
        surface_qualities = analysis.get("surface_qualities", [])
        technique = analysis.get("technique", "wheel-thrown")
        mood = analysis.get("mood", "earthy")
        firing_state = analysis.get("firing_state", "finished")

    client = OpenAI(
        api_key=os.environ.get("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1"
    )

    # Build analysis summary
    analysis_summary = f"""- Type: {piece_type}
- Glaze: {glaze_type}
- Colors: {', '.join(primary_colors)}
- Surface: {', '.join(surface_qualities)}
- Technique: {technique}
- Mood: {mood}
- Firing: {firing_state}"""

    prompt = CAPTION_COT_PROMPT.format(
        analysis_summary=analysis_summary,
        voice_rules=voice_rules[:500] if voice_rules else "Warm, authentic pottery artist voice",
        idea_seed_section=idea_seed_section
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2500  # Need enough for 7 ideas + selection + final caption
    )

    response_text = response.choices[0].message.content
    return parse_cot_caption_response(response_text)


def generate_caption_with_cot_ollama(analysis, model: str, base_url: str, voice_rules: str, idea_seed: str = None, creative_director: str = None) -> dict:
    """Generate caption with chain of thought via Ollama.

    Args:
        analysis: PhotoAnalysis object OR dict with analysis fields
        model: Ollama model name
        base_url: Ollama server URL
        voice_rules: Brand voice guidelines
        idea_seed: Optional creative association - gentle inspiration (one of 7 ideas)
        creative_director: Optional strong direction - shapes ALL outputs around a theme/series
    """
    # Build creative direction section (stronger than idea seed)
    if creative_director:
        idea_seed_section = f"""🎬 CREATIVE DIRECTOR MODE - ACTIVE
The potter has set a specific creative direction for this piece:

"{creative_director}"

ALL 7 of your caption ideas should align with this theme/concept while still varying in tone (emotional, technical, playful, etc.).
This is NOT optional - the potter wants outputs that serve this vision.
"""
    elif idea_seed:
        idea_seed_section = f"""IDEA SEED (optional inspiration):
The potter noted: "{idea_seed}"
One of your 7 ideas MAY explore this creative angle, but don't force it. The other 6 should be completely different approaches.
"""
    else:
        idea_seed_section = ""

    # Support both PhotoAnalysis and dict
    if hasattr(analysis, 'piece_type'):
        piece_type = analysis.piece_type
        glaze_type = analysis.glaze_type
        primary_colors = analysis.primary_colors
        surface_qualities = getattr(analysis, 'surface_qualities', [])
        technique = analysis.technique
        mood = analysis.mood
        firing_state = analysis.firing_state
    else:
        piece_type = analysis.get("piece_type", "piece")
        glaze_type = analysis.get("glaze_type")
        primary_colors = analysis.get("primary_colors", [])
        surface_qualities = analysis.get("surface_qualities", [])
        technique = analysis.get("technique", "wheel-thrown")
        mood = analysis.get("mood", "earthy")
        firing_state = analysis.get("firing_state", "finished")

    # Build analysis summary
    analysis_summary = f"""- Type: {piece_type}
- Glaze: {glaze_type}
- Colors: {', '.join(primary_colors)}
- Surface: {', '.join(surface_qualities)}
- Technique: {technique}
- Mood: {mood}
- Firing: {firing_state}"""

    prompt = CAPTION_COT_PROMPT.format(
        analysis_summary=analysis_summary,
        voice_rules=voice_rules[:500] if voice_rules else "Warm, authentic pottery artist voice",
        idea_seed_section=idea_seed_section
    )

    is_cloud = model.endswith(":cloud")
    endpoint = "/api/chat" if is_cloud else "/api/generate"

    payload = {"model": model, "stream": False}

    if is_cloud:
        payload["messages"] = [{"role": "user", "content": prompt}]
    else:
        payload["prompt"] = prompt

    response = requests.post(f"{base_url}{endpoint}", json=payload, timeout=120)

    if response.status_code != 200:
        raise RuntimeError(f"Ollama error: {response.text}")

    result = response.json()
    if is_cloud:
        response_text = result.get("message", {}).get("content", "")
    else:
        response_text = result.get("response", "")

    return parse_cot_caption_response(response_text)


def parse_cot_response(response_text: str) -> dict:
    """Parse chain of thought response into reasoning and JSON."""
    reasoning = ""
    json_data = {}

    # Extract reasoning
    if "<reasoning>" in response_text and "</reasoning>" in response_text:
        start = response_text.find("<reasoning>") + len("<reasoning>")
        end = response_text.find("</reasoning>")
        reasoning = response_text[start:end].strip()

    # Extract JSON
    if "<json>" in response_text and "</json>" in response_text:
        start = response_text.find("<json>") + len("<json>")
        end = response_text.find("</json>")
        json_str = response_text[start:end].strip()
        try:
            json_data = json.loads(json_str)
        except json.JSONDecodeError:
            # Try to find JSON in the response anyway
            import re
            json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    json_data = json.loads(json_match.group())
                except:
                    pass
    else:
        # Try to find JSON directly
        import re
        json_match = re.search(r'\{[^{}]*\}', response_text, re.DOTALL)
        if json_match:
            try:
                json_data = json.loads(json_match.group())
            except:
                pass

    return {"reasoning": reasoning, "analysis": json_data}


def parse_cot_caption_response(response_text: str) -> dict:
    """Parse caption chain of thought response with ONE combined caption."""
    reasoning = ""
    final_caption = ""

    # Extract reasoning
    if "<reasoning>" in response_text and "</reasoning>" in response_text:
        start = response_text.find("<reasoning>") + len("<reasoning>")
        end = response_text.find("</reasoning>")
        reasoning = response_text[start:end].strip()

    # Extract the final combined caption
    if "<final_caption>" in response_text and "</final_caption>" in response_text:
        start = response_text.find("<final_caption>") + len("<final_caption>")
        end = response_text.find("</final_caption>")
        final_caption = response_text[start:end].strip()

    # Fallback if no caption found - look for actual caption content
    if not final_caption:
        lines = response_text.strip().split("\n")
        caption_lines = []
        in_caption = False

        for line in lines:
            stripped = line.strip()
            # Skip section headers and numbered brainstorm items
            if not stripped:
                if in_caption:
                    break  # End of caption block
                continue
            if stripped.startswith("###") or stripped.startswith("==="):
                if in_caption:
                    break  # End of caption block
                continue
            if stripped.startswith("STEP ") or "BRAINSTORM" in stripped.upper():
                if in_caption:
                    break
                continue
            # Skip numbered list items from brainstorm (e.g., "1. **Emotional")
            if stripped[0].isdigit() and ". " in stripped[:5]:
                if in_caption:
                    break
                continue
            # Skip lines that look like markdown formatting headers
            if stripped.startswith("**") and stripped.endswith("**"):
                if in_caption:
                    break
                continue
            # Found actual caption content
            if len(stripped) > 20:
                in_caption = True
                caption_lines.append(stripped)

        if caption_lines:
            final_caption = "\n".join(caption_lines[:3])  # Max 3 lines for fallback

    # Parse caption into components
    lines = final_caption.split("\n") if final_caption else []
    hook = lines[0] if lines else ""

    body_lines = []
    cta = ""
    for line in lines[1:]:
        if "?" in line or line.strip().startswith("DM") or "comment" in line.lower():
            cta = line.strip()
            break
        if line.strip():
            body_lines.append(line.strip())

    return {
        "reasoning": reasoning,
        "hook": hook,
        "body": " ".join(body_lines),
        "cta": cta,
        "full_caption": final_caption
    }


def sync_to_dashboard(output_dir: Path):
    """Compile all test results into dashboard's test_data.json."""
    from collections import defaultdict

    all_results = []
    photo_models = defaultdict(dict)  # photo -> {model_name: result_data}

    # Process all ab_test_results files
    for f in sorted(output_dir.glob("ab_test_results_*.json")):
        try:
            with open(f) as fp:
                data = json.load(fp)

            # Get model names and normalize them
            model_a_name = normalize_model_name(data.get("model_a", {}).get("name", MODEL_GEMINI))
            model_b_name = normalize_model_name(data.get("model_b", {}).get("name", MODEL_KIMI))

            # Process model_a_results
            photos_dir = output_dir / "ab_test_photos"
            for r in data.get("model_a_results", []):
                photo = r.get("filename", "")
                if photo:
                    # Validate photo exists
                    photo_path = photos_dir / photo
                    if not photo_path.exists():
                        # Try common extensions
                        base = photo.rsplit('.', 1)[0] if '.' in photo else photo
                        found = False
                        for ext in ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']:
                            if (photos_dir / (base + ext)).exists():
                                photo = base + ext
                                found = True
                                break
                        if not found:
                            print(f"  ⚠️ Photo not found, skipping: {photo}")
                            continue
                    result = {
                        "photo": photo,
                        "model": model_a_name,
                        "vision": r.get("analysis", {}),
                        "caption": r.get("caption", {}),
                        "vision_reasoning": r.get("vision_reasoning", ""),
                        "caption_reasoning": r.get("caption_reasoning", "")
                    }
                    photo_models[photo][model_a_name] = result

            # Process model_b_results
            for r in data.get("model_b_results", []):
                photo = r.get("filename", "")
                if photo:
                    # Validate photo exists
                    photo_path = photos_dir / photo
                    if not photo_path.exists():
                        # Try common extensions
                        base = photo.rsplit('.', 1)[0] if '.' in photo else photo
                        found = False
                        for ext in ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']:
                            if (photos_dir / (base + ext)).exists():
                                photo = base + ext
                                found = True
                                break
                        if not found:
                            print(f"  ⚠️ Photo not found, skipping: {photo}")
                            continue
                    result = {
                        "photo": photo,
                        "model": model_b_name,
                        "vision": r.get("analysis", {}),
                        "caption": r.get("caption", {}),
                        "vision_reasoning": r.get("vision_reasoning", ""),
                        "caption_reasoning": r.get("caption_reasoning", "")
                    }
                    photo_models[photo][model_b_name] = result

        except Exception as e:
            print(f"  Warning: Could not parse {f.name}: {e}")

    # Build flat results list (keep most recent per photo+model)
    for photo, models in sorted(photo_models.items()):
        for model, r in models.items():
            all_results.append(r)

    # Save to dashboard
    dashboard_dir = output_dir.parent / "human-door"
    dashboard_dir.mkdir(exist_ok=True)
    test_data_path = dashboard_dir / "test_data.json"

    test_data = {
        "total_tests": len(all_results),
        "results": all_results
    }

    with open(test_data_path, "w") as f:
        json.dump(test_data, f, indent=2)

    # Also populate caption_results table in database
    db_path = dashboard_dir / "feedback.db"
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            c = conn.cursor()
            # Create table if not exists
            c.execute('''
                CREATE TABLE IF NOT EXISTS caption_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    photo TEXT NOT NULL,
                    model TEXT NOT NULL,
                    hook TEXT,
                    body TEXT,
                    cta TEXT,
                    hashtags TEXT,
                    vision_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(photo, model)
                )
            ''')
            # Insert/update results
            for r in all_results:
                caption = r.get("caption", {})
                c.execute('''
                    INSERT OR REPLACE INTO caption_results
                    (photo, model, hook, body, cta, hashtags, vision_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    r.get("photo"),
                    r.get("model"),
                    caption.get("hook", ""),
                    caption.get("body", ""),
                    caption.get("cta", ""),
                    caption.get("hashtags", ""),
                    json.dumps(r.get("vision", {}))
                ))
            conn.commit()
            conn.close()
            print(f"📊 Populated caption_results table with {len(all_results)} entries")
        except Exception as e:
            print(f"  Warning: Could not populate database: {e}")

    print(f"🔄 Synced {len(all_results)} results to Human Door dashboard")


def run_ab_test(single_mode: bool = False, target_photo: str = None, cot_mode: bool = False):
    """Run A/B test on all photos in "To Post" album.

    Args:
        single_mode: If True, test only 1 photo per model for quick validation
        target_photo: Specific photo filename to test (e.g., "IMG_4908.JPG")
        cot_mode: If True, use chain of thought prompts and capture reasoning
    """
    # Check OpenRouter API key before starting
    if MODEL_A["backend"] == "openrouter" and not os.environ.get("OPENROUTER_API_KEY"):
        print("\n❌ OPENROUTER_API_KEY not set!")
        print("   Create .env file: cp .env.example .env")
        print("   Then add your API key from https://openrouter.ai/keys\n")
        return

    media = get_media_from_album("To Post")
    photos = [(i, m) for i, m in enumerate(media) if m.media_type == MediaType.PHOTO]

    if not photos:
        print("No photos found in 'To Post' album.")
        return

    total = len(photos)

    # Find target photo if specified
    if target_photo:
        # Normalize target (add .JPG if no extension)
        if "." not in target_photo:
            target_photo = f"{target_photo}.JPG"
        target_photos = [(i, m) for i, m in photos if m.filename == target_photo or m.filename == target_photo.upper()]
        if not target_photos:
            print(f"❌ Photo '{target_photo}' not found in 'To Post' album.")
            print(f"   Available photos: {[m.name for i, m in photos[:5]]}...")
            return
        test_photos_a = target_photos
        test_photos_b = target_photos
        mode_str = f"Testing specific photo: {target_photo}"
    elif single_mode:
        # Quick test: same photo for both models
        test_photos_a = photos[:1]
        test_photos_b = photos[:1]  # Same photo
        mode_str = "Testing 1 photo per model (--single mode)"
    else:
        # Full split test
        split_point = total // 2
        test_photos_a = photos[:split_point]
        test_photos_b = photos[split_point:]
        mode_str = f"Model A: {split_point} photos, Model B: {total - split_point} photos"

    print(f"\n{'='*60}")
    print("A/B Vision + Caption Test")
    print(f"{'='*60}")
    print(f"Total photos: {total}")
    print(mode_str)
    print(f"{'='*60}\n")

    results = {
        "test_date": datetime.now().isoformat(),
        "test_mode": "target" if target_photo else ("single" if single_mode else "split"),
        "target_photo": target_photo,
        "model_a": MODEL_A,
        "model_b": MODEL_B,
        "model_a_results": [],
        "model_b_results": [],
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        voice_rules = load_voice_rules() if cot_mode else None

        # Test Model A
        print(f"\n🔵 Testing {MODEL_A['name']}...")
        for i, (idx, _) in enumerate(test_photos_a):
            exported = export_media_by_index("To Post", idx, str(tmpdir))
            if exported:
                print(f"  [{i+1}/{len(test_photos_a)}] {Path(exported).name}")
                try:
                    if cot_mode:
                        # Chain of thought mode - use dict directly
                        cot_result = analyze_with_cot_openrouter(str(exported), MODEL_A["vision_model"])
                        vision_reasoning = cot_result.get("reasoning", "")
                        analysis_dict = cot_result.get("analysis", {})

                        piece_type = analysis_dict.get("piece_type", "?")
                        glaze_type = analysis_dict.get("glaze_type", "?")
                        print(f"    ✅ Vision: {piece_type} / {glaze_type}")

                        caption_result = generate_caption_with_cot_openrouter(
                            analysis_dict, MODEL_A["caption_model"], voice_rules
                        )
                        caption_reasoning = caption_result.get("reasoning", "")
                        caption = {k: v for k, v in caption_result.items() if k != "reasoning"}

                        # Add hashtags from analysis dict
                        if "hashtags" not in caption or not caption.get("hashtags"):
                            # Create a simple object with needed attributes
                            class SimpleAnalysis:
                                pass
                            simple_analysis = SimpleAnalysis()
                            simple_analysis.glaze_type = analysis_dict.get("glaze_type")
                            simple_analysis.technique = analysis_dict.get("technique")
                            simple_analysis.piece_type = analysis_dict.get("piece_type")
                            simple_analysis.content_type = ContentType.FINISHED_PIECE
                            caption["hashtags"] = select_hashtags(simple_analysis)

                        print(f"    ✅ Caption: \"{caption.get('hook', '')[:50]}...\"")

                        results["model_a_results"].append({
                            "filename": Path(exported).name,
                            "vision_reasoning": vision_reasoning,
                            "analysis": analysis_dict,
                            "caption_reasoning": caption_reasoning,
                            "caption": caption,
                        })
                    else:
                        # Standard mode
                        analysis = analyze_with_backend(Path(exported), MODEL_A)
                        print(f"    ✅ Vision: {analysis.piece_type} / {analysis.glaze_type}")

                        caption = generate_caption_with_backend(analysis, MODEL_A)
                        print(f"    ✅ Caption: \"{caption['hook'][:50]}...\"")

                        results["model_a_results"].append({
                            "filename": Path(exported).name,
                            "analysis": asdict(analysis),
                            "caption": caption,
                        })
                except Exception as e:
                    print(f"    ❌ Error: {e}")
                    results["model_a_results"].append({
                        "filename": Path(exported).name,
                        "error": str(e),
                    })

        # Test Model B
        print(f"\n🟢 Testing {MODEL_B['name']}...")
        for i, (idx, _) in enumerate(test_photos_b):
            exported = export_media_by_index("To Post", idx, str(tmpdir))
            if exported:
                print(f"  [{i+1}/{len(test_photos_b)}] {Path(exported).name}")
                try:
                    if cot_mode:
                        # Chain of thought mode - use dict directly
                        cot_result = analyze_with_cot_ollama(str(exported), MODEL_B["vision_model"], BASE_URL)
                        vision_reasoning = cot_result.get("reasoning", "")
                        analysis_dict = cot_result.get("analysis", {})

                        piece_type = analysis_dict.get("piece_type", "?")
                        glaze_type = analysis_dict.get("glaze_type", "?")
                        print(f"    ✅ Vision: {piece_type} / {glaze_type}")

                        caption_result = generate_caption_with_cot_ollama(
                            analysis_dict, MODEL_B["caption_model"], BASE_URL, voice_rules
                        )
                        caption_reasoning = caption_result.get("reasoning", "")
                        caption = {k: v for k, v in caption_result.items() if k != "reasoning"}

                        # Add hashtags from analysis dict
                        if "hashtags" not in caption or not caption.get("hashtags"):
                            # Create a simple object with needed attributes
                            class SimpleAnalysis:
                                pass
                            simple_analysis = SimpleAnalysis()
                            simple_analysis.glaze_type = analysis_dict.get("glaze_type")
                            simple_analysis.technique = analysis_dict.get("technique")
                            simple_analysis.piece_type = analysis_dict.get("piece_type")
                            simple_analysis.content_type = ContentType.FINISHED_PIECE
                            caption["hashtags"] = select_hashtags(simple_analysis)

                        print(f"    ✅ Caption: \"{caption.get('hook', '')[:50]}...\"")

                        results["model_b_results"].append({
                            "filename": Path(exported).name,
                            "vision_reasoning": vision_reasoning,
                            "analysis": analysis_dict,
                            "caption_reasoning": caption_reasoning,
                            "caption": caption,
                        })
                    else:
                        # Standard mode
                        analysis = analyze_with_backend(Path(exported), MODEL_B)
                        print(f"    ✅ Vision: {analysis.piece_type} / {analysis.glaze_type}")

                        caption = generate_caption_with_backend(analysis, MODEL_B)
                        print(f"    ✅ Caption: \"{caption['hook'][:50]}...\"")

                        results["model_b_results"].append({
                            "filename": Path(exported).name,
                            "analysis": asdict(analysis),
                            "caption": caption,
                        })
                except Exception as e:
                    print(f"    ❌ Error: {e}")
                    results["model_b_results"].append({
                        "filename": Path(exported).name,
                        "error": str(e),
                    })

    # Save results
    output_dir = Path(__file__).parent.parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    results_path = output_dir / f"ab_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n✅ Results saved to: {results_path}")

    # Sync to Human Door dashboard
    sync_to_dashboard(output_dir)

    # Print summary comparison
    print_comparison(results)

    return results_path


def print_comparison(results: dict):
    """Print a side-by-side comparison summary with captions and chain of thought."""
    has_cot = any("vision_reasoning" in r for r in results.get("model_a_results", []))

    print(f"\n{'='*70}")
    print("SUMMARY COMPARISON")
    print(f"{'='*70}\n")

    a_results = results["model_a_results"]
    b_results = results["model_b_results"]

    model_a_name = results['model_a']['name']
    model_b_name = results['model_b']['name']

    # If single or target mode, show detailed comparison of same photo
    is_detailed_mode = results.get("test_mode") in ["single", "target"] and a_results and b_results
    if is_detailed_mode:
        print("📸 SAME PHOTO - DIFFERENT MODELS\n")
        a = a_results[0]
        b = b_results[0]

        print(f"File: {a.get('filename', '?')}")
        print("=" * 70)

        # Chain of Thought - Vision (if available)
        if has_cot and "vision_reasoning" in a:
            print(f"\n{'🧠 VISION CHAIN OF THOUGHT':^70}")
            print("=" * 70)

            print(f"\n🔵 {model_a_name} Vision Reasoning:")
            print("-" * 70)
            print(a.get("vision_reasoning", "No reasoning captured"))

            print(f"\n🟢 {model_b_name} Vision Reasoning:")
            print("-" * 70)
            print(b.get("vision_reasoning", "No reasoning captured"))

        # Vision comparison
        print(f"\n{'VISION ANALYSIS RESULTS':^70}")
        print("=" * 70)
        print(f"{'Model A':<35} | {'Model B':<35}")
        print("-" * 70)

        a_piece = a.get("analysis", {}).get("piece_type", "?") if "analysis" in a else "ERROR"
        a_glaze = a.get("analysis", {}).get("glaze_type", "?") if "analysis" in a else "-"
        b_piece = b.get("analysis", {}).get("piece_type", "?") if "analysis" in b else "ERROR"
        b_glaze = b.get("analysis", {}).get("glaze_type", "?") if "analysis" in b else "-"

        print(f"{a_piece} / {(a_glaze or '-'):<28} | {b_piece} / {(b_glaze or '-')}")

        # Additional vision details
        a_colors = a.get("analysis", {}).get("primary_colors", []) if "analysis" in a else []
        b_colors = b.get("analysis", {}).get("primary_colors", []) if "analysis" in b else []
        a_surface = a.get("analysis", {}).get("surface_qualities", []) if "analysis" in a else []
        b_surface = b.get("analysis", {}).get("surface_qualities", []) if "analysis" in b else []

        print(f"Colors: {', '.join(a_colors):<26} | Colors: {', '.join(b_colors)}")
        print(f"Surface: {', '.join(a_surface):<25} | Surface: {', '.join(b_surface)}")

        # Chain of Thought - Caption (if available)
        if has_cot and "caption_reasoning" in a:
            print(f"\n{'🧠 CAPTION CHAIN OF THOUGHT':^70}")
            print("=" * 70)

            print(f"\n🔵 {model_a_name} Caption Reasoning:")
            print("-" * 70)
            print(a.get("caption_reasoning", "No reasoning captured"))

            print(f"\n🟢 {model_b_name} Caption Reasoning:")
            print("-" * 70)
            print(b.get("caption_reasoning", "No reasoning captured"))

        # Caption comparison
        print(f"\n{'CAPTION RESULTS':^70}")
        print("=" * 70)

        a_hook = a.get("caption", {}).get("hook", "?") if "caption" in a else "ERROR"
        b_hook = b.get("caption", {}).get("hook", "?") if "caption" in b else "ERROR"

        print(f"\n🔵 {model_a_name} Hook:")
        print(f'"{a_hook}"')
        print(f"\n🟢 {model_b_name} Hook:")
        print(f'"{b_hook}"')

        print(f"\n{'FULL CAPTIONS':^70}")
        print("=" * 70)

        a_caption = a.get("caption", {}).get("full_caption", "?") if "caption" in a else "ERROR"
        b_caption = b.get("caption", {}).get("full_caption", "?") if "caption" in b else "ERROR"

        print(f"\n🔵 {model_a_name}:")
        print("-" * 70)
        print(a_caption)
        print(f"\n🟢 {model_b_name}:")
        print("-" * 70)
        print(b_caption)
    else:
        # Full split test - show summary table
        print(f"{'Filename':<30} | {'Model A':<25} | {'Model B':<25}")
        print("-" * 80)

        max_len = max(len(a_results), len(b_results))
        for i in range(max_len):
            a_item = a_results[i] if i < len(a_results) else {}
            b_item = b_results[i] if i < len(b_results) else {}

            a_name = a_item.get("filename", "")
            b_name = b_item.get("filename", "")

            a_piece = a_item.get("analysis", {}).get("piece_type", "?") if "analysis" in a_item else "ERROR"
            a_glaze = a_item.get("analysis", {}).get("glaze_type", "?") if "analysis" in a_item else "-"

            b_piece = b_item.get("analysis", {}).get("piece_type", "?") if "analysis" in b_item else "ERROR"
            b_glaze = b_item.get("analysis", {}).get("glaze_type", "?") if "analysis" in b_item else "-"

            print(f"{a_name:<30} | {a_piece} / {(a_glaze or '-'):<20} |")

            if b_name and b_name != a_name:
                print(f"{b_name:<30} | | {b_piece} / {(b_glaze or '-'):<20}")

    print(f"\n{'='*70}\n")

    # Stats
    a_success = sum(1 for r in a_results if "analysis" in r)
    b_success = sum(1 for r in b_results if "analysis" in r)

    print(f"Model A ({model_a_name}): {a_success}/{len(a_results)} successful")
    print(f"Model B ({model_b_name}): {b_success}/{len(b_results)} successful\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A/B test vision + caption models")
    parser.add_argument("--single", action="store_true", help="Test only 1 photo per model (quick validation)")
    parser.add_argument("--photo", type=str, help="Test a specific photo by filename (e.g., IMG_4908.JPG)")
    parser.add_argument("--cot", action="store_true", help="Enable chain of thought mode (shows reasoning)")
    args = parser.parse_args()

    run_ab_test(single_mode=args.single, target_photo=args.photo, cot_mode=args.cot)
