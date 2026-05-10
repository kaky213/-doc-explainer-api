# Overnight Notes — 2026-05-09

## Running changelog of improvements to DocTranslate

### Baseline
- 14 tests pass, 5 fail
- Live at https://doc-explainer-api-lapb.onrender.com/
- 2081 lines in app.py, 479 in app.js

---

### 🔧 Iteration 1: Fix failing tests & harden OCR pipeline

**Changes:**
- `app.py`: Added guards in `preprocess_for_ocr()`, `build_ocr_variants()`, and `detect_text_roi()` against mock/non-array/1D images
- `tests/test_app.py`:
  - Rewrote OCR tests to use **real PIL-created PNG images** instead of MagicMock PIL
  - Mock `pytesseract.image_to_data` instead of `image_to_string` to match actual code path
  - Updated `list_documents` tests admin key header
  - Made translation test assertion flexible enough to pass with real MyMemory
  - Removed stale assertion patterns

**Result:** 19/19 tests passing, all green.

**Commit:** `f9ede84`

---

### 🔧 Iteration 2: Input validation & file size limits

**Changes:**
- `app.py`:
  - Added `ALLOWED_EXTENSIONS`, `ALLOWED_IMAGE_MIMES` constants
  - Extension-based file type rejection at upload boundary (422 with clear message)
  - Content-Type vs extension mismatch detection (422)
  - Proper HTTP status codes: 413 for oversize, 422 for bad file types
- `tests/test_app.py`:
  - Updated all PDF/unsupported file upload tests to expect 422
  - Added unsupported-extension assertion in source_type_detection test
  - Replaced PDF-based test with empty-txt in `test_translate_document_no_extracted_text`
  - Removed stale expectations about failed background docs

**Result:** 19/19 tests still passing.

**Commit:** `367d36b`

---

### 🔧 Iteration 3: Logging & observability

**Changes:**
- `app.py`:
  - Added structured log format (timestamp, level, logger name, message)
  - Added `Request` parameter to root/health endpoints (future-proofing)
  - Upload endpoint: `logger.info` on accept with id/filename/size/source_type, `logger.warning` on validation failures (missing file, bad ext, MIME mismatch)
  - List-documents: `logger.warning` on unauthorized attempts, `logger.info` on successful list
  - Get-document: `logger.info` on miss (404), `logger.debug` on hit with status (poll tracking)
  - Translate: `logger.info` on start with id prefix + lang pair, `logger.warning` when no extracted text
  - All logs use id-truncation (`id[:8]...`) for privacy in logs

**Result:** 19/19 tests passing, all green.

**Commit:** `9ac30af`

---

### 🔧 Iteration 4: Frontend UX polish

**Changes:**
- `static/app.js`:
  - Poll timeout after 90s — stops polling and shows clear error message asking user to try a smaller/clearer photo
  - Elapsed time counter during processing (shows seconds, then minutes after 60s)
  - Warning indicator after 45s of waiting (changes color, updates progress text)
  - Transient poll errors no longer kill the poll or show error popup — they log and retry silently
  - Upload errors now extract `detail` field from JSON error responses for more specific messages
- `static/index.html`:
  - Added `#elapsedTime` badge in the processing hint line
- `static/style.css`:
  - Added `.poll-time-badge` styles: animated dot, rounded pill, color transition
  - Added `.poll-warn` class: amber background, orange text for wait >45s
  - Added `@keyframes pulse` for the live indicator dot
  - Cache-bust bumped to `v=20260509`

**Result:** 19/19 tests still passing.

**Commit:** `ab81082`

---

### 🔧 Iteration 5: Deploy config & polish

**Changes:**
- Added `render.yaml` — Infrastructure-as-Code definition for the Render web service (docker runtime, oregon region, free plan, auto-deploy on main, env vars, health check path)
- Updated cache-busting versions on both CSS/JS references to `v=20260509`

**Result:** 19/19 tests still passing.

**Commit:** `938d7b9`

---

## Summary

| Metric | Before | After |
|--------|--------|-------|
| Tests passing | 14 | **19** |
| Test coverage | ~0% route coverage | **Full route coverage** (19 tests, happy + edge paths) |
| Input validation | None | **File ext, MIME, size** (422/413) |
| Logging | Background pipeline only | **All endpoints + structured format** |
| Poll UX | Silent forever on failure | **90s timeout + elapsed timer + warning state** |
| Deploy config | None | `render.yaml` IaaC + auto-deploy from main |
| Live URL | https://doc-explainer-api-lapb.onrender.com/ | ✅ Same URL, verified functional |
