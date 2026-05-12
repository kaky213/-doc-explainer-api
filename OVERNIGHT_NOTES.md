

---

### 🔧 Iteration 14: Multilingual upgrade — refactor, script-aware OCR, frontend expansion (2026-05-11)

#### Audit of Current Language Assumptions

**OCR Pipeline:**
- **`lang_candidates`** (line 768): 7 hardcoded Latin-only combos — `"eng"`, `"eng+spa"`, `"eng+fra"`, `"eng+deu"`, `"eng+por"`, `"eng+ita"`, `"eng+nld"` — but **this variable is never used!** Tier 1 only tries `"eng"`, Tier 2 only tries `fallback_langs`.
- **`fallback_langs`** (line 920): 6 hardcoded Latin-only combos — no Arabic, Russian, Hindi, CJK.
- **`OCR_LANGS`** (line 1025): `"eng+spa+fra+deu+por+ita+chi_sim"` — includes chi_sim but never used in actual OCR calls (it's only a config constant).
- **No script routing**: Arabic text goes through `"eng"` first, wastes time, returns nothing.
- **`language_word_bonus`** (line 470): Only English, German, French (`eng_words`, `deu_words`, `fra_words`). Spanish, Portuguese, Italian omitted from the bonus.
- **`detect_language_from_ocr_text`** (line 502): Only checks Portuguese, Spanish, English, German, French. No Dutch, Russian, Arabic, Hindi, CJK.
- **No Unicode/script detection**: All heuristics assume Latin script.

**Translation Pipeline:**
- **`normalize_lang_code`** (line 1712): Good mapping but no "auto" or frontend code fallback.
- **`translate_with_mymemory`** (line 1754): Skips auto-detect. CJK/Devanagari/Arabic often fail on MyMemory free tier.
- **`translate_document`** best-effort fallback (line ~2376): Hardcoded word lists for Fr/It/Es — should use `detect_language_from_ocr_text`.
- **DeepSeek prompts** (line 1817-1845): Assume `source_lang`/`target_lang` are human-readable (e.g., "Spanish"). Fine if codes are normalized.
- **TranslationRequest model** (line 1106): Only has `target_language: str` and `source_language_hint: Optional[str]` — source hint exists but is rarely used.

**Frontend:**
- **`langName()` in app.js** (line 95): Only 7 languages: en, es, fr, de, it, pt, zh-CN.
- **Target language dropdown** (index.html): Only those 7.
- **No source language selector**: User can only choose target language. Source is always auto-detected.
- **No visual grouping**: Languages not organized by script.

**Tesseract Packs Installed (before):** chi_sim, deu, eng, fra, ita, osd, por, spa (8 packs)
**Tesseract Packs Installed (after):** +nld, rus, ara, hin, chi_tra, jpn, kor (15 packs)

**Tests (before):**
- `test_app.py`: Only English OCR paths. No multilingual OCR tests.
- `test_ocr_reliability.py`: English synthetic images. No non-Latin script tests.

---

#### Changes Made

**config.py** (new):
- Centralized ALL constants: SUPPORTED_TARGET_LANGUAGES, LANG_SCRIPT_GROUPS,
  ISO_TO_TESSERACT, TESSERACT_SCRIPT_GROUPS, SCRIPT_OCR_STRATEGIES,
  GENERAL_FALLBACK_LANGS, MYMEMORY_WEAK_LANGS, all file/path limits
- Each script group has its own OCR strategy (primary, fallback combos)
- CJK scripts separated by language (never combine chi_sim+jpn+kor)

**lang_detect.py** (new):
- `detect_script_from_text()`: Unicode range analysis for Latin, Cyrillic,
  Arabic, Devanagari, Han, Kana, Hangul. Returns {scripts, dominant, pct, is_mixed}
- `detect_language_from_ocr_text()`: Returns {lang, confidence, script}
  - Script routing: if dominant is Arabic → return ar, Devanagari → hi, etc.
  - Latin scoring: function words × 7 langs + accented chars + strong clues
  - CJK: checks for kana presence to differentiate Japanese vs Chinese
- `normalize_lang_code()`: Full mapping from all codes to ISO 639-1
- `normalize_to_tesseract()`: ISO 639-1 → Tesseract 3-letter codes

**app.py changes:**
- Replaced old `detect_language_from_ocr_text` (5 lang, hardcoded) →
  delegates to lang_detect module (14 lang, script-aware)
- Replaced old `language_word_bonus` (5 lang dict) → confidence-based from lang_detect
- Replaced old `normalize_lang_code` (inline dict) → delegates to lang_detect
- OCR Tier 2: script-aware fallback — detects script from partial text,
  picks appropriate language pack (rus/ara/hin/chi_sim/jpn/kor) before general fallback
- Added Tier 3: general fallback for when script-specific also fails
- Translation: skip MyMemory for CJK/Arabic/Devanagari → direct to DeepSeek
- Best-effort language fallback: uses proper detect_language_from_ocr_text instead
  of hardcoded fr/it/es food word lists

**Frontend (index.html + app.js):**
- Source language selector (auto-detect + all 14 langs, grouped by script)
- Target language: 7→14 options, grouped by script with optgroup labels
- Retry dropdown: same 14 options
- langName(): expanded to cover all 14 languages
- translate()/retranslate()/forceTrans(): all send source_language_hint
- Results display: syncs source selector to detected language

**Dockerfile:**
- Added nld, rus, ara, hin, chi_tra, jpn, kor Tesseract packages
- Organized by script with comments for maintainability

**Tesseract packs installed locally:** 15 total (all verified working)

#### Remaining / Future Work

- **Source_language_hint in OCR pipeline**: Currently hint only flows to
  translation, not to run_best_effort_ocr. Could optimize OCR by passing
  the hint to skip English-first when user says the doc is Arabic.
- **Non-Latin test fixtures**: Reliability tests only generate Latin images.
  Should add synthetic Russian/Arabic/Hindi/CJK images.
- **MyMemory+DeepSeek combo**: For Latin translations, MyMemory works fine.
  For CJK etc, goes direct to DeepSeek (requires DEEPSEEK_API_KEY env var).
  Could try combining: MyMemory for phrase-level, DeepSeek for polishing.

### ✅ Items 5-12 Completion Status (2026-05-11)

All items from the multilingual plan are now implemented, tested, and documented.

**5. Translation pipeline for major languages** ✅
- 14 priority languages supported (7 Latin + 1 Cyrillic + 1 Arabic + 1 Devanagari + 4 CJK)
- Centralized mappings in `config.py`: `SUPPORTED_TARGET_LANGUAGES`, `SUPPORTED_SOURCE_LANGUAGES`,
  `ISO_TO_TESSERACT`, `TESSERACT_TO_ISO`, `MYMEMORY_WEAK_LANGS`, `LANG_SCRIPT_GROUPS`
- Translation routing: MyMemory first for Latin, skip for CJK/Arabic/Devanagari → direct to DeepSeek
- Code normalization: `normalize_lang_code()` handles ISO↔BCP47↔human names, `normalize_to_tesseract()`
- Frontend: 14-language dropdown with script-grouped optgroups, source language selector with Auto-detect

**6. Mixed-language document handling** ✅
- OCR tolerates mixed-script text via Tier 2 script-aware fallback
- Script detection reports `is_mixed: true` with per-script percentages
- Test fixtures for mixed Latin (`mixed_latin_doc`), CJK+Latin (`mixed_cjk_latin_doc`),
  Arabic+English (`mixed_arabic_english_doc`)
- Pipeline tests verify end-to-end: image generation → OCR → script detection → language detection

**7. Analysis/explanation fallback** ✅
- `analyze_document_content` exception handler now detects language/script from OCR text
- Logs metadata (detected_script, detected_lang, source=heuristic) without leaking document text
- Graceful fallback message regardless of source language (no nonsense for non-English)
- All languages fall through uniformly

**8. Multilingual test coverage** ✅
- `tests/test_multilingual.py`: 59 tests across 4 test classes
- `TestLangDetection`: 16 tests — all 14 languages + empty/short/numeric text
- `TestScriptDetection`: 10 tests — all 7 scripts + mixed pairs + empty
- `TestOcrMultilingual`: 14 tests — OCR with appropriate language pack per fixture
- `TestFullMultilingualPipeline`: 12 tests — end-to-end image→OCR→detection
- `TestMultilingualFallbackBehavior`: 7 tests — edge cases, normalization mappings
- All fixtures in `tests/test_fixtures/generate_fixtures.py` — programmatic, no committed binaries

**9. Observability for multilingual behavior** ✅
- OCR Tier 2/3 transition logs: `best_score`, `script`, `is_mixed`, tier language sets
- Analysis fallback logs: `detected_script`, `detected_lang`, `source=heuristic`
- Translation timing logs: `detected_lang`, `ocr_conf`, `ocr_quality`
- No document text leaked in any log line

**10. Performance (staged OCR strategy)** ✅
- Tier 1: English-only fast path with early exit at high-confidence
- Tier 2: Script-aware fallback — only for low-quality Tier 1 results
- Tier 3: General Latin combos — only when Tier 1/2 both fail
- Never tries all language packs on every image
- Bounded retries: 6 image variants × 1 lang (Tier 1), not 6 × 14
- Render-friendly: no heavy infra, no extra services

**11. Documentation** ✅
- README: Fully updated with multilingual support table, OCR strategy, language detection,
  translation pipeline section, mixed-language handling, adding languages guide, config file overview
- Dockerfile: All 15 language packs installed with comments by script group
- `.env.example`: Clear comments for each variable
- `OVERNIGHT_NOTES.md`: This completion summary

**12. Success criteria** ✅
- ✅ Clear list of 14 supported languages (documented in README, config.py, frontend)
- ✅ Improved OCR/translation across 5 script groups (Latin, Cyrillic, Arabic, Devanagari, CJK)
- ✅ Multilingual fallback (graceful message regardless of source language)
- ✅ 59 multilingual tests + 46 existing tests = 105 total, all passing
- ✅ No regression for English/Spanish (original 46 tests pass)
- ✅ No hangs — bounded OCR retries, timeout-aware pipeline

**Total test count: 105 tests, 0 failures**
