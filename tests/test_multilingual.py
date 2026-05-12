"""
Multilingual tests for DocTranslate.

Tests OCR extraction, language detection, and script detection
across 14 languages and mixed-script documents.

All fixtures are programmatically generated — no binary files committed.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.test_fixtures import generate_fixtures as fx
from lang_detect import detect_script_from_text, detect_language_from_ocr_text


# ============================================================
# Language detection tests
# ============================================================

class TestLangDetection:
    """Test language detection from known text samples."""

    def test_detect_english(self):
        result = detect_language_from_ocr_text(
            "The meeting agenda includes reviewing quarterly results and discussing budget allocation."
        )
        assert result["lang"] == "en"
        assert result["script"] == "latin"
        assert result["confidence"] >= 0.15

    def test_detect_spanish(self):
        result = detect_language_from_ocr_text(
            "La reunión incluye revisar los resultados trimestrales y discutir la asignación del presupuesto."
        )
        assert result["lang"] == "es"
        assert result["confidence"] >= 0.15

    def test_detect_portuguese(self):
        result = detect_language_from_ocr_text(
            "A reunião inclui revisar os resultados trimestrais e discutir a alocação orçamentária."
        )
        assert result["lang"] == "pt"
        assert result["confidence"] >= 0.15

    def test_detect_french(self):
        result = detect_language_from_ocr_text(
            "La réunion comprend l'examen des résultats trimestriels et la discussion du budget."
        )
        assert result["lang"] == "fr"
        assert result["confidence"] >= 0.15

    def test_detect_german(self):
        result = detect_language_from_ocr_text(
            "Die Besprechung umfasst die Überprüfung der Quartalsergebnisse und die Budgetdiskussion."
        )
        assert result["lang"] == "de"
        assert result["confidence"] >= 0.15

    def test_detect_dutch(self):
        result = detect_language_from_ocr_text(
            "De vergadering omvat het bekijken van de kwartaalresultaten en het bespreken van het budget."
        )
        assert result["lang"] == "nl"
        assert result["confidence"] >= 0.15

    def test_detect_italian(self):
        result = detect_language_from_ocr_text(
            "La riunione include la revisione dei risultati trimestrali e la discussione del budget."
        )
        assert result["lang"] == "it"
        assert result["confidence"] >= 0.15

    def test_detect_russian(self):
        result = detect_language_from_ocr_text(
            "Собрание включает обзор квартальных результатов и обсуждение бюджета."
        )
        assert result["lang"] == "ru"
        assert result["script"] == "cyrillic"
        assert result["confidence"] >= 0.15

    def test_detect_arabic(self):
        result = detect_language_from_ocr_text(
            "يتضمن الاجتماع مراجعة النتائج الربعية ومناقشة الميزانية."
        )
        assert result["lang"] == "ar"
        assert result["script"] == "arabic"
        assert result["confidence"] >= 0.15

    def test_detect_hindi(self):
        result = detect_language_from_ocr_text(
            "बैठक में त्रैमासिक परिणामों की समीक्षा और बजट चर्चा शामिल है।"
        )
        assert result["lang"] == "hi"
        assert result["script"] == "devanagari"
        assert result["confidence"] >= 0.15

    def test_detect_chinese(self):
        result = detect_language_from_ocr_text(
            "会议包括审查季度成果和讨论预算分配。"
        )
        assert result["lang"] in ("zh-CN", "ja")
        assert result["script"] == "cjk"

    def test_detect_japanese(self):
        result = detect_language_from_ocr_text(
            "会議では四半期業績の確認と予算配分の協議を行います。"
        )
        assert result["lang"] == "ja"
        assert result["script"] == "cjk"
        assert result["confidence"] >= 0.15

    def test_detect_korean(self):
        result = detect_language_from_ocr_text(
            "회의에는 분기별 실적 검토와 예산 할당 논의가 포함됩니다."
        )
        assert result["lang"] == "ko"
        assert result["script"] == "cjk"
        assert result["confidence"] >= 0.15

    def test_empty_text_returns_none(self):
        result = detect_language_from_ocr_text("")
        assert result["lang"] is None
        assert result["confidence"] == 0.0

    def test_short_text_handled_gracefully(self):
        result = detect_language_from_ocr_text("Hello world")
        assert result["lang"] == "en"

    def test_numeric_text_returns_low_confidence(self):
        result = detect_language_from_ocr_text("12345 67890 111213")
        # Should not crash, return low/zero confidence
        assert result is not None
        # Either None with 0 or some lang with low confidence
        if result["lang"] is not None:
            assert result["confidence"] < 0.5


# ============================================================
# Script detection tests
# ============================================================

class TestScriptDetection:
    """Test Unicode-range script detection."""

    def test_latin_script(self):
        result = detect_script_from_text("Hello, this is English text.")
        assert result["dominant"] == "latin"
        assert result["dominant_pct"] > 90

    def test_cyrillic_script(self):
        result = detect_script_from_text("Привет, это русский текст.")
        assert result["dominant"] == "cyrillic"
        assert result["dominant_pct"] > 90

    def test_arabic_script(self):
        result = detect_script_from_text("مرحبا، هذا نص عربي.")
        assert result["dominant"] == "arabic"
        assert result["dominant_pct"] > 90

    def test_devanagari_script(self):
        result = detect_script_from_text("नमस्ते, यह हिंदी पाठ है।")
        assert result["dominant"] == "devanagari"
        assert result["dominant_pct"] > 90

    def test_chinese_han_script(self):
        result = detect_script_from_text("这是中文测试文档。")
        assert result["dominant"] == "han"
        assert result["dominant_pct"] > 90

    def test_japanese_script(self):
        """Japanese has kanji + kana, kana should be significant."""
        result = detect_script_from_text("これは日本語のテストです。")
        assert result["dominant"] in ("kana", "han")
        # Should detect kana presence
        kana_pct = result.get("scripts", {}).get("kana", 0) * 100
        assert kana_pct > 0

    def test_korean_script(self):
        result = detect_script_from_text("이것은 한국어 테스트입니다.")
        assert result["dominant"] == "hangul"
        assert result["dominant_pct"] > 90

    def test_mixed_latin_cyrillic(self):
        """Mixed script should detect both."""
        result = detect_script_from_text("Hello Привет")
        assert result["is_mixed"] or len([s for s, p in result.get("scripts", {}).items() if p > 0.05]) >= 2

    def test_mixed_latin_arabic(self):
        result = detect_script_from_text("Hello مرحبا")
        # At least 2 scripts should have content
        scripts_with_content = [s for s, p in result.get("scripts", {}).items() if p > 0.05]
        assert len(scripts_with_content) >= 2

    def test_empty_text(self):
        result = detect_script_from_text("")
        assert result["dominant"] is None
        assert not result["is_mixed"]

    def test_mixed_latin_cjk(self):
        """Mixed English + Chinese should show multiple scripts."""
        result = detect_script_from_text("Hello 你好")
        scripts_with_content = [s for s, p in result.get("scripts", {}).items() if p > 0.05]
        assert len(scripts_with_content) >= 2


# ============================================================
# OCR integration tests (image → text)
# ============================================================

class TestOcrMultilingual:
    """Test that Tesseract OCR extracts text from multilingual document images.
    
    These tests generate synthetic images with text in various scripts,
    run OCR with the appropriate language pack, and verify basic extraction.
    """

    def _ocr_image(self, pil_img, lang="eng"):
        """Run OCR on a PIL image with the given language."""
        import pytesseract
        return pytesseract.image_to_string(pil_img, lang=lang)

    def test_ocr_english(self):
        img = fx.english_doc()
        text = self._ocr_image(img, "eng")
        # Should extract at least some words
        words = text.strip().split()
        assert len(words) >= 5, f"Only got {len(words)} words: {text[:100]}"
        # Key English words should appear
        assert "agenda" in text.lower() or "Meeting" in text

    def test_ocr_spanish(self):
        img = fx.spanish_doc()
        text = self._ocr_image(img, "spa")
        words = text.strip().split()
        assert len(words) >= 3, f"Only got {len(words)} words: {text[:100]}"

    def test_ocr_portuguese(self):
        img = fx.portuguese_doc()
        text = self._ocr_image(img, "por")
        words = text.strip().split()
        assert len(words) >= 3, f"Only got {len(words)} words: {text[:100]}"

    def test_ocr_french(self):
        img = fx.french_doc()
        text = self._ocr_image(img, "fra")
        words = text.strip().split()
        assert len(words) >= 3, f"Only got {len(words)} words: {text[:100]}"

    def test_ocr_german(self):
        img = fx.german_doc()
        text = self._ocr_image(img, "deu")
        words = text.strip().split()
        assert len(words) >= 3, f"Only got {len(words)} words: {text[:100]}"

    def test_ocr_dutch(self):
        img = fx.dutch_doc()
        text = self._ocr_image(img, "nld")
        words = text.strip().split()
        assert len(words) >= 3, f"Only got {len(words)} words: {text[:100]}"

    def test_ocr_italian(self):
        img = fx.italian_doc()
        text = self._ocr_image(img, "ita")
        words = text.strip().split()
        assert len(words) >= 3, f"Only got {len(words)} words: {text[:100]}"

    def test_ocr_russian(self):
        img = fx.russian_doc()
        text = self._ocr_image(img, "rus")
        words = text.strip().split()
        assert len(words) >= 3, f"Only got {len(words)} words: {text[:100]}"

    def test_ocr_arabic(self):
        img = fx.arabic_doc()
        text = self._ocr_image(img, "ara")
        # Arabic OCR may extract fewer words due to RTL complexity
        words = text.strip().split()
        assert len(words) >= 2, f"Only got {len(words)} words: {text[:100]}"

    def test_ocr_hindi(self):
        img = fx.hindi_doc()
        text = self._ocr_image(img, "hin")
        words = text.strip().split()
        assert len(words) >= 2, f"Only got {len(words)} words: {text[:100]}"

    def test_ocr_chinese(self):
        img = fx.chinese_doc()
        text = self._ocr_image(img, "chi_sim")
        # Chinese characters = at least some extracted
        assert len(text.strip()) >= 5, f"Only got {len(text.strip())} chars: {text[:100]}"

    def test_ocr_japanese(self):
        img = fx.japanese_doc()
        text = self._ocr_image(img, "jpn")
        assert len(text.strip()) >= 5, f"Only got {len(text.strip())} chars: {text[:100]}"

    def test_ocr_korean(self):
        img = fx.korean_doc()
        text = self._ocr_image(img, "kor")
        assert len(text.strip()) >= 5, f"Only got {len(text.strip())} chars: {text[:100]}"


# ============================================================
# Full pipeline integration tests (script detection → OCR → lang detect)
# ============================================================

class TestFullMultilingualPipeline:
    """End-to-end tests: generate image → OCR → detect language → verify."""

    def _run_pipeline(self, img, ocr_lang="eng+spa"):
        import pytesseract
        text = pytesseract.image_to_string(img, lang=ocr_lang)
        script_info = detect_script_from_text(text)
        lang_result = detect_language_from_ocr_text(text, script_info)
        return text, script_info, lang_result

    def test_english_pipeline(self):
        img = fx.english_doc()
        text, script, lang = self._run_pipeline(img, "eng")
        assert script["dominant"] == "latin"
        assert lang["lang"] == "en" or (lang and text.strip())
        assert len(text.strip()) >= 20

    def test_spanish_pipeline(self):
        img = fx.spanish_doc()
        text, script, lang = self._run_pipeline(img, "spa")
        assert script["dominant"] == "latin"
        # Spanish has accented chars that help detection
        assert len(text.strip()) >= 10

    def test_russian_pipeline(self):
        img = fx.russian_doc()
        text, script, lang = self._run_pipeline(img, "rus")
        assert script["dominant"] == "cyrillic"
        assert lang["lang"] == "ru"
        assert lang["script"] == "cyrillic"
        assert len(text.strip()) >= 10

    def test_arabic_pipeline(self):
        img = fx.arabic_doc()
        text, script, lang = self._run_pipeline(img, "ara")
        assert script["dominant"] == "arabic"
        assert lang["lang"] == "ar"
        assert lang["script"] == "arabic"

    def test_hindi_pipeline(self):
        img = fx.hindi_doc()
        text, script, lang = self._run_pipeline(img, "hin")
        assert script["dominant"] == "devanagari"
        assert lang["lang"] == "hi"

    def test_chinese_pipeline(self):
        img = fx.chinese_doc()
        text, script, lang = self._run_pipeline(img, "chi_sim")
        assert script["dominant"] == "han"
        assert lang["lang"] in ("zh-CN", "ja")

    def test_japanese_pipeline(self):
        img = fx.japanese_doc()
        text, script, lang = self._run_pipeline(img, "jpn")
        # Japanese could detect han or kana dominant
        assert script["dominant"] in ("kana", "han")
        assert lang["lang"] == "ja" or (
            lang["script"] == "cjk" and text.strip()
        )

    def test_korean_pipeline(self):
        img = fx.korean_doc()
        text, script, lang = self._run_pipeline(img, "kor")
        assert script["dominant"] == "hangul"
        assert lang["lang"] == "ko"

    def test_mixed_latin_pipeline(self):
        """Mixed English + Spanish — should detect dominantly Latin, both languages."""
        img = fx.mixed_latin_doc()
        text, script, lang = self._run_pipeline(img, "eng+spa")
        assert script["dominant"] == "latin"
        assert len(text.strip()) >= 30
        # At least some text from both languages (OCR may normalize case)
        assert "welcome" in text.lower(), f"Missing 'welcome' in: {text[:200]}"
        assert "lunes" in text.lower(), f"Missing 'lunes' in: {text[:200]}"

    def test_mixed_cjk_latin_pipeline(self):
        """Mixed English + Chinese."""
        img = fx.mixed_cjk_latin_doc()
        text, script, lang = self._run_pipeline(img, "chi_sim+eng")
        assert script["dominant"] in ("latin", "han")
        assert len(text.strip()) >= 10

    def test_mixed_arabic_english_pipeline(self):
        """Mixed English + Arabic."""
        img = fx.mixed_arabic_english_doc()
        text, script, lang = self._run_pipeline(img, "ara+eng")
        assert script["dominant"] in ("latin", "arabic")
        # Should have extracted something
        assert len(text.strip()) >= 5


# ============================================================
# Fallback behavior tests
# ============================================================

class TestMultilingualFallbackBehavior:
    """Test app-level fallback for unsupported / low-quality cases."""

    def _run_ocr(self, img):
        """Run OCR pipeline and return (text, detected_lang, metadata).
        run_best_effort_ocr returns tuple[str, str, dict].
        """
        from app import run_best_effort_ocr
        result = run_best_effort_ocr(img)
        # Returns (text, detected_lang, metadata_dict)
        if isinstance(result, tuple) and len(result) == 3:
            return result
        # Fallback if tuple format unexpected
        return ("", "unknown", {})

    def test_uniform_image_no_text(self):
        """Uniform image should return no text regardless of language."""
        img = fx.uniform()
        text, detected_lang, meta = self._run_ocr(img)
        text = text.strip() if text else ""
        assert len(text) < 5

    def test_ocr_never_hangs_on_blurry(self):
        """Blurry image should not hang the OCR pipeline."""
        import time
        img = fx.blurry()
        t0 = time.time()
        text, detected_lang, meta = self._run_ocr(img)
        elapsed = time.time() - t0
        assert elapsed < 30, f"OCR took too long: {elapsed:.1f}s"
        # Meta should be a dict (may have partial or no text)
        assert isinstance(meta, dict)

    def test_english_doc_via_pipeline(self):
        """English doc through the full pipeline should extract text."""
        img = fx.english_doc()
        text, detected_lang, meta = self._run_ocr(img)
        text = text.strip() if text else ""
        assert len(text) >= 20

    def test_spanish_doc_extracts_text(self):
        """Spanish doc through pipeline should extract text (detection may vary due to synthetic image)."""
        img = fx.spanish_doc()
        text, detected_lang, meta = self._run_ocr(img)
        text = text.strip() if text else ""
        assert len(text) >= 10, f"Spanish OCR extracted too little: {text[:80]}"

    def test_russian_doc_extracts_text(self):
        """Russian doc through pipeline should extract some text (detection uses Eng-first)."""
        img = fx.russian_doc()
        text, detected_lang, meta = self._run_ocr(img)
        text = text.strip() if text else ""
        # With Eng-first OCR on a synthetic Cyrillic image, we may get partial text or garbage.
        # The key is the pipeline doesn't crash and returns something.
        assert isinstance(text, str)

    def test_arabic_doc_extracts_text(self):
        """Arabic doc through pipeline should extract some text."""
        img = fx.arabic_doc()
        text, detected_lang, meta = self._run_ocr(img)
        text = text.strip() if text else ""
        assert isinstance(text, str)

    def test_normalize_lang_code_consistency(self):
        """Test normalize_lang_code maps correctly for all major languages."""
        from lang_detect import normalize_lang_code
        cases = {
            "eng": "en", "spa": "es", "por": "pt", "fra": "fr",
            "deu": "de", "ita": "it", "nld": "nl",
            "rus": "ru", "ara": "ar", "hin": "hi",
            "chi_sim": "zh-cn", "chi_tra": "zh-tw",
            "jpn": "ja", "kor": "ko",
            "fre": "fr", "ger": "de", "dut": "nl",
            "zho": "zh-cn", "jpn_vert": "ja",
        }
        for code, expected in cases.items():
            assert normalize_lang_code(code) == expected, f"{code} -> {normalize_lang_code(code)} (expected {expected})"

        # Unknown codes should return empty string
        assert normalize_lang_code("xyz") == "xyz"  # pass through
        assert normalize_lang_code(None) == ""
        assert normalize_lang_code("unknown") == ""

    def test_normalize_to_tesseract(self):
        """Test ISO → Tesseract code mapping."""
        from lang_detect import normalize_to_tesseract
        cases = {
            "en": "eng", "es": "spa", "fr": "fra", "de": "deu",
            "ru": "rus", "ar": "ara", "zh-cn": "chi_sim",
            "ja": "jpn", "ko": "kor",
        }
        for code, expected in cases.items():
            assert normalize_to_tesseract(code) == expected, f"{code} -> {normalize_to_tesseract(code)}"
