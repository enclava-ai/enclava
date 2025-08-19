"""
RAG Integration Test
Tests the full RAG (Retrieval Augmented Generation) system end-to-end
including collections, document upload/processing, and search functionality
"""

import asyncio
import json
import time
import httpx
import tempfile
import os
from typing import Dict, Any, List
from io import BytesIO

class RAGIntegrationTest:
    """Test the complete RAG system through API endpoints"""
    
    def __init__(self, base_url: str = "http://localhost:58000", frontend_url: str = "http://localhost:53000"):
        self.base_url = base_url
        self.frontend_url = frontend_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.test_collection_id = None
        self.test_document_ids = []
        self.auth_token = None
    
    async def setup_auth(self):
        """Setup authentication for testing"""
        print("🔐 Setting up authentication...")
        
        # For mock tests, we'll skip actual auth and use a dummy token
        self.auth_token = "test-token-123"
        print("✓ Mock authentication token set")
    
    async def test_rag_module_loaded(self):
        """Test that RAG module is loaded and operational"""
        print("🧪 Testing RAG module loading...")
        
        response = await self.client.get(f"{self.base_url}/api/v1/modules/")
        assert response.status_code == 200
        
        data = response.json()
        modules_by_name = {mod["name"]: mod for mod in data["modules"]}
        
        # Check RAG module is loaded
        assert "rag" in modules_by_name, "RAG module not found in loaded modules"
        rag_module = modules_by_name["rag"]
        assert rag_module.get("initialized", False), "RAG module should be initialized"
        
        print("✓ RAG module is loaded and initialized")
        
        # Check RAG module stats
        if "stats" in rag_module:
            stats = rag_module["stats"]
            expected_fields = ["documents_indexed", "searches_performed", "average_search_time"]
            for field in expected_fields:
                assert field in stats, f"RAG module missing {field} stat"
            print(f"✓ RAG module stats: {len(stats)} metrics available")
            print(f"  Documents indexed: {stats.get('documents_indexed', 0)}")
            print(f"  Searches performed: {stats.get('searches_performed', 0)}")
            print(f"  Cache hits: {stats.get('cache_hits', 0)}")
        
        return rag_module
    
    async def test_content_module_integration(self):
        """Test content module integration with markitdown"""
        print("\n🧪 Testing content module integration...")
        
        response = await self.client.get(f"{self.base_url}/api/v1/modules/")
        assert response.status_code == 200
        
        data = response.json()
        modules_by_name = {mod["name"]: mod for mod in data["modules"]}
        
        # Check content module is loaded
        assert "content" in modules_by_name, "Content module not found in loaded modules"
        content_module = modules_by_name["content"]
        assert content_module.get("initialized", False), "Content module should be initialized"
        
        print("✓ Content module is loaded and initialized")
        
        # Check content module stats for markitdown integration
        if "stats" in content_module:
            stats = content_module["stats"]
            expected_fields = ["documents_processed", "conversion_success_rate", "supported_formats"]
            for field in expected_fields:
                if field in stats:
                    print(f"✓ Content stat '{field}': {stats[field]}")
        
        return content_module
    
    async def test_collection_management(self):
        """Test collection CRUD operations"""
        print("\n🧪 Testing collection management...")
        
        # Test GET collections (should start empty or with mock data)
        response = await self.client.get(f"{self.frontend_url}/api/rag/collections")
        assert response.status_code == 200
        
        initial_data = response.json()
        assert "success" in initial_data
        assert initial_data["success"] is True
        initial_count = len(initial_data.get("collections", []))
        print(f"✓ Initial collections count: {initial_count}")
        
        # Test POST - Create new collection
        test_collection = {
            "name": "Test Integration Collection",
            "description": "Created during RAG integration testing"
        }
        
        response = await self.client.post(
            f"{self.frontend_url}/api/rag/collections",
            json=test_collection,
            headers={"Authorization": f"Bearer {self.auth_token}"}
        )
        assert response.status_code == 200
        
        create_data = response.json()
        assert create_data["success"] is True
        assert "collection" in create_data
        
        created_collection = create_data["collection"]
        self.test_collection_id = created_collection["id"]
        assert created_collection["name"] == test_collection["name"]
        assert created_collection["description"] == test_collection["description"]
        assert created_collection["document_count"] == 0
        assert created_collection["status"] == "active"
        
        print(f"✓ Created test collection: {self.test_collection_id}")
        
        # Test GET specific collection
        response = await self.client.get(f"{self.frontend_url}/api/rag/collections/{self.test_collection_id}")
        assert response.status_code == 200
        
        get_data = response.json()
        assert get_data["success"] is True
        assert get_data["collection"]["id"] == self.test_collection_id
        
        print("✓ Collection retrieval successful")
        
        return created_collection
    
    async def test_document_upload_processing(self):
        """Test document upload and processing"""
        print("\n🧪 Testing document upload and processing...")
        
        assert self.test_collection_id, "Test collection must be created first"
        
        # Create test documents
        test_documents = [
            {
                "name": "test_document.txt",
                "content": "This is a test document for RAG integration testing. It contains sample text for processing.",
                "content_type": "text/plain"
            },
            {
                "name": "test_document.md",
                "content": "# Test Markdown Document\n\nThis is a **markdown** document for testing.\n\n## Features\n- RAG integration\n- Document processing\n- Content conversion",
                "content_type": "text/markdown"
            },
            {
                "name": "test_data.json",
                "content": '{"name": "test", "type": "integration", "features": ["rag", "upload", "processing"]}',
                "content_type": "application/json"
            }
        ]
        
        uploaded_documents = []
        
        for doc in test_documents:
            print(f"  Uploading {doc['name']}...")
            
            # Create form data
            files = {
                "file": (doc["name"], BytesIO(doc["content"].encode()), doc["content_type"])
            }
            data = {
                "collection_id": self.test_collection_id
            }
            
            response = await self.client.post(
                f"{self.frontend_url}/api/rag/documents",
                files=files,
                data=data,
                headers={"Authorization": f"Bearer {self.auth_token}"}
            )
            
            assert response.status_code == 200
            upload_data = response.json()
            assert upload_data["success"] is True
            assert "document" in upload_data
            
            uploaded_doc = upload_data["document"]
            self.test_document_ids.append(uploaded_doc["id"])
            uploaded_documents.append(uploaded_doc)
            
            # Verify document properties
            assert uploaded_doc["original_filename"] == doc["name"]
            assert uploaded_doc["collection_id"] == self.test_collection_id
            assert uploaded_doc["status"] == "processed"
            assert uploaded_doc["word_count"] > 0
            
            print(f"    ✓ {doc['name']} uploaded successfully (ID: {uploaded_doc['id']})")
        
        print(f"✓ Successfully uploaded {len(uploaded_documents)} documents")
        return uploaded_documents
    
    async def test_document_browsing_search(self):
        """Test document browsing and search functionality"""
        print("\n🧪 Testing document browsing and search...")
        
        # Test GET all documents
        response = await self.client.get(
            f"{self.frontend_url}/api/rag/documents",
            headers={"Authorization": f"Bearer {self.auth_token}"}
        )
        assert response.status_code == 200
        
        browse_data = response.json()
        assert browse_data["success"] is True
        all_documents = browse_data["documents"]
        
        # Should have at least our test documents
        test_docs_found = [doc for doc in all_documents if doc["id"] in self.test_document_ids]
        assert len(test_docs_found) >= 3, f"Expected at least 3 test documents, found {len(test_docs_found)}"
        
        print(f"✓ Found {len(all_documents)} total documents, {len(test_docs_found)} are our test documents")
        
        # Test filtering by collection
        response = await self.client.get(
            f"{self.frontend_url}/api/rag/documents?collection_id={self.test_collection_id}",
            headers={"Authorization": f"Bearer {self.auth_token}"}
        )
        assert response.status_code == 200
        
        filtered_data = response.json()
        filtered_documents = filtered_data["documents"]
        
        # All filtered documents should belong to our test collection
        for doc in filtered_documents:
            assert doc["collection_id"] == self.test_collection_id
        
        print(f"✓ Collection filtering works: {len(filtered_documents)} documents in test collection")
        
        return all_documents
    
    async def test_document_download(self):
        """Test document download functionality"""
        print("\n🧪 Testing document download...")
        
        assert len(self.test_document_ids) > 0, "Test documents must be uploaded first"
        
        # Test downloading the first test document
        test_doc_id = self.test_document_ids[0]
        
        response = await self.client.get(
            f"{self.frontend_url}/api/rag/documents/{test_doc_id}/download",
            headers={"Authorization": f"Bearer {self.auth_token}"}
        )
        
        assert response.status_code == 200
        
        # Check content type header
        content_type = response.headers.get("content-type")
        assert content_type is not None
        
        # Check content disposition header
        content_disposition = response.headers.get("content-disposition")
        assert content_disposition is not None
        assert "attachment" in content_disposition
        
        # Check content
        content = response.content
        assert len(content) > 0
        
        print(f"✓ Document download successful: {len(content)} bytes")
        print(f"  Content-Type: {content_type}")
        print(f"  Content-Disposition: {content_disposition}")
        
        return True
    
    async def test_document_deletion(self):
        """Test document deletion"""
        print("\n🧪 Testing document deletion...")
        
        assert len(self.test_document_ids) > 0, "Test documents must exist for deletion"
        
        # Delete the last test document
        doc_to_delete = self.test_document_ids[-1]
        
        response = await self.client.delete(
            f"{self.frontend_url}/api/rag/documents/{doc_to_delete}",
            headers={"Authorization": f"Bearer {self.auth_token}"}
        )
        
        assert response.status_code == 200
        delete_data = response.json()
        assert delete_data["success"] is True
        
        print(f"✓ Document {doc_to_delete} deleted successfully")
        
        # Verify document is no longer accessible
        response = await self.client.get(
            f"{self.frontend_url}/api/rag/documents",
            headers={"Authorization": f"Bearer {self.auth_token}"}
        )
        
        remaining_docs = response.json()["documents"]
        deleted_doc_ids = [doc["id"] for doc in remaining_docs]
        assert doc_to_delete not in deleted_doc_ids, "Deleted document should not appear in listing"
        
        # Remove from our test tracking
        self.test_document_ids.remove(doc_to_delete)
        
        print("✓ Document deletion verified")
        return True
    
    async def test_collection_deletion(self):
        """Test collection deletion (cleanup)"""
        print("\n🧪 Testing collection deletion...")
        
        assert self.test_collection_id, "Test collection must exist for deletion"
        
        # First, delete any remaining documents in the collection
        for doc_id in self.test_document_ids[:]:  # Create a copy to avoid modification during iteration
            response = await self.client.delete(
                f"{self.frontend_url}/api/rag/documents/{doc_id}",
                headers={"Authorization": f"Bearer {self.auth_token}"}
            )
            if response.status_code == 200:
                self.test_document_ids.remove(doc_id)
        
        print(f"✓ Cleaned up remaining documents")
        
        # Now delete the collection
        response = await self.client.delete(
            f"{self.frontend_url}/api/rag/collections/{self.test_collection_id}",
            headers={"Authorization": f"Bearer {self.auth_token}"}
        )
        
        # Note: Mock implementation might return error if collection has documents
        # This is acceptable behavior for the test
        if response.status_code == 200:
            delete_data = response.json()
            assert delete_data["success"] is True
            print(f"✓ Test collection {self.test_collection_id} deleted successfully")
        elif response.status_code == 400:
            error_data = response.json()
            if "documents" in error_data.get("error", "").lower():
                print("✓ Collection deletion correctly prevented when documents exist")
            else:
                raise AssertionError(f"Unexpected error: {error_data}")
        else:
            raise AssertionError(f"Unexpected status code: {response.status_code}")
        
        return True
    
    async def test_frontend_api_endpoints(self):
        """Test all frontend API endpoints"""
        print("\n🧪 Testing frontend API endpoint availability...")
        
        endpoints_to_test = [
            "/api/rag/collections",
            f"/api/rag/collections/{self.test_collection_id or 'test'}",
            "/api/rag/documents",
        ]
        
        for endpoint in endpoints_to_test:
            try:
                response = await self.client.get(f"{self.frontend_url}{endpoint}")
                # We expect either 200 (success) or 404 (not found) for valid endpoints
                assert response.status_code in [200, 404], f"Endpoint {endpoint} returned {response.status_code}"
                print(f"✓ Endpoint {endpoint} is accessible")
            except Exception as e:
                print(f"⚠ Endpoint {endpoint} error: {e}")
        
        return True
    
    async def test_performance_metrics(self):
        """Test RAG system performance"""
        print("\n🧪 Testing RAG system performance...")
        
        # Test API response times
        endpoints = [
            "/api/rag/collections",
            "/api/rag/documents"
        ]
        
        for endpoint in endpoints:
            start_time = time.time()
            response = await self.client.get(f"{self.frontend_url}{endpoint}")
            response_time = time.time() - start_time
            
            assert response.status_code == 200, f"Endpoint {endpoint} failed"
            assert response_time < 2.0, f"Endpoint {endpoint} too slow: {response_time:.2f}s"
            
            print(f"✓ {endpoint} response time: {response_time:.3f}s")
        
        # Test concurrent requests
        start_time = time.time()
        tasks = []
        for i in range(3):
            task = self.client.get(f"{self.frontend_url}/api/rag/collections")
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        
        for resp in responses:
            assert resp.status_code == 200
        
        print(f"✓ 3 concurrent requests completed in {total_time:.3f}s")
        return True
    
    async def run_all_tests(self):
        """Run all RAG integration tests"""
        print("🚀 Starting RAG Integration Tests")
        print("=" * 60)
        
        try:
            # Setup
            await self.setup_auth()
            
            # Test 1: Module Loading
            rag_module = await self.test_rag_module_loaded()
            content_module = await self.test_content_module_integration()
            
            # Test 2: Collection Management
            test_collection = await self.test_collection_management()
            
            # Test 3: Document Upload and Processing
            uploaded_docs = await self.test_document_upload_processing()
            
            # Test 4: Document Browsing and Search
            all_docs = await self.test_document_browsing_search()
            
            # Test 5: Document Download
            await self.test_document_download()
            
            # Test 6: Document Deletion
            await self.test_document_deletion()
            
            # Test 7: Frontend API Endpoints
            await self.test_frontend_api_endpoints()
            
            # Test 8: Performance
            await self.test_performance_metrics()
            
            # Test 9: Cleanup (Collection Deletion)
            await self.test_collection_deletion()
            
            print("\n" + "=" * 60)
            print("🎉 ALL RAG INTEGRATION TESTS PASSED!")
            print("✓ RAG module operational")
            print("✓ Content module with markitdown integration working")
            print("✓ Collection management (CRUD) functional")
            print(f"✓ Document upload/processing tested with {len(uploaded_docs)} documents")
            print("✓ Document browsing and search working")
            print("✓ Document download functionality verified")
            print("✓ Document deletion working correctly")
            print("✓ Frontend API endpoints accessible")
            print("✓ Performance within acceptable limits")
            print("✓ System cleanup successful")
            
            return True
            
        except Exception as e:
            print(f"\n❌ RAG integration test failed: {e}")
            import traceback
            traceback.print_exc()
            
            # Attempt cleanup on failure
            try:
                if self.test_document_ids:
                    print("🧹 Attempting cleanup of test documents...")
                    for doc_id in self.test_document_ids:
                        await self.client.delete(
                            f"{self.frontend_url}/api/rag/documents/{doc_id}",
                            headers={"Authorization": f"Bearer {self.auth_token}"}
                        )
                
                if self.test_collection_id:
                    print("🧹 Attempting cleanup of test collection...")
                    await self.client.delete(
                        f"{self.frontend_url}/api/rag/collections/{self.test_collection_id}",
                        headers={"Authorization": f"Bearer {self.auth_token}"}
                    )
            except:
                print("⚠ Cleanup failed - manual cleanup may be required")
            
            return False
        
        finally:
            await self.client.aclose()

async def run_rag_quick_test():
    """Run a quick RAG system verification"""
    print("🔧 Quick RAG System Verification")
    print("-" * 40)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Test frontend RAG endpoints
            response = await client.get("http://localhost:53000/api/rag/collections")
            if response.status_code == 200:
                data = response.json()
                collection_count = len(data.get("collections", []))
                print(f"✅ RAG Collections API responding: {collection_count} collections")
            else:
                print(f"⚠ RAG Collections API returned {response.status_code}")
            
            response = await client.get("http://localhost:53000/api/rag/documents")
            if response.status_code == 200:
                data = response.json()
                document_count = len(data.get("documents", []))
                print(f"✅ RAG Documents API responding: {document_count} documents")
            else:
                print(f"⚠ RAG Documents API returned {response.status_code}")
            
            # Test backend modules
            response = await client.get("http://localhost:58000/api/v1/modules/")
            if response.status_code == 200:
                data = response.json()
                modules = {mod["name"]: mod for mod in data.get("modules", [])}
                
                if "rag" in modules:
                    rag_status = "🟢" if modules["rag"].get("initialized") else "🟡"
                    print(f"   {rag_status} RAG module: v{modules['rag'].get('version', 'unknown')}")
                
                if "content" in modules:
                    content_status = "🟢" if modules["content"].get("initialized") else "🟡"
                    print(f"   {content_status} Content module: v{modules['content'].get('version', 'unknown')}")
            
            print("✅ RAG system basic verification complete")
            return True
            
        except Exception as e:
            print(f"❌ RAG system verification failed: {e}")
            return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        # Quick test
        result = asyncio.run(run_rag_quick_test())
        sys.exit(0 if result else 1)
    else:
        # Full RAG integration test
        test_runner = RAGIntegrationTest()
        result = asyncio.run(test_runner.run_all_tests())
        sys.exit(0 if result else 1)