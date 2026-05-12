"""
Generate synthetic test images for OCR reliability tests.

All images are created programmatically — no binary files committed.
Keeps test size small while covering real-world image scenarios.
"""

import io
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter


SAMPLE_TEXT = (
    "This is a sample document for testing optical character recognition. "
    "The quick brown fox jumps over the lazy dog. "
    "12345 67890"
)


def _draw_text_on_image(draw, text, position=(20, 20), font_size=14):
    """Draw text on image using default PIL font. Position is (x, y)."""
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
    except (IOError, OSError):
        font = ImageFont.load_default()
    x, y = position
    for line in text.split("\n"):
        draw.text((x, y), line, fill=0, font=font)
        y += font_size + 4


def normal_document():
    """Create a normal, well-lit document image."""
    img = Image.new("RGB", (400, 300), "white")
    draw = ImageDraw.Draw(img)
    _draw_text_on_image(draw, SAMPLE_TEXT, font_size=14)
    return img


def rotated_90():
    """Create a document rotated 90 degrees (phone camera auto-rotate fail)."""
    img = Image.new("RGB", (400, 300), "white")
    draw = ImageDraw.Draw(img)
    _draw_text_on_image(draw, SAMPLE_TEXT, font_size=14)
    return img.rotate(90, expand=True, fillcolor="white")


def rotated_180():
    """Create an upside-down document image."""
    img = Image.new("RGB", (400, 300), "white")
    draw = ImageDraw.Draw(img)
    _draw_text_on_image(draw, SAMPLE_TEXT, font_size=14)
    return img.rotate(180, expand=True, fillcolor="white")


def low_contrast():
    """Create a washed-out, low-contrast document image."""
    img = Image.new("RGB", (400, 300), (180, 180, 180))
    draw = ImageDraw.Draw(img)
    _draw_text_on_image(draw, SAMPLE_TEXT, font_size=14)
    # Apply further contrast reduction
    img = img.point(lambda p: p * 0.6 + 70)
    return img


def noisy():
    """Create a noisy/grainy document image."""
    img = Image.new("RGB", (400, 300), "white")
    draw = ImageDraw.Draw(img)
    _draw_text_on_image(draw, SAMPLE_TEXT, font_size=14)
    # Add random noise
    np_img = np.array(img, dtype=np.float64)
    noise = np.random.normal(0, 40, np_img.shape)
    np_img = np.clip(np_img + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(np_img)


def blurry():
    """Create a blurry document image."""
    img = Image.new("RGB", (400, 300), "white")
    draw = ImageDraw.Draw(img)
    _draw_text_on_image(draw, SAMPLE_TEXT, font_size=14)
    # Apply Gaussian blur
    return img.filter(ImageFilter.GaussianBlur(radius=3))


def large_wide():
    """Create a very wide image (panoramic / extreme aspect ratio)."""
    img = Image.new("RGB", (2000, 100), "white")
    draw = ImageDraw.Draw(img)
    _draw_text_on_image(draw, SAMPLE_TEXT, font_size=12)
    return img


def tiny():
    """Create a tiny image (too small for readable text)."""
    img = Image.new("RGB", (10, 10), "white")
    return img


def uniform():
    """Create a solid gray uniform image (blank/empty)."""
    return Image.new("RGB", (200, 150), (128, 128, 128))


def uniform_near_white():
    """Create nearly blank image (very faint content, essentially empty)."""
    return Image.new("RGB", (200, 150), (245, 245, 245))


def dark_underexposed():
    """Create a very dark image (underexposed photo)."""
    img = Image.new("RGB", (400, 300), (20, 20, 20))
    draw = ImageDraw.Draw(img)
    _draw_text_on_image(draw, SAMPLE_TEXT, font_size=14)
    return img


def to_png_bytes(pil_image) -> bytes:
    """Convert PIL image to PNG bytes for upload."""
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    return buf.getvalue()


# Registry for iterate-all-fixtures pattern
FIXTURE_REGISTRY = {
    "normal_document": normal_document,
    "rotated_90": rotated_90,
    "rotated_180": rotated_180,
    "low_contrast": low_contrast,
    "noisy": noisy,
    "blurry": blurry,
    "large_wide": large_wide,
    "tiny": tiny,
    "uniform": uniform,
    "uniform_near_white": uniform_near_white,
    "dark_underexposed": dark_underexposed,
}
