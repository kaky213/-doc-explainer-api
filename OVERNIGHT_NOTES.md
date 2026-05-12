

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

**Tesseract Packs Installed:** chi_sim, deu, eng, fra, ita, osd, por, spa (8 packs)
**Missing for priority languages:** nld, rus, ara, hin, chi_tra, jpn, kor

**Tests:**
- `test_app.py`: Tests only English OCR paths. No multilingual OCR tests.
- `test_ocr_reliability.py`: English synthetic images. No non-Latin script tests.
