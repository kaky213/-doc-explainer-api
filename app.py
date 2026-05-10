"""
Document Explainer API - Backend for document photo analysis, translation, and explanation
"""
import httpx
from dotenv import load_dotenv
import json
import os
import uuid
import logging
import time
from pathlib import Path

# Absolute base directory — works regardless of uvicorn's CWD
BASE_DIR = Path(__file__).resolve().parent
import cv2
import numpy as np
import re
from datetime import datetime
from enum import Enum
from typing import List, Optional

import uuid

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks, Header, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from pydantic import BaseModel

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s UTC %(levelname)-7s %(name)s %(message)s')
logger = logging.getLogger(__name__)

# Debug flag for verbose OCR logging
DEBUG_OCR = True

# Try to import OCR dependencies (optional)
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    pytesseract = None
    Image = None
    OCR_AVAILABLE = False

def debug_ocr_flow(best_text: str, detected_language: str, best: dict) -> tuple:
    """Debug logging for OCR flow"""
    if DEBUG_OCR:
        logger.info(f"OCR debug - Text length: {len(best_text)}, Language: {detected_language}")
        logger.info(f"OCR debug - Confidence: {best.get('confidence')}, Quality: {best.get('quality')}")
        logger.info(f"OCR debug - ROI method: {best.get('roi_method')}, ROI confidence: {best.get('roi_confidence')}")
        logger.info(f"OCR debug - Original size: {best.get('original_size')}, ROI size: {best.get('roi_size')}")
    return best_text, detected_language, best


def ocr_quality_from_score(score: float, conf: float, text: str = "") -> str:
    # Simple heuristic; tweak as you collect real data
    
    # Check for white-on-dark / chalkboard-style layout (high char count + alphabetic but non-linear layout)
    # This triggers for dense text with lots of content even if OCR scores it low
    if text and len(text.strip()) >= 50:
        alpha_ratio = sum(1 for c in text if c.isalpha()) / max(len(text.strip()), 1)
        if alpha_ratio >= 0.5 and len(text.strip()) >= 100:
            # Lots of text with reasonable letter ratio — likely a board/sign/menu with partial errors
            # Don't call it "low" even if confidence is mediocre
            if conf >= 60:
                return "medium"
    
    if conf >= 85 and score >= 80:
        return "high"
    if conf >= 60 and score >= 50:
        return "medium"
    if text and len(text.strip()) >= 40 and conf >= 55:
        # Borderline: lots of text, near-threshold confidence — be permissive for menus/boards
        return "low"  # Still technically low, but has enough text for partial results
    return "low"


def rotate_image_cv(img, angle: float):
    if angle % 360 == 0:
        return img
    if len(img.shape) == 2:
        h, w = img.shape
    else:
        h, w = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated


def get_osd_rotation(pil_image):
    try:
        osd = pytesseract.image_to_osd(
            pil_image,
            lang="osd",
            config="--psm 0",
            output_type=pytesseract.Output.DICT,
        )
        angle = float(osd.get("rotate", 0))
        if angle > 180:
            angle -= 360
        if abs(angle) < 1:
            return 0.0
        return angle
    except Exception:
        return 0.0


def score_ocr_text(text: str) -> float:
    if not text:
        return 0.0
    cleaned = text.strip()
    if not cleaned:
        return 0.0
    letters = sum(ch.isalpha() for ch in cleaned)
    digits = sum(ch.isdigit() for ch in cleaned)
    spaces = sum(ch.isspace() for ch in cleaned)
    useful = letters + digits
    length_score = min(len(cleaned), 500) / 10.0
    ratio_score = (useful / max(len(cleaned), 1)) * 100.0
    line_score = min(len([ln for ln in cleaned.splitlines() if ln.strip()]), 12) * 2.0
    return length_score + ratio_score + line_score + spaces * 0.1


def average_confidence(data_dict) -> float:
    confs = []
    for raw in data_dict.get("conf", []):
        try:
            val = float(raw)
            if val >= 0:
                confs.append(val)
        except Exception:
            pass
    if not confs:
        return 0.0
    return sum(confs) / len(confs)


def preprocess_for_ocr(pil_image):
    """
    Resize, enhance contrast, and normalize an image for OCR.
    Returns (preprocessed_pil, info_dict)
    """
    img = np.array(pil_image)
    # Handle edge cases: mock objects in tests, empty arrays, 1D arrays
    if not isinstance(img, np.ndarray) or img.ndim == 0 or img.size == 0:
        # Fall back to a small blank image
        gray = np.ones((100, 100), dtype=np.uint8) * 255
    elif img.ndim == 1:
        # Single channel as 1D array — reshape to grayscale
        gray = img.reshape(-1, 1) if img.ndim == 1 else img
    elif img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray = img

    if gray.ndim != 2:
        gray = np.ones((100, 100), dtype=np.uint8) * 255

    h, w = gray.shape[:2]
    max_dim = 2000
    info = {"original_dims": (w, h)}

    # Step 1: Downscale large images to max 2000px on longest side
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        gray = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_AREA)
        info["resized_dims"] = (new_w, new_h)
        info["resize_scale"] = round(scale, 3)
    else:
        info["resized_dims"] = (w, h)
        info["resize_scale"] = 1.0

    # Step 2: CLAHE contrast enhancement (improves real-world photos significantly)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Step 3: Light deskew from OSD
    try:
        osd = pytesseract.image_to_osd(enhanced, config="--psm 0 -c min_characters_to_try=5")
        import re
        angle_match = re.search(r"Rotate: (\d+)", osd)
        if angle_match:
            angle = int(angle_match.group(1))
            if angle in [90, 180, 270]:
                if angle == 90:
                    enhanced = cv2.rotate(enhanced, cv2.ROTATE_90_CLOCKWISE)
                elif angle == 180:
                    enhanced = cv2.rotate(enhanced, cv2.ROTATE_180)
                elif angle == 270:
                    enhanced = cv2.rotate(enhanced, cv2.ROTATE_90_COUNTERCLOCKWISE)
                info["deskew_rotation"] = angle
    except Exception:
        pass  # OSD may fail on small/noisy images

    pil_result = Image.fromarray(enhanced)
    return pil_result, info


def build_ocr_variants(pil_image):
    img = np.array(pil_image)
    if not isinstance(img, np.ndarray) or img.ndim < 2 or img.size == 0:
        # Fallback: return original only
        return {
            "original": pil_image,
            "otsu": pil_image,
            "adaptive": pil_image,
        }
    if img.ndim == 2:
        gray = img
    elif img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        return {"original": pil_image, "otsu": pil_image, "adaptive": pil_image}

    blur = cv2.GaussianBlur(gray, (3, 3), 0)
    otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    
    # Use a smaller block size and gentler C for adaptive thresholding
    # This works better for signs with colored/textured backgrounds
    adaptive = cv2.adaptiveThreshold(
        blur, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10
    )

    return {
        "original": pil_image,
        "otsu": otsu,
        "adaptive": adaptive,
    }


def language_word_bonus(text: str, lang: str) -> float:
    """Return bonus score (0.0 to 30.0) based on how many known common function words for that language appear in the text."""
    # Hardcoded dictionary of high-frequency short words per language
    lang_words = {
        "por": ["de", "da", "do", "das", "dos", "e", "em", "é", "seja", "bem", "para", "que", "com", "um", "uma"],
        "spa": ["de", "la", "el", "en", "es", "y", "del", "los", "las", "que", "con", "una", "por", "se", "al"],
        "deu": ["der", "die", "das", "und", "ist", "in", "von", "den", "dem", "zu", "nicht", "mit", "für", "auf", "ein"],
        "eng": ["the", "and", "is", "in", "of", "to", "a", "for", "on", "this", "with", "are", "or", "be", "an"],
        "fra": ["le", "la", "les", "de", "du", "des", "et", "en", "est", "que", "une", "pour", "pas", "au", "sur"],
    }
    
    if not text or lang not in lang_words:
        return 0.0
    
    # Clean and split text into words
    words = text.lower().split()
    bonus = 0.0
    
    # Check each word against language-specific function words
    for word in words:
        # Remove punctuation for better matching
        clean_word = word.strip(".,;:!?\"'()[]{}<>")
        if clean_word in lang_words[lang]:
            bonus += 2.0  # 2 points per matched function word
    
    # Cap the bonus at 30.0
    return min(bonus, 30.0)


def detect_language_from_ocr_text(text: str):
    """
    Lightweight heuristic to infer likely language from short noisy OCR text.
    Returns ISO-style language code (pt, es, en, de, fr) or None if confidence is too weak.
    """
    if not text:
        return None
    
    # Normalize: lowercase, remove extra whitespace
    normalized = text.lower().strip()
    
    # Too short for reliable detection
    words = normalized.split()
    if len(words) < 3:
        return None
    
    # Language scoring
    scores = {
        'pt': 0,  # Portuguese
        'es': 0,  # Spanish
        'en': 0,  # English
        'de': 0,  # German
        'fr': 0,  # French
    }
    
    # 1. Function word matching
    function_words = {
        'pt': ['de', 'em', 'mais', 'casa', 'para', 'com', 'bem', 'seja', 'uma', 'que',
               'não', 'se', 'como', 'mas', 'ao', 'pela', 'pelo', 'num', 'numa'],
        'es': ['de', 'la', 'el', 'en', 'es', 'y', 'del', 'los', 'las', 'que',
               'con', 'una', 'por', 'se', 'al', 'un', 'lo', 'su', 'para', 'mi'],
        'en': ['the', 'and', 'is', 'in', 'of', 'to', 'a', 'for', 'on', 'this',
               'with', 'are', 'or', 'be', 'an', 'that', 'it', 'as', 'was', 'he'],
        'de': ['der', 'die', 'das', 'und', 'ist', 'in', 'von', 'den', 'dem', 'zu',
               'nicht', 'mit', 'für', 'auf', 'ein', 'sich', 'des', 'auch', 'hat', 'noch'],
        'fr': ['le', 'la', 'les', 'de', 'du', 'des', 'et', 'en', 'est', 'que',
               'une', 'pour', 'pas', 'au', 'sur', 'un', 'il', 'qui', 'ne', 'vous'],
    }
    
    for word in words:
        # Remove punctuation for better matching
        clean_word = word.strip(".,;:!?\"'()[]{}<>")
        for lang, word_list in function_words.items():
            if clean_word in word_list:
                scores[lang] += 2
    
    # 2. Accented character detection (strong indicators)
    char_clues = {
        'pt': ['ã', 'õ', 'ç', 'ê', 'â', 'ô'],  # Portuguese unique
        'es': ['ñ', 'á', 'é', 'í', 'ó', 'ú', 'ü'],  # Spanish unique
        'fr': ['à', 'â', 'ç', 'è', 'é', 'ê', 'ë', 'î', 'ï', 'ô', 'ù', 'û', 'ü'],  # French
        'de': ['ä', 'ö', 'ü', 'ß'],  # German
    }
    
    for lang, chars in char_clues.items():
        for char in chars:
            if char in normalized:
                scores[lang] += 3  # Strong indicator
    
    # 3. Portuguese-specific strong clues
    pt_strong_clues = ['proprio', 'existencia', 'confeitaria', 'fabrica', 'fabrico',
                       'possivel', 'processo', 'conhecimento', 'especifico',
                       'você', 'avô', 'português', 'francês']
    for clue in pt_strong_clues:
        if clue in normalized:
            scores['pt'] += 3
    
    # 4. Spanish-specific strong clues
    es_strong_clues = ['qué', 'cómo', 'dónde', 'cuándo', 'por qué', 'año', 'español',
                       'señor', 'niño', 'mañana', 'llamar', 'llegar', 'calle']
    for clue in es_strong_clues:
        if clue in normalized:
            scores['es'] += 3
    
    # Determine winner
    max_score = max(scores.values())
    if max_score < 3:  # Confidence threshold
        return None
    
    # Get language with highest score
    detected = max(scores.items(), key=lambda x: x[1])
    return detected[0]  # Return language code


def detect_text_roi(pil_image):
    """
    Detect likely text region in image using simple heuristics.
    Input image is already preprocessed (CLAHE, resized, deskewed).
    Returns (roi_pil_image, roi_info_dict)
    """
    try:
        import numpy as np
        cv_image = np.array(pil_image)
        
        # Guard against mock/non-array inputs
        if not isinstance(cv_image, np.ndarray) or cv_image.ndim < 2 or cv_image.size == 0:
            raise ValueError("Invalid image array")
        
        # Handle grayscale input from preprocessing
        if cv_image.ndim == 3:
            gray = cv2.cvtColor(cv_image, cv2.COLOR_RGB2GRAY)
        else:
            gray = cv_image
        
        if gray.ndim != 2:
            raise ValueError("Non-2D grayscale array")
        
        h, w = gray.shape[:2]
        original_size = (w, h)
        
        # Edge detection using Canny instead of adaptive threshold
        # Canny works better for finding sign boundaries in real-world photos
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 30, 120)
        
        # Dilate edges to close gaps
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        dilated = cv2.dilate(edges, kernel, iterations=2)
        
        # Find contours
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        best_contour = None
        best_score = 0
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 1000 or area > h * w * 0.9:
                continue
            
            x, y, rect_w, rect_h = cv2.boundingRect(contour)
            area_ratio = area / (h * w)
            aspect_ratio = rect_w / max(rect_h, 1)
            
            if aspect_ratio < 0.3 or aspect_ratio > 4.0:
                continue
            
            center_x = x + rect_w / 2
            center_y = y + rect_h / 2
            dist_to_center = np.sqrt((center_x - w/2)**2 + (center_y - h/2)**2)
            max_dist = np.sqrt((w/2)**2 + (h/2)**2)
            center_score = 1.0 - (dist_to_center / max_dist)
            area_score = 1.0 - abs(0.5 - area_ratio) * 2.0
            aspect_score = 1.0 - min(abs(1.5 - aspect_ratio), 1.0)
            score = center_score * 0.4 + area_score * 0.3 + aspect_score * 0.3
            
            if score > best_score:
                best_score = score
                best_contour = contour
        
        if best_contour and best_score > 0.4:
            x, y, rect_w, rect_h = cv2.boundingRect(best_contour)
            pad_x = max(int(rect_w * 0.08), 8)
            pad_y = max(int(rect_h * 0.08), 8)
            x = max(0, x - pad_x)
            y = max(0, y - pad_y)
            rect_w = min(w - x, rect_w + 2 * pad_x)
            rect_h = min(h - y, rect_h + 2 * pad_y)
            
            if rect_w >= 50 and rect_h >= 50:
                roi = gray[y:y+rect_h, x:x+rect_w]
                roi_pil = Image.fromarray(roi)
                roi_info = {
                    "method": "contour",
                    "confidence": round(best_score, 2),
                    "original_size": original_size,
                    "roi_size": (rect_w, rect_h),
                    "roi_position": (x, y),
                    "area_ratio": round(rect_w * rect_h / (w * h), 2)
                }
                return roi_pil, roi_info
        
        # Fallback: central crop (15% from each side)
        margin_x = int(w * 0.15)
        margin_y = int(h * 0.15)
        if margin_x * 2 < w and margin_y * 2 < h:
            roi = gray[margin_y:h-margin_y, margin_x:w-margin_x]
            roi_pil = Image.fromarray(roi)
            roi_info = {
                "method": "central",
                "confidence": 0.3,
                "original_size": original_size,
                "roi_size": (w - 2*margin_x, h - 2*margin_y),
                "roi_position": (margin_x, margin_y),
            }
            return roi_pil, roi_info
        
    except Exception as e:
        logger.warning(f"ROI detection failed: {e}")
    
    # Final fallback: original image
    roi_info = {
        "method": "original",
        "confidence": 0.0,
        "original_size": (pil_image.width, pil_image.height),
        "roi_size": (pil_image.width, pil_image.height),
        "roi_position": (0, 0),
        "reason": "fallback"
    }
    return pil_image, roi_info


def run_best_effort_ocr(pil_image):
    # Step 1: Preprocess (resize, CLAHE, deskew)
    preprocessed, pre_info = preprocess_for_ocr(pil_image)
    
    # Step 2: Detect ROI for better OCR accuracy
    roi_pil, roi_info = detect_text_roi(preprocessed)
    
    # Log preprocessing and ROI decisions
    if DEBUG_OCR:
        logger.info(f"Preprocess: orig={pre_info.get('original_dims')}, "
                   f"resized={pre_info.get('resized_dims')}, "
                   f"deskew={pre_info.get('deskew_rotation', 'none')}")
        logger.info(f"ROI detection: method={roi_info.get('method')}, "
                   f"confidence={roi_info.get('confidence')}, "
                   f"original={roi_info.get('original_size')}, "
                   f"roi={roi_info.get('roi_size')}")
    
    # Step 3: Build OCR variants from ROI
    variants = build_ocr_variants(roi_pil)

    # Diverse language candidates for real-world photos (signs, labels, notices)
    # Use multiple language packs in order of global sign prevalence
    lang_candidates = [
        "eng",           # English (default for most signs)
        "eng+spa",       # Spanish (very common)
        "eng+fra",       # French
        "eng+deu",       # German (was missing!)
        "eng+por",       # Portuguese
        "eng+ita",       # Italian
        "eng+nld",       # Dutch
    ]
    psm_candidates = [6, 11]  # 6=uniform block, 11=sparse text

    best = {
        "text": "",
        "score": -1,
        "confidence": 0.0,
        "lang": "unknown",
        "variant": "original",
        "psm": 6,
    }

    # Track if we found a high-confidence result for early exit
    high_confidence_found = False

    for variant_name, variant_img in variants.items():
        if high_confidence_found:
            if DEBUG_OCR:
                logger.info(f"Early exit: skipping remaining variants")
            break
            
        for lang in lang_candidates:
            if high_confidence_found:
                break
                
            for psm in psm_candidates:
                if high_confidence_found:
                    break
                    
                config = f"--oem 3 --psm {psm}"
                try:
                    data = pytesseract.image_to_data(
                        variant_img,
                        lang=lang,
                        config=config,
                        output_type=pytesseract.Output.DICT
                    )

                    n = len(data.get("text", []))
                    lines = {}
                    for i in range(n):
                        raw_txt = data["text"][i] or ""
                        txt = raw_txt.strip()
                        if not txt:
                            continue
                        try:
                            ln = int(data.get("line_num", [0])[i])
                        except Exception:
                            ln = 0
                        try:
                            left = int(data.get("left", [0])[i])
                        except Exception:
                            left = 0
                        try:
                            c = float(data.get("conf", ["-1"])[i])
                        except Exception:
                            c = -1.0
                        if ln not in lines:
                            lines[ln] = []
                        lines[ln].append((left, txt, c))

                    line_texts = []
                    line_confs = []
                    for ln in sorted(lines.keys()):
                        words = sorted(lines[ln], key=lambda x: x[0])
                        texts = [w[1] for w in words]
                        confs = [w[2] for w in words if w[2] >= 0]
                        if not texts:
                            continue

                        avg_conf = sum(confs) / len(confs) if confs else -1.0
                        line_text = " ".join(texts).strip()

                        alpha_words = [t for t in texts if sum(ch.isalpha() for ch in t) >= 2]
                        alpha_chars = sum(ch.isalpha() for ch in line_text)

                        keep_line = False
                        if avg_conf < 0:
                            keep_line = alpha_chars >= 6 and len(alpha_words) >= 2
                        elif avg_conf >= 55:
                            keep_line = alpha_chars >= 4
                        elif avg_conf >= 40:
                            keep_line = alpha_chars >= 6 and len(alpha_words) >= 2

                        if keep_line:
                            line_texts.append(line_text)
                            if avg_conf >= 0:
                                line_confs.append(avg_conf)

                    text = "\n".join(line_texts).strip()
                    if line_confs:
                        conf = sum(line_confs) / len(line_confs)
                    else:
                        conf = average_confidence(data)

                    score = score_ocr_text(text) + conf + language_word_bonus(text, lang)
                    if score > best["score"]:
                        best = {
                            "text": text,
                            "score": score,
                            "confidence": conf,
                            "lang": lang,
                            "variant": variant_name,
                            "psm": psm,
                            "roi_method": roi_info.get("method"),
                            "roi_confidence": roi_info.get("confidence"),
                            "roi_size": roi_info.get("roi_size"),
                            "original_size": roi_info.get("original_size"),
                            "preprocessing": pre_info,
                        }

                        if conf >= 85 and score >= 80:
                            high_confidence_found = True
                            if DEBUG_OCR:
                                logger.info(f"Early exit: confidence={conf:.1f}%, score={score:.1f}")
                        elif conf >= 90:
                            high_confidence_found = True
                            if DEBUG_OCR:
                                logger.info(f"Early exit: very high confidence={conf:.1f}%")
                except Exception:
                    pass

    detected_language = "unknown"
    if best["lang"] != "unknown":
        parts = best["lang"].split("+")
        detected_language = parts[-1] if len(parts) > 1 else parts[0]

    best_text = best["text"].strip()
    
    if detected_language == "unknown" or not detected_language:
        fallback_lang = detect_language_from_ocr_text(best_text)
        if fallback_lang:
            detected_language = fallback_lang
    
    quality = ocr_quality_from_score(best.get("score", 0.0), best.get("confidence", 0.0), best_text)
    best["quality"] = quality
    
    return debug_ocr_flow(best_text, detected_language, best)


app = FastAPI(
    title="Document Explainer API",
    description="Backend API for document photo analysis, translation, and plain-language explanation",
    version="1.0.0",
    docs_url=None,
    redoc_url=None
)

# Demo access key — protects internal endpoints from public use
# Set DEMO_ADMIN_KEY in .env or default to a non-guessable string
DEMO_ADMIN_KEY = os.getenv("DEMO_ADMIN_KEY", "change-me-in-production")

# Add no-cache middleware for static assets
class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

app.add_middleware(NoCacheMiddleware)

# Mount static files for frontend
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Constants
DATA_DIR = str(BASE_DIR / "data")
UPLOADS_DIR = str(BASE_DIR / "data" / "uploads")
DOCUMENTS_FILE = str(BASE_DIR / "data" / "documents.json")

# OCR Configuration
# Supported languages: English, Spanish, French, German, Portuguese, Italian, Chinese (Simplified)
# Format: language codes separated by '+' for multi-language OCR
OCR_LANGS = "eng+spa+fra+deu+por+ita+chi_sim"


# Enums
class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentSourceType(str, Enum):
    TEXT_FILE = "text_file"
    IMAGE_FILE = "image_file"
    UNSUPPORTED = "unsupported"


# Data models
class DocumentBase(BaseModel):
    """Base model for document metadata"""
    filename: str
    content_type: str
    stored_path: str
    source_type: DocumentSourceType
    status: DocumentStatus = DocumentStatus.UPLOADED
    detected_language: Optional[str] = None
    ocr_confidence: Optional[float] = None
    ocr_quality: Optional[str] = None
    ocr_status: Optional[str] = None  # New: "low_quality", "good", "no_text"
    retake_tips: Optional[str] = None  # New: AI-generated tips for retaking photo
    translation_skipped: Optional[bool] = None  # New: True if translation skipped due to low quality
    reason: Optional[str] = None  # New: Reason for skipping translation
    # Document understanding fields
    document_analysis_enabled: Optional[bool] = None
    document_type: Optional[str] = None
    document_type_confidence: Optional[str] = None  # high / medium / low
    document_summary: Optional[str] = None
    key_details: Optional[List[dict]] = None
    amount_due: Optional[str] = None
    due_date: Optional[str] = None
    sender_name: Optional[str] = None
    reference_number: Optional[str] = None
    suggested_actions: Optional[List[str]] = None
    confidence_notes: Optional[str] = None
    analysis_skipped: Optional[bool] = None
    analysis_skipped_reason: Optional[str] = None
    # Extended document analysis fields
    appointment_date: Optional[str] = None
    appointment_time: Optional[str] = None
    appointment_location: Optional[str] = None
    provider_name: Optional[str] = None
    patient_name: Optional[str] = None
    bill_period_start: Optional[str] = None
    bill_period_end: Optional[str] = None
    statement_date: Optional[str] = None
    balance_previous: Optional[str] = None
    payments_since_last: Optional[str] = None
    response_deadline: Optional[str] = None
    case_number: Optional[str] = None
    form_identifier: Optional[str] = None
    # Sign / general text image fields
    sign_type_description: Optional[str] = None
    visible_text: Optional[str] = None
    hazard_level: Optional[str] = None
    location_context: Optional[str] = None
    target_language: Optional[str] = None
    extracted_text: Optional[str] = None
    translated_text: Optional[str] = None
    explanation: Optional[str] = None
    disclaimer: str = "This is an automated explanation and not legal advice. Always consult a professional for important matters."


class TranslationRequest(BaseModel):
    """Request model for document translation"""
    target_language: str
    source_language_hint: Optional[str] = None
    explanation_style: str = "default"


class Document(DocumentBase):
    """Full document model with metadata"""
    id: str
    created_at: str


class DocumentResponse(Document):
    """Response model for document endpoints"""
    pass


# Helper functions for JSON persistence
def ensure_directories():
    """Ensure data and uploads directories exist"""
    os.makedirs(UPLOADS_DIR, exist_ok=True)


def load_documents() -> List[Document]:
    """Load all documents from JSON file"""
    ensure_directories()
    
    if not os.path.exists(DOCUMENTS_FILE):
        return []
    
    try:
        with open(DOCUMENTS_FILE, 'r') as f:
            data = json.load(f)
            return [Document(**doc) for doc in data]
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_documents(documents: List[Document]):
    """Save documents to JSON file"""
    ensure_directories()
    
    # Convert Document objects to dictionaries
    docs_data = []
    for doc in documents:
        doc_dict = doc.model_dump()
        docs_data.append(doc_dict)
    
    with open(DOCUMENTS_FILE, 'w') as f:
        json.dump(docs_data, f, indent=2)


def get_document_by_id(doc_id: str) -> Optional[Document]:
    """Get a document by ID"""
    documents = load_documents()
    for doc in documents:
        if doc.id == doc_id:
            return doc
    return None


def update_document(doc_id: str, updates: dict):
    """Update a document with new values"""
    documents = load_documents()
    
    for i, doc in enumerate(documents):
        if doc.id == doc_id:
            # Update the document with new values
            for key, value in updates.items():
                setattr(documents[i], key, value)
            save_documents(documents)
            return True
    
    return False


def get_source_type_from_filename(filename: str) -> DocumentSourceType:
    """Determine document source type from file extension"""
    if not filename:
        return DocumentSourceType.UNSUPPORTED
    
    file_ext = os.path.splitext(filename)[1].lower()
    
    if file_ext == '.txt':
        return DocumentSourceType.TEXT_FILE
    elif file_ext in ['.png', '.jpg', '.jpeg']:
        return DocumentSourceType.IMAGE_FILE
    else:
        return DocumentSourceType.UNSUPPORTED


def save_uploaded_file(file: UploadFile) -> str:
    """Save uploaded file to disk and return stored path"""
    ensure_directories()

    file_ext = os.path.splitext(file.filename)[1] if file.filename else ""
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    stored_path = os.path.join(UPLOADS_DIR, unique_filename)

    with open(stored_path, "wb") as buffer:
        for chunk in iter(lambda: file.file.read(1024 * 1024), b""):
            buffer.write(chunk)

    return stored_path


def process_document_background(doc_id: str, stored_path: str, filename: str):
    """
    Background task to process uploaded document with robust error handling.
    Guarantees document status is always updated to COMPLETED or FAILED.
    """
    
    # Start timing
    start_time = time.time()
    ocr_time = 0
    translation_time = 0
    
    logger.info(f"Starting background processing for document {doc_id}: {filename}")
    
    try:
        # Update status to processing
        update_document(doc_id, {"status": DocumentStatus.PROCESSING})
        
        # Check file extension
        file_ext = os.path.splitext(filename)[1].lower()
        
        if file_ext == '.txt':
            # Process .txt file
            try:
                with open(stored_path, 'r', encoding='utf-8') as f:
                    text_content = f.read()
                
                word_count = len(text_content.split())
                extracted_text = text_content
                explanation = f"Text document with {word_count} words."
                detected_language = "unknown"
                
                updates = {
                    "status": DocumentStatus.COMPLETED,
                    "extracted_text": extracted_text,
                    "translated_text": None,
                    "explanation": explanation,
                    "detected_language": detected_language
                }
                
                # Apply updates
                update_document(doc_id, updates)
                logger.info(f"Background processing COMPLETED for document {doc_id}: text file with {word_count} words")
                
            except Exception as e:
                logger.error(f"Text file processing failed for {filename}: {e}", exc_info=True)
                raise  # Re-raise to be caught by outer except
            
        elif file_ext in ['.png', '.jpg', '.jpeg']:
            # Process image file with OCR
            if not OCR_AVAILABLE:
                # OCR dependencies not installed
                updates = {
                    "status": DocumentStatus.FAILED,
                    "explanation": "OCR processing requires pytesseract and Pillow. Install with: pip install pytesseract pillow and ensure Tesseract OCR is installed on the system with language packs."
                }
                update_document(doc_id, updates)
                logger.error(f"Background processing FAILED for document {doc_id}: OCR dependencies not installed")
                
            else:
                try:
                    # Open and process image
                    image = Image.open(stored_path)
                    
                    # First check if we can read the image at all
                    image.verify()  # Verify image integrity
                    image = Image.open(stored_path)  # Reopen after verify
                    
                    # Use improved OCR with language detection
                    ocr_start = time.time()
                    best_text, detected_language, best = run_best_effort_ocr(image)
                    ocr_time = (time.time() - ocr_start) * 1000  # Convert to ms
                    
                    if not best_text or not best_text.strip():
                        # No text found in image
                        updates = {
                            "status": DocumentStatus.COMPLETED,  # Completed but empty
                            "extracted_text": "",
                            "translated_text": None,
                            "explanation": "OCR found no text in the image.",
                            "detected_language": "unknown",
                            "ocr_confidence": 0.0,
                            "ocr_quality": "low",
                            "ocr_status": "no_text",
                            # Document analysis fields
                            "document_analysis_enabled": True,
                            "analysis_skipped": True,
                            "analysis_skipped_reason": "no_text_found",
                            "document_type": "unknown_document",
                            "document_type_confidence": "low",
                            "document_summary": "No text detected in the image.",
                            "key_details": None,
                            "amount_due": None,
                            "due_date": None,
                            "sender_name": None,
                            "reference_number": None,
                            "suggested_actions": ["Take the photo again closer to the text.", "Make sure there's even lighting without glare."],
                            "confidence_notes": "No readable text found in this photo.",
                            "appointment_date": None,
                            "appointment_time": None,
                            "appointment_location": None,
                            "provider_name": None,
                            "patient_name": None,
                            "bill_period_start": None,
                            "bill_period_end": None,
                            "statement_date": None,
                            "balance_previous": None,
                            "payments_since_last": None,
                            "response_deadline": None,
                            "case_number": None,
"form_identifier": None,
                            "sign_type_description": None,
                            "visible_text": None,
                            "hazard_level": None,
                            "location_context": None
                        }
                        update_document(doc_id, updates)
                        
                        # Log timing for empty OCR results
                        total_time = (time.time() - start_time) * 1000
                        logger.info(f"Timing: doc {doc_id} total={total_time:.0f} ms, ocr={ocr_time:.0f} ms, translation=0 ms")
                        
                        logger.info(f"Background processing COMPLETED for document {doc_id}: no text found in image")
                        
                    else:
                        # Text found successfully
                        explanation = f"Text extracted with {best.get('quality', 'unknown')} quality using {best.get('lang', 'unknown')} language model."
                        
                        # Perform document analysis if OCR quality is acceptable
                        analysis_updates = {
                            "document_analysis_enabled": True,
                            "analysis_skipped": False,
                            "analysis_skipped_reason": None
                        }
                        
                        # Check if OCR quality is good enough for analysis
                        # For boards/menus with meaningful text, relax both gates
                        has_meaningful_text = best_text and len(best_text.strip()) >= 40 and best.get("confidence", 0) >= 45
                        
                        if has_meaningful_text:
                            # Has meaningful dense text — allow analysis with relaxed gates
                            quality_ok = True
                            conf_ok = True
                        else:
                            quality_ok = best.get("quality") not in ("low", None)
                            conf_ok = best.get("confidence", 0) >= 60
                        
                        if quality_ok and conf_ok:
                            try:
                                logger.info(f"Starting document analysis for document {doc_id}")
                                analysis_start = time.time()
                                # Run async function in sync context
                                import asyncio
                                analysis_result = asyncio.run(analyze_document_content(best_text))
                                analysis_time = (time.time() - analysis_start) * 1000
                                logger.info(f"Document analysis completed in {analysis_time:.0f} ms")
                                
                                # Add analysis results to updates
                                analysis_updates.update({
                                    "document_type": analysis_result.get("document_type"),
                                    "document_type_confidence": analysis_result.get("document_type_confidence"),
                                    "document_summary": analysis_result.get("document_summary"),
                                    "key_details": analysis_result.get("key_details"),
                                    "amount_due": analysis_result.get("amount_due"),
                                    "due_date": analysis_result.get("due_date"),
                                    "sender_name": analysis_result.get("sender_name"),
                                    "reference_number": analysis_result.get("reference_number"),
                                    "suggested_actions": analysis_result.get("suggested_actions"),
                                    "confidence_notes": analysis_result.get("confidence_notes"),
                                    "appointment_date": analysis_result.get("appointment_date"),
                                    "appointment_time": analysis_result.get("appointment_time"),
                                    "appointment_location": analysis_result.get("appointment_location"),
                                    "provider_name": analysis_result.get("provider_name"),
                                    "patient_name": analysis_result.get("patient_name"),
                                    "bill_period_start": analysis_result.get("bill_period_start"),
                                    "bill_period_end": analysis_result.get("bill_period_end"),
                                    "statement_date": analysis_result.get("statement_date"),
                                    "balance_previous": analysis_result.get("balance_previous"),
                                    "payments_since_last": analysis_result.get("payments_since_last"),
                                    "response_deadline": analysis_result.get("response_deadline"),
                                    "case_number": analysis_result.get("case_number"),
                                    "form_identifier": analysis_result.get("form_identifier")
                                })
                                
                            except Exception as analysis_error:
                                logger.error(f"Document analysis failed for {doc_id}: {analysis_error}", exc_info=True)
                                analysis_updates.update({
                                    "document_type": "unknown_document",
                                    "document_type_confidence": "low",
                                    "document_summary": "We weren't able to analyze this document at this time. The text was read but couldn't be classified.",
                                    "key_details": None,
                                    "amount_due": None,
                                    "due_date": None,
                                    "sender_name": None,
                                    "reference_number": None,
                                    "suggested_actions": ["Try uploading the photo again.", "If the problem continues, the image may be too complex for automatic analysis."],
                                    "confidence_notes": "Analysis service encountered an error.",
                                    "appointment_date": None,
                                    "appointment_time": None,
                                    "appointment_location": None,
                                    "provider_name": None,
                                    "patient_name": None,
                                    "bill_period_start": None,
                                    "bill_period_end": None,
                                    "statement_date": None,
                                    "balance_previous": None,
                                    "payments_since_last": None,
                                    "response_deadline": None,
                                    "case_number": None,
"form_identifier": None,
                            "sign_type_description": None,
                            "visible_text": None,
                            "hazard_level": None,
                            "location_context": None
                                })
                        else:
                            # OCR quality too low for analysis
                            logger.info(f"Skipping document analysis for {doc_id} due to low OCR quality")
                            analysis_updates.update({
                                "analysis_skipped": True,
                                "analysis_skipped_reason": "low_ocr_quality",
                                "document_type": "unknown_document",
                                "document_type_confidence": "low",
                                "document_summary": "The text in this photo is too blurry or unclear for us to identify what kind of document it is. Try retaking the photo in better light.",
                                "key_details": None,
                                "amount_due": None,
                                "due_date": None,
                                "sender_name": None,
                                "reference_number": None,
                                "suggested_actions": ["Take the photo again in better lighting.", "Make sure the text fills most of the frame."],
                                "confidence_notes": "Low OCR confidence prevents detailed analysis.",
                                "appointment_date": None,
                                "appointment_time": None,
                                "appointment_location": None,
                                "provider_name": None,
                                "patient_name": None,
                                "bill_period_start": None,
                                "bill_period_end": None,
                                "statement_date": None,
                                "balance_previous": None,
                                "payments_since_last": None,
                                "response_deadline": None,
                                "case_number": None,
"form_identifier": None,
                            "sign_type_description": None,
                            "visible_text": None,
                            "hazard_level": None,
                            "location_context": None
                            })
                        
                        updates = {
                            "status": DocumentStatus.COMPLETED,
                            "extracted_text": best_text,
                            "translated_text": None,
                            "explanation": explanation,
                            "detected_language": detected_language,
                            "ocr_confidence": best.get("confidence"),
                            "ocr_quality": best.get("quality"),
                            "ocr_status": "good"  # Will be re-evaluated in translate_document
                        }
                        # Merge analysis updates
                        updates.update(analysis_updates)
                        
                        # Apply updates
                        update_document(doc_id, updates)
                        
                        # Debug logging
                        logger.info(f"Background processing COMPLETED for document {doc_id}")
                        logger.info(f"  - Filename: {filename}")
                        logger.info(f"  - Language: {detected_language}")
                        logger.info(f"  - Confidence: {best.get('confidence')}")
                        logger.info(f"  - Quality: {best.get('quality')}")
                        logger.info(f"  - Text preview: {best_text[:100]}...")
                        
                        # Log timing for successful OCR (no translation yet)
                        total_time = (time.time() - start_time) * 1000
                        logger.info(f"Timing: doc {doc_id} total={total_time:.0f} ms, ocr={ocr_time:.0f} ms, translation=0 ms")
                        
                except Exception as ocr_error:
                    # OCR processing failed
                    logger.error(f"Background processing FAILED for document {doc_id}: OCR error", exc_info=True)
                    error_msg = str(ocr_error)
                    # Check if it's a language pack error
                    if "language" in error_msg.lower() or "lang" in error_msg.lower():
                        error_msg += " (Language packs may not be installed. See README for installation instructions.)"
                    
                    updates = {
                        "status": DocumentStatus.FAILED,
                        "explanation": f"OCR processing failed: {error_msg}",
                        "extracted_text": None,
                        "translated_text": None,
                        "detected_language": "unknown",
                        "ocr_confidence": None,
                        "ocr_quality": None
                    }
                    update_document(doc_id, updates)
                    
                    # Log timing for failed OCR
                    total_time = (time.time() - start_time) * 1000
                    logger.info(f"Timing: doc {doc_id} total={total_time:.0f} ms, ocr={ocr_time:.0f} ms, translation=0 ms (FAILED)")
                    
        else:
            # Unsupported file type
            updates = {
                "status": DocumentStatus.FAILED,
                "explanation": f"File type '{file_ext}' is not supported. Supported types: .txt, .png, .jpg, .jpeg"
            }
            update_document(doc_id, updates)
            logger.error(f"Background processing FAILED for document {doc_id}: unsupported file type {file_ext}")
        
    except Exception as e:
        # Catch-all for any unhandled exception
        logger.error(f"Background processing CRITICAL FAILURE for document {doc_id}: {e}", exc_info=True)
        
        # Last-ditch attempt to update status
        try:
            update_document(doc_id, {
                "status": DocumentStatus.FAILED,
                "explanation": f"Critical processing failure: {str(e)[:200]}"
            })
        except Exception as update_error:
            # Even updating the status failed - log but can't do more
            logger.critical(f"Cannot update document status for {doc_id}: {update_error}")
        
        # Log timing for critical failure
        total_time = (time.time() - start_time) * 1000
        logger.info(f"Timing: doc {doc_id} total={total_time:.0f} ms (CRITICAL FAILURE)")
        
        # Re-raise to ensure FastAPI logs it
        raise


# Endpoints
@app.get("/")
async def root_redirect(request: Request):
    """Redirect root to the frontend app"""
    logger.info("Root redirect: / -> /static/index.html")
    from starlette.responses import RedirectResponse
    return RedirectResponse(url="/static/index.html")


@app.get("/health")
async def health_check(request: Request):
    """Simple health check endpoint"""
    return {"status": "ok"}


# Allowed file extensions and corresponding MIME types
ALLOWED_EXTENSIONS = {'.txt', '.png', '.jpg', '.jpeg'}
ALLOWED_IMAGE_MIMES = {'image/png', 'image/jpeg'}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_TEXT_BYTES = 5 * 1024 * 1024


@app.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    request: Request = None
):
    """Upload a document for processing"""
    
    # Validate filename
    if not file.filename:
        logger.warning("Upload rejected: no filename provided")
        raise HTTPException(status_code=400, detail="Filename is required")
    
    # Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        logger.warning(f"Upload rejected: unsupported type '{file_ext}' for '{file.filename}'")
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{file_ext}'. Allowed: .txt, .png, .jpg, .jpeg"
        )
    
    # Validate content type when present
    if file.content_type:
        ct_lower = file.content_type.lower()
        if file_ext in ALLOWED_IMAGE_MIMES:
            if ct_lower not in ALLOWED_IMAGE_MIMES and "octet-stream" not in ct_lower:
                logger.warning(f"Upload rejected: MIME mismatch '{file.content_type}' for extension '{file_ext}'")
                raise HTTPException(
                    status_code=422,
                    detail=f"Content-Type '{file.content_type}' does not match file extension '{file_ext}'"
                )
    
    # Check file size (max 10MB for images, 5MB for text)
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    is_image = file_ext in {'.png', '.jpg', '.jpeg'}
    if is_image and file_size > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail=f"Photo is too large ({file_size / 1024 / 1024:.0f}MB). Maximum is {MAX_IMAGE_BYTES / 1024 / 1024:.0f}MB.")
    if not is_image and file_size > MAX_TEXT_BYTES:
        raise HTTPException(status_code=413, detail=f"Document is too large ({file_size / 1024 / 1024:.0f}MB). Text files must be under {MAX_TEXT_BYTES / 1024 / 1024:.0f}MB.")
    
    # Save uploaded file
    stored_path = save_uploaded_file(file)
    
    # Create document record
    documents = load_documents()
    
    doc_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    source_type = get_source_type_from_filename(file.filename)
    
    logger.info(f"Upload accepted: id={doc_id[:8]}... name={file.filename} type={source_type} size={file_size}")
    
    document = Document(
        id=doc_id,
        filename=file.filename,
        content_type=file.content_type or "application/octet-stream",
        stored_path=stored_path,
        source_type=source_type,
        status=DocumentStatus.UPLOADED,
        created_at=now
    )
    
    # Save to documents list
    documents.append(document)
    save_documents(documents)
    
    # Trigger background processing
    background_tasks.add_task(
        process_document_background,
        doc_id,
        stored_path,
        file.filename
    )
    
    return document


@app.get("/documents", response_model=List[DocumentResponse])
async def list_documents(x_admin_key: str = Header(None)):
    """List all uploaded documents (admin only — requires X-Admin-Key header)"""
    if x_admin_key != DEMO_ADMIN_KEY:
        logger.warning("List-documents attempt without valid admin key")
        raise HTTPException(status_code=403, detail="Not authorized")
    documents = load_documents()
    logger.info(f"List-documents: returning {len(documents)} docs")
    return documents


@app.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    """Get a specific document by ID (used by frontend to poll processing status)"""
    document = get_document_by_id(document_id)
    if document is None:
        logger.info(f"Get-document miss: id={document_id}")
        raise HTTPException(status_code=404, detail="Document not found")
    logger.debug(f"Get-document hit: id={document_id[:8]}... status={document.status}")
    return document
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
MYMEMORY_EMAIL = os.getenv("MYMEMORY_EMAIL")




def normalize_lang_code(lang: str | None) -> str:
    lang = (lang or "").strip().lower()
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
        "ara": "ar",
        "hin": "hi",
    }
    if not lang or lang in {"unknown", "und", "none", "uncertain"}:
        return ""
    return mapping.get(lang, lang)

async def translate_with_mymemory(text: str, source_lang: str, target_lang: str) -> str | None:
    source_lang = normalize_lang_code(source_lang)
    target_lang = normalize_lang_code(target_lang)

    if not source_lang or source_lang in {"unknown", "und", "none", "auto"}:
        return None
    if source_lang == target_lang:
        return None  # MyMemory returns 'PLEASE SELECT TWO DISTINCT LANGUAGES' for same-lang

    params = {
        "q": text,
        "langpair": f"{source_lang}|{target_lang}",
    }
    if MYMEMORY_EMAIL:
        params["de"] = MYMEMORY_EMAIL

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get("https://api.mymemory.translated.net/get", params=params)
        resp.raise_for_status()
        data = resp.json()

    translated = (data.get("responseData") or {}).get("translatedText", "") or ""
    translated = translated.strip()

    if not translated:
        return None

    if translated.lower() == text.strip().lower():
        return None

    return translated


async def deepseek_chat(system_prompt: str, user_prompt: str) -> str:
    if not DEEPSEEK_API_KEY:
        raise HTTPException(status_code=500, detail="DEEPSEEK_API_KEY is not configured")

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=45) as client:
        resp = await client.post(
            "https://api.deepseek.com/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    return data["choices"][0]["message"]["content"].strip()


async def translate_with_deepseek(text: str, source_lang: str, target_lang: str) -> str:
    return await deepseek_chat(
        system_prompt=(
            "You are a translation engine. Translate accurately and naturally. "
            "Return only the translated text with no notes."
        ),
        user_prompt=f"Translate this text from {source_lang} to {target_lang}:\n\n{text}",
    )


async def explain_with_deepseek(translated_text: str, target_lang: str) -> str:
    return await deepseek_chat(
        system_prompt=(
            "You explain signs, notices, and documents in plain language. "
            "Be accurate, practical, and easy to understand. "
            "Always respond in the requested language. "
            "Return exactly three short labeled sections in this order:\n"
            "1) Meaning - one or two sentences that restate what the text says.\n"
            "2) Why it matters - one or two sentences about the risk or importance.\n"
            "3) What to do - one or two sentences with clear guidance for the reader."
        ),
        user_prompt=(
            f"Explain this text in {target_lang}:\n\n"
            f"{translated_text}\n\n"
            "Follow the three-section format (Meaning, Why it matters, What to do). "
            "Keep each section brief but more informative than a one-line summary."
        ),
    )


def is_low_quality_ocr(extracted_text: str, ocr_quality: str | None, ocr_confidence: float | None) -> bool:
    """
    Determine if OCR results are low quality.
    Returns True if text is unreadable or confidence is too low.
    
    NOTE: This determines whether to FULLY block translation.
    For dense text on boards/menus, we still attempt best-effort even
    if quality is low — the caller checks has_meaningful_text() separately.
    """
    # No text at all
    if not extracted_text or not extracted_text.strip():
        return True
    
    # Text is very short (likely gibberish or partial)
    if len(extracted_text.strip()) < 10:
        return True
    
    # Check if text has enough real words (simple heuristic)
    words = extracted_text.strip().split()
    if len(words) < 2:
        return True
    
    # Count alphabetic characters vs total
    alpha_chars = sum(1 for c in extracted_text if c.isalpha())
    total_chars = len(extracted_text)
    if total_chars > 0 and alpha_chars / total_chars < 0.3:
        return True  # Mostly non-alphabetic characters
    
    # Really low confidence (pure garbage)
    if ocr_confidence is not None and ocr_confidence < 20:
        return True
    
    # For medium/long text with reasonable letter ratio, don't block
    # even if quality is marked "low" — these are boards/menus with partial text
    if extracted_text and len(extracted_text.strip()) >= 40:
        alpha_ratio = sum(1 for c in extracted_text if c.isalpha()) / max(len(extracted_text.strip()), 1)
        if alpha_ratio >= 0.4 and len(extracted_text.strip().split()) >= 5:
            # Has meaningful alphabetic content — don't fully block
            # The caller will still note low confidence
            return False
    
    # OCR quality explicitly marked as low (fallback for short/weak text)
    if ocr_quality == "low":
        return True
    
    # Very low confidence (fallback)
    if ocr_confidence is not None and ocr_confidence < 55:
        return True
    
    return False


async def generate_retake_tips(target_lang: str = "en") -> str:
    """
    Generate AI-powered tips for retaking a better photo.
    """
    try:
        return await deepseek_chat(
            system_prompt=(
                "You are a camera/OCR assistant. Give practical, concise advice "
                "for taking better photos of signs and documents. "
                "Respond in clear, simple language. "
                "Format as 3-4 bullet points, each on its own line starting with • "
                "Keep each tip under 15 words."
            ),
            user_prompt=(
                "The current photo had low OCR quality. In 3-4 short bullet points, "
                "explain how the user should retake the photo of a sign so OCR can read it clearly. "
                "Mention distance, framing, lighting, and focus. Be very practical."
            ),
        )
    except Exception as e:
        logger.error(f"Failed to generate retake tips: {e}")
        # Fallback tips
        fallback_tips = (
            "• Get closer to fill the frame with text\n"
            "• Ensure text is evenly lit without glare\n"
            "• Hold camera steady and parallel to text\n"
            "• Tap on text area to focus before shooting"
        )
        return fallback_tips


async def analyze_document_content(extracted_text: str) -> dict:
    """
    Analyze document content to determine type, extract key details, and generate summary.
    Returns a structured analysis dictionary.
    """
    system_prompt = """You are a document analysis assistant. Analyze the provided OCR text from a document photo.

CRITICAL RULES:
1. Return ONLY raw JSON, no markdown, no explanations, no additional text.
2. Never invent facts not supported by the OCR text.
3. If uncertain, use "appears to be" language and set confidence to "low" or "medium".
4. Leave fields as null if information is not clearly present.
5. For amounts and dates, extract only if clearly stated.
6. Suggested actions must be informational only, not legal/financial/medical advice.
7. Do not state that a user "must" do something unless the document text clearly says so.
8. ALWAYS attempt to extract ALL relevant fields for the document type.
9. For each field, evaluate confidence based on clarity in the OCR text.
10. If a field is ambiguous or missing, set it to null and explain uncertainty in confidence_notes.

IMAGE TYPE CATEGORIES (choose the best match or "unknown_document"):
- utility_bill
- phone_bill
- internet_bill
- medical_bill
- bank_notice
- government_notice
- government_form
- immigration_notice
- receipt
- invoice
- warning_sign (safety hazard / electrical / chemical / construction warnings)
- safety_sign (fire exit, first aid, emergency equipment, PPE signs)
- public_notice (posted rules, announcements, community board notices)
- street_sign (street names, directions, traffic-adjacent informational signs)
- product_label (ingredients, instructions, warnings on products/packages)
- general_text_image (any other photographed text — menus, posters, flyers, hand-written notes)

FIELD EXTRACTION PRIORITIES BY DOCUMENT TYPE:

For appointment reminders / medical notices:
- appointment_date (format: YYYY-MM-DD or original format)
- appointment_time (format: HH:MM AM/PM or original format)
- appointment_location (clinic/facility name or address)
- provider_name
- patient_name (if clearly visible)

For bills (medical, utility, phone, internet, etc.):
- bill_period_start (format: YYYY-MM-DD or original format)
- bill_period_end (format: YYYY-MM-DD or original format)
- statement_date (format: YYYY-MM-DD or original format)
- amount_due (format: $X.XX or original format)
- due_date (format: YYYY-MM-DD or original format)
- balance_previous (format: $X.XX or original format)
- payments_since_last (format: $X.XX or original format)

For government letters/forms:
- response_deadline (format: YYYY-MM-DD or original format)
- case_number
- form_identifier (e.g., "I-130", "I-485", etc.)
- sender_name

For signs/text images (warning_sign, safety_sign, street_sign, public_notice, product_label, general_text_image):
- sign_type_description (e.g., "Electrical hazard warning", "Fire exit sign", "Street name")
- visible_text (the full readable text from the image)
- hazard_level if applicable: "danger", "warning", "caution", "informational", or null
- location_context if identifiable: e.g., "construction site", "electrical panel", "product package"
- sender_name (if one is visible, else null)

For ALL image types:
- sender_name
- reference_number (if applicable, else null)
- document_summary (plain English, 1-3 sentences describing what this image/text is and what it says)
- suggested_actions (2-4 informational steps explaining what the user should understand or do)
- confidence_notes (brief explanation of uncertainty if any)

OUTPUT JSON SCHEMA:
{
  "document_type": "string or null",
  "document_type_confidence": "high/medium/low or null",
  "document_summary": "string or null",
  "key_details": [
    {"label": "string", "value": "string", "confidence": "high/medium/low"}
  ] or null,
  "amount_due": "string or null",
  "due_date": "string or null",
  "sender_name": "string or null",
  "reference_number": "string or null",
  "suggested_actions": ["string"] or null,
  "confidence_notes": "string or null",
  "appointment_date": "string or null",
  "appointment_time": "string or null",
  "appointment_location": "string or null",
  "provider_name": "string or null",
  "patient_name": "string or null",
  "bill_period_start": "string or null",
  "bill_period_end": "string or null",
  "statement_date": "string or null",
  "balance_previous": "string or null",
  "payments_since_last": "string or null",
  "response_deadline": "string or null",
  "case_number": "string or null",
  "form_identifier": "string or null",
  "sign_type_description": "string or null",
  "visible_text": "string or null",
  "hazard_level": "string or null",
  "location_context": "string or null"
}

KEY DETAILS POPULATION (CRITICAL — FOLLOW STRICTLY):
You MUST populate key_details with ALL extracted facts. This is the section users see as "Key Details" in the UI.

If you extract ANY concrete fact (date, time, amount, name, location, identifier, etc.) from the document, it MUST appear in key_details in a human-readable label/value pair.

key_details must NEVER be null or empty when the summary contains concrete facts.

Examples:
- For appointment_date: {"label": "Appointment date", "value": "2026-05-10", "confidence": "high"}
- For amount_due: {"label": "Amount due", "value": "$84.22", "confidence": "high"}
- For case_number: {"label": "Case number", "value": "USCIS-2026-12345", "confidence": "medium"}
- For appointment_time: {"label": "Appointment time", "value": "10:00 AM", "confidence": "high"}
- For appointment_location: {"label": "Location", "value": "Westside Clinic - Room 205", "confidence": "medium"}
- For provider_name: {"label": "Provider", "value": "Dr. Sarah Johnson", "confidence": "high"}
- For patient_name: {"label": "Patient name", "value": "Jane R. Doe", "confidence": "high"}
- For bill_period_start: {"label": "Billing period start", "value": "2026-04-01", "confidence": "medium"}
- For bill_period_end: {"label": "Billing period end", "value": "2026-04-30", "confidence": "medium"}
- For statement_date: {"label": "Statement date", "value": "2026-05-05", "confidence": "medium"}
- For balance_previous: {"label": "Previous balance", "value": "$150.00", "confidence": "medium"}
- For payments_since_last: {"label": "Payments since last statement", "value": "$50.00", "confidence": "medium"}
- For response_deadline: {"label": "Response deadline", "value": "2026-07-30", "confidence": "high"}
- For form_identifier: {"label": "Form", "value": "I-485", "confidence": "high"}
- For sign_type_description: {"label": "Type of sign", "value": "Electrical hazard warning", "confidence": "high"}
- For hazard_level: {"label": "Hazard level", "value": "Danger", "confidence": "high"}
- For visible_text: {"label": "Text on sign", "value": "GEFAHR - Hochspannung Lebensgefahr", "confidence": "high"}
- For location_context: {"label": "Location context", "value": "High-voltage electrical panel", "confidence": "medium"}

RULE: If document_summary mentions dates, amounts, names, or locations, those same facts MUST appear as structured entries in key_details.

Include confidence level for each key detail based on clarity in OCR text."""
    
    user_prompt = f"""Analyze this document OCR text:

{extracted_text}

Follow all rules strictly. Return ONLY the JSON object."""
    
    try:
        # First attempt with strict JSON output
        response = await deepseek_chat(system_prompt, user_prompt)
        
        # Try to parse the JSON
        try:
            analysis = json.loads(response)
            
            # Validate required structure
            required_fields = ["document_type", "document_type_confidence", "document_summary", 
                             "key_details", "amount_due", "due_date", "sender_name", 
                             "reference_number", "suggested_actions", "confidence_notes",
                             "appointment_date", "appointment_time", "appointment_location",
                             "provider_name", "patient_name", "bill_period_start",
                             "bill_period_end", "statement_date", "balance_previous",
                             "payments_since_last", "response_deadline", "case_number",
                             "form_identifier",
                             "sign_type_description", "visible_text", "hazard_level", "location_context"]
            
            # Ensure all fields are present (can be null)
            for field in required_fields:
                if field not in analysis:
                    analysis[field] = None
            
            # Validate key_details structure if present
            if analysis["key_details"]:
                if not isinstance(analysis["key_details"], list):
                    analysis["key_details"] = None
                else:
                    # Ensure each item has required fields
                    valid_details = []
                    for item in analysis["key_details"]:
                        if isinstance(item, dict) and "label" in item and "value" in item and "confidence" in item:
                            valid_details.append(item)
                    analysis["key_details"] = valid_details if valid_details else None
            
            # HARD GUARANTEE: Auto-populate key_details from structured fields if empty.
            # Also parse the summary text using regex as a fallback for facts the AI
            # mentions in prose but didn't put into structured fields.
            if not analysis.get("key_details"):
                auto_details = []
                
                # Step 1: Try structured fields first
                field_mappings = [
                    ("appointment_date", "Appointment date", None),
                    ("appointment_time", "Appointment time", None),
                    ("appointment_location", "Location", None),
                    ("provider_name", "Provider", None),
                    ("patient_name", "Patient name", None),
                    ("amount_due", "Amount due", "high"),
                    ("due_date", "Due date", None),
                    ("bill_period_start", "Billing period start", "medium"),
                    ("bill_period_end", "Billing period end", "medium"),
                    ("statement_date", "Statement date", "medium"),
                    ("balance_previous", "Previous balance", "medium"),
                    ("payments_since_last", "Payments since last statement", "medium"),
                    ("response_deadline", "Response deadline", None),
                    ("case_number", "Case number", None),
                    ("form_identifier", "Form", None),
                    ("sender_name", "Sender", "medium"),
                    ("reference_number", "Reference number", "medium"),
                ]
                
                for field_key, label, default_conf in field_mappings:
                    value = analysis.get(field_key)
                    if value and isinstance(value, str) and value.strip():
                        auto_details.append({
                            "label": label,
                            "value": value,
                            "confidence": default_conf or "medium"
                        })
                
                # Step 2: Parse the summary text with robust regex patterns.
                # This handles the common case where the AI writes facts in prose
                # summary but leaves structured JSON fields null.
                summary = (analysis.get("document_summary") or "").strip()
                doc_type = analysis.get("document_type", "") or ""
                
                # Define extractors as (label, list-of-patterns, fallback_confidence)
                # Each pattern should capture value in group(1) (or group(1)+group(2) for ranges).
                # Patterns are tried in order; first match wins.
                summary_extractors = [
                    ("Amount due", "high", [
                        r'amount due (?:(?:is|of|:)\s*)?\$?([\d,]+(?:\.\d{2})?)',
                        r'(?:you )?owe \$?([\d,]+(?:\.\d{2})?)',
                        r'(?:total|amount)[.:]? \$?([\d,]+(?:\.\d{2})?)',
                    ]),
                    ("Due date", "medium", [
                        r'due date (?:(?:is|of|:)\s*)?([A-Z][a-z]+ \d+,? ?\d{4})',
                        r'due date (?:(?:is|of|:)\s*)?(\d{1,2}/\d{1,2}/\d{4})',
                        r'(?:due|payable) (?:by|on) ([A-Z][a-z]+ \d+,? ?\d{4})',
                    ]),
                    # Service/billing periods (range)
                    ("Service period", "medium", [
                        # Pattern: "... from DateA to DateB" - captures two groups
                        (r'(?:from|between) ([A-Z][a-z]+ \d+)[^\d]+(?:to|and|through|-) ([A-Z][a-z]+ \d+,? ?\d{4})', True),
                        (r'(?:billing|service) period (?:is |of ).*?([A-Z][a-z]+ \d+)[^\d]+(?:to|and|through|-) ([A-Z][a-z]+ \d+,? ?\d{4})', True),
                    ]),
                ]
                
                if summary and len(summary) > 20:
                    for label, conf, pattern_list in summary_extractors:
                        # Skip if already found from structured fields
                        if any(d.get("label", "") == label for d in auto_details):
                            continue
                        
                        for pattern_item in pattern_list:
                            is_range = False
                            if isinstance(pattern_item, tuple):
                                pattern, is_range = pattern_item
                            else:
                                pattern = pattern_item
                            
                            match = re.search(pattern, summary, re.IGNORECASE)
                            if match:
                                if is_range and match.lastindex and match.lastindex >= 2:
                                    value = f"{match.group(1).strip()} - {match.group(2).strip()}"
                                else:
                                    value = match.group(1).strip() if match.lastindex else match.group(0).strip()
                                auto_details.append({"label": label, "value": value, "confidence": conf})
                                break  # stop after first matching pattern for this label
                    
                    # Appointment dates from summary: look for "scheduled for|appointment on Date at Time"
                    appt_date_pat = r'(?:appointment|scheduled) (?:is |for |on )?([A-Z][a-z]+ \d+,? ?\d{4})'
                    appt_time_pat = r'(?:appointment|scheduled|at) (?:for |on |at )?(\d{1,2}:\d{2} ?[AP]M)'
                    appt_loc_pat = r'(?:at|located at|location:?) ([A-Z][a-z]+[A-Za-z ]*(?:Clinic|Hospital|Center|Office|Room \d+))'
                    
                    if not any(d.get("label") == "Appointment date" for d in auto_details):
                        am = re.search(appt_date_pat, summary, re.IGNORECASE)
                        if am:
                            auto_details.append({"label": "Appointment date", "value": am.group(1), "confidence": "medium"})
                    
                    if not any(d.get("label") == "Appointment time" for d in auto_details):
                        atm = re.search(appt_time_pat, summary, re.IGNORECASE)
                        if atm:
                            auto_details.append({"label": "Appointment time", "value": atm.group(1), "confidence": "medium"})
                    
                    if not any(d.get("label") == "Location" for d in auto_details):
                        alm = re.search(appt_loc_pat, summary, re.IGNORECASE)
                        if alm:
                            auto_details.append({"label": "Location", "value": alm.group(1), "confidence": "medium"})
                
                if auto_details:
                    analysis["key_details"] = auto_details
                    logger.info(f"Auto-populated key_details with {len(auto_details)} items from structured fields + summary")
                    if auto_details:
                        logger.info(f"key_details labels: {[d['label'] for d in auto_details]}")
            
            # Validate suggested_actions if present
            if analysis["suggested_actions"]:
                if not isinstance(analysis["suggested_actions"], list):
                    analysis["suggested_actions"] = None
                else:
                    # Ensure all items are strings
                    analysis["suggested_actions"] = [str(action) for action in analysis["suggested_actions"] if action]
            
            return analysis
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse AI response as JSON, attempting repair: {e}")
            
            # Try to extract JSON from the response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    analysis = json.loads(json_match.group())
                    logger.info("Successfully extracted JSON from response")
                    return analysis
                except json.JSONDecodeError:
                    pass
            
            # Fallback to safe default
            logger.error("Could not parse or extract JSON from AI response, using fallback")
            return {
                "document_type": "unknown_document",
                "document_type_confidence": "low",
                "document_summary": "Unable to analyze document content reliably.",
                "key_details": None,
                "amount_due": None,
                "due_date": None,
                "sender_name": None,
                "reference_number": None,
                "suggested_actions": ["Double-check the details below against your original document.", "Some information may not have been fully extracted."],
                "confidence_notes": "Some details may not have been fully extracted due to formatting or layout.",
                "appointment_date": None,
                "appointment_time": None,
                "appointment_location": None,
                "provider_name": None,
                "patient_name": None,
                "bill_period_start": None,
                "bill_period_end": None,
                "statement_date": None,
                "balance_previous": None,
                "payments_since_last": None,
                "response_deadline": None,
                "case_number": None,
"form_identifier": None,
                            "sign_type_description": None,
                            "visible_text": None,
                            "hazard_level": None,
                            "location_context": None
            }
            
    except Exception as e:
        logger.error(f"Document analysis failed: {e}")
        # Safe fallback
        return {
            "document_type": "unknown_document",
            "document_type_confidence": "low",
            "document_summary": "We weren't able to analyze this document at this time. The text was read but couldn't be classified.",
            "key_details": None,
            "amount_due": None,
            "due_date": None,
            "sender_name": None,
            "reference_number": None,
            "suggested_actions": ["Try uploading again.", "If the problem keeps happening, the image may need better lighting."],
            "confidence_notes": "Analysis service was temporarily unavailable.",
            "appointment_date": None,
            "appointment_time": None,
            "appointment_location": None,
            "provider_name": None,
            "patient_name": None,
            "bill_period_start": None,
            "bill_period_end": None,
            "statement_date": None,
            "balance_previous": None,
            "payments_since_last": None,
            "response_deadline": None,
            "case_number": None,
"form_identifier": None,
                            "sign_type_description": None,
                            "visible_text": None,
                            "hazard_level": None,
                            "location_context": None
        }


@app.post("/documents/{document_id}/translate", response_model=DocumentResponse)
async def translate_document(document_id: str, request: TranslationRequest):
    # Start timing for translation
    start_time = time.time()
    mymemory_time = 0
    deepseek_time = 0
    explanation_time = 0
    
    doc = get_document_by_id(document_id)
    if doc is None:
        logger.info(f"Translate miss: id={document_id}")
        raise HTTPException(status_code=404, detail="Document not found")

    if not doc.extracted_text or doc.extracted_text.strip() == "":
        logger.warning(f"Translate blocked: no extracted text for doc {document_id}")
        raise HTTPException(
            status_code=400,
            detail="Cannot translate: no OCR text available for this document."
        )
    
    logger.info(f"Translate start: doc={document_id[:8]}... lang={request.source_language_hint or 'auto'}->{request.target_language}")
    
    # Check if OCR quality is low
    is_low_quality = is_low_quality_ocr(
        doc.extracted_text,
        doc.ocr_quality,
        doc.ocr_confidence
    )
    
    raw_lang = (doc.detected_language or request.source_language_hint or "").strip().lower()
    source_lang = raw_lang if raw_lang and raw_lang not in {"unknown", "und", "none", "auto", "uncertain"} else "auto"
    target_lang = request.target_language

    # --- Best-effort mode for boards/menus/posters with partial but meaningful text ---
    # If quality is low but there's enough alphabetic text, do best-effort translation
    text = doc.extracted_text or ""
    has_meaningful_text = (
        len(text.strip()) >= 40
        and len(text.strip().split()) >= 5
        and sum(1 for c in text if c.isalpha()) / max(len(text.strip()), 1) >= 0.4
    )

    # Also trigger best-effort when background task recorded stale error data
    # (doc was processed before the relaxed-quality gates were added)
    bg_task_stale = (
        not is_low_quality  # OCR is ok now
        and has_meaningful_text
        and doc.document_type == "unknown_document"
        and (doc.confidence_notes or "").startswith("Low OCR")
        and doc.document_summary
        and ("low for reliable" in doc.document_summary or "too blurry" in doc.document_summary or "try retaking" in doc.document_summary)
    )
    
    should_best_effort = (is_low_quality and has_meaningful_text and (doc.ocr_confidence or 0) >= 20) or bg_task_stale

    if should_best_effort:
        # Best-effort: meaningful partial text, attempt translation anyway
        logger.info(f"Best-effort translate: doc {document_id}, text_len={len(text.strip())}, conf={doc.ocr_confidence}")
        is_low_quality = False  # Override — proceed to translation
        
        # Mark as partial quality in confidence notes
        if doc.ocr_quality == "low" or doc.ocr_status in ("low_quality", "low_quality_partial", "good", None) or bg_task_stale:
            new_lang = doc.detected_language
            # Try to detect language from text if ocr detected 'eng' but text is clearly French/Italian/Spanish
            if not new_lang or new_lang == "eng":
                fr_words = ["oignon", "soupe", "boeuf", "confit", "canard", "crème", "brûlée", "escargot", "terrine", "chèvre"]
                it_words = ["bruschetta", "carpaccio", "prosciutto", "carbonara", "risotto", "tiramisu", "lasagna", "fiorentina", "melanzane"]
                es_words = ["feria", "cultura", "concursos", "folklorico", "inauguracion", "gratuita", "baile", "taller"]
                if any(w in text.lower() for w in fr_words):
                    new_lang = "fra"
                elif any(w in text.lower() for w in it_words):
                    new_lang = "ita"
                elif any(w in text.lower() for w in es_words):
                    new_lang = "spa"
            update_document(document_id, {
                "ocr_status": "best_effort",
                "detected_language": new_lang,
                "confidence_notes": "This photo was partially readable. Some lines may be missing or inaccurate due to photo quality."
            })
            doc = get_document_by_id(document_id)

    if is_low_quality:
        # Truly low quality — block with retake tips (unchanged behavior)
        updates_block = {
            "ocr_status": "low_quality",
            "translation_skipped": True,
            "reason": "low_ocr_quality",
            "detected_language": "uncertain",
            "analysis_skipped": True,
            "analysis_skipped_reason": "low_ocr_quality",
            "document_type": "unknown_document",
            "document_type_confidence": "low",
            "document_summary": "The text in this photo is too blurry or unclear for us to translate. Try retaking with better lighting.",
            "key_details": None,
            "amount_due": None,
            "due_date": None,
            "sender_name": None,
            "reference_number": None,
            "suggested_actions": ["Take the photo again in better lighting.", "Make sure the text fills most of the frame."],
            "confidence_notes": "This text was difficult to read and may be incomplete.",
            "appointment_date": None,
            "appointment_time": None,
            "appointment_location": None,
            "provider_name": None,
            "patient_name": None,
            "bill_period_start": None,
            "bill_period_end": None,
            "statement_date": None,
            "balance_previous": None,
            "payments_since_last": None,
            "response_deadline": None,
            "case_number": None,
            "form_identifier": None,
            "sign_type_description": None,
            "visible_text": None,
            "hazard_level": None,
            "location_context": None
        }
        
        if not doc.retake_tips:
            try:
                retake_tips = await generate_retake_tips(target_lang=request.target_language)
                updates_block["retake_tips"] = retake_tips
            except Exception as e:
                logger.error(f"Failed to generate retake tips: {e}")
                updates_block["retake_tips"] = (
                    "\u2022 Get closer to fill the frame with text\n"
                    "\u2022 Ensure text is evenly lit without glare\n"
                    "\u2022 Hold camera steady and parallel to text\n"
                    "\u2022 Tap on text area to focus before shooting"
                )
        
        update_document(document_id, updates_block)
        
        blocked_text = "Text not clear enough for accurate translation.\n\n"
        if doc.retake_tips or updates_block.get("retake_tips"):
            blocked_text += f"Tips for better photos:\n{updates_block.get('retake_tips') or doc.retake_tips}"
        else:
            blocked_text += (
                "Tips for better photos:\n"
                "\u2022 Get closer to fill the frame with text\n"
                "\u2022 Ensure text is evenly lit without glare\n"
                "\u2022 Hold camera steady and parallel to text\n"
                "\u2022 Tap on text area to focus before shooting"
            )
        
        updates_response = {
            "target_language": target_lang,
            "translated_text": blocked_text,
            "explanation": "The text in this photo is too blurry or unclear for translation. Tips below can help you get a better photo.",
            "translation_skipped": True,
            "reason": "low_ocr_quality",
        }
        if not update_document(document_id, updates_response):
            raise HTTPException(status_code=500, detail="Failed to update document")
        
        total_time = (time.time() - start_time) * 1000
        logger.info(f"Translation timing: doc {document_id} total={total_time:.0f} ms (BLOCKED-low-quality)")
        
        return get_document_by_id(document_id)
    
    # --- Normal path: OCR quality is acceptable or best-effort override ---
    if not doc.ocr_status or doc.ocr_status in ("low_quality", "low_quality_partial"):
        update_document(document_id, {"ocr_status": "good"})
        doc = get_document_by_id(document_id)

    translated_text = None
    explanation = None
    
    # Try MyMemory translation first (free) — skip if source == target
    # MyMemory returns 'PLEASE SELECT TWO DISTINCT LANGUAGES' which is useless
    if source_lang != "auto" and source_lang != target_lang:
        mymemory_start = time.time()
        translated_text = await translate_with_mymemory(
            doc.extracted_text,
            source_lang,
            target_lang
        )
        mymemory_time = (time.time() - mymemory_start) * 1000
    
    # If MyMemory failed or auto language, try DeepSeek
    if not translated_text:
        try:
            deepseek_start = time.time()
            translated_text = await translate_with_deepseek(
                doc.extracted_text,
                normalize_lang_code(source_lang) if source_lang != "auto" else "unknown",
                normalize_lang_code(target_lang)
            )
            deepseek_time = (time.time() - deepseek_start) * 1000
        except Exception as e:
            logger.error(f"DeepSeek translation failed: {e}")
            translated_text = f"[{target_lang}] " + doc.extracted_text[:500]
    
    # Generate explanation
    if translated_text and not translated_text.startswith(f"[{target_lang}]"):
        try:
            explanation_start = time.time()
            explanation = await explain_with_deepseek(translated_text, target_lang)
            explanation_time = (time.time() - explanation_start) * 1000
        except Exception as e:
            logger.error(f"DeepSeek explanation failed: {e}")
            explanation = f"Automated explanation in {target_lang} based on OCR text."
    else:
        explanation = f"Placeholder translation in {target_lang}. Real translation requires valid source language detection."

    # After explanation generation, re-read doc to get latest confidence_notes
    # (the background task may have set them since our initial fetch)
    latest_doc = get_document_by_id(document_id)
    final_conf_notes = latest_doc.confidence_notes if latest_doc else doc.confidence_notes
    
    # Override confidence_notes for best-effort docs
    if latest_doc and latest_doc.ocr_status == "best_effort":
        final_conf_notes = "This photo was partially readable. Some text may be missing or inaccurate due to photo quality."
    
    updates = {
        "target_language": target_lang,
        "translated_text": translated_text,
        "explanation": explanation,
        "translation_skipped": False,
        "reason": None,
        "confidence_notes": final_conf_notes,
    }

    if not update_document(document_id, updates):
        raise HTTPException(status_code=500, detail="Failed to update document")

    total_time = (time.time() - start_time) * 1000
    logger.info(f"Translation timing: doc {document_id} total={total_time:.0f} ms, "
               f"mymemory={mymemory_time:.0f} ms, deepseek={deepseek_time:.0f} ms, "
               f"explanation={explanation_time:.0f} ms")

    return get_document_by_id(document_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
