#!/usr/bin/env python3
import asyncio
import aiohttp
import json

async def test_delete():
    async with aiohttp.ClientSession() as session:
        # Login 
        login_data = {'email': 'simpletest1753302142@example.com', 'password': 'TestPassword123!'}
        async with session.post('http://localhost:58000/api/v1/auth/login', json=login_data) as response:
            if response.status == 200:
                login_result = await response.json()
                token = login_result['access_token']
                
                # Check collections
                headers = {'Authorization': f'Bearer {token}'}
                async with session.get('http://localhost:58000/api/v1/rag/collections', headers=headers) as response:
                    if response.status == 200:
                        collections = await response.json()
                        print(f'Collections found: {len(collections.get("collections", []))}')
                        for col in collections.get('collections', []):
                            print(f'  - ID: {col["id"]}, Name: {col["name"]}, Docs: {col["document_count"]}')
                        
                        # Try to delete first collection if exists
                        if collections.get('collections'):
                            col_id = collections['collections'][0]['id']
                            async with session.delete(f'http://localhost:58000/api/v1/rag/collections/{col_id}', headers=headers) as del_response:
                                print(f'Delete status: {del_response.status}')
                                if del_response.status != 200:
                                    error_data = await del_response.json()
                                    print(f'Delete error: {error_data}')
                    else:
                        print(f'Failed to get collections: {response.status}')
            else:
                print('Login failed')

if __name__ == "__main__":
    asyncio.run(test_delete())