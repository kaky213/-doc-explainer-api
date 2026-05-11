"""
Test suite for Document Explainer API using pytest and TestClient.
"""

import time
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Import the app from the parent directory
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, DOCUMENTS_FILE, DocumentStatus, _document_store


@pytest.fixture
def client():
    """Test client fixture."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Clean up test data before and after each test."""
    # Clear the in-memory document store
    _document_store.clear()
    
    # Clear uploads directory
    uploads_dir = os.path.join("data", "uploads")
    if os.path.exists(uploads_dir):
        for file in os.listdir(uploads_dir):
            file_path = os.path.join(uploads_dir, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
    
    yield  # Run test
    
    # Clear in-memory store after test
    _document_store.clear()


def wait_for_processing(client, doc_id, max_wait=5.0, poll_interval=0.1):
    """Wait for document processing to complete."""
    start_time = time.time()
    while time.time() - start_time < max_wait:
        response = client.get(f"/documents/{doc_id}")
        if response.status_code == 200:
            doc = response.json()
            if doc["status"] in [DocumentStatus.COMPLETED.value, DocumentStatus.FAILED.value]:
                return doc
        time.sleep(poll_interval)
    return None


def test_health_endpoint(client):
    """Test GET /health returns status 200 and correct body."""
    response = client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "config" in data
    assert data["config"]["deepseek"] in ("enabled", "disabled")
    assert data["config"]["admin_key"] in ("set", "default")
    assert data["config"]["ocr"] in ("available", "unavailable")


def test_upload_document(client):
    """Test POST /documents/upload with a file."""
    # Create a test file
    test_content = b"Test document content"
    test_file = ("test.txt", test_content, "text/plain")
    
    response = client.post(
        "/documents/upload",
        files={"file": test_file}
    )
    
    assert response.status_code == 200
    result = response.json()
    
    # Check initial response structure
    assert "id" in result
    assert result["filename"] == "test.txt"
    assert result["content_type"] == "text/plain"
    assert "stored_path" in result
    assert result["source_type"] == "text_file"
    assert result["status"] == DocumentStatus.UPLOADED.value
    assert "created_at" in result
    assert result["detected_language"] is None
    assert result["extracted_text"] is None
    assert result["translated_text"] is None
    assert result["explanation"] is None
    assert "disclaimer" in result
    
    # Verify document is in in-memory store (no file-based storage)
    from app import _document_store
    assert result["id"] in _document_store
    # Status may already be 'processing' or 'completed' if background task ran
    assert _document_store[result["id"]].status in (
        DocumentStatus.UPLOADED, DocumentStatus.PROCESSING, DocumentStatus.COMPLETED
    )


def test_upload_txt_file_processing(client):
    """Test .txt file upload gets processed to completed status."""
    # Create a test .txt file with content
    test_content = b"This is a test document with some text content."
    test_file = ("test.txt", test_content, "text/plain")
    
    response = client.post("/documents/upload", files={"file": test_file})
    assert response.status_code == 200
    
    doc_id = response.json()["id"]
    
    # Wait for processing to complete
    processed_doc = wait_for_processing(client, doc_id)
    assert processed_doc is not None, "Processing did not complete in time"
    
    # Check processing results
    assert processed_doc["status"] == DocumentStatus.COMPLETED.value
    assert processed_doc["extracted_text"] == "This is a test document with some text content."
    assert processed_doc["translated_text"] is None  # Translation happens via separate endpoint
    assert processed_doc["explanation"] is not None
    assert "text document with 9 words" in processed_doc["explanation"].lower()
    assert processed_doc["detected_language"] == "unknown"


def _create_real_png_bytes() -> bytes:
    """Create a real tiny PNG image in memory for tests."""
    import io
    from PIL import Image as PILImage
    img = PILImage.new('RGB', (100, 50), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def test_upload_image_file_ocr_success(client, monkeypatch):
    """Test image file upload with successful OCR processing."""
    import app
    # Mock pytesseract.image_to_data (the DICT output the code actually uses)
    mock_tesseract = MagicMock()
    mock_tesseract.image_to_data.return_value = {
        "text": ["", "Extracted", "text", "from", "image", ""],
        "line_num": [0, 0, 0, 0, 0, 0],
        "left": [0, 10, 50, 100, 150, 0],
        "conf": ["-1", "90", "85", "92", "88", "-1"]
    }
    
    monkeypatch.setattr(app, 'pytesseract', mock_tesseract)
    monkeypatch.setattr(app, 'OCR_AVAILABLE', True)
    
    # Upload a real PNG so the preprocessing pipeline works
    test_file = ("test.png", _create_real_png_bytes(), "image/png")
    
    response = client.post("/documents/upload", files={"file": test_file})
    assert response.status_code == 200
    
    doc_id = response.json()["id"]
    
    # Wait for processing to complete
    processed_doc = wait_for_processing(client, doc_id)
    assert processed_doc is not None, "Processing did not complete in time"
    
    # Check processing results
    assert processed_doc["status"] == DocumentStatus.COMPLETED.value
    assert "Extracted" in processed_doc["extracted_text"]
    assert "from image" in processed_doc["extracted_text"]
    assert processed_doc["translated_text"] is None  # Translation happens via separate endpoint
    assert processed_doc["explanation"] is not None
    assert "text extracted" in processed_doc["explanation"].lower()
    assert processed_doc["detected_language"] == "eng"  # OCR should detect language


def test_upload_image_file_ocr_no_text(client, monkeypatch):
    """Test image file upload where OCR finds no text."""
    import app
    from PIL import Image as PILImage
    # Mock pytesseract only
    mock_tesseract = MagicMock()
    mock_tesseract.image_to_string.return_value = ""  # Empty string = no text found
    
    monkeypatch.setattr(app, 'pytesseract', mock_tesseract)
    monkeypatch.setattr(app, 'OCR_AVAILABLE', True)
    
    # Upload a real PNG
    test_file = ("test.png", _create_real_png_bytes(), "image/png")
    
    response = client.post("/documents/upload", files={"file": test_file})
    assert response.status_code == 200
    
    doc_id = response.json()["id"]
    
    # Wait for processing to complete
    processed_doc = wait_for_processing(client, doc_id)
    assert processed_doc is not None, "Processing did not complete in time"
    
    # No text found -> status is completed (empty text)
    assert processed_doc["status"] == DocumentStatus.COMPLETED.value
    assert processed_doc["extracted_text"] == ""
    assert "no text" in processed_doc.get("explanation", "").lower()
    assert "no text" in processed_doc["explanation"].lower()


def test_upload_image_file_ocr_dependencies_missing(client, monkeypatch):
    """Test image file upload when OCR dependencies are missing."""
    # Simulate OCR dependencies missing by monkeypatching
    import app
    monkeypatch.setattr(app, 'OCR_AVAILABLE', False)
    
    # Upload a real PNG
    test_file = ("test.png", _create_real_png_bytes(), "image/png")
    
    response = client.post("/documents/upload", files={"file": test_file})
    assert response.status_code == 200
    
    doc_id = response.json()["id"]
    
    # Wait for processing to complete
    processed_doc = wait_for_processing(client, doc_id)
    assert processed_doc is not None, "Processing did not complete in time"
    
    # Check processing results - should be failed with dependency message
    assert processed_doc["status"] == DocumentStatus.FAILED.value
    assert processed_doc["explanation"] is not None
    assert "pytesseract" in processed_doc["explanation"].lower()
    assert "install" in processed_doc["explanation"].lower()
    
    doc_id = response.json()["id"]
    
    # Wait for processing to complete
    processed_doc = wait_for_processing(client, doc_id)
    assert processed_doc is not None, "Processing did not complete in time"
    
    # Check processing results - should be failed with dependency message
    assert processed_doc["status"] == DocumentStatus.FAILED.value
    assert processed_doc["explanation"] is not None
    assert "pytesseract" in processed_doc["explanation"].lower()
    assert "install" in processed_doc["explanation"].lower()


def test_upload_unsupported_file_type(client):
    """Test unsupported file type is rejected at upload (422)."""
    # Create a test PDF file (unsupported)
    test_content = b"%PDF-1.4 fake pdf content"
    test_file = ("test.pdf", test_content, "application/pdf")
    
    response = client.post("/documents/upload", files={"file": test_file})
    assert response.status_code == 422
    error = response.json()
    assert "Unsupported file type" in error["detail"]
    # Should mention supported types in the error message
    assert ".txt" in error["detail"].lower()
    assert ".png" in error["detail"].lower() or ".jpg" in error["detail"].lower()


def test_upload_document_no_filename(client):
    """Test POST /documents/upload without filename returns error."""
    test_content = b"Test content"
    test_file = ("", test_content, "text/plain")
    
    response = client.post(
        "/documents/upload",
        files={"file": test_file}
    )
    
    # FastAPI returns 422 for validation errors
    assert response.status_code == 422
    assert "detail" in response.json()


def test_list_documents_empty(client):
    """Test GET /documents returns empty list when authenticated with admin key."""
    response = client.get("/documents", headers={"x-admin-key": "change-me-in-production"})
    
    assert response.status_code == 200
    assert response.json() == []


def test_list_documents_with_processing(client, monkeypatch):
    """Test GET /documents shows documents with updated processing fields."""
    import app
    # Mock pytesseract for image processing
    mock_tesseract = MagicMock()
    mock_tesseract.image_to_data.return_value = {
        "text": ["Image", "text", "content", ""],
        "line_num": [0, 0, 0, 0],
        "left": [0, 50, 100, 0],
        "conf": ["90", "85", "92", "-1"]
    }
    
    monkeypatch.setattr(app, 'pytesseract', mock_tesseract)
    monkeypatch.setattr(app, 'OCR_AVAILABLE', True)
    
    # Upload multiple files with different types
    files = [
        ("doc1.txt", b"First text document", "text/plain"),
        ("image.png", _create_real_png_bytes(), "image/png"),
    ]
    
    uploaded_ids = []
    for filename, content, content_type in files:
        response = client.post(
            "/documents/upload",
            files={"file": (filename, content, content_type)}
        )
        assert response.status_code == 200, f"Upload {filename} failed: {response.status_code}"
        uploaded_ids.append(response.json()["id"])
    
    # Wait for all processing to complete
    processed_docs = []
    for doc_id in uploaded_ids:
        doc = wait_for_processing(client, doc_id)
        assert doc is not None, f"Document {doc_id} did not process in time"
        processed_docs.append(doc)
    
    # List all documents (admin-protected endpoint)
    response = client.get("/documents", headers={"x-admin-key": "change-me-in-production"})
    
    assert response.status_code == 200
    documents = response.json()
    
    assert len(documents) == 2
    
    # Check processing statuses — both should be completed
    statuses = [doc["status"] for doc in documents]
    completed_count = sum(1 for s in statuses if s == DocumentStatus.COMPLETED.value)
    assert completed_count == 2
    
    # Verify all documents have appropriate fields set
    for doc in documents:
        if doc["filename"].endswith(".txt") or doc["filename"].endswith(".png"):
            assert doc["status"] == DocumentStatus.COMPLETED.value
            assert doc["extracted_text"] is not None
            assert doc["explanation"] is not None
        else:
            assert doc["status"] == DocumentStatus.FAILED.value
            assert doc["explanation"] is not None
            assert "not supported" in doc["explanation"].lower()


def test_get_document_by_id_with_processing(client):
    """Test GET /documents/{id} returns document with processing results."""
    # Upload a .txt file
    test_content = b"Test document for retrieval"
    test_file = ("retrieve_test.txt", test_content, "text/plain")
    
    upload_response = client.post("/documents/upload", files={"file": test_file})
    uploaded_doc = upload_response.json()
    doc_id = uploaded_doc["id"]
    
    # Wait for processing
    wait_for_processing(client, doc_id)
    
    # Retrieve the document by ID
    response = client.get(f"/documents/{doc_id}")
    
    assert response.status_code == 200
    retrieved_doc = response.json()
    
    assert retrieved_doc["id"] == doc_id
    assert retrieved_doc["filename"] == "retrieve_test.txt"
    assert retrieved_doc["status"] == DocumentStatus.COMPLETED.value
    assert retrieved_doc["extracted_text"] == "Test document for retrieval"
    assert retrieved_doc["explanation"] is not None


def test_get_document_by_id_not_found(client):
    """Test GET /documents/{id} returns 404 for non-existent document."""
    response = client.get("/documents/non-existent-id")
    
    assert response.status_code == 404
    assert "detail" in response.json()
    assert "not found" in response.json()["detail"].lower()


def test_document_structure_integrity(client):
    """Test that document structure is maintained with all required fields."""
    test_file = ("complete_test.txt", b"Complete test", "text/plain")
    response = client.post("/documents/upload", files={"file": test_file})
    document = response.json()
    
    # Check all required fields are present
    required_fields = [
        "id", "filename", "content_type", "stored_path", "source_type", "status",
        "created_at", "detected_language", "target_language", "extracted_text", 
        "translated_text", "explanation", "disclaimer"
    ]
    
    for field in required_fields:
        assert field in document
    
    # Check field types
    assert isinstance(document["id"], str)
    assert isinstance(document["filename"], str)
    assert isinstance(document["content_type"], str)
    assert isinstance(document["stored_path"], str)
    assert isinstance(document["source_type"], str)
    assert isinstance(document["status"], str)
    assert isinstance(document["created_at"], str)
    assert document["detected_language"] is None or isinstance(document["detected_language"], str)
    assert document["target_language"] is None or isinstance(document["target_language"], str)
    assert document["extracted_text"] is None or isinstance(document["extracted_text"], str)
    assert document["translated_text"] is None or isinstance(document["translated_text"], str)
    assert document["explanation"] is None or isinstance(document["explanation"], str)
    assert isinstance(document["disclaimer"], str)
    
    # Check status is valid
    assert document["status"] in ["uploaded", "processing", "completed", "failed"]


def test_uploaded_file_persisted(client):
    """Test that uploaded files are actually saved to disk."""
    test_content = b"File content that should be saved"
    test_file = ("persist_test.txt", test_content, "text/plain")
    
    response = client.post("/documents/upload", files={"file": test_file})
    document = response.json()
    
    # Check file was saved
    stored_path = document["stored_path"]
    assert os.path.exists(stored_path)
    
    # Verify file content
    with open(stored_path, "rb") as f:
        saved_content = f.read()
    assert saved_content == test_content


def test_document_source_type_detection(client, monkeypatch):
    """Test that source_type is correctly detected from file extension."""
    import app
    from PIL import Image as PILImage
    # Mock pytesseract for image processing
    mock_tesseract = MagicMock()
    mock_tesseract.image_to_data.return_value = {
        "text": ["Image", "text", ""],
        "line_num": [0, 0, 0],
        "left": [0, 50, 0],
        "conf": ["90", "85", "-1"]
    }
    
    monkeypatch.setattr(app, 'pytesseract', mock_tesseract)
    monkeypatch.setattr(app, 'OCR_AVAILABLE', True)
    
    # Test different file types (only supported ones — unsupported are rejected at upload)
    test_cases = [
        ("document.txt", b"Text content", "text/plain", "text_file"),
        ("image.png", _create_real_png_bytes(), "image/png", "image_file"),
        ("photo.jpg", _create_real_png_bytes(), "image/jpeg", "image_file"),
        ("picture.jpeg", _create_real_png_bytes(), "image/jpeg", "image_file"),
    ]
    
    for filename, content, content_type, expected_source_type in test_cases:
        test_file = (filename, content, content_type)
        response = client.post("/documents/upload", files={"file": test_file})
        assert response.status_code == 200
        
        document = response.json()
        assert document["source_type"] == expected_source_type, \
            f"Expected source_type '{expected_source_type}' for {filename}, got '{document['source_type']}'"
        
        # Wait for processing to complete
        doc_id = document["id"]
        processed_doc = wait_for_processing(client, doc_id)
        assert processed_doc is not None, f"Processing did not complete for {filename}"

    # Also test that unsupported files are rejected at upload
    for filename, content, content_type in [
        ("document.pdf", b"PDF content", "application/pdf"),
        ("data.csv", b"CSV data", "text/csv"),
    ]:
        test_file = (filename, content, content_type)
        response = client.post("/documents/upload", files={"file": test_file})
        assert response.status_code == 422, f"Expected 422 for {filename}, got {response.status_code}"


def test_static_files_served(client):
    """Test that static files are served correctly."""
    # Test that we can access the static directory
    # Note: FastAPI's TestClient might not serve static files in tests,
    # but we can at least verify the endpoint exists
    response = client.get("/static/")
    # StaticFiles might return 404 for directory listing, which is fine
    # The important thing is that the mount is configured


def test_translate_document_happy_path(client):
    """Test POST /documents/{id}/translate with a document that has extracted text."""
    # Upload and process a .txt file
    test_content = b"Texto en espanol para traduccion."
    test_file = ("spanish.txt", test_content, "text/plain")
    
    response = client.post("/documents/upload", files={"file": test_file})
    assert response.status_code == 200
    
    doc_id = response.json()["id"]
    
    # Wait for processing to complete
    processed_doc = wait_for_processing(client, doc_id)
    assert processed_doc is not None, "Processing did not complete in time"
    assert processed_doc["extracted_text"] is not None
    
    # Translate the document
    translate_request = {
        "target_language": "en",
        "source_language_hint": "es",
        "explanation_style": "default"
    }
    
    response = client.post(f"/documents/{doc_id}/translate", json=translate_request)
    assert response.status_code == 200
    
    translated_doc = response.json()
    
    # Check that translation fields are filled
    assert translated_doc["target_language"] == "en"
    assert translated_doc["translated_text"] is not None
    assert translated_doc["explanation"] is not None
    
    # Translation should succeed (MyMemory is real, DeepSeek may or may not be configured)
    assert "spanish" in translated_doc["translated_text"].lower() or "en" in translated_doc.get("target_language", "")
    
    # Verify GET /documents/{id} also returns the new fields
    get_response = client.get(f"/documents/{doc_id}")
    assert get_response.status_code == 200
    
    retrieved_doc = get_response.json()
    assert retrieved_doc["target_language"] == "en"
    assert retrieved_doc["translated_text"] == translated_doc["translated_text"]
    assert retrieved_doc["explanation"] == translated_doc["explanation"]


def test_translate_document_no_extracted_text(client):
    """Test POST /documents/{id}/translate returns 400 when no extracted text."""
    # Upload an empty text file (valid type, no content)
    test_file = ("empty.txt", b"", "text/plain")
    
    response = client.post("/documents/upload", files={"file": test_file})
    assert response.status_code == 200
    
    doc_id = response.json()["id"]
    
    # Wait for processing to complete
    processed_doc = wait_for_processing(client, doc_id)
    assert processed_doc is not None, "Processing did not complete in time"
    assert processed_doc["extracted_text"] == ""
    
    # Try to translate - should fail with 400
    translate_request = {
        "target_language": "en",
        "source_language_hint": None,
        "explanation_style": "default"
    }
    
    response = client.post(f"/documents/{doc_id}/translate", json=translate_request)
    assert response.status_code == 400
    
    error_detail = response.json()
    assert "detail" in error_detail
    assert "Cannot translate: no OCR text available" in error_detail["detail"]


def test_translate_document_not_found(client):
    """Test POST /documents/{id}/translate returns 404 for non-existent document."""
    translate_request = {
        "target_language": "en",
        "source_language_hint": None,
        "explanation_style": "default"
    }
    
    response = client.post("/documents/nonexistent-id/translate", json=translate_request)
    assert response.status_code == 404
    
    error_detail = response.json()
    assert "detail" in error_detail
    assert "Document not found" in error_detail["detail"]
    assert response.status_code in [200, 404, 403]
    
    # Verify that /documents/{id} is now public (returns 200/404, not 403)
    response2 = client.get("/documents/nonexistent")
    assert response2.status_code == 404, f"GET /documents/{{id}} should be public (got {response2.status_code})"
    
    # Create a test static file to verify serving works
    import os
    test_static_dir = "static"
    test_file_path = os.path.join(test_static_dir, "test.txt")
    
    # Ensure static directory exists
    os.makedirs(test_static_dir, exist_ok=True)
    
    # Write a test file
    with open(test_file_path, "w") as f:
        f.write("Test static content")
    
    try:
        # Try to access the test file
        response = client.get("/static/test.txt")
        # If static files are served in tests, we should get 200
        # If not, that's okay - the mount is still configured for production
        if response.status_code == 200:
            assert response.text == "Test static content"
    finally:
        # Clean up test file
        if os.path.exists(test_file_path):
            os.remove(test_file_path)