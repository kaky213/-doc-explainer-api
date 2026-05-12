/* DocTranslate — v3 frontend */

class DocTranslateApp {
  constructor() {
    this.currentDocumentId = null;
    this.pollTimer = null;
    this.pollStart = null;
    this.pollElapsedTimer = null;
    this.POLL_TIMEOUT_MS = 63000;  // 60s processing + 3s buffer (matches backend MAX_DOC_PROCESSING_TIME)
    this.autoTranslateTriggered = false;

    this.initEls();
    this.initEvents();
    this.checkStatus();
  }

  /* ========== ELEMENTS ========== */
  initEls() {
    this.fileInput = document.getElementById('fileInput');
    this.chooseBtn = document.getElementById('chooseBtn');
    this.cameraBtn = document.getElementById('cameraBtn');
    this.fileInfo = document.getElementById('fileInfo');
    this.uploadBtn = document.getElementById('uploadBtn');
    this.uploadStatus = document.getElementById('uploadStatus');
    this.uploadSection = document.getElementById('uploadSection');

    this.targetLang = document.getElementById('targetLanguage');
    this.retryLang = document.getElementById('retryTargetLanguage');

    this.processingSection = document.getElementById('processingSection');
    this.progressText = document.getElementById('progressText');
    this.stepEls = document.querySelectorAll('.step');

    this.resultsSection = document.getElementById('resultsSection');
    this.preview = document.getElementById('imagePreviewContainer');
    this.sourceLang = document.getElementById('sourceLanguage');
    this.targetBadge = document.getElementById('targetLanguageBadge');
    this.transBox = document.getElementById('translatedText');
    this.explBox = document.getElementById('explanation');

    this.summaryCard = document.getElementById('documentSummary');
    this.docBadge = document.getElementById('documentTypeBadge');
    this.docType = document.getElementById('documentType');
    this.docSummary = document.getElementById('documentSummaryText');
    this.kdSec = document.getElementById('keyDetailsSection');
    this.kdGrid = document.getElementById('keyDetails');
    this.actSec = document.getElementById('suggestedActionsSection');
    this.actList = document.getElementById('suggestedActions');
    this.noteSec = document.getElementById('confidenceNotesSection');
    this.noteEl = document.getElementById('confidenceNotes');

    this.retakeCard = document.getElementById('retakeHelper');
    this.tipsEl = document.getElementById('retakeTips');

    this.newBtn = document.getElementById('newPhotoBtn');
    this.copyBtn = document.getElementById('copyTranslationBtn');
    this.speakBtn = document.getElementById('speakTranslationBtn');
    this.retryBtn = document.getElementById('retryTranslateBtn');
    this.refreshBtn = document.getElementById('refreshBtn');
    this.retakePhotoBtn = document.getElementById('retakePhotoBtn');
    this.tryBtn = document.getElementById('tryAnywayBtn');
    this.tryBtn2 = document.getElementById('tryAnywayBtn2');

    this.statusDot = document.getElementById('statusDot');
    this.statusLabel = document.getElementById('statusLabel');
  }

  /* ========== EVENTS ========== */
  initEvents() {
    this.chooseBtn.addEventListener('click', () => this.fileInput.click());
    this.fileInput.addEventListener('change', e => this.onFile(e));
    this.cameraBtn.addEventListener('click', () => this.fileInput.click());
    this.uploadBtn.addEventListener('click', () => this.upload());

    this.targetLang.addEventListener('change', () => this.syncLangs());
    this.retryLang.addEventListener('change', () => this.syncLangs(true));
    this.sourceLang.addEventListener('change', () => {});

    this.newBtn.addEventListener('click', () => this.reset());
    this.copyBtn.addEventListener('click', () => this.doCopy());
    this.speakBtn.addEventListener('click', () => this.doSpeak());
    this.retryBtn.addEventListener('click', () => this.retranslate());
    this.refreshBtn.addEventListener('click', () => this.checkStatus());

    this.retakePhotoBtn.addEventListener('click', () => this.reset());
    this.tryBtn.addEventListener('click', () => this.forceTrans());
    this.tryBtn2.addEventListener('click', () => this.forceTrans());
  }

  syncLangs(fromRetry) {
    if (fromRetry) this.targetLang.value = this.retryLang.value;
    else this.retryLang.value = this.targetLang.value;
    this.targetBadge.textContent = this.langName(this.targetLang.value);
  }

  langName(c) {
    const names = {
      en:'English',es:'Español',pt:'Português',fr:'Français',de:'Deutsch',
      it:'Italiano',nl:'Nederlands',ru:'Русский',ar:'العربية',hi:'हिन्दी',
      'zh-CN':'中文 (简体)','zh-TW':'中文 (繁體)',ja:'日本語',ko:'한국어',
      auto:'Auto-detect'
    };
    return names[c] || c;
  }

  /* ========== FILE ========== */
  onFile(e) {
    const f = e.target.files[0];
    if (!f) return;
    const span = this.fileInfo.querySelector('span');
    if (span) span.textContent = f.name;
    this.fileInfo.classList.add('selected');
    if (f.type.startsWith('image/')) this.showPreview(f);
  }

  showPreview(f) {
    const r = new FileReader();
    r.onload = e => {
      this.preview.innerHTML = `<img src="${e.target.result}" alt="Preview">`;
    };
    r.readAsDataURL(f);
  }

  /* ========== UPLOAD ========== */
  async upload() {
    const f = this.fileInput.files[0];
    if (!f) { this.msg('Please select a photo first', 'err'); return; }
    this.showProcessing();
    try {
      this.setStep(0);
      this.progressText.textContent = 'Uploading photo…';
      const fd = new FormData();
      fd.append('file', f);
      const r = await fetch('/documents/upload', { method:'POST', body:fd });
      if (!r.ok) {
        const errBody = await r.json().catch(() => ({}));
        throw new Error(errBody.detail || `Upload failed (${r.status})`);
      }
      const doc = await r.json();
      this.currentDocumentId = doc.id;
      this.autoTranslateTriggered = false;
      this.setStep(1);
      this.progressText.textContent = 'Reading text from image…';
      this.startElapsedTimer();
      this.startPoll();
    } catch(e) {
      console.error(e);
      this.msg(`Upload failed: ${e.message}`, 'err');
      this.reset();
    }
  }

  showProcessing() {
    this.uploadSection.classList.add('hidden');
    this.processingSection.classList.remove('hidden');
    this.resultsSection.classList.add('hidden');
    this.stepEls.forEach(s => s.classList.remove('active','completed'));
    this.elapsedTimeEl = document.getElementById('elapsedTime');
    if (this.elapsedTimeEl) this.elapsedTimeEl.textContent = '';
    this.msg('', '');
  }

  startElapsedTimer() {
    this.pollStart = Date.now();
    clearInterval(this.pollElapsedTimer);
    this.pollElapsedTimer = setInterval(() => {
      if (!this.pollStart) return;
      const elapsed = Math.floor((Date.now() - this.pollStart) / 1000);
      const mins = Math.floor(elapsed / 60);
      const secs = elapsed % 60;
      if (this.elapsedTimeEl) {
        this.elapsedTimeEl.textContent = mins > 0
          ? `${mins}m ${secs}s`
          : `${secs}s`;
      }
      // Show warnings at progressive thresholds
      const badge = document.querySelector('.poll-time-badge');
      if (badge) {
        if (elapsed > 45) {
          badge.classList.add('poll-warn');
          this.progressText.textContent = 'Still reading text — large images may take longer…';
        } else if (elapsed > 25) {
          badge.classList.add('poll-warn-mild');
          this.progressText.textContent = 'This is taking a bit longer than usual…';
        } else {
          badge.classList.remove('poll-warn', 'poll-warn-mild');
        }
      }
    }, 1000);
  }

  stopElapsedTimer() {
    clearInterval(this.pollElapsedTimer);
    this.pollElapsedTimer = null;
    if (this.elapsedTimeEl) this.elapsedTimeEl.textContent = '';
  }

  setStep(idx) {
    this.stepEls.forEach((s,i) => {
      s.classList.remove('active','completed');
      if (i < idx) s.classList.add('completed');
      else if (i === idx) s.classList.add('active');
    });
  }

  startPoll() {
    clearInterval(this.pollTimer);
    this.pollAttempts = 0;
    this.pollInterval = 2000;
    // Poll immediately, then schedule with adaptive backoff
    setTimeout(() => this.poll(), 100);
    this.scheduleNextPoll();
  }

  scheduleNextPoll() {
    this.pollAttempts++;
    // Adaptive backoff: 2s → 3s → 5s (then hold at 5s)
    if (this.pollAttempts > 12) this.pollInterval = 5000;
    else if (this.pollAttempts > 5) this.pollInterval = 3000;
    else this.pollInterval = 2000;
    this.pollTimer = setTimeout(() => {
      this.poll();
      this.scheduleNextPoll();
    }, this.pollInterval);
  }

  stopPoll() {
    clearTimeout(this.pollTimer);
    this.pollTimer = null;
    this.stopElapsedTimer();
  }

  async poll() {
    if (!this.currentDocumentId) return;
    
    // Check timeout
    if (this.pollStart && (Date.now() - this.pollStart) > this.POLL_TIMEOUT_MS) {
      this.stopPoll();
      this.progressText.textContent = 'Processing timed out';
      this.msg('This image took too long to process. Try a smaller file, a clearer photo, or one with less text.', 'err');
      this.reset();
      return;
    }
    
    try {
      const r = await fetch(`/documents/${this.currentDocumentId}`);
      if (!r.ok) {
        // Don't stop polling on transient network errors — just log and retry
        console.warn(`Poll transient failure: ${r.status} for ${this.currentDocumentId}`);
        // Still schedule next poll — transient errors shouldn't kill the flow
        this.continuePolling();
        return;
      }
      const d = await r.json();
      if (d.status === 'completed') {
        this.stopPoll();
        this.setStep(2);
        
        // Check if OCR was low quality or produced no text
        const ocrQuality = d.ocr_quality || 'unknown';
        const ocrStatus = d.ocr_status || 'good';
        
        if (ocrQuality === 'none' || ocrStatus === 'no_text') {
          // Couldn't read any text — surface failure with guidance
          this.progressText.textContent = 'Couldn\'t read the photo';
          this.msg(
            d.confidence_notes || d.explanation || 'No readable text found. Make sure text fills most of the frame with even lighting.',
            'err'
          );
          this.renderNoTextState(d);
          return;
        }
        
        if (ocrQuality === 'low' || ocrStatus === 'low_quality') {
          this.progressText.textContent = 'Partially readable';
          this.onOcrDone(d);
          // Show warning banner for low-quality OCR
          this.msg(
            d.confidence_notes || 'The text was partially readable — some content may be missing or incorrect.',
            'warn'
          );
          return;
        }
        
        this.progressText.textContent = 'Translating text…';
        this.onOcrDone(d);
      } else if (d.status === 'failed') {
        this.stopPoll();
        // Show backend error detail with actionable guidance
        const failMsg = d.explanation || d.confidence_notes || 'Unable to read text from this image. Try a clearer photo.';
        this.msg(failMsg, 'err');
        this.renderFailedState(d);
      } else {
        // Show phase-specific progress using ocr_status field
        const phase = d.ocr_status;
        if (phase === 'loading_image') {
          this.progressText.textContent = 'Loading image…';
        } else if (phase === 'ocr_processing') {
          this.progressText.textContent = 'Reading text…';
        } else if (phase === 'analyzing') {
          this.progressText.textContent = 'Analyzing document…';
        } else {
          this.progressText.textContent = 'Processing…';
        }
        // Schedule next poll
        this.continuePolling();
      }
    } catch(e) {
      console.warn('Poll network error (will retry):', e.message);
      // Still schedule next poll — transient network blips shouldn't kill the flow
      this.continuePolling();
    }
  }
  
  renderNoTextState(d) {
    // Show the retake card immediately instead of translating garbage
    this.retakeCard.classList.remove('hidden');
    document.getElementById('translationCard').classList.add('hidden');
    document.getElementById('explanationCard').classList.add('hidden');
    if (d.retake_tips) this.renderTips(d.retake_tips);
  }
  
  renderFailedState(d) {
    // Show actionable failure with retake guidance
    this.retakeCard.classList.remove('hidden');
    if (d.retake_tips) this.renderTips(d.retake_tips);
  }

  async onOcrDone(doc) {
    if (!this.autoTranslateTriggered && doc.extracted_text) {
      this.autoTranslateTriggered = true;
      await this.translate(doc);
    }
  }

  async translate(doc) {
    try {
      const lang = this.targetLang.value;
      const sourceHint = this.sourceLang.value !== 'auto' ? this.sourceLang.value : undefined;
      this.progressText.textContent = 'Translating to ' + this.langName(lang) + '…';
      const body = {target_language:lang};
      if (sourceHint) body.source_language_hint = sourceHint;
      const r = await fetch(`/documents/${doc.id}/translate`, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(body)
      });
      if (!r.ok) throw new Error(`Translation failed (${r.status})`);
      const td = await r.json();
      this.setStep(3);
      this.progressText.textContent = 'Building explanation…';
      setTimeout(() => this.showResults(td), 300);
    } catch(e) {
      console.error(e);
      this.msg(`Translation failed: ${e.message}`, 'err');
      this.showResults(doc);
    }
  }

  /* ========== RENDER ========== */
  showResults(doc) {
    this.processingSection.classList.add('hidden');
    this.resultsSection.classList.remove('hidden');
    this.renderAll(doc);
    this.targetBadge.textContent = this.langName(this.targetLang.value);
    this.retryLang.value = this.targetLang.value;
  }

  renderAll(doc) {
    this.renderSummary(doc);

    // Check OCR quality for smart UI state
    const noText = doc.ocr_quality === 'none' || doc.ocr_status === 'no_text';
    const lowQuality = doc.ocr_quality === 'low' || doc.ocr_status === 'low_quality';
    const skipped = doc.translation_skipped === true;
    
    // Add quality warning banner for low-confidence reads
    const qualityBanner = document.getElementById('qualityWarning');
    if (qualityBanner) {
      if (lowQuality) {
        qualityBanner.classList.remove('hidden');
        qualityBanner.textContent = '⚠ Partially readable — some content may be missing or incorrect. Check the original photo if something looks off.';
      } else if (noText) {
        qualityBanner.classList.remove('hidden');
        qualityBanner.textContent = '⚠ Could not read text from this photo. Try retaking with better lighting.';
      } else {
        qualityBanner.classList.add('hidden');
      }
    }

    const bad = skipped || lowQuality || noText;
    this.retakeCard.classList.toggle('hidden', !bad);
    document.getElementById('translationCard').classList.toggle('hidden', bad);
    document.getElementById('explanationCard').classList.toggle('hidden', bad);

    if (bad && doc.retake_tips) this.renderTips(doc.retake_tips);

    const detectedCode = doc.detected_language && doc.detected_language !== 'unknown' ? doc.detected_language : null;
    this.sourceLang.textContent = detectedCode
      ? (this.langName(detectedCode) || detectedCode) : 'Auto-detected';
    // Sync source selector to detected language if user hasn't manually overridden
    if (detectedCode && this.sourceLang.value === 'auto') {
      const codeMap = {'eng':'en','spa':'es','por':'pt','fra':'fr','deu':'de','ita':'it',
                       'nld':'nl','rus':'ru','ara':'ar','hin':'hi','chi_sim':'zh-CN',
                       'chi_tra':'zh-TW','jpn':'ja','kor':'ko'};
      const isoCode = codeMap[detectedCode] || detectedCode;
      if ([...this.sourceLang.options].some(o => o.value === isoCode)) {
        this.sourceLang.value = isoCode;
      }
    }

    if (doc.translated_text) {
      this.transBox.innerHTML = this.fmt(doc.translated_text);
    } else {
      this.transBox.innerHTML = '<span class="empty-state">No translation available</span>';
    }

    if (doc.explanation) {
      this.explBox.innerHTML = this.fmt(doc.explanation);
    } else {
      this.explBox.innerHTML = '<span class="empty-state">No explanation available</span>';
    }
  }

  renderSummary(doc) {
    if (doc.document_analysis_enabled !== true || !doc.document_type) {
      this.summaryCard.classList.add('hidden');
      return;
    }
    this.summaryCard.classList.remove('hidden');

    const dt = (doc.document_type || 'unknown_document')
      .replace(/_/g,' ').replace(/\b\w/g,l=>l.toUpperCase());
    const conf = doc.document_type_confidence || 'low';

    this.docType.textContent = dt;
    this.docBadge.textContent = dt;
    this.docBadge.className = 'doc-pill';
    if (conf === 'low') {
      this.docBadge.className = 'doc-pill doc-pill-warn';
      this.docBadge.textContent = 'Low quality';
    }

    this.docSummary.textContent = doc.document_summary || 'No summary available.';

    // Key details
    this.kdGrid.innerHTML = '';
    const all = [];
    if (doc.key_details && doc.key_details.length) {
      doc.key_details.forEach(k => { if (k.label && k.value) all.push(k); });
    }

    const isBill = /bill|invoice|utility/.test(doc.document_type||'');
    const isGov = /government|immigration|bank_notice/.test(doc.document_type||'');
    const isAppt = /appointment|medical/.test(doc.document_type||'');

    const exists = l => all.some(k => k.label.toLowerCase().includes(l));
    if (isBill) {
      if (doc.amount_due && !exists('amount')) all.push({label:'Amount due',value:doc.amount_due,confidence:'high'});
      if (doc.due_date && !exists('due date')) all.push({label:'Due date',value:doc.due_date,confidence:'medium'});
      if (doc.bill_period_start && doc.bill_period_end) all.push({label:'Billing period',value:`${doc.bill_period_start} – ${doc.bill_period_end}`,confidence:'medium'});
      if (doc.statement_date && !exists('statement')) all.push({label:'Statement date',value:doc.statement_date,confidence:'medium'});
    }
    if (isAppt) {
      if (doc.appointment_date && !exists('date')) all.push({label:'Appointment date',value:doc.appointment_date,confidence:'medium'});
      if (doc.appointment_time && !exists('time')) all.push({label:'Appointment time',value:doc.appointment_time,confidence:'medium'});
      if (doc.appointment_location && !exists('location')) all.push({label:'Location',value:doc.appointment_location,confidence:'medium'});
    }
    if (doc.sender_name && !exists('sender')) all.push({label:'Sender',value:doc.sender_name,confidence:'medium'});
    if (doc.reference_number && !exists('reference')) all.push({label:'Reference number',value:doc.reference_number,confidence:'medium'});
    if (isGov) {
      if (doc.case_number && !exists('case')) all.push({label:'Case number',value:doc.case_number,confidence:'medium'});
      if (doc.response_deadline && !exists('deadline')) all.push({label:'Response deadline',value:doc.response_deadline,confidence:'medium'});
    }

    if (all.length) {
      this.kdSec.classList.remove('hidden');
      all.forEach(k => {
        const el = document.createElement('div');
        el.className = 'kd-item';
        const bc = k.confidence||'low';
        el.innerHTML = `<div class="kd-bar ${bc}"></div><span class="kd-label">${k.label}</span><span class="kd-value">${k.value}</span>`;
        this.kdGrid.appendChild(el);
      });
    } else {
      this.kdSec.classList.add('hidden');
    }

    // Suggested actions
    this.actList.innerHTML = '';
    if (doc.suggested_actions && doc.suggested_actions.length) {
      this.actSec.classList.remove('hidden');
      doc.suggested_actions.forEach(a => {
        if (!a || !a.trim()) return;
        const el = document.createElement('div');
        el.className = 'action-item';
        el.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="none" style="flex-shrink:0;margin-top:1px"><path d="M8 2a6 6 0 100 12A6 6 0 008 2zM6.5 8l1.5 1.5L11 6.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg><span>${a}</span>`;
        this.actList.appendChild(el);
      });
    } else {
      this.actSec.classList.add('hidden');
    }

    // Confidence notes
    if (doc.confidence_notes && doc.confidence_notes.trim()) {
      this.noteSec.classList.remove('hidden');
      this.noteEl.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="none" style="flex-shrink:0;margin-top:1px"><path d="M8 2a6 6 0 100 12A6 6 0 008 2zM8 7v3M8 5.5v.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/></svg><span>${doc.confidence_notes}</span>`;
    } else {
      this.noteSec.classList.add('hidden');
    }
  }

  renderTips(tips) {
    this.tipsEl.innerHTML = '';
    const lines = tips.split('\n').map(l => l.replace(/^[•\-\*\d\.\s]+/,'').trim()).filter(Boolean);
    const icons = [
      '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M4 8l3 3 5-5" stroke="#4361ee" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>',
      '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="3" stroke="#4361ee" stroke-width="1.5"/><path d="M8 11v3M8 2v3" stroke="#4361ee" stroke-width="1.3" stroke-linecap="round"/></svg>',
      '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M8 3v10" stroke="#4361ee" stroke-width="1.5" stroke-linecap="round"/></svg>',
      '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6" stroke="#4361ee" stroke-width="1.5"/><path d="M8 5v3l2 2" stroke="#4361ee" stroke-width="1.3" stroke-linecap="round"/></svg>'
    ];
    lines.forEach((l,i) => {
      const el = document.createElement('div'); el.className = 'tip-item';
      el.innerHTML = icons[i % icons.length] + '<span>' + l + '</span>';
      this.tipsEl.appendChild(el);
    });
    if (!this.tipsEl.children.length) {
      const defs = [
        'Get closer so the text fills most of the frame',
        'Ensure even lighting without glare or shadows',
        'Hold your camera steady, parallel to the text',
        'Tap on the text area to focus before shooting'
      ];
      defs.forEach((t,i) => {
        const el = document.createElement('div'); el.className = 'tip-item';
        el.innerHTML = icons[i] + '<span>' + t + '</span>';
        this.tipsEl.appendChild(el);
      });
    }
  }

  fmt(t) {
    if (!t) return '';
    // Escape HTML entities first to prevent XSS from any content in translated text or explanations
    let s = t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    // Then convert markdown-style formatting to safe HTML
    return s.replace(/\n/g,'<br>')
            .replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>')
            .replace(/\*(.+?)\*/g,'<em>$1</em>');
  }

  /* ========== ACTIONS ========== */
  reset() {
    this.currentDocumentId = null;
    this.autoTranslateTriggered = false;
    this.stopPoll();
    this.fileInput.value = '';
    const span = this.fileInfo.querySelector('span');
    if (span) span.textContent = 'No photo selected';
    this.fileInfo.classList.remove('selected');
    this.preview.innerHTML =
      '<div class="preview-empty">' +
      '<svg width="40" height="40" viewBox="0 0 40 40" fill="none"><rect x="4" y="8" width="32" height="24" rx="4" stroke="#ced4da" stroke-width="2"/><circle cx="20" cy="18" r="5" stroke="#ced4da" stroke-width="2"/><path d="M12 29l5-6 4 4 6-9 7 11" stroke="#ced4da" stroke-width="2" stroke-linecap="round"/></svg>' +
      '</div>';
    this.uploadSection.classList.remove('hidden');
    this.processingSection.classList.add('hidden');
    this.resultsSection.classList.add('hidden');
    this.msg('','');
  }

  async retranslate() {
    if (!this.currentDocumentId) return;
    try {
      this.msg('Re-translating…', 'info');
      const lang = this.retryLang.value;
      const sourceHint = this.sourceLang.value !== 'auto' ? this.sourceLang.value : undefined;
      const body = {target_language:lang};
      if (sourceHint) body.source_language_hint = sourceHint;
      const r = await fetch(`/documents/${this.currentDocumentId}/translate`, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(body)
      });
      if (!r.ok) throw new Error(`Retranslation failed (${r.status})`);
      const d = await r.json();
      this.renderAll(d);
      this.targetLang.value = this.retryLang.value;
      this.targetBadge.textContent = this.langName(lang);
      this.msg('Translation updated', 'ok');
    } catch(e) { this.msg(`Retranslation failed: ${e.message}`, 'err'); }
  }

  async forceTrans() {
    if (!this.currentDocumentId) return;
    this.retakeCard.classList.add('hidden');
    document.getElementById('translationCard').classList.remove('hidden');
    document.getElementById('explanationCard').classList.remove('hidden');
    this.msg('Trying to translate…', 'info');
    try {
      const sourceHint = this.sourceLang.value !== 'auto' ? this.sourceLang.value : undefined;
      const body = {target_language:this.targetLang.value};
      if (sourceHint) body.source_language_hint = sourceHint;
      const r = await fetch(`/documents/${this.currentDocumentId}/translate`, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(body)
      });
      if (!r.ok) throw new Error(`Translation failed (${r.status})`);
      const d = await r.json();
      this.renderAll(d);
    } catch(e) {
      this.retakeCard.classList.remove('hidden');
      this.msg(`Translation failed: ${e.message}`, 'err');
    }
  }

  async doCopy() {
    const t = this.transBox.textContent || this.transBox.innerText;
    if (!t || t.includes('No translation')) { this.msg('No text to copy','err'); return; }
    try {
      await navigator.clipboard.writeText(t);
      this.msg('Copied!','ok');
    } catch(e) { this.msg('Failed to copy','err'); }
  }

  doSpeak() {
    const t = this.transBox.textContent || this.transBox.innerText;
    if (!t || t.includes('No translation')) { this.msg('No text to speak','err'); return; }
    if ('speechSynthesis' in window) {
      const u = new SpeechSynthesisUtterance(t);
      u.lang = this.targetLang.value;
      speechSynthesis.speak(u);
      this.msg('Speaking…','info');
    } else { this.msg('Text-to-speech not supported','err'); }
  }

  /* ========== STATUS ========== */
  async checkStatus() {
    this.statusDot.className = 'status-light checking';
    this.statusLabel.textContent = 'Checking…';
    try {
      const r = await fetch('/health');
      if (r.ok) {
        this.statusDot.className = 'status-light online';
        this.statusLabel.textContent = 'Online';
      } else {
        this.statusDot.className = 'status-light offline';
        this.statusLabel.textContent = 'Offline';
      }
    } catch {
      this.statusDot.className = 'status-light offline';
      this.statusLabel.textContent = 'Offline';
    }
  }

  msg(text, type) {
    if (!text) { this.uploadStatus.className = 'msg-bar'; this.uploadStatus.style.display = 'none'; return; }
    this.uploadStatus.textContent = text;
    this.uploadStatus.className = 'msg-bar show ' + type;
    if (type === 'ok') {
      setTimeout(() => {
        if (this.uploadStatus.textContent === text) this.msg('','');
      }, 5000);
    }
  }
}

document.addEventListener('DOMContentLoaded', () => { window.app = new DocTranslateApp(); });
