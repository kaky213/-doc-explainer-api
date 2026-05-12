"""
Language and script detection for OCR text.

Provides:
- Script detection from Unicode ranges (Latin, Cyrillic, Arabic, etc.)
- Language identification from word frequency + accented characters
- Normalized language code conversion
"""

import re


# ============================================================
# Script detection
# ============================================================

# Unicode ranges for script detection
SCRIPT_RANGES = {
    "latin": [(0x0041, 0x007A), (0x00C0, 0x024F), (0x1E00, 0x1EFF)],
    "cyrillic": [(0x0400, 0x04FF), (0x0500, 0x052F)],
    "arabic": [(0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF)],
    "devanagari": [(0x0900, 0x097F), (0xA8E0, 0xA8FF)],
    "han": [(0x4E00, 0x9FFF), (0x3400, 0x4DBF), (0xF900, 0xFAFF), (0x2F800, 0x2FA1F)],
    "kana": [(0x3040, 0x309F), (0x30A0, 0x30FF)],
    "hangul": [(0xAC00, 0xD7AF), (0x1100, 0x11FF), (0x3130, 0x318F)],
}


def detect_script_from_text(text: str) -> dict:
    """
    Detect scripts present in text by Unicode range analysis.
    
    Returns dict: {
        "scripts": {"latin": 0.85, "cyrillic": 0.0, ...},  # fractions of total chars
        "dominant": "latin",  # script code with highest fraction
        "dominant_pct": 85.0,
        "is_mixed": False,  # True if >10% in two or more scripts
        "non_alpha_pct": 0.0,  # fraction of spaces/punct/digits
    }
    """
    if not text or not text.strip():
        return {
            "scripts": {},
            "dominant": None,
            "dominant_pct": 0.0,
            "is_mixed": False,
            "non_alpha_pct": 0.0,
        }

    total_chars = 0
    script_counts = {s: 0 for s in SCRIPT_RANGES}

    for ch in text:
        cp = ord(ch)
        # Skip whitespace, digits, punctuation
        if ch.isspace() or ch.isdigit():
            continue
        # Basic ASCII punctuation
        if 0x0020 <= cp <= 0x0040 or 0x005B <= cp <= 0x0060 or 0x007B <= cp <= 0x007E:
            continue
        total_chars += 1
        for script, ranges in SCRIPT_RANGES.items():
            for start, end in ranges:
                if start <= cp <= end:
                    script_counts[script] += 1
                    break

    non_alpha_pct = 0.0
    if text and len(text) > 0:
        alpha_count = sum(1 for c in text if c.isalpha())
        non_alpha_pct = 1.0 - (alpha_count / max(len(text), 1))

    total_script_chars = sum(script_counts.values())
    if total_script_chars == 0:
        return {
            "scripts": {},
            "dominant": None,
            "dominant_pct": 0.0,
            "is_mixed": False,
            "non_alpha_pct": non_alpha_pct,
        }

    scripts_pct = {}
    for script, count in script_counts.items():
        if count > 0:
            scripts_pct[script] = round(count / total_script_chars, 4)

    dominant = max(scripts_pct, key=scripts_pct.get) if scripts_pct else None
    dominant_pct = scripts_pct.get(dominant, 0.0) * 100 if dominant else 0.0

    # Mixed script detection: >10% in two or more scripts
    significant = [s for s, p in scripts_pct.items() if p > 0.10]
    is_mixed = len(significant) >= 2

    return {
        "scripts": scripts_pct,
        "dominant": dominant,
        "dominant_pct": dominant_pct,
        "is_mixed": is_mixed,
        "non_alpha_pct": non_alpha_pct,
    }


# ============================================================
# Language identification heuristics
# ============================================================

def _normalize_text(text: str) -> str:
    """Lowercase and strip whitespace for comparison."""
    if not text:
        return ""
    return text.lower().strip()


def detect_language_from_ocr_text(text: str, script_info: dict = None) -> dict:
    """
    Lightweight heuristic to infer likely language from short noisy OCR text.
    
    Args:
        text: OCR-extracted text to analyze.
        script_info: Optional output from detect_script_from_text(). 
                     If not provided, it will be computed.
    
    Returns dict: {
        "lang": "de" | "en" | "es" | "fr" | "it" | "nl" | "pt" | "ru" | "ar" | "hi"
                | "zh" | "ja" | "ko" | None,
        "confidence": 0.0-1.0,
        "script": "latin" | "cyrillic" | "arabic" | "devanagari" | "cjk" | None,
    }
    """
    if not text or not text.strip():
        return {"lang": None, "confidence": 0.0, "script": None}

    normalized = _normalize_text(text)
    words = [w.strip(".,;:!?\"'()[]{}<>") for w in normalized.split()]
    words = [w for w in words if len(w) > 1]
    
    if not words:
        return {"lang": None, "confidence": 0.0, "script": None}

    # Compute script info if not provided
    if script_info is None:
        script_info = detect_script_from_text(text)

    dominant_script = script_info.get("dominant")

    # ------------------------------------------------
    # Script-based routing: if dominant script is known,
    # return the most likely language for that script.
    # ------------------------------------------------
    if dominant_script == "cyrillic":
        # Russian (most common Cyrillic), could be Ukrainian
        ru_score = sum(1 for w in words if w in _RUSSIAN_WORDS)
        ukr_score = sum(1 for w in words if w in _UKRAINIAN_WORDS)
        if ru_score >= ukr_score:
            return {"lang": "ru", "confidence": min(0.5 + ru_score * 0.05, 0.9), "script": "cyrillic"}
        return {"lang": "ru", "confidence": 0.5, "script": "cyrillic"}  # default to Russian

    if dominant_script == "arabic":
        return {"lang": "ar", "confidence": 0.8, "script": "arabic"}

    if dominant_script == "devanagari":
        return {"lang": "hi", "confidence": 0.8, "script": "devanagari"}

    if dominant_script == "han":
        # Could be Chinese (simplified/traditional), could be Japanese kanji
        # Check for kana presence to differentiate Japanese vs Chinese
        kana_pct = script_info.get("scripts", {}).get("kana", 0.0)
        if kana_pct > 0.05:
            return {"lang": "ja", "confidence": 0.7, "script": "cjk"}
        return {"lang": "zh-CN", "confidence": 0.6, "script": "cjk"}

    if dominant_script == "kana":
        # Pure kana → Japanese
        return {"lang": "ja", "confidence": 0.8, "script": "cjk"}

    if dominant_script == "hangul":
        return {"lang": "ko", "confidence": 0.8, "script": "cjk"}

    # ------------------------------------------------
    # Latin script: function word + accented char scoring
    # ------------------------------------------------
    if dominant_script in (None, "latin"):
        return _detect_latin_language(text, words, script_info)

    # Unknown script
    return {"lang": None, "confidence": 0.0, "script": dominant_script}


def _detect_latin_language(text: str, words: list, script_info: dict) -> dict:
    """
    Detect language within Latin-script text using function words,
    accented characters, and letter-frequency clues.
    """
    scores = {
        "en": 0,
        "es": 0,
        "pt": 0,
        "fr": 0,
        "de": 0,
        "it": 0,
        "nl": 0,
    }

    # 1. Function word matching
    function_words = {
        "en": {"the", "and", "is", "in", "of", "to", "a", "for", "on", "this",
               "with", "are", "or", "be", "an", "that", "it", "as", "was", "he",
               "have", "not", "but", "by", "from", "they", "has", "had", "been"},
        "es": {"de", "la", "el", "que", "en", "y", "a", "los", "se", "las",
               "por", "con", "para", "una", "del", "como", "más", "pero", "sus",
               "le", "ya", "este", "entre", "todo", "esa"},
        "pt": {"de", "da", "do", "em", "para", "com", "por", "uma", "como",
               "mais", "mas", "que", "dos", "aos", "nas", "nos", "das", "a",
               "essa", "seu", "sua", "este", "isso", "entre", "todo"},
        "fr": {"le", "la", "les", "de", "du", "des", "et", "en", "est", "que",
               "une", "pour", "pas", "au", "sur", "dans", "avec", "ce", "son",
               "elle", "ils", "nous", "vous", "sont", "mais", "ou", "où"},
        "de": {"der", "die", "das", "und", "ist", "in", "von", "den", "dem", "zu",
               "nicht", "mit", "für", "auf", "ein", "sich", "des", "auch", "hat",
               "noch", "werden", "aus", "bei", "nach", "um"},
        "it": {"il", "la", "le", "gli", "dei", "che", "di", "a", "in", "per",
               "con", "su", "del", "della", "una", "un", "lo", "nel", "dal",
               "gli", "sono", "ha", "ho", "era", "non", "si", "delle"},
        "nl": {"de", "het", "een", "van", "in", "en", "die", "dat", "voor",
               "op", "te", "met", "aan", "bij", "naar", "zijn", "niet", "ook",
               "wordt", "heeft", "als", "dan", "nog", "uit", "over"},
    }

    for w in words:
        w_clean = w.lower()
        for lang, word_set in function_words.items():
            if w_clean in word_set:
                scores[lang] += 2  # 2 points per matched function word

    # 2. Accented character detection (strong indicators)
    accent_clues = {
        "pt": {"ã", "õ", "ç", "ê", "â", "ô"},
        "es": {"ñ", "á", "é", "í", "ó", "ú", "ü"},
        "fr": {"é", "è", "ê", "ë", "à", "â", "ù", "û", "ü", "ô", "î", "ç", "œ"},
        "de": {"ä", "ö", "ü", "ß"},
        "it": {"à", "è", "é", "ì", "ò", "ù"},
        "nl": {"ë", "ï", "ö", "ü", "é", "è"},
    }

    for lang, chars in accent_clues.items():
        for ch in text.lower():
            if ch in chars:
                scores[lang] += 3  # Strong indicator

    # 3. Language-specific strong clues
    strong_clues = {
        "pt": ["proprio", "existencia", "confeitaria", "fabrica", "fabrico",
               "possivel", "processo", "conhecimento", "especifico",
               "você", "avô", "português", "francês", "obrigado", "muito"],
        "es": ["qué", "cómo", "dónde", "cuándo", "por qué", "año", "español",
               "gracias", "señor", "señora", "muchas", "buenos", "días"],
    }

    for lang, clues in strong_clues.items():
        for clue in clues:
            if clue in text.lower():
                scores[lang] += 3

    # Ensure at least 1 point for Latin scripts to avoid "None" when there IS text
    # (someone can write in English without function words, e.g. lists)
    if script_info and script_info.get("dominant") == "latin" and max(scores.values()) < 3:
        # Give English a slight edge by default for Latin script
        scores["en"] += 1

    # Determine winner
    max_score = max(scores.values())
    if max_score < 3:
        # Low confidence — return English as best guess for Latin text
        if script_info and script_info.get("dominant") == "latin":
            return {"lang": "en", "confidence": 0.3, "script": "latin"}
        return {"lang": None, "confidence": 0.0, "script": "latin"}

    detected = max(scores, key=scores.get)
    # Convert confidence to 0-1 scale: max_score / 40 (cap at 1.0)
    confidence = min(max_score / 40.0, 1.0)
    return {"lang": detected, "confidence": confidence, "script": "latin"}


# Common Russian words for Cyrillic scoring
_RUSSIAN_WORDS = {
    "что", "как", "для", "это", "она", "они", "его", "её", "еще",
    "все", "более", "когда", "очень", "даже", "можно", "такие",
    "если", "чтобы", "будет", "также", "потом", "теперь", "после",
}

# Common Ukrainian words
_UKRAINIAN_WORDS = {
    "що", "як", "для", "це", "вона", "вони", "його", "ще",
    "всі", "більше", "коли", "дуже", "навіть", "можна", "такі",
    "якщо", "щоб", "буде", "також", "потім", "тепер", "після",
}


# ============================================================
# Language code normalization
# ============================================================

def normalize_lang_code(lang: str | None) -> str:
    """
    Normalize various language code formats to MyMemory/DeepSeek-compatible codes.
    Input can be ISO 639-1, ISO 639-2/Tesseract, or partial codes.
    Returns ISO 639-1 code (e.g., "en", "fr") or empty string for unknown.
    """
    lang = (lang or "").strip().lower()
    if not lang or lang in {"unknown", "und", "none", "uncertain", "auto"}:
        return ""

    mapping = {
        "eng": "en",
        "fra": "fr",
        "fre": "fr",
        "deu": "de",
        "ger": "de",
        "spa": "es",
        "por": "pt",
        "ita": "it",
        "nld": "nl",
        "dut": "nl",
        "rus": "ru",
        "jpn": "ja",
        "jpn_vert": "ja",
        "kor": "ko",
        "chi_sim": "zh-cn",
        "chi_tra": "zh-tw",
        "zho": "zh-cn",
        "ara": "ar",
        "hin": "hi",
        "ukr": "uk",
        "pol": "pl",
        "ces": "cs",
        "cze": "cs",
        "dan": "da",
        "swe": "sv",
        "nor": "no",
        "fin": "fi",
        "ron": "ro",
        "rum": "ro",
        "hun": "hu",
        "tur": "tr",
        "ell": "el",
        "gre": "el",
        "heb": "he",
        "uk": "uk",
        "pl": "pl",
        "cs": "cs",
        "da": "da",
        "sv": "sv",
        "no": "no",
        "fi": "fi",
        "ro": "ro",
        "hu": "hu",
        "tr": "tr",
        "el": "el",
        "he": "he",
    }

    # Direct ISO 639-1 code (2-letter) — use as-is
    if len(lang) == 2 and lang in {"en", "es", "pt", "fr", "de", "it", "nl",
                                     "ru", "ar", "hi", "ja", "ko", "zh",
                                     "uk", "pl", "cs", "da", "sv", "no",
                                     "fi", "ro", "hu", "tr", "el", "he"}:
        return lang

    return mapping.get(lang, lang)


def normalize_to_tesseract(lang: str | None) -> str:
    """
    Normalize ISO 639-1 or other codes to Tesseract 3-letter codes.
    Returns Tesseract language code or empty string for unknown.
    """
    lang = (lang or "").strip().lower()
    mapping = {
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
        "zh-cn": "chi_sim",
        "zh-tw": "chi_tra",
        "zh": "chi_sim",
        "ja": "jpn",
        "ko": "kor",
        "uk": "ukr",
        "pl": "pol",
    }
    if len(lang) == 3 and lang in {"eng", "spa", "por", "fra", "deu", "ita",
                                     "nld", "rus", "ara", "hin", "chi_sim",
                                     "chi_tra", "jpn", "kor", "ukr"}:
        return lang
    return mapping.get(lang, "")


def get_language_display_name(code: str) -> str:
    """Get a human-readable display name for a language code."""
    mapping = {
        "en": "English", "es": "Español", "pt": "Português",
        "fr": "Français", "de": "Deutsch", "it": "Italiano",
        "nl": "Nederlands", "ru": "Русский", "ar": "العربية",
        "hi": "हिन्दी", "zh-CN": "中文 (简体)", "zh-TW": "中文 (繁體)",
        "ja": "日本語", "ko": "한국어",
    }
    return mapping.get(code, code)
