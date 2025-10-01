#!/usr/bin/env python3
"""
Import a JSONL file into a Qdrant collection from inside the backend container.

Usage (from host):
  docker compose exec enclava-backend bash -lc \
    'python /app/scripts/import_jsonl.py \
      --collection rag_test_import_859b1f01 \
      --file /app/_to_delete/helpjuice-export.jsonl'

Notes:
  - Runs fully inside the backend, so Docker service hostnames (e.g. enclava-qdrant)
    and privatemode-proxy are reachable.
  - Uses RAGModule + JSONLProcessor to embed/index each JSONL line.
  - Creates the collection if missing (size=1024, cosine).
"""

import argparse
import asyncio
import os
from datetime import datetime


async def import_jsonl(collection_name: str, file_path: str):
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams
    from app.modules.rag.main import RAGModule
    from app.services.jsonl_processor import JSONLProcessor
    from app.core.config import settings

    if not os.path.exists(file_path):
        raise SystemExit(f"File not found: {file_path}")

    # Ensure collection exists (inside container uses Docker DNS hostnames)
    client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    collections = client.get_collections().collections
    if not any(c.name == collection_name for c in collections):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=1024, distance=Distance.COSINE),
        )
        print(f"Created Qdrant collection '{collection_name}' (size=1024, cosine)")
    else:
        print(f"Using existing Qdrant collection '{collection_name}'")

    # Initialize RAG
    rag = RAGModule({
        "chunk_size": 300,
        "chunk_overlap": 50,
        "max_results": 10,
        "score_threshold": 0.3,
        "embedding_model": "intfloat/multilingual-e5-large-instruct",
    })
    await rag.initialize()

    # Process JSONL
    processor = JSONLProcessor(rag)
    with open(file_path, "rb") as f:
        content = f.read()

    doc_id = await processor.process_and_index_jsonl(
        collection_name=collection_name,
        content=content,
        filename=os.path.basename(file_path),
        metadata={
            "source": "jsonl_upload",
            "upload_date": datetime.utcnow().isoformat(),
            "file_path": os.path.abspath(file_path),
        },
    )

    # Report stats using safe HTTP method to avoid client parsing issues
    try:
        info = await rag._get_collection_info_safely(collection_name)
        print(f"Import complete. Points: {info.get('points_count', 0)}, vector_size: {info.get('vector_size', 'n/a')}")
    except Exception as e:
        print(f"Import complete. (Could not fetch collection info safely: {e})")
    await rag.cleanup()
    return doc_id


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--collection", required=True, help="Qdrant collection name")
    ap.add_argument("--file", required=True, help="Path inside container (e.g. /app/_to_delete/...).")
    args = ap.parse_args()

    asyncio.run(import_jsonl(args.collection, args.file))


if __name__ == "__main__":
    main()
