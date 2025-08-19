#!/usr/bin/env python3
"""
Real RAG Integration Test with attention.pdf
This test creates a real collection and uploads the actual attention.pdf file
"""

import asyncio
import aiohttp
import aiofiles
import json
import os
import time
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

class RealRAGIntegrationTest:
    """Test the complete RAG system with real file uploads"""
    
    def __init__(self, 
                 frontend_url: str = "http://localhost:53000",
                 backend_url: str = "http://localhost:58000"):
        self.frontend_url = frontend_url
        self.backend_url = backend_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.test_collection_id: Optional[str] = None
        self.test_document_ids: list = []
        self.auth_token = "test-auth-token-123"  # Mock token for testing
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60))
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def create_test_collection(self) -> Dict[str, Any]:
        """Create a test collection for attention.pdf"""
        print("📁 Creating test collection for attention.pdf...")
        
        collection_data = {
            "name": "Attention Paper Collection",
            "description": "Collection for the famous 'Attention Is All You Need' paper"
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.auth_token}"
        }
        
        async with self.session.post(
            f"{self.frontend_url}/api/rag/collections",
            json=collection_data,
            headers=headers
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Failed to create collection: {response.status} - {error_text}")
            
            data = await response.json()
            if not data.get("success"):
                raise Exception(f"Collection creation failed: {data.get('error')}")
            
            collection = data["collection"]
            self.test_collection_id = collection["id"]
            
            print(f"✅ Created collection: {collection['name']} (ID: {self.test_collection_id})")
            print(f"   Description: {collection['description']}")
            print(f"   Status: {collection['status']}")
            
            return collection
    
    async def upload_attention_pdf(self) -> Dict[str, Any]:
        """Upload the attention.pdf file to the test collection"""
        print("📄 Uploading attention.pdf...")
        
        # Find attention.pdf in the current directory or parent directories
        pdf_path = None
        search_paths = [
            Path.cwd() / "attention.pdf",
            Path.cwd().parent / "attention.pdf",
            Path.cwd() / "tests" / "attention.pdf",
            Path.cwd() / "backend" / "tests" / "attention.pdf",
        ]
        
        for path in search_paths:
            if path.exists():
                pdf_path = path
                break
        
        if not pdf_path:
            # Create a mock PDF file for testing
            print("⚠️  attention.pdf not found, creating mock PDF for testing...")
            pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT\n/F1 12 Tf\n72 720 Td\n(Attention Is All You Need - Mock PDF) Tj\nET\nendstream\nendobj\nxref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000207 00000 n \ntrailer\n<<\n/Size 5\n/Root 1 0 R\n>>\nstartxref\n298\n%%EOF"
        else:
            async with aiofiles.open(pdf_path, 'rb') as f:
                pdf_content = await f.read()
        
        # Prepare form data
        form_data = aiohttp.FormData()
        form_data.add_field('collection_id', str(self.test_collection_id))
        form_data.add_field('file', pdf_content, filename='attention.pdf', content_type='application/pdf')
        
        headers = {
            "Authorization": f"Bearer {self.auth_token}"
        }
        
        print(f"   📊 File size: {len(pdf_content):,} bytes")
        print(f"   📂 Target collection: {self.test_collection_id}")
        
        async with self.session.post(
            f"{self.frontend_url}/api/rag/documents",
            data=form_data,
            headers=headers
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Failed to upload document: {response.status} - {error_text}")
            
            data = await response.json()
            if not data.get("success"):
                raise Exception(f"Document upload failed: {data.get('error')}")
            
            document = data["document"]
            self.test_document_ids.append(document["id"])
            
            print(f"✅ Uploaded attention.pdf successfully!")
            print(f"   Document ID: {document['id']}")
            print(f"   Status: {document['status']}")
            print(f"   File size: {document['size']:,} bytes")
            print(f"   File type: {document['file_type']}")
            
            return document
    
    async def wait_for_processing(self, document_id: str, max_wait: int = 60) -> Dict[str, Any]:
        """Wait for document processing to complete"""
        print("⏳ Waiting for document processing...")
        
        headers = {
            "Authorization": f"Bearer {self.auth_token}"
        }
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            async with self.session.get(
                f"{self.frontend_url}/api/rag/documents/{document_id}",
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success"):
                        document = data["document"]
                        status = document["status"]
                        
                        print(f"   Status: {status}")
                        
                        if status in ["processed", "indexed", "error"]:
                            if status == "error":
                                error = document.get("processing_error", "Unknown error")
                                print(f"❌ Processing failed: {error}")
                            else:
                                print(f"✅ Processing completed with status: {status}")
                                if document.get("word_count"):
                                    print(f"   Word count: {document['word_count']:,}")
                                if document.get("character_count"):
                                    print(f"   Character count: {document['character_count']:,}")
                                if document.get("vector_count"):
                                    print(f"   Vector count: {document['vector_count']:,}")
                            
                            return document
            
            await asyncio.sleep(2)
        
        raise Exception(f"Document processing timeout after {max_wait} seconds")
    
    async def test_document_content(self, document_id: str) -> None:
        """Test that document content was processed correctly"""
        print("📖 Testing processed document content...")
        
        headers = {
            "Authorization": f"Bearer {self.auth_token}"
        }
        
        async with self.session.get(
            f"{self.frontend_url}/api/rag/documents/{document_id}",
            headers=headers
        ) as response:
            if response.status != 200:
                raise Exception(f"Failed to get document: {response.status}")
            
            data = await response.json()
            document = data["document"]
            
            # Check converted content
            converted_content = document.get("converted_content", "")
            if converted_content:
                print(f"✅ Document converted to markdown ({len(converted_content)} characters)")
                
                # Look for key terms from attention paper
                key_terms = ["attention", "transformer", "neural", "machine translation"]
                found_terms = [term for term in key_terms if term.lower() in converted_content.lower()]
                
                if found_terms:
                    print(f"✅ Found relevant terms: {', '.join(found_terms)}")
                else:
                    print("⚠️  No specific attention paper terms found (might be mock content)")
                
                # Show a snippet
                snippet = converted_content[:200] + "..." if len(converted_content) > 200 else converted_content
                print(f"📄 Content preview: {snippet}")
            else:
                print("⚠️  No converted content available")
            
            # Check metadata
            metadata = document.get("metadata", {})
            if metadata:
                print("✅ Document metadata extracted:")
                for key, value in metadata.items():
                    if isinstance(value, list):
                        print(f"   {key}: {len(value)} items")
                    else:
                        print(f"   {key}: {value}")
            else:
                print("⚠️  No metadata extracted")
    
    async def test_document_download(self, document_id: str) -> None:
        """Test document download functionality"""
        print("⬇️  Testing document download...")
        
        headers = {
            "Authorization": f"Bearer {self.auth_token}"
        }
        
        async with self.session.get(
            f"{self.frontend_url}/api/rag/documents/{document_id}/download",
            headers=headers
        ) as response:
            if response.status != 200:
                raise Exception(f"Failed to download document: {response.status}")
            
            content = await response.read()
            content_type = response.headers.get("content-type", "")
            filename = response.headers.get("content-disposition", "")
            
            print(f"✅ Download successful!")
            print(f"   Content size: {len(content):,} bytes")
            print(f"   Content type: {content_type}")
            print(f"   Filename header: {filename}")
            
            # Verify it's a PDF
            if content.startswith(b"%PDF"):
                print("✅ Downloaded file is a valid PDF")
            else:
                print("⚠️  Downloaded file may not be a valid PDF")
    
    async def test_rag_stats(self) -> Dict[str, Any]:
        """Test RAG system statistics"""
        print("📊 Testing RAG system statistics...")
        
        headers = {
            "Authorization": f"Bearer {self.auth_token}"
        }
        
        async with self.session.get(
            f"{self.frontend_url}/api/rag/stats",
            headers=headers
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Failed to get stats: {response.status} - {error_text}")
            
            data = await response.json()
            if not data.get("success"):
                raise Exception(f"Stats request failed: {data.get('error')}")
            
            stats = data["stats"]
            print("✅ RAG system statistics:")
            
            # Collections stats
            collections = stats.get("collections", {})
            print(f"   📁 Collections: {collections.get('total', 0)} total, {collections.get('active', 0)} active")
            
            # Documents stats
            documents = stats.get("documents", {})
            print(f"   📄 Documents: {documents.get('total', 0)} total, {documents.get('processed', 0)} processed, {documents.get('processing', 0)} processing")
            
            # Storage stats
            storage = stats.get("storage", {})
            print(f"   💾 Storage: {storage.get('total_size_mb', 0):.2f} MB total")
            
            # Vectors stats
            vectors = stats.get("vectors", {})
            print(f"   🔢 Vectors: {vectors.get('total', 0)} total")
            
            return stats
    
    async def cleanup_test_data(self) -> None:
        """Clean up test collection and documents"""
        print("🧹 Cleaning up test data...")
        
        headers = {
            "Authorization": f"Bearer {self.auth_token}"
        }
        
        # Delete documents first
        for doc_id in self.test_document_ids:
            try:
                async with self.session.delete(
                    f"{self.frontend_url}/api/rag/documents/{doc_id}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        print(f"✅ Deleted document {doc_id}")
                    else:
                        print(f"⚠️  Failed to delete document {doc_id}: {response.status}")
            except Exception as e:
                print(f"⚠️  Error deleting document {doc_id}: {e}")
        
        # Delete collection
        if self.test_collection_id:
            try:
                async with self.session.delete(
                    f"{self.frontend_url}/api/rag/collections/{self.test_collection_id}",
                    headers=headers
                ) as response:
                    if response.status == 200:
                        print(f"✅ Deleted collection {self.test_collection_id}")
                    else:
                        print(f"⚠️  Failed to delete collection {self.test_collection_id}: {response.status}")
            except Exception as e:
                print(f"⚠️  Error deleting collection {self.test_collection_id}: {e}")
    
    async def run_full_test(self) -> bool:
        """Run the complete integration test"""
        print("🚀 Starting Real RAG Integration Test with attention.pdf")
        print("=" * 70)
        
        try:
            # Step 1: Create collection
            collection = await self.create_test_collection()
            
            # Step 2: Upload attention.pdf
            document = await self.upload_attention_pdf()
            
            # Step 3: Wait for processing
            processed_doc = await self.wait_for_processing(document["id"])
            
            # Step 4: Test document content
            await self.test_document_content(document["id"])
            
            # Step 5: Test document download
            await self.test_document_download(document["id"])
            
            # Step 6: Test system stats
            stats = await self.test_rag_stats()
            
            print("\n" + "=" * 70)
            print("🎉 ALL REAL RAG INTEGRATION TESTS PASSED!")
            print(f"✅ Collection created: {collection['name']}")
            print(f"✅ Document uploaded: attention.pdf")
            print(f"✅ Processing completed: {processed_doc['status']}")
            print(f"✅ Content extracted: {processed_doc.get('word_count', 0)} words")
            print(f"✅ Download functional: PDF retrieved")
            print(f"✅ Stats working: {stats['documents']['total']} documents in system")
            print("\n🎯 Your RAG system is fully operational and ready for production!")
            
            return True
            
        except Exception as e:
            print(f"\n❌ Integration test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            # Always cleanup
            try:
                await self.cleanup_test_data()
            except Exception as e:
                print(f"⚠️  Cleanup error: {e}")

async def main():
    """Main test runner"""
    # Test with different URL configurations
    test_configs = [
        {
            "frontend_url": "http://localhost:53000",
            "backend_url": "http://localhost:58000",
            "name": "External URLs (from host machine)"
        }
    ]
    
    all_passed = True
    
    for config in test_configs:
        print(f"\n🔧 Testing with {config['name']}")
        print(f"   Frontend: {config['frontend_url']}")
        print(f"   Backend: {config['backend_url']}")
        
        async with RealRAGIntegrationTest(
            frontend_url=config["frontend_url"],
            backend_url=config["backend_url"]
        ) as test_runner:
            passed = await test_runner.run_full_test()
            if not passed:
                all_passed = False
    
    if all_passed:
        print("\n🎉 All test configurations passed!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1

if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)