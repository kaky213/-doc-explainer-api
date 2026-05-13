"""
Centralized configuration for DocTranslate.

All tunable constants, language mappings, and supported language lists live here.
Importing this module should have no side effects beyond defining constants.
"""

from pathlib import Path

# File upload limits
# These are the maximum theoretical values.
# The API layer (app.py) may enforce stricter limits for the demo.
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.txt'}
MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20 MB (app.py: 10 MB for demo)
MAX_TEXT_BYTES = 5 * 1024 * 1024    # 5 MB for .txt files (matches app.py)

# OCR Configuration
# All Tesseract languages to load. This constant is used for availability checks.
# Individual OCR calls use targeted language combos, not this megamix.
OCR_LANGS = "eng+spa+fra+deu+por+ita+chi_sim+nld+rus+ara+hin+chi_tra+jpn+kor"

# Maximum time (seconds) for processing a single document (OCR + analysis)
MAX_DOC_PROCESSING_TIME = 60

# Per-call OCR timeout (seconds) — prevents a single Tesseract call from hanging
OCR_PER_CALL_TIMEOUT = 30

# Image preprocessing
MAX_IMAGE_DIMENSION = 2000  # downscale images to this max side for OCR (2000px keeps fine print readable)
MAX_IMAGE_DIMENSION_UPLOAD = 8000  # reject uploads larger than this on any side
MIN_IMAGE_DIMENSION_UPLOAD = 20  # reject uploads smaller than this

# Upscaling: if longest side is below this threshold, 2x upscale before OCR
# (helps preserve small text on low-resolution images/screenshots)
MIN_DPI_TEXT_SIZE = 50  # minimum pixel height for readable text (heuristic)
OCR_UPSCALE_THRESHOLD = 800  # if max side < this, upscale 2x via Lanczos

# ============================================================
# Supported languages
# ============================================================

# Display names for all supported languages (ISO 639-1 codes)
LANG_DISPLAY_NAMES = {
    # Latin script
    "en": "English",
    "es": "Español",
    "pt": "Português",
    "fr": "Français",
    "de": "Deutsch",
    "it": "Italiano",
    "nl": "Nederlands",
    # Cyrillic
    "ru": "Русский",
    # Arabic
    "ar": "العربية",
    # Devanagari
    "hi": "हिन्दी",
    # CJK
    "zh-CN": "中文 (简体)",
    "zh-TW": "中文 (繁體)",
    "ja": "日本語",
    "ko": "한국어",
}

# Language script groups for UI organization
LANG_SCRIPT_GROUPS = {
    "Latin": ["en", "es", "pt", "fr", "de", "it", "nl"],
    "Cyrillic": ["ru"],
    "Arabic": ["ar"],
    "Devanagari": ["hi"],
    "CJK": ["zh-CN", "zh-TW", "ja", "ko"],
}

# Supported target languages for translation
SUPPORTED_TARGET_LANGUAGES = [
    "en", "es", "pt", "fr", "de", "it", "nl",
    "ru", "ar", "hi",
    "zh-CN", "zh-TW", "ja", "ko",
]

# Supported source language selections (including "auto" for auto-detect)
SUPPORTED_SOURCE_LANGUAGES = ["auto"] + SUPPORTED_TARGET_LANGUAGES

# DeepSeek / API-friendly language names for prompts
LANG_FULL_NAMES = {
    "en": "English",
    "es": "Spanish",
    "pt": "Portuguese",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "nl": "Dutch",
    "ru": "Russian",
    "ar": "Arabic",
    "hi": "Hindi",
    "zh-CN": "Chinese (Simplified)",
    "zh-TW": "Chinese (Traditional)",
    "ja": "Japanese",
    "ko": "Korean",
}

# ============================================================
# Tesseract language mappings
# ============================================================

# ISO 639-1 → Tesseract traineddata language name
# Tesseract uses three-letter codes (ISO 639-3/Tesseract convention)
ISO_TO_TESSERACT = {
    "en": "eng",
    "es": "spa",
    "pt": "por",
    "fr": "fra",
    "de": "deu",
    "it": "ita",
    "nl": "nld",
    "ru": "rus",
    "ar": "ara",
    "hi": "hin",
    "zh-CN": "chi_sim",
    "zh-TW": "chi_tra",
    "ja": "jpn",
    "ko": "kor",
}

# Tesseract → ISO (reverse mapping)
TESSERACT_TO_ISO = {v: k for k, v in ISO_TO_TESSERACT.items()}

# Script grouping for Tesseract — determines which languages can be combined
TESSERACT_SCRIPT_GROUPS = {
    "latin": ["eng", "spa", "por", "fra", "deu", "ita", "nld"],
    "cyrillic": ["rus", "ukr"],
    "arabic": ["ara"],
    "devanagari": ["hin"],
    "cjk": ["chi_sim", "chi_tra", "jpn", "kor"],
}

# OCR language strategy: combinations to try for each script
# These are Tesseract 3-letter codes
SCRIPT_OCR_STRATEGIES = {
    "latin": {
        "primary": ["eng"],  # English first — fastest, most common
        "fallback_latin": [
            "eng+spa", "eng+fra", "eng+deu",
            "eng+por", "eng+ita", "eng+nld",
        ],
    },
    "cyrillic": {
        "primary": ["rus", "rus+ukr"],
        "fallback_latin": [
            "eng+rus", "eng+ukr",
        ],
    },
    "arabic": {
        "primary": ["ara", "ara+eng"],
        "fallback_latin": ["ara+eng"],
    },
    "devanagari": {
        "primary": ["hin", "hin+eng"],
        "fallback_latin": ["hin+eng"],
    },
    "cjk": {
        "primary_chinese": ["chi_sim", "chi_tra"],
        "primary_japanese": ["jpn", "jpn+eng"],
        "primary_korean": ["kor", "kor+eng"],
    },
}

# General fallback: if script detection fails, try these combos
# Ordered by global prevalence / likelihood
GENERAL_FALLBACK_LANGS = [
    "eng+spa", "eng+fra", "eng+deu", "eng+por",
    "eng+ita", "eng+nld", "eng+rus", "eng+ara",
    "eng+hin", "chi_sim+eng", "jpn+eng", "kor+eng",
]

# ============================================================
# Translation API config
# ============================================================

# MyMemory → ISO lang code mapping (MyMemory uses 2-letter ISO 639-1)
# This is the same as LANG_DISPLAY_NAMES keys, so normalize_lang_code handles it.
# Additional special cases for MyMemory API:
MYMEMORY_LANG_MAP = {
    "zh-cn": "zh-CN",
    "zh-tw": "zh-TW",
    "ja": "ja",
    "ko": "ko",
}

# MyMemory skip list: languages that MyMemory free tier handles poorly
# Skip directly to DeepSeek for these
MYMEMORY_WEAK_LANGS = {"ar", "hi", "ja", "ko", "zh-CN", "zh-TW"}

# ============================================================
# Paths
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = str(BASE_DIR / "data")
UPLOADS_DIR = str(BASE_DIR / "data" / "uploads")
DOCUMENTS_FILE = str(BASE_DIR / "data" / "documents.json")
