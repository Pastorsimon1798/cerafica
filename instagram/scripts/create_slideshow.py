#!/usr/bin/env python3
"""
Create a weekly Instagram slideshow reel from product photos.

Uses rembg for background removal, planetary exploration log framing,
a recap slide, and a CTA slide with the shop URL.

Usage:
  python create_slideshow.py
  python create_slideshow.py --pieces Pallth-7 Nex-un-3 Cupr-ex-6
  python create_slideshow.py --week "2026.03.29 — 2026.04.04"
  python create_slideshow.py --exports ~/Downloads/cerafica_exports
"""

import argparse
import json
import os
import sqlite3
import random
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

# Import rembg from the dedicated venv
sys.path.insert(0, "/tmp/bgremove_env/lib/python3.14/site-packages")
from rembg import remove

# ============================================================================
# CONFIGURATION
# ============================================================================

REPO_ROOT = Path(__file__).parent.parent.parent
DB_PATH = REPO_ROOT / "tools" / "feedback.db"
PRODUCTS_PATH = REPO_ROOT / "inventory" / "products.json"
POSTING_PACKS_DIR = REPO_ROOT / "instagram" / "posting-packs"
EXPORTS_DIR = Path(os.environ.get("CERAFICA_EXPORTS_DIR", str(Path.home() / "Downloads" / "cerafica_exports")))
OUTPUT_DIR = REPO_ROOT / "output" / "slideshow"
SHOP_URL = "cerafica.com/shop"

W, H = 1080, 1350

# Color palette
CYAN = (30, 195, 210)
CYAN_DIM = (15, 130, 155)
CYAN_FAINT = (8, 65, 78)
AMBER = (255, 170, 0)
WHITE = (255, 255, 255)
WHITE_SOFT = (200, 210, 215)
SPACE = (10, 10, 18)
NEBULA_PURPLE = (42, 26, 58)
NEBULA_TEAL = (10, 42, 42)

SLIDE_DURATION = 3  # seconds per slide


# ============================================================================
# HELPERS
# ============================================================================

def find_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        str(Path.home() / "Library/Fonts/JetBrainsMonoNerdFontMono-Bold.ttf"),
        str(Path.home() / "Library/Fonts/FiraCode-Bold.ttf"),
    ] if bold else [
        str(Path.home() / "Library/Fonts/JetBrainsMonoNerdFontMono-Regular.ttf"),
        str(Path.home() / "Library/Fonts/FiraCode-Regular.ttf"),
        "Menlo.ttc",
        "/System/Library/Fonts/Menlo.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def make_space_background(w: int, h: int) -> Image.Image:
    img = Image.new("RGB", (w, h), SPACE)
    draw = ImageDraw.Draw(img)
    for _ in range(3):
        x, y = random.randint(0, w), random.randint(0, h)
        r = random.randint(200, 500)
        color = random.choice([NEBULA_PURPLE, NEBULA_TEAL, (20, 15, 35)])
        for i in range(r, 0, -5):
            alpha = max(0, min(255, int(8 * (1 - i / r))))
            c = tuple(min(255, int(v * alpha / 255)) for v in color)
            draw.ellipse([x - i, y - i, x + i, y + i], fill=c)
    for _ in range(150):
        x, y = random.randint(0, w), random.randint(0, h)
        brightness = random.randint(80, 255)
        size = random.choice([1, 1, 1, 2])
        draw.point((x, y), fill=(brightness, brightness, brightness))
    return img


def wrap_text(text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = current + (" " if current else "") + word
        bbox = font.getbbox(test)
        if bbox[2] - bbox[0] > max_width:
            if current:
                lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def remove_background(photo_path: Path) -> Image.Image:
    """Remove background using rembg, return RGBA image."""
    img = Image.open(photo_path).convert("RGB")
    result = remove(img)
    return result.convert("RGBA")


def place_on_space(product_rgba: Image.Image, canvas_w: int, canvas_h: int) -> Image.Image:
    """Place a transparent product onto a space background, centered and sized."""
    # Crop to content
    bbox = product_rgba.getbbox()
    if not bbox:
        return product_rgba.convert("RGB")
    product_cropped = product_rgba.crop(bbox)

    # Target area for the product
    product_area_top = 140
    product_area_bottom = canvas_h - 400
    area_h = product_area_bottom - product_area_top
    area_w = canvas_w - 100

    pw, ph = product_cropped.size
    scale = min(area_w / pw, area_h / ph, 1.0)
    new_w = int(pw * scale)
    new_h = int(ph * scale)
    product_resized = product_cropped.resize((new_w, new_h), Image.LANCZOS)

    # Create space background and paste
    bg = make_space_background(canvas_w, canvas_h)
    x = (canvas_w - new_w) // 2
    y = product_area_top + (area_h - new_h) // 2
    bg.paste(product_resized, (x, y), product_resized)

    # Subtle glow behind product
    glow = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    margin = 20
    glow_draw.rounded_rectangle(
        [x - margin, y - margin, x + new_w + margin, y + new_h + margin],
        radius=8, outline=(*CYAN_FAINT, 40), width=2
    )
    bg = Image.alpha_composite(bg.convert("RGBA"), glow).convert("RGB")

    return bg


# ============================================================================
# FRAME GENERATION
# ============================================================================

def create_product_frame(planet_name: str, lore: dict) -> Image.Image:
    """Create a planetary exploration log frame with bg-removed product."""
    photo_path = EXPORTS_DIR / PHOTO_MAP[planet_name]
    print(f"  Removing background for {planet_name}...", end=" ", flush=True)
    product_rgba = remove_background(photo_path)
    print("done", flush=True)

    print(f"  Placing on space background...", end=" ", flush=True)
    img = place_on_space(product_rgba, W, H)
    print("done", flush=True)

    draw = ImageDraw.Draw(img)

    # Border
    draw.rectangle([20, 20, W - 21, H - 21], outline=CYAN_DIM, width=1)
    draw.rectangle([24, 24, W - 25, H - 25], outline=CYAN_FAINT, width=1)

    font_title = find_font(28, bold=True)
    font_planet = find_font(36, bold=True)
    font_sub = find_font(18)
    font_body = find_font(20)
    font_small = find_font(16)

    # Header
    draw.text((50, 45), "CERAFICA EXPLORATION LOG", font=font_title, fill=CYAN)
    draw.text((50, 78), f"SECTOR: {lore.get('subtitle', planet_name.upper())}", font=font_sub, fill=CYAN_DIM)
    bbox = font_planet.getbbox(planet_name)
    draw.text((W - 50 - (bbox[2] - bbox[0]), 42), planet_name, font=font_planet, fill=AMBER)
    draw.line([(50, 115), (W - 50, 115)], fill=CYAN_DIM, width=1)

    # Footer
    footer_top = H - 400
    draw.line([(50, footer_top), (W - 50, footer_top)], fill=CYAN_DIM, width=1)

    y = footer_top + 20

    # Website description (curated, accurate text from products.json)
    description = lore.get("description", "")
    if description:
        draw.text((50, y), "SURVEYOR'S LOG:", font=font_sub, fill=CYAN_DIM)
        y += 25
        for line in wrap_text(description, font_body, W - 100)[:4]:
            draw.text((50, y), line, font=font_body, fill=WHITE_SOFT)
            y += 28

    y += 10
    draw.line([(50, y), (W - 50, y)], fill=CYAN_FAINT, width=1)
    y += 12

    # Materials (from products.json)
    materials = lore.get("materials", "")
    if materials:
        draw.text((50, y), "MATERIALS:", font=font_sub, fill=CYAN_DIM)
        y += 25
        for line in wrap_text(materials, font_body, W - 100)[:2]:
            draw.text((50, y), line, font=font_body, fill=WHITE_SOFT)
            y += 28

    # Dimensions + price bar
    y = H - 90
    draw.line([(50, y), (W - 50, y)], fill=CYAN_FAINT, width=1)
    y += 10
    dims = lore.get("dimensions", "")
    price = lore.get("price", "")
    if dims:
        draw.text((50, y), f"SIZE: {dims}", font=font_small, fill=CYAN_DIM)
    if price:
        price_text = f"${price}"
        bbox = font_small.getbbox(price_text)
        draw.text((W - 50 - (bbox[2] - bbox[0]), y), price_text, font=font_small, fill=AMBER)

    # Atmosphere data (real lore from DB)
    orbital = lore.get("orbital_data", "")
    if orbital:
        y = H - 65
        for line in orbital.split("\n"):
            if "Atmosphere:" in line or "Breathability:" in line:
                draw.text((50, y), line.strip(), font=font_small, fill=CYAN_DIM)
                y += 22

    # Shop URL at very bottom
    draw.line([(50, H - 45), (W - 50, H - 45)], fill=CYAN_FAINT, width=1)
    draw.text((50, H - 35), f"{SHOP_URL}", font=font_sub, fill=CYAN)

    return img


def create_recap_slide(products_data: list[dict], week_label: str) -> Image.Image:
    """Create a stylized recap text slide using real product descriptions."""
    img = make_space_background(W, H)
    draw = ImageDraw.Draw(img)

    draw.rectangle([20, 20, W - 21, H - 21], outline=CYAN_DIM, width=1)
    draw.rectangle([24, 24, W - 25, H - 25], outline=CYAN_FAINT, width=1)

    font_title = find_font(32, bold=True)
    font_sub = find_font(24)
    font_body = find_font(22)
    font_small = find_font(18)
    font_piece = find_font(28, bold=True)
    font_url = find_font(20)
    font_dim = find_font(16)

    # Title
    draw.text((W // 2 - 220, 80), "WEEKLY RECAP", font=font_title, fill=AMBER)
    draw.line([(W // 2 - 220, 125), (W // 2 + 220, 125)], fill=CYAN, width=2)
    draw.text((W // 2 - 120, 145), week_label, font=font_small, fill=CYAN_DIM)

    # Discoveries — use real descriptions from products.json
    y = 220
    draw.text((80, y), "THIS WEEK'S DISCOVERIES", font=font_sub, fill=CYAN)
    y += 45

    for product in products_data:
        name = product["name"].upper()
        desc = product.get("description", "")
        price = product.get("price", "")
        dims = product.get("dimensions_cm", "")

        draw.text((100, y), name, font=font_piece, fill=AMBER)
        y += 36
        for line in wrap_text(desc, font_body, W - 200)[:2]:
            draw.text((100, y), line, font=font_body, fill=WHITE_SOFT)
            y += 28
        # Dimensions + price on one line
        meta = ""
        if dims:
            meta = dims
        if price:
            meta = f"{meta}  |  ${price}" if meta else f"${price}"
        if meta:
            draw.text((100, y), meta, font=font_dim, fill=CYAN_DIM)
            y += 24
        y += 12

    draw.line([(80, y + 5), (W - 80, y + 5)], fill=CYAN_FAINT, width=1)
    y += 30

    draw.text((80, y), "FIVE NEW WORLDS SURVEYED", font=font_sub, fill=CYAN)
    y += 40
    for line in [
        "Each piece a planet. Each glaze a geological",
        "event captured in ceramic form. Hand-thrown,",
        "one of one.",
    ]:
        draw.text((100, y), line, font=font_body, fill=WHITE_SOFT)
        y += 32

    # CTA with URL
    y = H - 160
    draw.line([(80, y), (W - 80, y)], fill=CYAN_FAINT, width=1)
    y += 25
    draw.text((W // 2 - 170, y), "SHOP ALL PIECES", font=font_sub, fill=AMBER)
    y += 32
    draw.text((W // 2 - 185, y), f"{SHOP_URL}", font=font_url, fill=CYAN)
    y += 28
    draw.text((W // 2 - 175, y), "Free pickup in Long Beach, CA", font=font_small, fill=CYAN_DIM)

    return img


def create_cta_slide() -> Image.Image:
    """Create a beautiful final CTA slide with shop URL, on-theme."""
    img = Image.new("RGB", (W, H), (4, 4, 8))
    draw = ImageDraw.Draw(img)

    # Deep space background with nebula glow
    for cx, cy, r, color in [
        (W // 2, H // 3, 400, NEBULA_TEAL),
        (W // 3, H * 2 // 3, 300, NEBULA_PURPLE),
        (W * 2 // 3, H // 2, 350, (15, 25, 45)),
    ]:
        for i in range(r, 0, -4):
            alpha = max(0, min(255, int(12 * (1 - i / r))))
            c = tuple(min(255, int(v * alpha / 255)) for v in color)
            draw.ellipse([cx - i, cy - i, cx + i, cy + i], fill=c)

    # Stars
    for _ in range(200):
        x, y = random.randint(0, W), random.randint(0, H)
        brightness = random.randint(60, 255)
        size = random.choice([1, 1, 1, 1, 2])
        draw.point((x, y), fill=(brightness, brightness, brightness))

    # Double border
    draw.rectangle([30, 30, W - 31, H - 31], outline=CYAN_DIM, width=1)
    draw.rectangle([34, 34, W - 35, H - 35], outline=CYAN_FAINT, width=1)

    # Corner accents
    accent_len = 40
    for x, y, dx, dy in [(30, 30, 1, 1), (W - 30, 30, -1, 1),
                          (30, H - 30, 1, -1), (W - 30, H - 30, -1, -1)]:
        draw.line([(x, y), (x + accent_len * dx, y)], fill=CYAN, width=2)
        draw.line([(x, y), (x, y + accent_len * dy)], fill=CYAN, width=2)

    # Horizontal rule at top
    draw.line([(W // 2 - 180, 200), (W // 2 + 180, 200)], fill=CYAN, width=1)

    # Brand name
    font_brand = find_font(52, bold=True)
    brand_text = "CERAFICA"
    bbox = font_brand.getbbox(brand_text)
    brand_x = (W - (bbox[2] - bbox[0])) // 2
    draw.text((brand_x, 240), brand_text, font=font_brand, fill=WHITE)

    # Subtitle
    font_tagline = find_font(22)
    tagline = "CERAMICS FROM OTHER WORLDS"
    bbox = font_tagline.getbbox(tagline)
    tag_x = (W - (bbox[2] - bbox[0])) // 2
    draw.text((tag_x, 310), tagline, font=font_tagline, fill=CYAN_DIM)

    # Decorative line
    draw.line([(W // 2 - 120, 360), (W // 2 + 120, 360)], fill=CYAN_FAINT, width=1)

    # Center content area
    center_y = H // 2 - 40

    # "SHOP ALL PIECES" label
    font_cta = find_font(28, bold=True)
    cta_text = "SHOP ALL PIECES"
    bbox = font_cta.getbbox(cta_text)
    cta_x = (W - (bbox[2] - bbox[0])) // 2
    draw.text((cta_x, center_y), cta_text, font=font_cta, fill=AMBER)

    # URL — the hero element
    font_url_large = find_font(42, bold=True)
    url_text = "cerafica.com/shop"
    bbox = font_url_large.getbbox(url_text)
    url_x = (W - (bbox[2] - bbox[0])) // 2

    # Glow behind URL text
    glow_y = center_y + 60
    glow_img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_img)
    for offset in range(8, 0, -1):
        alpha = max(0, min(255, int(6 * (8 - offset))))
        glow_draw.text((url_x - offset, glow_y - offset), url_text,
                       font=font_url_large, fill=(*CYAN, alpha))
        glow_draw.text((url_x + offset, glow_y + offset), url_text,
                       font=font_url_large, fill=(*CYAN, alpha))
    img = Image.alpha_composite(img.convert("RGBA"), glow_img).convert("RGB")
    draw = ImageDraw.Draw(img)

    draw.text((url_x, glow_y), url_text, font=font_url_large, fill=CYAN)

    # Decorative line below URL
    draw.line([(W // 2 - 180, glow_y + 60), (W // 2 + 180, glow_y + 60)], fill=CYAN_FAINT, width=1)

    # Bottom info
    font_bottom = find_font(18)
    font_bottom_small = find_font(16)

    bottom_y = H - 180
    info_lines = [
        ("Hand-thrown stoneware, one of one", WHITE_SOFT),
        ("Free pickup in Long Beach, CA", CYAN_DIM),
    ]
    for text, color in info_lines:
        bbox = font_bottom.getbbox(text)
        tx = (W - (bbox[2] - bbox[0])) // 2
        draw.text((tx, bottom_y), text, font=font_bottom, fill=color)
        bottom_y += 30

    # Scanline effect (subtle)
    scanline = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    scanline_draw = ImageDraw.Draw(scanline)
    for y_pos in range(0, H, 3):
        scanline_draw.line([(0, y_pos), (W, y_pos)], fill=(0, 0, 0, 15))
    img = Image.alpha_composite(img.convert("RGBA"), scanline).convert("RGB")

    return img


# ============================================================================
# MAIN
# ============================================================================

def get_lore_data(planet_name: str) -> dict:
    lore = {}

    # Pull product data from products.json (authoritative source)
    products = json.loads(PRODUCTS_PATH.read_text())
    for p in products:
        if p.get("name", "").lower() == planet_name.lower():
            lore["description"] = p.get("description", "")
            lore["materials"] = p.get("materials", "")
            lore["dimensions"] = p.get("dimensions_cm", "")
            lore["price"] = p.get("price", "")
            break

    # Pull orbital data from DB (curated worldbuilding)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    piece = conn.execute(
        "SELECT * FROM series_pieces WHERE planet_name = ?", (planet_name,)
    ).fetchone()
    if piece:
        d = dict(piece)
        lore["orbital_data"] = d.get("orbital_data", "")
    conn.close()

    # Pull caption from posting pack (curated, human-written)
    slug = planet_name.lower().replace("-", "-")  # e.g., "pallth-7"
    pack_path = POSTING_PACKS_DIR / f"{slug}-rotating.md"
    if pack_path.exists():
        pack_text = pack_path.read_text()
        # Extract caption from between ``` markers after "## Caption"
        import re
        caption_match = re.search(r"## Caption\s*\n```(.+?)```", pack_text, re.DOTALL)
        if caption_match:
            lore["caption"] = caption_match.group(1).strip()
            # First sentence for subtitle
            first_sentence = lore["caption"].split(".")[0].strip().upper()
            if len(first_sentence) > 45:
                first_sentence = first_sentence[:42] + "..."
            lore["subtitle"] = first_sentence
        else:
            lore["subtitle"] = planet_name.upper()
    else:
        lore["subtitle"] = planet_name.upper()

    return lore


def find_photo_for_piece(planet_name: str, exports_dir: Path) -> str | None:
    """Find a photo in exports_dir matching the piece name."""
    if not exports_dir.exists():
        return None
    # Try common patterns: planet-name.jpg, planet_name.jpg, IMG_*.JPG
    slug = planet_name.lower().replace("-", "")
    for f in sorted(exports_dir.iterdir()):
        if f.suffix.lower() not in (".jpg", ".jpeg", ".png"):
            continue
        if slug in f.stem.lower().replace("-", "").replace("_", ""):
            return f.name
    return None


def main():
    parser = argparse.ArgumentParser(description="Create a weekly Instagram slideshow reel")
    parser.add_argument("--pieces", nargs="+", help="Planet names to include (default: all available)")
    parser.add_argument("--week", help="Week label (default: auto-detect this week)")
    parser.add_argument("--exports", help="Directory with exported photos (default: ~/Downloads/cerafica_exports)")
    parser.add_argument("--duration", type=int, default=3, help="Seconds per slide (default: 3)")
    args = parser.parse_args()

    global EXPORTS_DIR, SLIDE_DURATION
    if args.exports:
        EXPORTS_DIR = Path(args.exports)
    SLIDE_DURATION = args.duration

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load all products
    products = json.loads(PRODUCTS_PATH.read_text())

    # Determine which pieces to include
    if args.pieces:
        piece_names = args.pieces
    else:
        # Auto-detect: use all pieces that have posting packs
        piece_names = []
        for p in products:
            name = p.get("name", "")
            slug = name.lower().replace("-", "-")
            pack = POSTING_PACKS_DIR / f"{slug}-rotating.md"
            if pack.exists():
                piece_names.append(name)

    if not piece_names:
        print("No pieces found. Use --pieces to specify, or create posting packs first.")
        return

    print(f"Weekly slideshow: {len(piece_names)} pieces")

    # Auto-detect week range
    if args.week:
        week_label = args.week
    else:
        today = date.today()
        # Most recent Saturday to Friday
        days_since_saturday = (today.weekday() - 5) % 7
        saturday = today - timedelta(days=days_since_saturday)
        friday = saturday + timedelta(days=6)
        week_label = f"{saturday.strftime('%Y.%m.%d')} — {friday.strftime('%Y.%m.%d')}"

    # Build photo map: find photos for each piece
    photo_map = {}
    for name in piece_names:
        photo = find_photo_for_piece(name, EXPORTS_DIR)
        if photo:
            photo_map[name] = photo
        else:
            print(f"  WARNING: No photo found for {name} in {EXPORTS_DIR}")

    # Load product data for pieces in this slideshow
    recap_products = [p for p in products if p.get("name", "") in piece_names]

    frame_paths = []
    for planet_name in piece_names:
        if planet_name not in photo_map:
            print(f"\nSkipping {planet_name} (no photo)")
            continue
        print(f"\nGenerating frame for {planet_name}...")
        lore = get_lore_data(planet_name)
        frame = create_product_frame(planet_name, lore)
        path = OUTPUT_DIR / f"{planet_name.lower().replace('-', '')}_slide.jpg"
        frame.save(path, "JPEG", quality=95)
        frame_paths.append(str(path))
        print(f"  Saved: {path}")

    print(f"\nGenerating recap slide ({week_label})...")
    recap = create_recap_slide(recap_products, week_label)
    recap_path = OUTPUT_DIR / "recap_slide.jpg"
    recap.save(recap_path, "JPEG", quality=95)
    frame_paths.insert(0, str(recap_path))
    print(f"  Saved: {recap_path}")

    print("\nGenerating CTA slide...")
    cta = create_cta_slide()
    cta_path = OUTPUT_DIR / "cta_slide.jpg"
    cta.save(cta_path, "JPEG", quality=95)
    frame_paths.append(str(cta_path))
    print(f"  Saved: {cta_path}")

    # Convert each slide to a short video clip for mcp-video merge
    print(f"\nConverting {len(frame_paths)} slides to video clips...")
    clip_paths = []
    for i, path in enumerate(frame_paths):
        clip_path = OUTPUT_DIR / f"clip_{i:02d}.mp4"
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", str(path),
            "-t", str(SLIDE_DURATION),
            "-vf", "scale=1080:1350,format=yuv420p",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
            "-an", str(clip_path)
        ]
        subprocess.run(cmd, capture_output=True, text=True)
        clip_paths.append(str(clip_path))
    print(f"  {len(clip_paths)} clips created")

    # Merge with fade transitions using mcp-video
    print("\nMerging with fade transitions (mcp-video)...")
    output_mp4 = OUTPUT_DIR / "weekly_recap_reel.mp4"
    mcp_video = "/tmp/mcp-video-env/bin/mcp-video"
    cmd = [
        mcp_video, "merge",
        "-t", "fade",
        "-td", "0.5",
        "-o", str(output_mp4),
        *clip_paths
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"mcp-video merge failed: {result.stderr[-500:]}")
        print("Falling back to ffmpeg concat...")
        concat_path = OUTPUT_DIR / "concat.txt"
        with open(concat_path, "w") as f:
            for path in clip_paths:
                f.write(f"file '{path}'\n")
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_path),
            "-c", "copy", str(output_mp4)
        ]
        subprocess.run(cmd, capture_output=True, text=True)

    # Add fade-in to start and fade-out to end
    final_mp4 = OUTPUT_DIR / "weekly_recap_final.mp4"
    print("Adding fade in/out...")
    cmd = [
        mcp_video, "fade",
        "--fade-in", "0.5",
        "--fade-out", "1.0",
        "-o", str(final_mp4),
        str(output_mp4)
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  Fade failed, using unmodified version")
        final_mp4 = output_mp4

    # Cleanup temp clips
    for path in clip_paths:
        Path(path).unlink(missing_ok=True)

    size_mb = final_mp4.stat().st_size / (1024 * 1024)
    print(f"\nDone! {final_mp4.name}")
    print(f"Size: {size_mb:.1f} MB | 1080x1350 | {len(frame_paths)} slides | {week_label}")


if __name__ == "__main__":
    random.seed(42)
    main()
