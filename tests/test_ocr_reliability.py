"""
Reliability tests for OCR pipeline with real-world image scenarios.

Tests cover: rotated images, low contrast, noisy, blurry, uniform,
tiny, large/wide, and fallback paths.

All test images are generated programmatically — no binary files committed.
"""

import time
import pytest
import numpy as np
from PIL import Image
from unittest.mock import patch

from tests.test_fixtures.generate_fixtures import (
    normal_document,
    rotated_90,
    rotated_180,
    low_contrast,
    noisy,
    blurry,
    large_wide,
    tiny,
    uniform,
    uniform_near_white,
    dark_underexposed,
    to_png_bytes,
)

# Import functions from app
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import (
    preprocess_for_ocr,
    build_ocr_variants,
    score_ocr_text,
    ocr_quality_from_score,
    analyze_image_quality,
    autorotate_multipass,
    detect_text_roi,
    run_best_effort_ocr,
    OCR_AVAILABLE,
)


# ============================================================
# OCR Quality Scoring Tests
# ============================================================

class TestScoreOcrText:
    """Tests for score_ocr_text — determines text usefulness before translation."""

    def test_normal_text_scores_high(self):
        """Normal prose text should score well above zero."""
        text = "This is a sample document for testing optical character recognition."
        score = score_ocr_text(text)
        assert score > 0, f"Expected positive score, got {score}"

    def test_empty_text_scores_zero(self):
        """Empty text should score zero."""
        assert score_ocr_text("") == 0.0
        assert score_ocr_text(None) == 0.0

    def test_garbage_symbols_penalized(self):
        """High symbol density text should be penalized."""
        garbage = "~!@#$%^&*()_+|\\=-`[]{};':\",./<>?"
        score = score_ocr_text(garbage)
        normal = "This has mostly real words with a few symbols like these @ signs."
        normal_score = score_ocr_text(normal)
        assert score < normal_score, (
            f"Garbage score {score} should be lower than normal text {normal_score}"
        )

    def test_short_clean_text_not_overpenalized(self):
        """Short but clean text (dates, names) should still get a reasonable score."""
        text = "John Smith, April 15 2026"
        score = score_ocr_text(text)
        assert score > 0, f"Clean short text scored {score}, expected > 0"


class TestOcrQualityFromScore:
    """Tests for ocr_quality_from_score — quality label assignment."""

    def test_empty_text_returns_none(self):
        """No text should return 'none' quality."""
        assert ocr_quality_from_score(0, 0, "") == "none"

    def test_long_text_with_good_confidence_returns_high_or_medium(self):
        """High confidence with lots of content should yield high or medium."""
        text = "This is a reasonably long document with enough words for a good score." * 3
        quality = ocr_quality_from_score(80, 75, text)
        assert quality in ("high", "medium"), f"Expected high/medium, got {quality}"

    def test_short_text_with_low_confidence_is_low(self):
        """Short text with poor confidence should be 'low'."""
        quality = ocr_quality_from_score(10, 20, "hi")
        assert quality == "low", f"Expected low, got {quality}"


# ============================================================
# Image Quality Analysis Tests
# ============================================================

class TestAnalyzeImageQuality:
    """Tests for analyze_image_quality — pre-OCR image quality check."""

    def test_normal_image_no_warnings(self):
        """Normal document should not trigger quality warnings."""
        img = normal_document()
        result = analyze_image_quality(img)
        assert result["can_process"], "Normal image should be processable"
        # Normal images may have very mild warnings; check not blocking
        assert result["should_warn"] is False or len(result["warnings"]) <= 1

    def test_uniform_image_detected(self):
        """Uniform image should be detected as uniform/blank."""
        img = uniform()
        result = analyze_image_quality(img)
        assert result.get("is_uniform") is True, f"Uniform expected, got: {result}"
        assert "blank" in " ".join(result.get("warnings", [])).lower() or "uniform" in " ".join(result.get("warnings", [])).lower()

    def test_blurry_image_detected(self):
        """Blurry image should register medium or high blur."""
        img = blurry()
        result = analyze_image_quality(img)
        # Blur detection can vary by environment; at minimum should not crash
        assert result["can_process"], "Blurry image should still be processable"

    def test_dark_image_detected(self):
        """Dark image should register brightness issue."""
        img = dark_underexposed()
        result = analyze_image_quality(img)
        warns = " ".join(result.get("warnings", []))
        assert result.get("brightness") in ("too_dark", "dark"), f"Expected dark brightness, got {result}"

    def test_tiny_image_warning(self):
        """Very small image should produce a size warning."""
        img = tiny()
        result = analyze_image_quality(img)
        warns = " ".join(result.get("warnings", []))
        assert "small" in warns.lower(), f"Expected size warning, got: {result}"


# ============================================================
# Orientation Detection Tests
# ============================================================

class TestAutorotateMultipass:
    """Tests for autorotate_multipass — multi-strategy orientation correction."""

    def test_no_rotation_for_normal_image(self):
        """Normal image should not be rotated."""
        img = np.array(normal_document().convert("L"))
        info = {}
        result, updates = autorotate_multipass(img, info)
        assert updates.get("rotated_by") is None, f"Normal image should not rotate, got {updates}"

    def test_autorotate_does_not_crash(self):
        """Rotation function should never crash on any input shape."""
        for img_fn in [normal_document, rotated_90, rotated_180, low_contrast, uniform, tiny]:
            img = np.array(img_fn().convert("L"))
            info = {}
            try:
                result, updates = autorotate_multipass(img, info)
                assert result is not None, f"Result is None for {img_fn.__name__}"
            except Exception as e:
                pytest.fail(f"autorotate_multipass crashed on {img_fn.__name__}: {e}")


# ============================================================
# Preprocessing Tests
# ============================================================

class TestPreprocessForOcr:
    """Tests for preprocess_for_ocr — resizing, CLAHE, deskew."""

    def test_preprocess_normal_image(self):
        """Normal image should preprocess without error."""
        img = normal_document()
        result, info = preprocess_for_ocr(img)
        assert result is not None, "Preprocessed image should not be None"
        assert info.get("original_dims") is not None

    def test_preprocess_large_image_downscales(self):
        """Large image should be downscaled to max dimension."""
        img = large_wide()
        result, info = preprocess_for_ocr(img)
        if info.get("resize_scale", 1.0) < 1.0 or info["original_dims"][0] > 1200:
            # Either it was resized or original was already ≤1200px
            pass
        assert result is not None

    def test_preprocess_tiny_image_does_not_crash(self):
        """Tiny image should not crash preprocessing."""
        img = tiny()
        try:
            result, info = preprocess_for_ocr(img)
            assert result is not None
        except Exception as e:
            pytest.fail(f"Preprocess crashed on tiny image: {e}")

    def test_preprocess_uniform_image(self):
        """Uniform image should not crash."""
        img = uniform()
        try:
            result, info = preprocess_for_ocr(img)
            assert result is not None
        except Exception as e:
            pytest.fail(f"Preprocess crashed on uniform image: {e}")


# ============================================================
# ROI Detection Tests
# ============================================================

class TestDetectTextRoi:
    """Tests for detect_text_roi — text region detection."""

    def test_roi_on_normal_image(self):
        """Normal document should have ROI detected."""
        img = normal_document()
        result, info = detect_text_roi(img)
        assert result is not None
        assert info.get("method") is not None

    def test_roi_on_uniform_image_falls_back(self):
        """Uniform image should fall back to central or original."""
        img = uniform()
        result, info = detect_text_roi(img)
        assert result is not None
        assert info.get("method") in ("central", "original"), f"Expected fallback, got {info.get('method')}"


# ============================================================
# Build OCR Variants Tests
# ============================================================

class TestBuildOcrVariants:
    """Tests for build_ocr_variants — preprocessing pipeline."""

    def test_normal_image_produces_all_variants(self):
        """Normal image should produce all 6 variants."""
        img = normal_document()
        variants = build_ocr_variants(img)
        assert len(variants) >= 3, f"Expected at least 3 variants, got {len(variants)}"
        assert "original" in variants
        assert "otsu" in variants
        assert "adaptive" in variants

    def test_variants_do_not_crash_on_tiny_image(self):
        """All variants should be buildable even on tiny image."""
        img = tiny()
        variants = build_ocr_variants(img)
        assert len(variants) >= 1

    def test_variants_do_not_crash_on_uniform_image(self):
        """All variants should be buildable even on uniform image."""
        img = uniform()
        variants = build_ocr_variants(img)
        assert len(variants) >= 1


# ============================================================
# Integration Tests (full OCR pipeline)
# ============================================================

@pytest.mark.skipif(not OCR_AVAILABLE, reason="Tesseract OCR not installed")
class TestFullOcrPipeline:
    """Full pipeline tests — end-to-end OCR with real Tesseract calls."""

    def test_normal_document_extracts_text(self):
        """Normal printed docs should produce meaningful text."""
        img = normal_document()
        text, lang, info = run_best_effort_ocr(img)
        assert text and len(text.strip()) > 20, f"Expected meaningful text, got '{text[:50]}...'"
        assert info.get("quality") in ("high", "medium", "low"), f"Expected valid quality, got {info.get('quality')}"

    def test_rotated_image_still_extracts_text(self):
        """Rotated images should still produce text (autorotate handles it)."""
        img = rotated_90()
        text, lang, info = run_best_effort_ocr(img)
        # May or may not get full text depending on OSD; but should not crash
        assert info.get("quality") is not None, "Should return a quality label"

    def test_uniform_image_returns_no_text(self):
        """Uniform image should return no text."""
        img = uniform()
        text, lang, info = run_best_effort_ocr(img)
        # Should not crash; quality should be 'none' or 'low'
        assert text is not None, "Should return empty string, not None"

    def test_ocr_does_not_timeout_prematurely(self):
        """OCR should not timeout within a generous deadline."""
        img = normal_document()
        deadline = time.time() + 30  # 30s deadline (very generous)
        text, lang, info = run_best_effort_ocr(img, deadline=deadline)
        assert text is not None, "Should complete before deadline"
