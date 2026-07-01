"""
Extract processing service.

This service orchestrates the Extract pipeline:
1. File processing (validation, PDF conversion, image encoding)
2. Budget checking and reservation
3. Vision model invocation
4. Response parsing and validation
5. Token tracking and analytics
6. Auto-reprocessing on validation failure
"""

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import utc_now
from app.middleware.analytics import set_analytics_data
from app.models.api_key import APIKey
from app.models.extract_job import ExtractJob
from app.models.extract_result import ExtractResult
from app.models.extract_settings import ExtractSettings
from app.models.user import User
from app.services.api_key_auth import APIKeyAuthService
from app.services.async_budget_enforcement import async_check_budget_for_request
from app.services.cost_calculator import CostCalculator
from app.services.llm.models import ChatRequest
from app.services.llm.service import llm_service

from ..exceptions import BudgetExceededError, ProcessingError
from ..schemas import ProcessResult
from ..templates.manager import TemplateManager
from .document_processor import DocumentProcessor
from .reprocessing import ReprocessingService
from .validators import DataValidator

logger = logging.getLogger(__name__)


class ExtractService:
    """
    Main Extract orchestration service.

    Handles the complete document processing pipeline with unified
    token tracking that matches agent requests.
    """

    def __init__(self):
        self.doc_processor = DocumentProcessor()
        self.validator = DataValidator()
        self.reprocessor = ReprocessingService()

    async def process_document(
        self,
        db: AsyncSession,
        file: UploadFile,
        template_id: str,
        context: Optional[dict],
        current_user: Dict[str, Any],
        api_key: Optional[APIKey] = None,
        config: Optional[dict] = None,
    ) -> ProcessResult:
        """
        Process a document through the Extract pipeline.

        This method follows the same token tracking pattern as
        agent requests to ensure unified reporting.

        Args:
            db: Database session
            file: Uploaded file (PDF, JPG, PNG)
            template_id: Extraction template to use
            context: Optional context dict for template placeholders (e.g., {"company_name": "Acme Corp"})
            current_user: Authenticated user dict with id, email, is_superuser keys
            api_key: API key (if API request)
            config: Module configuration

        Returns:
            ProcessResult with extracted data and metadata

        Raises:
            BudgetExceededError: If budget check fails
            ProcessingError: If processing fails
        """
        config = config or {}
        start_time = time.time()

        template_manager = TemplateManager(db)

        # 1. Create job record
        job = await self._create_job(
            db, file, template_id, context, current_user, api_key
        )
        logger.info("Created Extract job %s for user %s", job.id, current_user["id"])

        try:
            # 2. Process file to images
            images = await self.doc_processor.process_file(
                file,
                max_size_mb=config.get("max_file_size_mb", 10),
                max_dimension=config.get("image_max_dimension", 1024),
            )
            job.num_pages = len(images)
            logger.debug("Processed %d images from file", len(images))

            # 3. Get template
            template = await template_manager.get_template(template_id)

            # 4. Get model (priority: template.model > settings.default_model > config > fallback)
            model_name = await self._get_model_for_processing(db, template, config)
            job.model_used = model_name

            # 5. Estimate tokens for budget check
            # Vision models: ~85 tokens per image tile + prompt tokens
            estimated_tokens = self._estimate_tokens(images, template)

            # 6. Check budget before expensive operation
            budget_warnings = []
            if api_key:
                is_allowed, error_message, budget_warnings = (
                    await async_check_budget_for_request(
                        db,
                        api_key,
                        model_name,
                        estimated_tokens,
                        "extract/process",  # Endpoint identifier for analytics
                    )
                )

                if not is_allowed:
                    logger.warning(
                        "Budget check failed for job %s: %s", job.id, error_message
                    )
                    raise BudgetExceededError(error_message)

            # 7. Update job status
            job.status = "processing"
            await db.commit()

            # 8. Build messages with image(s)
            messages = self._build_messages(images, template, context)

            # 9. Call LLM service directly (same path used by agents)
            # This ensures the call goes through the same resilience patterns
            # and unified usage tracking via UsageRecordingService
            llm_request = ChatRequest(
                model=model_name,
                messages=messages,
                response_format={"type": "json_object"},
                user_id=str(current_user["id"]),
                api_key_id=api_key.id if api_key else None,
            )

            response = await llm_service.create_chat_completion(
                llm_request,
                db=db,
                user_id=int(current_user["id"]),
                api_key_id=api_key.id if api_key else None,
                endpoint="extract/process",
            )

            # 10. Parse and validate response
            parsed_data = self._parse_response(response.choices[0].message.content)
            validation_result = self.validator.validate(parsed_data, template)

            # 11. Calculate actual cost
            actual_cost_cents = CostCalculator.calculate_cost_cents(
                model_name,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
            )

            # Usage is now recorded by LLMService via UsageRecordingService
            # No need for manual async_record_request_usage call

            # 12. Update API key stats
            if api_key:
                auth_service = APIKeyAuthService(db)
                await auth_service.update_usage_stats(
                    {"api_key_id": api_key.id, "user_id": str(current_user["id"])},
                    response.usage.total_tokens,
                    actual_cost_cents,
                )

            # 13. Set analytics data for middleware
            set_analytics_data(
                model=model_name,
                request_tokens=response.usage.prompt_tokens,
                response_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
                cost_cents=actual_cost_cents,
                budget_warnings=budget_warnings,
            )

            # 15. Save result
            result = await self._save_result(
                db,
                job,
                parsed_data,
                response.choices[0].message.content,
                validation_result,
                response.usage,
                actual_cost_cents,
            )

            processing_time_ms = int((time.time() - start_time) * 1000)

            return ProcessResult(
                success=not validation_result.has_errors,
                job_id=str(job.id),
                data=parsed_data,
                raw_response=response.choices[0].message.content,
                validation_errors=validation_result.errors,
                validation_warnings=validation_result.warnings,
                processing_time_ms=processing_time_ms,
                tokens_used=response.usage.total_tokens,
                cost_cents=actual_cost_cents,
            )

        except BudgetExceededError:
            await db.rollback()  # Explicit rollback before marking failed
            await self._mark_job_failed(db, job, "Budget exceeded")
            raise
        except Exception as e:
            logger.exception("Extract processing failed for job %s", job.id)
            await db.rollback()  # Explicit rollback before marking failed
            await self._mark_job_failed(db, job, str(e))
            raise ProcessingError(f"Processing failed: {e}") from e

    def _build_messages(
        self,
        images: list,
        template,
        context: Optional[dict],
    ) -> list:
        """
        Build OpenAI-format messages with images.

        Creates a message array with:
        - System message from template
        - User message with images and prompt

        Injects context variables into template placeholders.
        """
        user_prompt = template.user_prompt
        system_prompt = template.system_prompt

        # Inject context variables into both prompts
        if context:
            for key, value in context.items():
                placeholder = f"{{{key}}}"
                # Replace in both system and user prompts
                system_prompt = system_prompt.replace(placeholder, str(value))
                user_prompt = user_prompt.replace(placeholder, str(value))

        # Build content array with images first, then text
        content = []
        for image_b64 in images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{image_b64}",
                        "detail": "high",  # Use high detail for document Extract
                    },
                }
            )
        content.append(
            {
                "type": "text",
                "text": user_prompt,
            }
        )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ]

    async def _get_model_for_processing(
        self, db: AsyncSession, template, config: dict
    ) -> str:
        """
        Get model for processing with priority cascade:
        1. Template-specific model (template.model)
        2. Module default model (settings.default_model)
        3. First available vision model from platform

        Raises ProcessingError if no vision models available.
        """
        # Check template override first
        if template.model:
            logger.debug(f"Using template-specific model: {template.model}")
            return template.model

        # Check module settings
        try:
            stmt = select(ExtractSettings).where(ExtractSettings.id == 1)
            result = await db.execute(stmt)
            settings = result.scalar_one_or_none()
            if settings and settings.default_model:
                logger.debug(f"Using module default model: {settings.default_model}")
                return settings.default_model
        except Exception as e:
            logger.warning(f"Failed to load extract settings: {e}")

        # Get first available vision model from platform
        try:
            vision_models = await self._get_available_vision_models()
            if not vision_models:
                raise ProcessingError(
                    "No vision-capable models available. "
                    "Please configure a model in Extract settings or contact administrator."
                )

            model = vision_models[0].id
            logger.info(f"Auto-selected first available vision model: {model}")
            return model
        except Exception as e:
            raise ProcessingError(f"Failed to get available vision models: {e}")

    async def _get_available_vision_models(self):
        """Get list of vision-capable models from LLM service."""
        all_models = await llm_service.get_models()
        vision_models = [m for m in all_models if "vision" in m.capabilities]
        return vision_models

    def _estimate_tokens(self, images: list, template) -> int:
        """
        Estimate tokens for budget check.

        Vision models charge based on image tiles (each ~85 tokens)
        plus the prompt tokens.
        """
        # Rough estimate: 765 tokens per 1024x1024 image (assuming 512x512 tiles)
        # Plus prompt overhead
        image_tokens = len(images) * 765
        prompt_tokens = len(template.system_prompt + template.user_prompt) // 4
        # Add buffer for response
        response_estimate = 2000

        return image_tokens + prompt_tokens + response_estimate

    def _parse_response(self, content: str) -> dict:
        """
        Parse JSON response from vision model.

        Handles markdown code blocks and JSON parsing errors.
        """
        # Remove markdown code blocks if present
        text = content.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        try:
            return json.loads(text.strip())
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse JSON response: %s", e)
            return {"_parse_error": str(e), "_raw": content}

    async def _create_job(
        self,
        db: AsyncSession,
        file: UploadFile,
        template_id: str,
        context: Optional[dict],
        current_user: Dict[str, Any],
        api_key: Optional[APIKey],
    ) -> ExtractJob:
        """Create job record in database."""
        # Generate safe filename
        original_filename = file.filename or "unknown"
        safe_filename = f"{uuid.uuid4().hex}_{original_filename}"

        # Get file size
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

        # Determine file type
        ext = (
            original_filename.rsplit(".", 1)[-1].lower()
            if "." in original_filename
            else "unknown"
        )

        # Store context as JSON string in buyer_context field for backwards compatibility
        context_json = json.dumps(context) if context else None

        job = ExtractJob(
            user_id=current_user["id"],
            api_key_id=api_key.id if api_key else None,
            filename=safe_filename,
            original_filename=original_filename,
            file_type=ext,
            file_size=file_size,
            status="pending",
            template_id=template_id,
            buyer_context=context_json,
        )

        db.add(job)
        await db.commit()
        await db.refresh(job)

        return job

    async def _save_result(
        self,
        db: AsyncSession,
        job: ExtractJob,
        parsed_data: dict,
        raw_response: str,
        validation_result,
        usage,
        cost_cents: int,
    ) -> ExtractResult:
        """Save extraction result and update job."""
        # Count existing results for attempt number using proper COUNT query
        count_stmt = select(func.count(ExtractResult.id)).where(
            ExtractResult.job_id == job.id
        )
        count_result = await db.execute(count_stmt)
        attempt_number = count_result.scalar_one() + 1

        result = ExtractResult(
            job_id=job.id,
            attempt_number=attempt_number,
            raw_response=raw_response,
            parsed_data=parsed_data,
            validation_errors=validation_result.errors,
            validation_warnings=validation_result.warnings,
            is_final=not validation_result.has_errors,
        )

        db.add(result)

        # Update job
        job.prompt_tokens = usage.prompt_tokens
        job.completion_tokens = usage.completion_tokens
        job.total_cost_cents = cost_cents

        if not validation_result.has_errors:
            job.status = "completed"
            job.completed_at = utc_now()
        else:
            # Mark job as complete with errors - don't leave it stuck in processing
            job.status = "completed_with_errors"
            job.completed_at = utc_now()

        await db.commit()
        await db.refresh(result)

        return result

    async def _mark_job_failed(self, db: AsyncSession, job: ExtractJob, error: str):
        """Mark job as failed."""
        job.status = "failed"
        job.error_message = error
        job.completed_at = utc_now()
        await db.commit()

    # Valid job status values
    ALLOWED_STATUSES = [
        "pending",
        "processing",
        "completed",
        "failed",
        "completed_with_errors",
    ]

    async def list_jobs(
        self,
        db: AsyncSession,
        user_id: int,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
    ):
        """List jobs for a user."""
        stmt = select(ExtractJob).where(ExtractJob.user_id == user_id)

        if status:
            if status not in self.ALLOWED_STATUSES:
                raise ValueError(
                    f"Invalid status '{status}'. Allowed: {self.ALLOWED_STATUSES}"
                )
            stmt = stmt.where(ExtractJob.status == status)

        stmt = stmt.order_by(ExtractJob.created_at.desc()).limit(limit).offset(offset)

        result = await db.execute(stmt)
        jobs = result.scalars().all()

        # Count total using proper COUNT query (not loading all into memory)
        count_stmt = select(func.count(ExtractJob.id)).where(
            ExtractJob.user_id == user_id
        )
        if status:
            count_stmt = count_stmt.where(ExtractJob.status == status)
        total_result = await db.execute(count_stmt)
        total = total_result.scalar_one()

        return {"jobs": jobs, "total": total, "limit": limit, "offset": offset}

    async def get_job(self, db: AsyncSession, job_id: str, user_id: int):
        """Get job details with result."""
        # Use eager loading to avoid N+1 query when accessing job.results
        stmt = (
            select(ExtractJob)
            .where(ExtractJob.id == job_id, ExtractJob.user_id == user_id)
            .options(selectinload(ExtractJob.results))
        )
        result = await db.execute(stmt)
        job = result.scalar_one_or_none()

        if not job:
            raise ProcessingError("Job not found")

        # Get result - prefer final, fall back to latest (for completed_with_errors)
        result_data = None
        validation_errors = None
        validation_warnings = None
        if job.results:
            final_results = [r for r in job.results if r.is_final]
            if final_results:
                result_data = final_results[0].parsed_data
            else:
                # Return latest result even if not final (e.g., completed_with_errors)
                latest = max(job.results, key=lambda r: r.attempt_number)
                result_data = latest.parsed_data
                validation_errors = latest.validation_errors
                validation_warnings = latest.validation_warnings

        return {
            "id": str(job.id),
            "user_id": str(job.user_id),
            "filename": job.filename,
            "original_filename": job.original_filename,
            "file_type": job.file_type,
            "file_size": job.file_size,
            "num_pages": job.num_pages,
            "status": job.status,
            "template_id": job.template_id,
            "buyer_context": job.buyer_context,
            "model_used": job.model_used,
            "prompt_tokens": job.prompt_tokens,
            "completion_tokens": job.completion_tokens,
            "total_cost_cents": job.total_cost_cents,
            "created_at": job.created_at,
            "completed_at": job.completed_at,
            "error_message": job.error_message,
            "result": result_data,
            "validation_errors": validation_errors,
            "validation_warnings": validation_warnings,
        }
