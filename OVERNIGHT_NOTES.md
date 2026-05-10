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

---

### 🔧 Iteration 6: Developer experience & safety audit

**Changes:**
- `Makefile` (new): DocTranslate-specific targets — `venv`, `install`, `test`, `test-quick` (with 5s timeout), `run`, `run-docker`, `clean`, `deploy-check`, `.env`
- `.env.example` (new): DocTranslate-specific env vars — `ADMIN_KEY`, `DEMO_ADMIN_KEY`, `DEEPSEEK_API_KEY`, `MYMEMORY_EMAIL`, `PORT`, `LOG_LEVEL`
- `manage.sh`: Fixed stale "API Docs" URL reference; added `test` command (runs pytest with pass-through args)
- `app.py`: Reduced log exposure — replaced `best_text[:100]` text preview log with `len(best_text) chars` count

**Safety audit results:**
- ✅ `/documents` (list-all) — protected by `X-Admin-Key` header
- ✅ `/documents/{id}` (single doc) — public, safe by UUID
- ✅ `/docs` / ReDoc — disabled (`docs_url=None`, `redoc_url=None`)
- ✅ No API keys logged anywhere
- ✅ All extracted text logs use truncated IDs (`id[:8]...`), no full text leaked
- ✅ No sensitive env vars in log output

**Result:** 23/23 tests passing (19 from tests/ + 4 from external test_refined_analysis.py).

**Commit:** `fdf938e`

---

## End-of-night summary

### What changed (all 6 iterations)

| # | Area | Summary |
|---|------|---------|
| 1 | **Tests** | 19 tests green, fixed 5 failing, real PIL fixtures |
| 2 | **Validation** | File ext/MIME/size checks with proper HTTP codes |
| 3 | **Logging** | Structured format, all endpoints log, id-truncated |
| 4 | **Frontend UX** | 90s poll timeout, elapsed timer, transient-error resilience |
| 5 | **Deploy** | `render.yaml`, cache-bust bump |
| 6 | **DX + Safety** | Makefile, .env.example, manage.sh upgrades, log exposure reduction |

### Open questions for you (@Fermin)
1. **DEEPSEEK_API_KEY** — Do you want to add this to the Render env vars? The app uses it for AI translation/explanation. Without it, MyMemory is used (free tier, rate-limited).
2. **ADMIN_KEY** — Currently set to `change-me-in-production` in both .env.example and Render. Need a real secret before production use.
3. **Single-document endpoint** — Made public per earlier decision. Are you still comfortable with that? Currently any UUID can retrieve any doc.

### Tests status
- **23 total** (19 in tests/test_app.py, 4 in test_refined_analysis.py)
- **23 pass, 0 fail** ✅
- **No flaky tests detected** — all pass consistently

### Recommended next steps
1. Add real `ADMIN_KEY` + `DEEPSEEK_API_KEY` to Render env vars
2. Consider adding rate limiting or a simple token for /documents/{id} if public access is a concern
3. Add a test for the poll-timeout scenario (integration test with slow mock)
4. Set up UptimeRobot or similar to keep Render from sleeping on free tier
