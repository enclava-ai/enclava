#!/usr/bin/env python3
import asyncio
import aiohttp
import json
import time

async def test_cascade_delete():
    async with aiohttp.ClientSession() as session:
        # Register a new test user
        timestamp = int(time.time())
        user_data = {
            "email": f"cascadetest{timestamp}@example.com",
            "password": "TestPassword123!",
            "username": f"cascadetest{timestamp}"
        }
        
        async with session.post("http://localhost:58000/api/v1/auth/register", json=user_data) as response:
            if response.status == 201:
                print("User registered successfully")
                
                # Login
                login_data = {"email": user_data["email"], "password": user_data["password"]}
                async with session.post("http://localhost:58000/api/v1/auth/login", json=login_data) as response:
                    if response.status == 200:
                        login_result = await response.json()
                        token = login_result['access_token']
                        headers = {'Authorization': f'Bearer {token}'}
                        
                        # Create a new collection
                        collection_data = {'name': 'Test Cascade Delete', 'description': 'Testing cascade deletion'}
                        async with session.post('http://localhost:58000/api/v1/rag/collections', json=collection_data, headers=headers) as response:
                            if response.status == 200:
                                collection_result = await response.json()
                                collection_id = collection_result['collection']['id']
                                print(f'✅ Created collection ID: {collection_id}')
                                
                                # Upload a test document
                                test_content = b'This is a test document for cascade deletion testing. It contains some text to verify the cascade deletion works properly.'
                                data = aiohttp.FormData()
                                data.add_field('collection_id', str(collection_id))
                                data.add_field('file', test_content, filename='test.txt', content_type='text/plain')
                                
                                async with session.post('http://localhost:58000/api/v1/rag/documents', data=data, headers=headers) as response:
                                    if response.status == 200:
                                        doc_result = await response.json()
                                        doc_id = doc_result["document"]["id"]
                                        print(f'✅ Uploaded document ID: {doc_id}')
                                        
                                        # Check that collection now shows 1 document
                                        async with session.get(f'http://localhost:58000/api/v1/rag/collections/{collection_id}', headers=headers) as response:
                                            if response.status == 200:
                                                collection_info = await response.json()
                                                doc_count = collection_info['collection']['document_count']
                                                print(f'📄 Collection has {doc_count} document(s)')
                                                
                                                # Now try to delete the collection with documents (should work with cascade=true)
                                                async with session.delete(f'http://localhost:58000/api/v1/rag/collections/{collection_id}?cascade=true', headers=headers) as del_response:
                                                    print(f'🗑️  Delete collection status: {del_response.status}')
                                                    if del_response.status == 200:
                                                        result = await del_response.json()
                                                        print(f'✅ Delete successful: {result["message"]}')
                                                        
                                                        # Verify collection is gone
                                                        async with session.get(f'http://localhost:58000/api/v1/rag/collections/{collection_id}', headers=headers) as response:
                                                            if response.status == 404:
                                                                print('✅ Collection successfully deleted (404 as expected)')
                                                            else:
                                                                print(f'❌ Collection should be deleted but still accessible: {response.status}')
                                                        
                                                        # Verify document is also gone
                                                        async with session.get(f'http://localhost:58000/api/v1/rag/documents/{doc_id}', headers=headers) as response:
                                                            if response.status == 404:
                                                                print('✅ Document successfully cascade deleted (404 as expected)')
                                                            else:
                                                                print(f'❌ Document should be deleted but still accessible: {response.status}')
                                                                
                                                    else:
                                                        error_data = await del_response.json()
                                                        print(f'❌ Delete failed: {error_data}')
                                            else:
                                                print(f'❌ Failed to get collection info: {response.status}')
                                    else:
                                        error_data = await response.json()
                                        print(f'❌ Document upload failed: {error_data}')
                            else:
                                error_data = await response.json()
                                print(f'❌ Collection creation failed: {error_data}')
                    else:
                        error_data = await response.json()
                        print(f'❌ Login failed: {error_data}')
            else:
                error_data = await response.json()
                print(f'❌ User registration failed: {error_data}')

if __name__ == "__main__":
    asyncio.run(test_cascade_delete())