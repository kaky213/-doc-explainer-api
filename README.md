# Document Explainer API

Backend API for document photo analysis, translation, and plain-language explanation.

**Purpose:** Help users understand complex documents by providing OCR, translation, and simplified explanations.

Perfect for:
- **Document analysis** - Extract text from document images
- **Language translation** - Translate documents between languages
- **Plain-language explanations** - Simplify complex legal or technical documents
- **Accessibility** - Make documents more accessible to non-experts

## ✨ Features

- ✅ **FastAPI** with automatic OpenAPI documentation
- ✅ **Production-ready Docker** configuration
- ✅ **Comprehensive testing** with pytest and TestClient
- ✅ **Makefile** for convenient development workflows
- ✅ **Health checks** and monitoring
- ✅ **Document processing pipeline** (planned)
- ✅ **Multi-language support** (planned)
- ✅ **Plain-language explanations** (planned)

## 🎯 V1 Scope (Current Implementation)

**Currently implemented:**

1. **Uploaded document files** - No live camera integration
2. **Basic file processing pipeline** - Background task processing
3. **Text file support** - .txt files with direct text extraction
4. **Image OCR support** - .png, .jpg, .jpeg files using Tesseract OCR
5. **Stub translation/explanation** - Placeholder for future enhancements
6. **Disclaimer system** - Built-in disclaimer in all document records
7. **No legal advice** - Explicit disclaimer that this is not legal advice

**Storage:**
- Document metadata (status, OCR results, translation) is stored **in-memory** in a Python dict keyed by `document_id`.
- This is stateless across restarts — fine for a demo/trial.
- Uploaded image files are saved to disk (required by Tesseract OCR).
- Once processed, disk image files can be cleaned up (see `cleanup_old_uploads()`).

**Processing details:**
- **.txt files:** Direct text extraction with word count
- **Image files (.png, .jpg, .jpeg):** OCR text extraction using Tesseract
- **Unsupported file types:** Marked as failed with explanation
- **Background processing:** Uses FastAPI background tasks for async processing

**OCR Requirements:**
- **Python packages:** pytesseract, Pillow (included in requirements.txt)
- **System dependency:** Tesseract OCR engine with language packs (see installation instructions above)
- **Supported languages:** English (eng), Spanish (spa), French (fra), German (deu), Portuguese (por), Italian (ita), Chinese Simplified (chi_sim)
- **OCR quality depends on installed language data** - install all language packs for best results

**Not yet implemented (planned for next steps):**
- PDF OCR support
- Language detection and translation
- Intelligent plain-language explanations
- Multi-page document support

**Out of scope for V1:**
- Live camera document capture
- Real-time processing
- Legal advice or interpretation
- Document editing or modification

## 🚀 Quick Start

### Using Make (recommended)

```bash
# Show all available commands
make help

# Setup development environment
make venv      # Create virtual environment
make install   # Install dependencies
make test      # Run tests
make run       # Start development server
```

### Manual Setup

```bash
# 1. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install system dependencies for OCR
# On Ubuntu/Debian:
sudo apt-get update
# Install Tesseract with multi-language support
sudo apt-get install -y tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-spa \
    tesseract-ocr-fra \
    tesseract-ocr-deu \
    tesseract-ocr-por \
    tesseract-ocr-ita \
    tesseract-ocr-chi-sim

# On macOS:
brew install tesseract
# Language packs are usually included with Homebrew tesseract

# On Windows:
# Download and install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki
# Make sure to select "Additional language data" during installation
# Add Tesseract to your PATH

# 4. Run tests
pytest tests/ -v

# 5. Start server
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

## 📁 Project Structure

```
doc-explainer-api/
├── app.py                 # Main FastAPI application
├── requirements.txt       # Python dependencies
├── Makefile              # Development commands
├── Dockerfile            # Production container
├── docker-compose.yml    # Container orchestration
├── pytest.ini            # Test configuration
├── .dockerignore         # Docker build exclusions
├── data/                 # Persistent data storage
│   ├── uploads/         # Uploaded document files
│   └── documents.json   # Document metadata
└── tests/                # Comprehensive test suite
    └── test_app.py      # Document endpoint tests
```

## 🐳 Docker Deployment

### Development with Docker Compose

```bash
# Start the service
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the service
docker-compose down
```

### Production Build

```bash
# Build the image
docker build -t fastapi-app .

# Run the container
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  --name fastapi-app \
  fastapi-app
```

## 🔧 Available Commands

### Make Commands
```bash
make help        # Show all commands
make venv        # Create virtual environment
make install     # Install dependencies
make test        # Run all tests
make run         # Start development server
make clean       # Clean temporary files
make dev         # Install + run (development)
make all         # venv + install + test (full setup)
```

### Docker Commands
```bash
make docker-build  # Build Docker image
make docker-run    # Start with Docker Compose
make docker-down   # Stop Docker Compose services
```

## 📚 API Reference

### Core Endpoints

**Health Check**
```bash
GET /health
```
Response: `{"status": "ok"}`

### Document Processing Endpoints

**Upload Document**
```bash
POST /documents/upload
Content-Type: multipart/form-data

file: [document file]
```

**Response:**
```json
{
  "id": "uuid-string",
  "filename": "document.pdf",
  "content_type": "application/pdf",
  "stored_path": "/app/data/uploads/uuid-string.pdf",
  "source_type": "unsupported",
  "status": "uploaded",
  "created_at": "2026-04-09T13:00:00",
  "detected_language": null,
  "target_language": null,
  "extracted_text": null,
  "translated_text": null,
  "explanation": null,
  "disclaimer": "This is an automated explanation and not legal advice..."
}
```

**List Documents**
```bash
GET /documents
```

**Get Specific Document**
```bash
GET /documents/{document-id}
```

**Translate and Explain Document**
```bash
POST /documents/{document-id}/translate
Content-Type: application/json

{
  "target_language": "en",
  "source_language_hint": "es",
  "explanation_style": "default"
}
```

**Request Fields:**
- `target_language` (required): BCP‑47 / ISO‑639‑1 language code (e.g., "en", "es", "fr", "de", "pt", "it", "zh-CN")
- `source_language_hint` (optional): Language code expected in the source text (e.g., "es" for Spanish), or `null` for auto‑detection
- `explanation_style` (optional): Currently only "default" is supported (friendly explanation for tourists/immigrants)

**Response:** Returns the updated document with translation and explanation fields populated.

**Error Responses:**
- `404 Not Found`: Document ID does not exist
- `400 Bad Request`: No extracted text available for translation

**Document Status Values:**
- `uploaded` - File uploaded, awaiting processing
- `processing` - OCR/analysis in progress
- `completed` - Processing finished successfully
- `failed` - Processing failed

**Document Source Type Values:**
- `text_file` - .txt files
- `image_file` - .png, .jpg, .jpeg files
- `unsupported` - All other file types

**Processing behavior:**
- **.txt files:** Direct text extraction with word count
- **Image files (.png, .jpg, .jpeg):** OCR text extraction using Tesseract
- **Other file types (.pdf, etc.):** Marked as `failed` with list of supported types
- **Background processing:** Processing happens asynchronously after upload
- **Status tracking:** Documents progress through `uploaded` → `processing` → `completed`/`failed`

**OCR Notes:**
- Requires Tesseract OCR with language packs installed (see setup instructions)
- Uses multi-language OCR: English, Spanish, French, German, Portuguese, Italian, Chinese Simplified
- OCR quality depends on installed language data - install all language packs for best results
- If OCR finds no text in an image, document is marked as `failed`
- If OCR dependencies are missing, document is marked as `failed` with installation instructions
- Language detection is not yet implemented - `detected_language` will show "unknown"

**Translation & Explanation Features:**
- **Translation endpoint:** POST `/documents/{id}/translate` with language selection
- **Stub implementation:** Basic translation prefixing and explanation generation
- **Future enhancements:** Real translation API integration, language detection, intelligent LLM-based explanations

**Next steps planned:** PDF OCR support, real translation API integration, and intelligent LLM-based explanations.

## 🧪 Testing

The project includes comprehensive tests using pytest and FastAPI's TestClient:

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_app.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=term-missing
```

**Test Coverage:**
- ✅ Health check endpoint
- ✅ Document upload with file validation
- ✅ Document listing and retrieval
- ✅ Error handling (404, 400)
- ✅ File persistence verification
- ✅ Document structure validation
- ✅ Static file serving
- ✅ Translation endpoint (happy path and error cases)
- ✅ 19+ comprehensive tests

## 🌐 Web Frontend

The project includes a minimal web frontend for interacting with the API.

### Accessing the Frontend

1. **Start the server:**
   ```bash
   make run
   # or
   uvicorn app:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Open in browser:**
   - Navigate to `http://localhost:8000/static/`
   - Or directly to `http://localhost:8000/static/index.html`

### Frontend Features

**File Upload:**
- Drag-and-drop or click to select files
- Supports: `.txt`, `.png`, `.jpg`, `.jpeg`
- Real-time file size display

**Document Management:**
- View document metadata (ID, filename, source_type, status)
- Monitor processing status with visual badges
- Auto-refresh every 2 seconds (optional)
- Manual refresh button

**Content Display:**
- Extracted text area with syntax highlighting
- Translated text display (when available)
- Plain-language explanation display
- Target language indicator
- Built-in disclaimer

**Status Monitoring:**
- Backend health check indicator
- Last updated timestamp
- Processing status animations

**Keyboard Shortcuts:**
- `Ctrl/Cmd + R` - Refresh document
- `Ctrl/Cmd + U` - Open file picker

### Frontend Architecture

**Files:**
- `static/index.html` - Main HTML structure
- `static/style.css` - CSS styles with responsive design
- `static/app.js` - JavaScript application logic

**Technology:**
- Plain HTML/CSS/JavaScript (no frameworks)
- Uses `fetch()` API for backend communication
- Font Awesome icons for visual elements
- CSS Grid/Flexbox for responsive layout

**Integration with Backend:**
- Automatically checks backend health
- Uses FormData for file uploads
- Polls document status until completed/failed
- Handles errors gracefully with user feedback

## 🛠️ Development Guide

### 1. Add Document Processing Endpoints
Edit `app.py` and follow the existing patterns:
- Define Pydantic models for document uploads and responses
- Add route decorators for document processing pipeline
- Keep OCR, translation, and explanation logic modular

### 2. Integrate OCR Services
Consider integrating:
- Tesseract OCR (open source)
- Google Cloud Vision API
- Amazon Textract
- Azure Computer Vision

### 3. Add Translation Services
Integrate with:
- Google Translate API
- DeepL API
- Amazon Translate
- Microsoft Translator

### 4. Implement Explanation Engine
Options for plain-language explanations:
- Rule-based simplification templates
- LLM integration (OpenAI, Anthropic, local models)
- Hybrid approach with validation

## 🔒 Production Considerations

### Security
- Use environment variables for secrets
- Implement rate limiting
- Add request validation
- Use HTTPS in production

### Monitoring
- Add structured logging
- Integrate with Prometheus for metrics
- Set up health check endpoints
- Configure alerting

### 🧠 DeepSeek Integration (Intelligent Analysis)

Document explanation is powered by **DeepSeek Chat** (`deepseek-chat` model).

**To enable:**
1. Set the environment variable `DEEPSEEK_API_KEY` to a valid DeepSeek API key.
2. Restart the service.

**When enabled:**
- The backend sends extracted text to DeepSeek for intelligent analysis.
- The response includes `document_type`, `document_summary`, `key_details`, `suggested_actions`, and `confidence_notes`.

**When disabled (fallback):**
- If `DEEPSEEK_API_KEY` is not set (or the call fails), the system falls back to heuristic analysis.
- Heuristic analysis infers document type from OCR text patterns (bills, appointments, government notices, etc.).
- Key details are extracted via simple pattern matching (dates, amounts, reference numbers).
- The frontend shows standard translation + explanation, but with less detailed document understanding.

**Setting on Render.com:**
- Go to your service Dashboard → Environment → Add `DEEPSEEK_API_KEY`.
- The service will pick it up on next deployment.

### ☑️ Deployment Checklist

Before deploying to production:
- [ ] Set `DEEPSEEK_API_KEY` environment variable in Render dashboard
- [ ] Set `DEMO_ADMIN_KEY` to a secure random string (at least 32 chars)
- [ ] Verify `/health` returns `{"status":"healthy"}`
- [ ] Verify `/documents` returns 403 without `X-Admin-Key` header
- [ ] Verify `/documents/{id}` returns a document by its UUID (public read)
- [ ] Check startup logs confirm "DeepSeek: ENABLED" and "Admin Key: SET"

### Scaling
- Use Gunicorn with Uvicorn workers
- Implement database connection pooling
- Add caching layers
- Consider message queues for async processing

## 📄 License

MIT License - Feel free to use this template for any project.

## 🤝 Contributing

This is a starter template - fork it and make it your own! Suggestions and improvements are welcome.

---

**Built with:** FastAPI, Pydantic, Uvicorn, pytest, Docker

**Purpose:** Make complex documents accessible through OCR, translation, and plain-language explanations.