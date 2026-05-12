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


# ============================================================
# Multilingual fixtures (programmatic, no binary files)
# ============================================================


def _get_font(size=16):
    """Get DejaVu Sans or fallback."""
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
    except (IOError, OSError):
        return ImageFont.load_default()


def _get_font_arabic(size=16):
    """Arabic font (Noto Naskh) or fallback."""
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf", size)
    except (IOError, OSError):
        return _get_font(size)


def _get_font_cjk(size=16):
    """CJK font (Noto Serif CJK SC) or fallback."""
    try:
        return ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", size, index=0)
    except (IOError, OSError):
        return _get_font(size)


def _draw_text(draw, text, font, x=20, y=20, fill=0):
    """Draw text at position, handling newlines."""
    line_height = font.size + 6
    for line in text.split("\n"):
        draw.text((x, y), line, fill=fill, font=font)
        y += line_height


def english_doc():
    """English printed document."""
    img = Image.new("RGB", (500, 200), "white")
    draw = ImageDraw.Draw(img)
    _draw_text(draw, (
        "Meeting Agenda\n"
        "1. Review quarterly results\n"
        "2. Discuss budget allocation\n"
        "3. Set goals for next quarter\n"
        "Date: January 15, 2024"
    ), _get_font(16))
    return img


def spanish_doc():
    """Spanish printed document."""
    img = Image.new("RGB", (500, 200), "white")
    draw = ImageDraw.Draw(img)
    _draw_text(draw, (
        "Orden del día\n"
        "1. Revisar resultados trimestrales\n"
        "2. Discutir la asignación del presupuesto\n"
        "3. Establecer metas para el próximo trimestre\n"
        "Fecha: 15 de enero de 2024"
    ), _get_font(16))
    return img


def portuguese_doc():
    """Portuguese printed document."""
    img = Image.new("RGB", (500, 200), "white")
    draw = ImageDraw.Draw(img)
    _draw_text(draw, (
        "Pauta da reunião\n"
        "1. Revisar resultados trimestrais\n"
        "2. Discutir alocação orçamentária\n"
        "3. Definir metas para o próximo trimestre\n"
        "Data: 15 de janeiro de 2024"
    ), _get_font(16))
    return img


def french_doc():
    """French printed document."""
    img = Image.new("RGB", (500, 200), "white")
    draw = ImageDraw.Draw(img)
    _draw_text(draw, (
        "Ordre du jour\n"
        "1. Examiner les résultats trimestriels\n"
        "2. Discuter de l'allocation budgétaire\n"
        "3. Fixer des objectifs pour le prochain trimestre\n"
        "Date : 15 janvier 2024"
    ), _get_font(16))
    return img


def german_doc():
    """German printed document."""
    img = Image.new("RGB", (500, 200), "white")
    draw = ImageDraw.Draw(img)
    _draw_text(draw, (
        "Tagesordnung\n"
        "1. Überprüfung der Quartalsergebnisse\n"
        "2. Diskussion der Budgetzuweisung\n"
        "3. Festlegung der Ziele für das nächste Quartal\n"
        "Datum: 15. Januar 2024"
    ), _get_font(16))
    return img


def dutch_doc():
    """Dutch printed document."""
    img = Image.new("RGB", (500, 200), "white")
    draw = ImageDraw.Draw(img)
    _draw_text(draw, (
        "Agenda\n"
        "1. Kwartaalresultaten bekijken\n"
        "2. Begrotingstoewijzing bespreken\n"
        "3. Doelen stellen voor volgend kwartaal\n"
        "Datum: 15 januari 2024"
    ), _get_font(16))
    return img


def italian_doc():
    """Italian printed document."""
    img = Image.new("RGB", (500, 200), "white")
    draw = ImageDraw.Draw(img)
    _draw_text(draw, (
        "Ordine del giorno\n"
        "1. Revisione dei risultati trimestrali\n"
        "2. Discussione dell'allocazione del budget\n"
        "3. Definizione degli obiettivi per il prossimo trimestre\n"
        "Data: 15 gennaio 2024"
    ), _get_font(16))
    return img


def russian_doc():
    """Russian printed document (Cyrillic)."""
    img = Image.new("RGB", (550, 200), "white")
    draw = ImageDraw.Draw(img)
    _draw_text(draw, (
        "Повестка дня\n"
        "1. Обзор квартальных результатов\n"
        "2. Обсуждение распределения бюджета\n"
        "3. Установка целей на следующий квартал\n"
        "Дата: 15 января 2024 года"
    ), _get_font(16))
    return img


def arabic_doc():
    """Arabic printed document."""
    img = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(img)
    font = _get_font_arabic(14)
    _draw_text(draw, (
        "جدول الأعمال\n"
        "1. مراجعة النتائج الربعية\n"
        "2. مناقشة تخصيص الميزانية\n"
        "3. تحديد الأهداف للربع القادم\n"
        "التاريخ: 15 يناير 2024"
    ), font)
    return img


def hindi_doc():
    """Hindi printed document (Devanagari)."""
    img = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(img)
    # FreeSerif supports Devanagari
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/freefont/FreeSerif.ttf", 16)
    except (IOError, OSError):
        font = _get_font(16)
    _draw_text(draw, (
        "कार्यसूची\n"
        "1. त्रैमासिक परिणामों की समीक्षा\n"
        "2. बजट आवंटन पर चर्चा\n"
        "3. अगली तिमाही के लिए लक्ष्य निर्धारित करें\n"
        "दिनांक: 15 जनवरी 2024"
    ), font)
    return img


def chinese_doc():
    """Chinese simplified document."""
    img = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(img)
    font = _get_font_cjk(16)
    _draw_text(draw, (
        "会议议程\n"
        "1. 审查季度成果\n"
        "2. 讨论预算分配\n"
        "3. 确定下季度目标\n"
        "日期: 2024年1月15日"
    ), font)
    return img


def japanese_doc():
    """Japanese document (kanji + kana)."""
    img = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", 16, index=2)  # JP
    except (IOError, OSError):
        font = _get_font_cjk(16)
    _draw_text(draw, (
        "議事日程\n"
        "1. 四半期の業績を確認する\n"
        "2. 予算配分について協議する\n"
        "3. 次の四半期の目標を設定する\n"
        "日付: 2024年1月15日"
    ), font)
    return img


def korean_doc():
    """Korean document (Hangul)."""
    img = Image.new("RGB", (600, 200), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc", 16, index=3)  # KR
    except (IOError, OSError):
        font = _get_font_cjk(16)
    _draw_text(draw, (
        "회의 의제\n"
        "1. 분기별 실적 검토\n"
        "2. 예산 할당 논의\n"
        "3. 다음 분기 목표 설정\n"
        "날짜: 2024년 1월 15일"
    ), font)
    return img


def mixed_latin_doc():
    """Mixed English + Spanish document (realistic bilingual form)."""
    img = Image.new("RGB", (600, 250), "white")
    draw = ImageDraw.Draw(img)
    font = _get_font(14)
    _draw_text(draw, (
        "Welcome Center / Centro de Bienvenida\n"
        "Name / Nombre: ___________________\n"
        "Date of Birth / Fecha de Nacimiento: ________\n"
        "Signature / Firma: ___________________\n"
        "\n"
        "Please read carefully / Por favor lea atentamente:\n"
        "Your appointment is on Monday. / Su cita es el lunes."
    ), font)
    return img


def mixed_cjk_latin_doc():
    """Mixed English + Chinese document."""
    img = Image.new("RGB", (650, 200), "white")
    draw = ImageDraw.Draw(img)
    font_cjk = _get_font_cjk(14)
    font_latin = _get_font(14)
    try:
        from itertools import cycle
        # Draw line by line
        lines = [
            ("International Office / 国际办公室", font_latin),
            ("Student Name / 学生姓名: _________", font_latin),
            ("Course: English for Business / 商务英语", font_latin),
            ("Please bring your passport / 请携带护照", font_latin),
        ]
        y = 20
        for text, f in lines:
            draw.text((20, y), text, fill=0, font=f)
            y += 24
    except Exception:
        _draw_text(draw, "English + 中文 mixed document test", font_cjk)
    return img


def mixed_arabic_english_doc():
    """Mixed English + Arabic document."""
    img = Image.new("RGB", (650, 200), "white")
    draw = ImageDraw.Draw(img)
    font_ar = _get_font_arabic(14)
    font_latin = _get_font(14)
    try:
        lines = [
            ("Welcome / مرحبا", font_latin),
            ("Passport Control / جوازات السفر", font_latin),
            ("Please have your documents ready", font_latin),
        ]
        y = 20
        for text, f in lines:
            draw.text((20, y), text, fill=0, font=f)
            y += 24
    except Exception:
        _draw_text(draw, "English + العربية mixed document", _get_font(14))
    return img


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
    # Multilingual
    "english_doc": english_doc,
    "spanish_doc": spanish_doc,
    "portuguese_doc": portuguese_doc,
    "french_doc": french_doc,
    "german_doc": german_doc,
    "dutch_doc": dutch_doc,
    "italian_doc": italian_doc,
    "russian_doc": russian_doc,
    "arabic_doc": arabic_doc,
    "hindi_doc": hindi_doc,
    "chinese_doc": chinese_doc,
    "japanese_doc": japanese_doc,
    "korean_doc": korean_doc,
    "mixed_latin_doc": mixed_latin_doc,
    "mixed_cjk_latin_doc": mixed_cjk_latin_doc,
    "mixed_arabic_english_doc": mixed_arabic_english_doc,
}
