"""
Clean Frame Theme

A minimal, professional frame with:
- Dark background
- Clean border around the product
- Brand name text at the bottom
- Optional product name
"""

from pathlib import Path
from typing import Optional

from .base import FrameTheme, FrameConfig

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class CleanFrameTheme(FrameTheme):
    """Clean, professional product frame."""

    @property
    def name(self) -> str:
        return "Clean"

    def generate(
        self,
        photo_path: str | Path,
        output_path: str | Path,
        product_name: str = "",
        product_info: Optional[dict] = None,
    ) -> Path:
        if not HAS_PIL:
            raise ImportError("Pillow is required for frame generation: pip install Pillow")

        photo_path = Path(photo_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cfg = self.config
        W, H = cfg.output_width, cfg.output_height

        # Create canvas
        canvas = Image.new("RGB", (W, H), cfg.background_color)

        # Load and resize product photo
        photo = Image.open(photo_path).convert("RGBA")

        # Calculate sizing: photo takes 80% of canvas width, centered
        margin = int(W * 0.10)
        max_photo_w = W - (margin * 2)
        max_photo_h = int(H * 0.75)

        # Scale photo to fit
        ratio = min(max_photo_w / photo.width, max_photo_h / photo.height)
        new_w = int(photo.width * ratio)
        new_h = int(photo.height * ratio)
        photo_resized = photo.resize((new_w, new_h), Image.LANCZOS)

        # Center horizontally, position in upper portion
        x = (W - new_w) // 2
        y = margin + (max_photo_h - new_h) // 2

        # Add subtle border
        border_width = 3
        border_color = cfg.accent_color
        draw = ImageDraw.Draw(canvas)
        draw.rectangle(
            [x - border_width, y - border_width,
             x + new_w + border_width, y + new_h + border_width],
            outline=border_color,
            width=border_width
        )

        # Paste photo
        canvas.paste(photo_resized, (x, y), photo_resized)

        # Add text below photo
        text_y = y + new_h + int(margin * 0.8)
        font_size = int(W * 0.025)

        try:
            font = ImageFont.truetype("DejaVuSans.ttf", font_size)
            font_small = ImageFont.truetype("DejaVuSans.ttf", int(font_size * 0.7))
        except (OSError, IOError):
            font = ImageFont.load_default()
            font_small = font

        # Product name
        if product_name:
            bbox = draw.textbbox((0, 0), product_name, font=font)
            text_w = bbox[2] - bbox[0]
            draw.text(
                ((W - text_w) // 2, text_y),
                product_name,
                fill=cfg.text_color,
                font=font
            )
            text_y += int(font_size * 1.8)

        # Brand name
        if cfg.brand_name:
            bbox = draw.textbbox((0, 0), cfg.brand_name, font=font_small)
            text_w = bbox[2] - bbox[0]
            # Dim the brand text
            brand_color = tuple(int(c * 0.6) for c in cfg.text_color)
            draw.text(
                ((W - text_w) // 2, text_y),
                cfg.brand_name,
                fill=brand_color,
                font=font_small
            )

        # Add logo if available
        if cfg.logo_path:
            logo_path = Path(cfg.logo_path)
            if logo_path.exists():
                try:
                    logo = Image.open(logo_path).convert("RGBA")
                    logo_size = int(W * 0.08)
                    logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
                    logo_x = W - margin - logo_size
                    logo_y = H - margin - logo_size
                    canvas.paste(logo, (logo_x, logo_y), logo)
                except Exception:
                    pass

        # Save
        canvas.save(str(output_path), quality=95)
        return output_path
