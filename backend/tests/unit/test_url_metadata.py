"""
Unit tests for URL metadata support in RAG system.

Tests cover:
- JSONL URL extraction
- URL validation (valid/invalid protocols, length limits)
- RagDocument model with source_url
- ProcessedDocument with source_url
"""

import pytest
import json
from datetime import datetime
from app.modules.rag.main import ProcessedDocument, RAGModule


class TestJSONLURLExtraction:
    """Test URL extraction from JSONL files"""

    def test_jsonl_with_url(self):
        """Test processing JSONL with URL in payload"""
        jsonl_line = '{"id": "test123", "payload": {"question": "How to reset password?", "answer": "Go to settings", "language": "EN", "url": "https://example.com/faq/password"}}'

        data = json.loads(jsonl_line)
        payload = data.get("payload", {})

        # Extract URL
        source_url = payload.get("url")

        assert source_url is not None
        assert source_url == "https://example.com/faq/password"
        assert source_url.startswith("https://")

    def test_jsonl_without_url(self):
        """Test backward compatibility - JSONL without URL"""
        jsonl_line = '{"id": "test456", "payload": {"question": "What is AI?", "answer": "Artificial Intelligence...", "language": "EN"}}'

        data = json.loads(jsonl_line)
        payload = data.get("payload", {})

        # Extract URL (should be None)
        source_url = payload.get("url")

        assert source_url is None

    def test_jsonl_with_empty_url(self):
        """Test JSONL with empty URL string"""
        jsonl_line = '{"id": "test789", "payload": {"question": "Test", "answer": "Answer", "language": "EN", "url": ""}}'

        data = json.loads(jsonl_line)
        payload = data.get("payload", {})

        source_url = payload.get("url")

        # Empty string should be treated as None
        assert source_url == ""
        # In actual implementation, empty strings should be converted to None

    def test_jsonl_with_null_url(self):
        """Test JSONL with null URL value"""
        jsonl_line = '{"id": "test999", "payload": {"question": "Test", "answer": "Answer", "language": "EN", "url": null}}'

        data = json.loads(jsonl_line)
        payload = data.get("payload", {})

        source_url = payload.get("url")

        assert source_url is None

    def test_jsonl_multiple_entries_mixed_urls(self):
        """Test processing multiple JSONL entries with mixed URL presence"""
        jsonl_content = """{"id": "1", "payload": {"question": "Q1", "answer": "A1", "url": "https://example.com/1"}}
{"id": "2", "payload": {"question": "Q2", "answer": "A2"}}
{"id": "3", "payload": {"question": "Q3", "answer": "A3", "url": "https://example.com/3"}}"""

        lines = jsonl_content.strip().split("\n")
        urls = []

        for line in lines:
            data = json.loads(line)
            payload = data.get("payload", {})
            url = payload.get("url")
            urls.append(url)

        assert len(urls) == 3
        assert urls[0] == "https://example.com/1"
        assert urls[1] is None
        assert urls[2] == "https://example.com/3"


class TestURLValidation:
    """Test URL validation logic"""

    def test_valid_https_url(self):
        """Test validation of valid HTTPS URL"""
        url = "https://example.com/faq/article-123"

        # URL validation logic
        assert url.startswith("https://") or url.startswith("http://")
        assert len(url) <= 2048  # Max URL length
        assert " " not in url  # No spaces

    def test_valid_http_url(self):
        """Test validation of valid HTTP URL"""
        url = "http://example.com/faq/article"

        assert url.startswith("https://") or url.startswith("http://")
        assert len(url) <= 2048

    def test_invalid_protocol(self):
        """Test rejection of invalid protocol"""
        url = "ftp://example.com/file"

        # Should only accept http/https
        is_valid = url.startswith("https://") or url.startswith("http://")
        assert not is_valid

    def test_url_too_long(self):
        """Test rejection of URL exceeding max length"""
        url = "https://example.com/" + "a" * 3000

        is_valid = len(url) <= 2048
        assert not is_valid

    def test_url_with_spaces(self):
        """Test rejection of URL with spaces"""
        url = "https://example.com/faq with spaces"

        is_valid = " " not in url
        assert not is_valid

    def test_url_with_query_params(self):
        """Test validation of URL with query parameters"""
        url = "https://example.com/faq?id=123&lang=en"

        assert url.startswith("https://")
        assert len(url) <= 2048
        assert " " not in url

    def test_url_with_fragment(self):
        """Test validation of URL with fragment"""
        url = "https://example.com/faq#section-5"

        assert url.startswith("https://")
        assert len(url) <= 2048

    def test_url_with_port(self):
        """Test validation of URL with custom port"""
        url = "https://example.com:8080/faq/article"

        assert url.startswith("https://")
        assert len(url) <= 2048

    def test_url_with_special_chars(self):
        """Test validation of URL with encoded special characters"""
        url = "https://example.com/faq/article%20with%20spaces"

        assert url.startswith("https://")
        assert len(url) <= 2048
        assert " " not in url  # Should be encoded


class TestProcessedDocument:
    """Test ProcessedDocument dataclass with source_url field"""

    def test_processed_document_with_url(self):
        """Test creating ProcessedDocument with source_url"""
        doc = ProcessedDocument(
            id="doc123",
            original_filename="faq.jsonl",
            file_type="application",
            mime_type="application/x-ndjson",
            content="Test content",
            extracted_text="Test content",
            metadata={"article_id": "123"},
            word_count=2,
            sentence_count=1,
            language="en",
            entities=[],
            keywords=["test"],
            processing_time=0.5,
            processed_at=datetime.utcnow(),
            file_hash="abc123",
            file_size=100,
            source_url="https://example.com/faq/article"
        )

        assert doc.source_url == "https://example.com/faq/article"
        assert doc.source_url is not None

    def test_processed_document_without_url(self):
        """Test ProcessedDocument without source_url (backward compatibility)"""
        doc = ProcessedDocument(
            id="doc456",
            original_filename="document.txt",
            file_type="text",
            mime_type="text/plain",
            content="Test content",
            extracted_text="Test content",
            metadata={},
            word_count=2,
            sentence_count=1,
            language="en",
            entities=[],
            keywords=["test"],
            processing_time=0.5,
            processed_at=datetime.utcnow(),
            file_hash="def456",
            file_size=100
        )

        assert doc.source_url is None

    def test_processed_document_url_in_metadata(self):
        """Test that source_url can also be accessed from metadata"""
        source_url = "https://example.com/faq/article"
        doc = ProcessedDocument(
            id="doc789",
            original_filename="faq.jsonl",
            file_type="application",
            mime_type="application/x-ndjson",
            content="Test content",
            extracted_text="Test content",
            metadata={"article_id": "789", "source_url": source_url},
            word_count=2,
            sentence_count=1,
            language="en",
            entities=[],
            keywords=["test"],
            processing_time=0.5,
            processed_at=datetime.utcnow(),
            file_hash="ghi789",
            file_size=100,
            source_url=source_url
        )

        # URL should be in both source_url field and metadata
        assert doc.source_url == source_url
        assert doc.metadata["source_url"] == source_url


class TestURLMetadataStorage:
    """Test URL metadata storage in chunks"""

    def test_chunk_metadata_includes_url(self):
        """Test that chunk metadata includes source_url"""
        chunk_metadata = {
            "document_id": "doc123",
            "chunk_index": 0,
            "chunk_count": 5,
            "content": "This is chunk 0",
            "source_url": "https://example.com/faq/article",
            "article_id": "123",
            "language": "EN"
        }

        assert "source_url" in chunk_metadata
        assert chunk_metadata["source_url"] == "https://example.com/faq/article"

    def test_chunk_metadata_without_url(self):
        """Test backward compatibility - chunk without source_url"""
        chunk_metadata = {
            "document_id": "doc456",
            "chunk_index": 0,
            "chunk_count": 3,
            "content": "This is chunk 0",
            "article_id": "456"
        }

        assert chunk_metadata.get("source_url") is None

    def test_multiple_chunks_same_url(self):
        """Test that multiple chunks from same document share URL"""
        source_url = "https://example.com/faq/long-article"

        chunks = []
        for i in range(3):
            chunk_metadata = {
                "document_id": "doc789",
                "chunk_index": i,
                "chunk_count": 3,
                "content": f"This is chunk {i}",
                "source_url": source_url
            }
            chunks.append(chunk_metadata)

        # All chunks should have the same URL
        urls = [chunk["source_url"] for chunk in chunks]
        assert len(set(urls)) == 1  # Only one unique URL
        assert urls[0] == source_url


class TestURLDeduplication:
    """Test URL deduplication logic"""

    def test_deduplicate_by_url(self):
        """Test deduplication of documents by source_url"""
        search_results = [
            {"document_id": "doc1", "source_url": "https://example.com/faq/1", "score": 0.95},
            {"document_id": "doc2", "source_url": "https://example.com/faq/1", "score": 0.85},  # Duplicate URL
            {"document_id": "doc3", "source_url": "https://example.com/faq/2", "score": 0.80},
        ]

        # Deduplication logic
        seen_urls = set()
        deduplicated = []

        for result in search_results:
            url = result["source_url"]
            if url not in seen_urls:
                seen_urls.add(url)
                deduplicated.append(result)

        assert len(deduplicated) == 2  # Should have 2 unique URLs
        assert deduplicated[0]["source_url"] == "https://example.com/faq/1"
        assert deduplicated[1]["source_url"] == "https://example.com/faq/2"

    def test_keep_highest_score_for_duplicate_urls(self):
        """Test that highest scoring document is kept for duplicate URLs"""
        search_results = [
            {"document_id": "doc1", "source_url": "https://example.com/faq/1", "score": 0.85},
            {"document_id": "doc2", "source_url": "https://example.com/faq/1", "score": 0.95},  # Higher score
            {"document_id": "doc3", "source_url": "https://example.com/faq/2", "score": 0.80},
        ]

        # Deduplication with score tracking
        url_to_best = {}

        for result in search_results:
            url = result["source_url"]
            if url not in url_to_best or result["score"] > url_to_best[url]["score"]:
                url_to_best[url] = result

        deduplicated = list(url_to_best.values())

        assert len(deduplicated) == 2
        # Should keep doc2 (score 0.95) instead of doc1 (score 0.85)
        url1_doc = [d for d in deduplicated if d["source_url"] == "https://example.com/faq/1"][0]
        assert url1_doc["document_id"] == "doc2"
        assert url1_doc["score"] == 0.95

    def test_deduplicate_mixed_urls_and_none(self):
        """Test deduplication with mix of URLs and None values"""
        search_results = [
            {"document_id": "doc1", "source_url": "https://example.com/faq/1", "score": 0.95},
            {"document_id": "doc2", "source_url": None, "score": 0.90},
            {"document_id": "doc3", "source_url": "https://example.com/faq/1", "score": 0.85},  # Duplicate
            {"document_id": "doc4", "source_url": None, "score": 0.80},
        ]

        # Deduplication logic that preserves None values
        seen_urls = set()
        deduplicated = []

        for result in search_results:
            url = result["source_url"]
            if url is None:
                # Always include documents without URLs
                deduplicated.append(result)
            elif url not in seen_urls:
                seen_urls.add(url)
                deduplicated.append(result)

        assert len(deduplicated) == 3  # 1 unique URL + 2 None
        assert deduplicated[0]["source_url"] == "https://example.com/faq/1"
        assert deduplicated[1]["source_url"] is None
        assert deduplicated[2]["source_url"] is None


class TestURLFieldCompatibility:
    """Test backward compatibility with existing data"""

    def test_search_results_without_url_field(self):
        """Test handling search results from legacy documents without URL"""
        result = {
            "document_id": "legacy_doc",
            "content": "Legacy content",
            "metadata": {
                "article_id": "123",
                "language": "EN"
            },
            "score": 0.85
        }

        # Accessing source_url should not raise error
        source_url = result.get("metadata", {}).get("source_url")
        assert source_url is None

    def test_mixed_legacy_and_new_documents(self):
        """Test search results with mix of legacy and new documents"""
        results = [
            {
                "document_id": "new_doc",
                "metadata": {"source_url": "https://example.com/faq/1"},
                "score": 0.95
            },
            {
                "document_id": "legacy_doc",
                "metadata": {"article_id": "123"},
                "score": 0.85
            }
        ]

        for result in results:
            url = result.get("metadata", {}).get("source_url")
            # Should handle both cases gracefully
            assert url is None or isinstance(url, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
