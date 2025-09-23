"""
Optimized JSONL Processor for RAG Module
Handles JSONL files efficiently to prevent resource exhaustion
"""

import json
import logging
import asyncio
from typing import Dict, Any, List
from datetime import datetime
import uuid

from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue
from qdrant_client.http.models import Batch

from app.modules.rag.main import ProcessedDocument
# from app.core.analytics import log_module_event  # Analytics module not available

logger = logging.getLogger(__name__)


class JSONLProcessor:
    """Specialized processor for JSONL files"""

    def __init__(self, rag_module):
        self.rag_module = rag_module
        self.config = rag_module.config

    async def process_and_index_jsonl(self, collection_name: str, content: bytes,
                                   filename: str, metadata: Dict[str, Any]) -> str:
        """Process and index a JSONL file efficiently

        Processes each JSON line as a separate document to avoid
        creating thousands of chunks from a single large document.
        """
        try:
            # Decode content
            jsonl_content = content.decode('utf-8', errors='replace')
            lines = jsonl_content.strip().split('\n')

            logger.info(f"Processing JSONL file {filename} with {len(lines)} lines")

            # Generate base document ID
            base_doc_id = self.rag_module._generate_document_id(jsonl_content, metadata)

            # Process lines in batches
            batch_size = 10  # Smaller batches for better memory management
            processed_count = 0

            for batch_start in range(0, len(lines), batch_size):
                batch_end = min(batch_start + batch_size, len(lines))
                batch_lines = lines[batch_start:batch_end]

                # Process batch
                await self._process_jsonl_batch(
                    collection_name,
                    batch_lines,
                    batch_start,
                    base_doc_id,
                    filename,
                    metadata
                )

                processed_count += len(batch_lines)

                # Log progress
                if processed_count % 50 == 0:
                    logger.info(f"Processed {processed_count}/{len(lines)} lines from {filename}")

                # Small delay to prevent resource exhaustion
                await asyncio.sleep(0.05)

            logger.info(f"Successfully processed JSONL file {filename} with {len(lines)} lines")
            return base_doc_id

        except Exception as e:
            logger.error(f"Error processing JSONL file {filename}: {e}")
            raise

    async def _process_jsonl_batch(self, collection_name: str, lines: List[str],
                                 start_idx: int, base_doc_id: str,
                                 filename: str, metadata: Dict[str, Any]) -> None:
        """Process a batch of JSONL lines"""
        try:
            points = []

            for line_idx, line in enumerate(lines, start=start_idx + 1):
                if not line.strip():
                    continue

                try:
                    # Parse JSON line
                    data = json.loads(line)

                    # Debug: check if data is None
                    if data is None:
                        logger.warning(f"JSON line {line_idx} parsed as None")
                        continue

                    # Handle helpjuice export format
                    if 'payload' in data and data['payload'] is not None:
                        payload = data['payload']
                        article_id = data.get('id', f'article_{line_idx}')

                        # Extract Q&A
                        question = payload.get('question', '')
                        answer = payload.get('answer', '')
                        language = payload.get('language', 'EN')

                        if question or answer:
                            # Create Q&A content
                            content = f"Question: {question}\n\nAnswer: {answer}"

                            # Create metadata
                            doc_metadata = {
                                **metadata,
                                "article_id": article_id,
                                "language": language,
                                "filename": filename,
                                "line_number": line_idx,
                                "content_type": "qa_pair",
                                "question": question[:100],  # Truncate for metadata
                                "processed_at": datetime.utcnow().isoformat()
                            }

                            # Generate single embedding for the Q&A pair
                            embeddings = await self.rag_module._generate_embeddings([content])

                            # Create point
                            point_id = str(uuid.uuid4())
                            points.append(PointStruct(
                                id=point_id,
                                vector=embeddings[0],
                                payload={
                                    **doc_metadata,
                                    "document_id": f"{base_doc_id}_{article_id}",
                                    "content": content,
                                    "chunk_index": 0,
                                    "chunk_count": 1
                                }
                            ))

                    # Handle generic JSON format
                    else:
                        content = json.dumps(data, indent=2, ensure_ascii=False)

                        # For larger JSON objects, we might need to chunk
                        if len(content) > 1000:
                            chunks = self.rag_module._chunk_text(content, chunk_size=500)
                            embeddings = await self.rag_module._generate_embeddings(chunks)

                            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                                point_id = str(uuid.uuid4())
                                points.append(PointStruct(
                                    id=point_id,
                                    vector=embedding,
                                    payload={
                                        **metadata,
                                        "filename": filename,
                                        "line_number": line_idx,
                                        "content_type": "json_object",
                                        "document_id": f"{base_doc_id}_line_{line_idx}",
                                        "content": chunk,
                                        "chunk_index": i,
                                        "chunk_count": len(chunks)
                                    }
                                ))
                        else:
                            # Small JSON - no chunking needed
                            embeddings = await self.rag_module._generate_embeddings([content])
                            point_id = str(uuid.uuid4())
                            points.append(PointStruct(
                                id=point_id,
                                vector=embeddings[0],
                                payload={
                                    **metadata,
                                    "filename": filename,
                                    "line_number": line_idx,
                                    "content_type": "json_object",
                                    "document_id": f"{base_doc_id}_line_{line_idx}",
                                    "content": content,
                                    "chunk_index": 0,
                                    "chunk_count": 1
                                }
                            ))

                except json.JSONDecodeError as e:
                    logger.warning(f"Error parsing JSONL line {line_idx}: {e}")
                    continue
                except Exception as e:
                    logger.warning(f"Error processing JSONL line {line_idx}: {e}")
                    continue

            # Insert all points in this batch
            if points:
                self.rag_module.qdrant_client.upsert(
                    collection_name=collection_name,
                    points=points
                )

                # Update stats
                self.rag_module.stats["documents_indexed"] += len(points)
                # log_module_event("rag", "jsonl_batch_processed", {  # Analytics module not available
                #     "filename": filename,
                #     "lines_processed": len(lines),
                #     "points_created": len(points)
                # })

        except Exception as e:
            logger.error(f"Error processing JSONL batch: {e}")
            raise