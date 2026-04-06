#!/usr/bin/env python3
"""
Weekly Orchestrator - Cerafica Instagram and Website Pipeline
=============================================================
Master automation script for weekly content generation.

Usage:
    python weekly-orchestrator.py              # Run weekly pipeline (3 posts)
    python weekly-orchestrator.py --count 5   # Generate 5 posts
    python weekly-orchestrator.py --dry-run   # Preview without writing
    python weekly-orchestrator.py --status    # Show current queue state
"""

# =============================================================================
# STDLIB IMPORTS
# =============================================================================
import argparse
import json
import logging
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

# =============================================================================
# PATH SETUP — add lib/ directory for local imports (must precede local imports)
# =============================================================================
SCRIPTS_DIR = Path(__file__).parent
REPO_ROOT = SCRIPTS_DIR.parent.parent
sys.path.insert(0, str(SCRIPTS_DIR / "lib"))
sys.path.insert(0, str(SCRIPTS_DIR))

# noqa: E402 — path manipulation required before local imports
from caption_generator import analyze_photo, analyze_video, generate_caption  # noqa: E402
from instagram_scheduler import get_posting_schedule  # noqa: E402

# =============================================================================
# PATHS
# =============================================================================
INBOX_DIR        = REPO_ROOT / "instagram" / "queue" / "inbox"
FRAMED_DIR       = REPO_ROOT / "output" / "framed"
INVENTORY_DIR    = REPO_ROOT / "inventory" / "available"
ARCHIVE_PATH     = REPO_ROOT / "instagram" / "data" / "archive" / "cerafica_archive.json"
PROCESSED_PATH   = REPO_ROOT / "instagram" / "data" / "processed.json"
PRODUCTS_PATH    = REPO_ROOT / "inventory" / "products.json"
PRICING_PATH     = REPO_ROOT / "inventory" / "pricing.json"
READY_DIR        = REPO_ROOT / "instagram" / "queue" / "READY"
THIS_WEEK_PATH   = REPO_ROOT / "THIS_WEEK.md"
WEBSITE_IMG_DIR  = REPO_ROOT / "website" / "images" / "products"
LOGS_DIR         = REPO_ROOT / "instagram" / "logs"
LOG_PATH         = LOGS_DIR / "orchestrator.log"

OLLAMA_BASE_URL  = "http://localhost:11434"
OLLAMA_VISION_MODEL = "kimi-k2.5:cloud"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm"}
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS

# Days old threshold: archive posts must be older than this to be re-used
ARCHIVE_MIN_AGE_DAYS = 90

# =============================================================================
# 1. LOGGING
# =============================================================================

_logger: Optional[logging.Logger] = None

def _get_logger() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("weekly-orchestrator")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s  %(levelname)-7s  %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")
    # stdout handler
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    # file handler
    try:
        fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception as e:
        print(f"[WARN] Could not open log file {LOG_PATH}: {e}")
    _logger = logger
    return logger


def log(msg: str, level: str = "info") -> None:
    """Timestamped logging to stdout + instagram/logs/orchestrator.log."""
    logger = _get_logger()
    level = level.lower()
    if level == "debug":
        logger.debug(msg)
    elif level == "warning" or level == "warn":
        logger.warning(msg)
    elif level == "error":
        logger.error(msg)
    elif level == "critical":
        logger.critical(msg)
    else:
        logger.info(msg)


# =============================================================================
# 2. PROCESSED TRACKING
# =============================================================================

def load_processed() -> set:
    """Load set of already-processed filenames from instagram/data/processed.json."""
    if not PROCESSED_PATH.exists():
        return set()
    try:
        with open(PROCESSED_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(data)
        if isinstance(data, dict) and "processed" in data:
            return set(data["processed"])
        return set()
    except Exception as e:
        log(f"Could not load processed.json: {e}", "warning")
        return set()


def save_processed(processed: set) -> None:
    """Write set of processed filenames to instagram/data/processed.json."""
    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(PROCESSED_PATH, "w", encoding="utf-8") as f:
            json.dump(sorted(processed), f, indent=2)
    except Exception as e:
        log(f"Could not save processed.json: {e}", "error")


# =============================================================================
# 3. PRICING
# =============================================================================

def load_pricing() -> dict:
    """Load inventory/pricing.json."""
    try:
        with open(PRICING_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"Could not load pricing.json: {e}", "warning")
        return {
            "size_categories": {
                "tiny":   {"price": 25},
                "small":  {"price": 45},
                "medium": {"price": 85},
                "large":  {"price": 145},
                "xlarge": {"price": 225},
            },
            "default_category": "medium",
        }


# =============================================================================
# 4-6. MEDIA SCANNERS
# =============================================================================

def scan_inbox() -> list:
    """Scan instagram/queue/inbox/ for image/video files not in processed set."""
    processed = load_processed()
    results = []
    if not INBOX_DIR.exists():
        log(f"Inbox directory does not exist: {INBOX_DIR}", "warning")
        return results
    for f in sorted(INBOX_DIR.iterdir()):
        if f.is_file() and f.suffix.lower() in MEDIA_EXTS and f.name not in processed:
            results.append(f)
    log(f"scan_inbox: found {len(results)} unprocessed files")
    return results


def scan_framed() -> list:
    """Scan output/framed/ recursively for mp4/jpg/png not in processed set."""
    processed = load_processed()
    results = []
    if not FRAMED_DIR.exists():
        log(f"Framed directory does not exist: {FRAMED_DIR}", "warning")
        return results
    for f in sorted(FRAMED_DIR.rglob("*")):
        if f.is_file() and f.suffix.lower() in MEDIA_EXTS and f.name not in processed:
            results.append(f)
    log(f"scan_framed: found {len(results)} unprocessed files")
    return results


def scan_inventory_available() -> list:
    """Scan inventory/available/ for jpg/png not in processed set."""
    processed = load_processed()
    results = []
    if not INVENTORY_DIR.exists():
        log(f"Inventory available directory does not exist: {INVENTORY_DIR}", "warning")
        return results
    for f in sorted(INVENTORY_DIR.iterdir()):
        if f.is_file() and f.suffix.lower() in IMAGE_EXTS and f.name not in processed:
            results.append(f)
    log(f"scan_inventory_available: found {len(results)} unprocessed files")
    return results


# =============================================================================
# 7. TOP PERFORMERS FROM ARCHIVE
# =============================================================================

def get_top_performers(limit: int = 5) -> list:
    """
    Load archive, filter posts >90 days old, sort by likes+comments,
    return top N not recently reposted.
    """
    if not ARCHIVE_PATH.exists():
        log(f"Archive not found: {ARCHIVE_PATH}", "warning")
        return []

    try:
        with open(ARCHIVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        log(f"Could not load archive: {e}", "error")
        return []

    posts = data.get("posts", [])
    cutoff = datetime.now() - timedelta(days=ARCHIVE_MIN_AGE_DAYS)
    processed = load_processed()

    eligible = []
    for post in posts:
        raw_date = post.get("date", "")
        try:
            if "T" in raw_date:
                post_date = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                post_date = post_date.replace(tzinfo=None)
            else:
                post_date = datetime.strptime(raw_date[:10], "%Y-%m-%d")
        except Exception:
            continue

        if post_date > cutoff:
            continue  # Too recent

        shortcode = post.get("shortcode", "")
        if shortcode in processed:
            continue  # Already re-used

        score = int(post.get("likes", 0)) + int(post.get("comments", 0))
        eligible.append({**post, "_score": score})

    eligible.sort(key=lambda p: p["_score"], reverse=True)
    top = eligible[:limit]
    log(f"get_top_performers: {len(top)} top performers from {len(eligible)} eligible")
    return top


# =============================================================================
# 8. FILL SLOTS
# =============================================================================

def fill_slots(count: int = 3) -> list:
    """
    Fill up to `count` content slots using priority chain:
    inbox -> framed -> inventory -> top_performers.

    Returns list of dicts with keys:
        path       (Path or None)
        source     (str)
        repost_data (dict or None)
    """
    slots = []

    def _add_from_paths(paths: list, source: str) -> None:
        for p in paths:
            if len(slots) >= count:
                return
            slots.append({"path": p, "source": source, "repost_data": None})

    _add_from_paths(scan_inbox(), "inbox")
    if len(slots) < count:
        _add_from_paths(scan_framed(), "framed")
    if len(slots) < count:
        _add_from_paths(scan_inventory_available(), "inventory")
    if len(slots) < count:
        performers = get_top_performers(limit=count - len(slots))
        for perf in performers:
            if len(slots) >= count:
                break
            slots.append({
                "path": None,
                "source": "archive_repost",
                "repost_data": perf,
            })

    log(f"fill_slots: filled {len(slots)}/{count} slots")
    return slots


# =============================================================================
# 9. ESTIMATE SIZE CATEGORY (AI VISION)
# =============================================================================

def estimate_size_category(photo_path: str) -> str:
    """
    Call Ollama vision model to estimate ceramic piece size category.
    Returns: tiny | small | medium | large | xlarge
    Falls back to 'medium' on any error.
    """
    import base64
    try:
        with open(photo_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        prompt = (
            "This is a handmade ceramic piece. Estimate its size: "
            "tiny (under 3 inches), small (3-4 inches fits in palm), "
            "medium (4-6 inches, mug/bowl), large (6-9 inches serving bowl/vase), "
            "or xlarge (10+ inches statement piece). "
            "Reply with just one word: tiny, small, medium, large, or xlarge."
        )

        payload = {
            "model": OLLAMA_VISION_MODEL,
            "prompt": prompt,
            "images": [image_data],
            "stream": False,
        }

        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json().get("response", "").strip().lower()

        # Extract the first matching size word
        for word in ["tiny", "small", "medium", "large", "xlarge"]:
            if word in result:
                return word

        log(f"estimate_size_category: unexpected response '{result}', using medium", "warning")
        return "medium"

    except Exception as e:
        log(f"estimate_size_category failed: {e}, falling back to medium", "warning")
        return "medium"


# =============================================================================
# 10. GENERATE PRODUCT NAME
# =============================================================================

def generate_product_name(analysis) -> str:
    """
    Derive a 2-4 word product name from PhotoAnalysis.
    e.g. "Speckled Stoneware Bowl"
    """
    piece_type = ""
    colors = []

    if hasattr(analysis, "piece_type"):
        piece_type = (analysis.piece_type or "").strip().title()
    if hasattr(analysis, "primary_colors"):
        colors = [c.strip().title() for c in (analysis.primary_colors or [])[:2]]

    parts = colors[:1] + ([piece_type] if piece_type else ["Ceramic Piece"])
    name = " ".join(parts)

    # Capitalise each word, strip extra spaces
    name = " ".join(w for w in name.split() if w)
    return name if name else "Handmade Ceramic Piece"


# =============================================================================
# 11. CREATE WEBSITE LISTING
# =============================================================================

def create_website_listing(slot: dict, caption_obj, size_cat: str, price: float,
                            product_name: str) -> dict:
    """
    Build a product dict matching products.json schema.
    Copy photo to website/images/products/[slug].jpg.
    Append to inventory/products.json.
    Return the product dict.
    """
    # Build slug from product name
    slug = re.sub(r"[^a-z0-9]+", "-", product_name.lower()).strip("-")
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slug = f"{slug}-{timestamp}"

    # Copy image
    dest_image = None
    if slot.get("path") and slot["path"].exists():
        WEBSITE_IMG_DIR.mkdir(parents=True, exist_ok=True)
        dest_ext = slot["path"].suffix.lower()
        if dest_ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            dest_ext = ".jpg"
        dest_image = WEBSITE_IMG_DIR / f"{slug}{dest_ext}"
        try:
            shutil.copy2(slot["path"], dest_image)
            log(f"Copied product image to {dest_image}")
        except Exception as e:
            log(f"Could not copy product image: {e}", "warning")
            dest_image = None

    # Build alt text
    alt_text = ""
    if hasattr(caption_obj, "alt_text"):
        alt_text = caption_obj.alt_text or ""

    product = {
        "id": slug,
        "name": product_name,
        "price": price,
        "category": size_cat,
        "description": alt_text or product_name,
        "dimensions_cm": "",
        "dimensions_in": "",
        "materials": ["stoneware"],
        "food_safe": True,
        "care": "Hand wash recommended",
        "one_of_one": True,
        "available": True,
        "coming_soon": False,
        "has_video": False,
        "video_src": "",
        "stripe_payment_link": "",
        "image": f"images/products/{slug}{dest_ext}" if dest_image else "",
    }

    # Append to inventory/products.json
    try:
        if PRODUCTS_PATH.exists():
            with open(PRODUCTS_PATH, "r", encoding="utf-8") as f:
                products = json.load(f)
            if not isinstance(products, list):
                products = []
        else:
            products = []

        products.append(product)

        with open(PRODUCTS_PATH, "w", encoding="utf-8") as f:
            json.dump(products, f, indent=2)
        log(f"Appended product '{product_name}' to products.json")
    except Exception as e:
        log(f"Could not update products.json: {e}", "error")

    return product


# =============================================================================
# 12. CREATE INSTAGRAM SLOT
# =============================================================================

def create_instagram_slot(slot: dict, caption_obj, schedule_time: datetime,
                           slot_num: int) -> Path:
    """
    Write instagram/queue/READY/[date]/[NN]-[DayMonDD]/ folder with:
      - media file (copy)
      - caption.txt
      - README.txt
    Returns the folder path.
    """
    date_str  = schedule_time.strftime("%Y-%m-%d")
    day_label = schedule_time.strftime("%a%b%d").upper()   # e.g. TUEapr07
    day_label = schedule_time.strftime("%a").upper() + schedule_time.strftime("%b%d").upper()
    folder_name = f"{slot_num:02d}-{day_label}"

    slot_dir = READY_DIR / date_str / folder_name
    slot_dir.mkdir(parents=True, exist_ok=True)

    # Copy media file
    media_path = slot.get("path")
    if media_path and Path(media_path).exists():
        dest_media = slot_dir / Path(media_path).name
        try:
            shutil.copy2(media_path, dest_media)
        except Exception as e:
            log(f"Could not copy media to slot: {e}", "warning")

    # caption.txt
    full_caption = ""
    if hasattr(caption_obj, "full_caption"):
        full_caption = caption_obj.full_caption or ""
    elif isinstance(caption_obj, str):
        full_caption = caption_obj

    try:
        with open(slot_dir / "caption.txt", "w", encoding="utf-8") as f:
            f.write(full_caption)
    except Exception as e:
        log(f"Could not write caption.txt: {e}", "error")

    # README.txt
    time_str = schedule_time.strftime("%A, %B %-d at %-I:%M %p")
    readme_content = (
        f"POST ON {schedule_time.strftime('%A').upper()} "
        f"at {schedule_time.strftime('%-I:%M %p')} "
        f"({date_str})\n\n"
        f"Steps:\n"
        f"  1. Open Instagram\n"
        f"  2. Create new post with the media file in this folder\n"
        f"  3. Copy caption from caption.txt and paste into Instagram\n"
        f"  4. Post!\n\n"
        f"Scheduled time: {time_str}\n"
        f"Source: {slot.get('source', 'unknown')}\n"
        f"Folder: {slot_dir}\n"
    )

    try:
        with open(slot_dir / "README.txt", "w", encoding="utf-8") as f:
            f.write(readme_content)
    except Exception as e:
        log(f"Could not write README.txt: {e}", "warning")

    log(f"Created Instagram slot: {slot_dir}")
    return slot_dir


# =============================================================================
# 13. WRITE THIS_WEEK.md
# =============================================================================

def write_this_week(posts_data: list) -> Path:
    """
    Write THIS_WEEK.md at repo root.
    ADHD-friendly: glanceable, day/time, copy-paste captions, website listing info.
    """
    lines = []
    today = datetime.now().strftime("%B %-d, %Y")

    lines.append("# This Week — Cerafica Instagram")
    lines.append(f"Generated: {today}")
    lines.append(f"Posts scheduled: {len(posts_data)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    for i, post in enumerate(posts_data, 1):
        sched = post.get("schedule_time")
        if isinstance(sched, datetime):
            day_time = sched.strftime("%A, %B %-d at %-I:%M %p")
        else:
            day_time = str(sched)

        folder = post.get("folder_path", "")
        caption = post.get("full_caption", "")
        source = post.get("source", "")
        product = post.get("product", None)

        lines.append(f"## Post {i} — {day_time}")
        lines.append("")
        lines.append(f"**Source:** {source}")
        lines.append(f"**Folder:** `{folder}`")
        lines.append("")
        lines.append("### Caption (copy-paste ready)")
        lines.append("")
        lines.append("```")
        lines.append(caption)
        lines.append("```")
        lines.append("")

        if product:
            lines.append("### Website Listing Created")
            lines.append("")
            lines.append(f"- **Product:** {product.get('name', '')}")
            lines.append(f"- **Price:** ${product.get('price', '')}")
            lines.append(f"- **ID:** `{product.get('id', '')}`")
            lines.append(f"- **Image:** `{product.get('image', '')}`")
            lines.append("")

        lines.append("---")
        lines.append("")

    if not posts_data:
        lines.append("No posts scheduled this week. Run the pipeline to generate content.")
        lines.append("")

    content = "\n".join(lines)

    try:
        with open(THIS_WEEK_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        log(f"Wrote THIS_WEEK.md to {THIS_WEEK_PATH}")
    except Exception as e:
        log(f"Could not write THIS_WEEK.md: {e}", "error")

    return THIS_WEEK_PATH


# =============================================================================
# 14. GIT COMMIT AND PUSH
# =============================================================================

def git_commit_and_push(changed_files: list) -> bool:
    """
    Stage changed_files, commit with weekly message, push.
    Returns True on success. Handles errors gracefully.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    n_posts = sum(1 for f in changed_files
                  if "READY" in str(f) and "caption.txt" in str(f))
    n_products = sum(1 for f in changed_files
                     if "products.json" in str(f))

    commit_msg = (
        f"Weekly content: {n_posts} posts + {n_products} shop listings {today}"
    )

    try:
        # Stage files
        for f in changed_files:
            result = subprocess.run(
                ["git", "add", str(f)],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                log(f"git add failed for {f}: {result.stderr}", "warning")

        # Commit
        result = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            log(f"git commit failed: {result.stderr}", "warning")
            return False

        log(f"git commit: {commit_msg}")

        # Push
        result = subprocess.run(
            ["git", "push"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            log(f"git push failed (non-fatal): {result.stderr}", "warning")
            return False

        log("git push: success")
        return True

    except Exception as e:
        log(f"git_commit_and_push error: {e}", "error")
        return False


# =============================================================================
# 15. MAIN ORCHESTRATION
# =============================================================================

def run_weekly(dry_run: bool = False, count: int = 3) -> dict:
    """
    Main orchestration function.
    Returns results dict with counts.
    """
    log(f"=== Weekly Orchestrator START (dry_run={dry_run}, count={count}) ===")

    results = {
        "slots_attempted": count,
        "slots_filled": 0,
        "posts_created": 0,
        "listings_created": 0,
        "errors": [],
        "dry_run": dry_run,
    }

    # --- Load shared state ---
    pricing = load_pricing()
    size_categories = pricing.get("size_categories", {})
    default_cat = pricing.get("default_category", "medium")
    processed = load_processed()

    # --- Get schedule ---
    try:
        schedule = get_posting_schedule(count=count)
    except Exception as e:
        log(f"Could not get posting schedule: {e}", "error")
        # Generate fallback schedule
        base = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        schedule = [base + timedelta(days=i) for i in range(1, count + 1)]

    # --- Fill content slots ---
    slots = fill_slots(count=count)
    results["slots_filled"] = len(slots)

    if not slots:
        log("No content slots could be filled. Exiting.", "warning")
        results["errors"].append("No media sources found")
        return results

    posts_data = []
    changed_files = []

    for i, (slot, sched_time) in enumerate(zip(slots, schedule), 1):
        log(f"--- Processing slot {i}/{len(slots)} (source={slot['source']}) ---")

        try:
            caption_obj = None
            analysis = None
            media_path = slot.get("path")
            is_repost = slot.get("source") == "archive_repost"

            # ---- Generate caption ----
            if is_repost:
                repost = slot["repost_data"] or {}
                original_caption = repost.get("caption", "")
                # Use original caption as a simple GeneratedCaption stand-in
                class _SimpleCap:
                    full_caption = original_caption
                    alt_text = "Archival ceramic piece"
                caption_obj = _SimpleCap()
                analysis = None
                log(f"  Repost from archive: shortcode={repost.get('shortcode')}")

            elif media_path and media_path.exists():
                ext = media_path.suffix.lower()
                try:
                    if ext in VIDEO_EXTS:
                        analysis = analyze_video(str(media_path), use_ai=True)
                    else:
                        analysis = analyze_photo(str(media_path), use_ai=True)
                    caption_obj = generate_caption(analysis, is_reel=(ext in VIDEO_EXTS))
                    log(f"  Generated caption for {media_path.name}")
                except Exception as e:
                    log(f"  Caption generation failed: {e}", "warning")
                    results["errors"].append(f"Caption failed for {media_path.name}: {e}")
                    class _FallbackCap:
                        full_caption = "Handmade with love. Link in bio to shop."
                        alt_text = "Handmade ceramic piece"
                    caption_obj = _FallbackCap()
            else:
                log(f"  No media path for slot {i}", "warning")
                class _EmptyCap:
                    full_caption = ""
                    alt_text = ""
                caption_obj = _EmptyCap()

            # ---- Website listing (only for new photos from inbox/inventory) ----
            product = None
            if not dry_run and analysis is not None and slot["source"] in ("inbox", "inventory"):
                try:
                    size_cat = estimate_size_category(str(media_path))
                    cat_data = size_categories.get(size_cat, size_categories.get(default_cat, {"price": 85}))
                    price = float(cat_data.get("price", 85))
                    product_name = generate_product_name(analysis)
                    product = create_website_listing(slot, caption_obj, size_cat, price, product_name)
                    results["listings_created"] += 1
                    changed_files.append(PRODUCTS_PATH)
                    if product.get("image"):
                        changed_files.append(WEBSITE_IMG_DIR / Path(product["image"]).name)
                    log(f"  Website listing created: {product_name} @ ${price}")
                except Exception as e:
                    log(f"  Website listing failed: {e}", "warning")
                    results["errors"].append(f"Listing failed: {e}")

            # ---- Create Instagram slot folder ----
            if not dry_run:
                try:
                    folder_path = create_instagram_slot(slot, caption_obj, sched_time, i)
                    results["posts_created"] += 1
                    changed_files.append(folder_path / "caption.txt")
                    changed_files.append(folder_path / "README.txt")
                    if media_path:
                        changed_files.append(folder_path / media_path.name)
                except Exception as e:
                    log(f"  create_instagram_slot failed: {e}", "error")
                    results["errors"].append(f"Slot creation failed: {e}")
                    folder_path = Path("")
            else:
                folder_path = READY_DIR / sched_time.strftime("%Y-%m-%d") / f"{i:02d}-DRY"
                log(f"  [DRY RUN] Would create slot: {folder_path}")

            # ---- Mark as processed ----
            if not dry_run:
                if media_path:
                    processed.add(media_path.name)
                if is_repost and slot.get("repost_data"):
                    shortcode = slot["repost_data"].get("shortcode", "")
                    if shortcode:
                        processed.add(shortcode)

            posts_data.append({
                "slot_num": i,
                "source": slot["source"],
                "schedule_time": sched_time,
                "folder_path": str(folder_path),
                "full_caption": getattr(caption_obj, "full_caption", ""),
                "product": product,
            })

        except Exception as e:
            log(f"Unexpected error in slot {i}: {e}", "error")
            results["errors"].append(f"Slot {i} error: {e}")
            import traceback
            log(traceback.format_exc(), "debug")

    # ---- Write THIS_WEEK.md ----
    if not dry_run:
        try:
            this_week_path = write_this_week(posts_data)
            changed_files.append(this_week_path)
        except Exception as e:
            log(f"write_this_week failed: {e}", "error")
    else:
        log("[DRY RUN] Would write THIS_WEEK.md")

    # ---- Save processed ----
    if not dry_run:
        save_processed(processed)

    # ---- Git commit + push ----
    if not dry_run and changed_files:
        try:
            git_ok = git_commit_and_push(changed_files)
            results["git_pushed"] = git_ok
        except Exception as e:
            log(f"git_commit_and_push failed: {e}", "error")
            results["git_pushed"] = False

    log(f"=== Weekly Orchestrator DONE: {results} ===")

    # ---- Print dry-run summary ----
    if dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN SUMMARY")
        print("=" * 60)
        for pd in posts_data:
            sched = pd["schedule_time"]
            print(f"\n[Slot {pd['slot_num']}] {sched.strftime('%A %b %-d at %-I:%M %p')}")
            print(f"  Source  : {pd['source']}")
            print(f"  Folder  : {pd['folder_path']}")
            caption_preview = (pd['full_caption'] or "")[:120].replace("\n", " ")
            print(f"  Caption : {caption_preview}...")
            if pd.get("product"):
                p = pd["product"]
                print(f"  Listing : {p.get('name')} @ ${p.get('price')}")
        print("\n" + "=" * 60 + "\n")

    return results


# =============================================================================
# 16. SHOW STATUS
# =============================================================================

def show_status() -> None:
    """Show current queue state."""
    print("\n" + "=" * 60)
    print("CERAFICA INSTAGRAM QUEUE STATUS")
    print("=" * 60)

    # READY queue
    ready_posts = []
    if READY_DIR.exists():
        for date_dir in sorted(READY_DIR.iterdir()):
            if date_dir.is_dir():
                for slot_dir in sorted(date_dir.iterdir()):
                    if slot_dir.is_dir():
                        has_caption = (slot_dir / "caption.txt").exists()
                        media_files = [f for f in slot_dir.iterdir()
                                       if f.suffix.lower() in MEDIA_EXTS]
                        ready_posts.append({
                            "path": slot_dir,
                            "date": date_dir.name,
                            "has_caption": has_caption,
                            "has_media": len(media_files) > 0,
                        })

    print(f"\nREADY posts: {len(ready_posts)}")
    for rp in ready_posts:
        status = "OK" if (rp["has_caption"] and rp["has_media"]) else "INCOMPLETE"
        print(f"  [{status}] {rp['date']} / {rp['path'].name}")

    # Inbox
    inbox_files = scan_inbox()
    print(f"\nInbox (unprocessed): {len(inbox_files)} files")
    for f in inbox_files[:5]:
        print(f"  {f.name}")
    if len(inbox_files) > 5:
        print(f"  ... and {len(inbox_files) - 5} more")

    # Framed
    framed_files = scan_framed()
    print(f"\nFramed (unprocessed): {len(framed_files)} files")

    # Inventory available
    inv_files = scan_inventory_available()
    print(f"Inventory available (unprocessed): {len(inv_files)} files")

    # Top performers
    performers = get_top_performers(limit=3)
    print(f"Archive top performers available: {len(performers)}")

    # Processed count
    processed = load_processed()
    print(f"\nTotal processed items: {len(processed)}")
    print("=" * 60 + "\n")


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cerafica Weekly Content Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python weekly-orchestrator.py              Run full pipeline (3 posts)
  python weekly-orchestrator.py --count 5   Generate 5 posts
  python weekly-orchestrator.py --dry-run   Preview without writing anything
  python weekly-orchestrator.py --status    Show current queue state
        """,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview pipeline output without writing any files",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current queue state and exit",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=3,
        metavar="N",
        help="Number of posts to generate (default: 3)",
    )

    args = parser.parse_args()

    if args.status:
        show_status()
        return

    results = run_weekly(dry_run=args.dry_run, count=args.count)

    print("\nResults:")
    print(f"  Slots filled:     {results['slots_filled']}/{results['slots_attempted']}")
    print(f"  Posts created:    {results['posts_created']}")
    print(f"  Listings created: {results['listings_created']}")
    if results.get("git_pushed") is not None:
        print(f"  Git pushed:       {results['git_pushed']}")
    if results["errors"]:
        print(f"\nWarnings/Errors ({len(results['errors'])}):")
        for err in results["errors"]:
            print(f"  - {err}")


if __name__ == "__main__":
    main()
