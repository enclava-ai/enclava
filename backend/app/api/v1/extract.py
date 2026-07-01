"""Extract API routes."""

import json
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, get_extract_auth_context
from app.db.database import get_db
from app.models.api_key import APIKey
from app.models.extract_settings import ExtractSettings
from app.models.user import User
from app.modules.extract.exceptions import TemplateExistsError, TemplateNotFoundError
from app.modules.extract.schemas import (
    ExtractContext,
    ExtractSettingsResponse,
    ExtractSettingsUpdate,
    JobDetailResponse,
    JobListResponse,
    ProcessResponse,
    TemplateCreate,
    TemplateListResponse,
    TemplateResponse,
    TemplateUpdate,
)
from app.modules.extract.services.document_processor import DocumentProcessor
from app.modules.extract.services.extract_service import ExtractService
from app.modules.extract.services.template_wizard import TemplateWizardService
from app.modules.extract.templates.manager import TemplateManager

router = APIRouter()
extract_service = ExtractService()
wizard_service = TemplateWizardService()
doc_processor = DocumentProcessor()

# Permission required to manage extract templates
PERMISSION_MANAGE_EXTRACT_TEMPLATES = "manage_extract_templates"


def check_template_management_permission(current_user: User) -> None:
    """
    Check if user has permission to manage extract templates.

    Raises HTTPException 403 if user lacks permission.
    """
    # Superusers always have permission
    if current_user.is_superuser:
        return

    # Check for specific permission using the user's has_permission method
    if not current_user.has_permission(PERMISSION_MANAGE_EXTRACT_TEMPLATES):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission '{PERMISSION_MANAGE_EXTRACT_TEMPLATES}' required to manage templates",
        )


# --- Document Processing ---


@router.post("/process", response_model=ProcessResponse)
async def process_document(
    file: UploadFile = File(..., description="Document to process (PDF, JPG, PNG)"),
    template: Optional[str] = Form(None, description="Template ID to use"),
    context: Optional[str] = Form(
        None, description="JSON context for template placeholders"
    ),
    db: AsyncSession = Depends(get_db),
    auth: tuple[Dict[str, Any], Optional[APIKey]] = Depends(get_extract_auth_context),
):
    """
    Process a document and extract structured data.

    Supports PDF (multi-page), JPG, and PNG files up to 10MB.

    The extraction uses the specified template or the default template
    if not specified. Context can include variables like company_name, currency, etc.

    Authentication: JWT (frontend) or API key (external)
    Required scope (API key): extract
    """
    current_user, api_key = auth

    # Parse and validate context JSON
    context_dict = None
    if context:
        try:
            parsed_context = json.loads(context)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400, detail="Invalid JSON in context parameter"
            )

        # Validate context structure and value types
        try:
            validated_context = ExtractContext.model_validate(parsed_context)
            context_dict = validated_context.to_dict()
        except ValidationError as e:
            # Extract the first error message for a cleaner response
            error_messages = []
            for error in e.errors():
                msg = error.get("msg", "Validation error")
                # Remove "Value error, " prefix that Pydantic adds
                if msg.startswith("Value error, "):
                    msg = msg[13:]
                error_messages.append(msg)
            detail = (
                "; ".join(error_messages)
                if error_messages
                else "Invalid context format"
            )
            raise HTTPException(status_code=400, detail=detail)

    # Load settings from database if available
    settings_stmt = select(ExtractSettings).where(ExtractSettings.id == 1)
    settings_result = await db.execute(settings_stmt)
    settings = settings_result.scalar_one_or_none()

    # Get configuration with database settings or defaults
    config = {
        "default_template": "detailed_invoice",
        "vision_model": settings.default_model if settings else None,
        "max_file_size_mb": 10,
        "image_max_dimension": 1024,
        "auto_reprocess": True,
        "max_retries": 2,
    }
    template_id = template or config.get("default_template", "detailed_invoice")

    # API key scope check
    if api_key:
        if not api_key.has_scope("extract"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Scope 'extract' required"
            )

    # Verify template exists BEFORE checking access (prevents enumeration)
    template_manager = TemplateManager(db)
    try:
        await template_manager.get_template(template_id)
    except TemplateNotFoundError:
        raise HTTPException(status_code=404, detail="Template not found")

    # Then check access (after we know template exists)
    if api_key and not api_key.can_access_template(template_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to use this template",
        )

    result = await extract_service.process_document(
        db=db,
        file=file,
        template_id=template_id,
        context=context_dict,
        current_user=current_user,  # Pass dict directly
        api_key=api_key,
        config=config,
    )

    return result


# --- Job Management ---


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    limit: int = Query(20, ge=1, le=100, description="Maximum results to return"),
    offset: int = Query(0, ge=0, description="Results to skip"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    auth: tuple[Dict[str, Any], Optional[APIKey]] = Depends(get_extract_auth_context),
):
    """
    List Extract jobs for the current user.

    Authentication: JWT (frontend) or API key (external)
    Required scope (API key): extract
    """
    current_user, api_key = auth

    # API key scope check
    if api_key and not api_key.has_scope("extract"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Scope 'extract' required"
        )

    return await extract_service.list_jobs(
        db, current_user["id"], limit, offset, status
    )


@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth: tuple[Dict[str, Any], Optional[APIKey]] = Depends(get_extract_auth_context),
):
    """
    Get job details and extraction result.

    Authentication: JWT (frontend) or API key (external)
    Required scope (API key): extract
    """
    current_user, api_key = auth

    # API key scope check
    if api_key and not api_key.has_scope("extract"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Scope 'extract' required"
        )

    return await extract_service.get_job(db, str(job_id), current_user["id"])


# --- Template Management ---


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    db: AsyncSession = Depends(get_db),
    auth: tuple[Dict[str, Any], Optional[APIKey]] = Depends(get_extract_auth_context),
):
    """
    List all extraction templates.

    Authentication: JWT (frontend) or API key (external)
    Required scope (API key): extract
    """
    current_user, api_key = auth

    # API key scope check
    if api_key and not api_key.has_scope("extract"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Scope 'extract' required"
        )

    manager = TemplateManager(db)
    templates = await manager.list_templates()
    return TemplateListResponse(templates=templates)


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    auth: tuple[Dict[str, Any], Optional[APIKey]] = Depends(get_extract_auth_context),
):
    """
    Get a template with full details including prompts.

    Authentication: JWT (frontend) or API key (external)
    Required scope (API key): extract
    """
    current_user, api_key = auth

    # API key scope check
    if api_key and not api_key.has_scope("extract"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Scope 'extract' required"
        )

    manager = TemplateManager(db)
    try:
        template = await manager.get_template(template_id)
        return template
    except TemplateNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/templates", response_model=TemplateResponse, status_code=201)
async def create_template(
    template: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new extraction template. Requires manage_extract_templates permission."""
    check_template_management_permission(current_user)
    manager = TemplateManager(db)
    try:
        result = await manager.create_template(template)
        return result
    except TemplateExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/templates/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: str,
    template: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update any template (including defaults). Requires manage_extract_templates permission."""
    check_template_management_permission(current_user)
    manager = TemplateManager(db)
    try:
        result = await manager.update_template(template_id, template)
        return result
    except TemplateNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete any template. Requires manage_extract_templates permission."""
    check_template_management_permission(current_user)
    manager = TemplateManager(db)
    try:
        await manager.delete_template(template_id)
    except TemplateNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/templates/reset-defaults", status_code=200)
async def reset_default_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reset all default templates to their original state. Requires manage_extract_templates permission."""
    check_template_management_permission(current_user)
    manager = TemplateManager(db)
    await manager.reset_defaults()
    return {"status": "defaults_restored"}


@router.post("/templates/wizard")
async def template_wizard(
    file: UploadFile = File(..., description="Sample document to analyze"),
    model: Optional[str] = Form("gpt-4o", description="Vision model to use"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Analyze a sample document and generate a template automatically.

    Upload an invoice, receipt, contract, or other document and the wizard
    will analyze it to suggest an appropriate extraction template.
    """
    # Get configuration
    config = {
        "vision_model": model or "gpt-4o",
        "max_file_size_mb": 10,
        "image_max_dimension": 1024,
    }

    # Process file to image
    images = await doc_processor.process_file(
        file,
        max_size_mb=config.get("max_file_size_mb", 10),
        max_dimension=config.get("image_max_dimension", 1024),
    )

    # Use first page/image for analysis
    if not images:
        raise HTTPException(status_code=400, detail="No valid images found in file")

    # Get user_id for tracking
    user_id = (
        current_user.get("id") if isinstance(current_user, dict) else current_user.id
    )

    # Analyze with wizard (with usage tracking)
    template_data = await wizard_service.analyze_document(
        images[0],
        model_name=config.get("vision_model", "gpt-4o"),
        db=db,
        user_id=user_id,
        api_key_id=None,  # JWT auth, no API key
    )

    # Validate template
    if not wizard_service.validate_template(template_data):
        raise HTTPException(status_code=500, detail="Generated template is invalid")

    # Format for frontend
    formatted_template = wizard_service.format_template_for_creation(template_data)

    return {
        "success": True,
        "template": formatted_template,
        "analysis": {
            "document_type": template_data.get("document_type", "unknown"),
            "fields": template_data.get("fields", []),
        },
    }


# --- Settings ---


@router.get("/models")
async def get_vision_models():
    """
    Get available vision-capable models from the platform.

    Public endpoint (no auth required for discovery).
    """
    from app.services.llm.service import llm_service

    try:
        all_models = await llm_service.get_models()
        vision_models = [m for m in all_models if "vision" in m.capabilities]

        return {
            "models": [
                {
                    "id": m.id,
                    "name": m.id,  # Use id as name for now
                    "provider": m.provider,
                    "supports_vision": True,
                }
                for m in vision_models
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load available models: {str(e)}",
        )


@router.get("/settings", response_model=ExtractSettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get Extract settings.

    JWT authentication only (not available via API key).
    Auto-populates default_model with first available vision model if not set.
    """
    from app.services.llm.service import llm_service

    stmt = select(ExtractSettings).where(ExtractSettings.id == 1)
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()

    # Auto-populate default_model if a vision model is available. If providers are
    # not configured yet, keep settings readable with a null default_model.
    if not settings or not settings.default_model:
        try:
            all_models = await llm_service.get_models()
            vision_models = [m for m in all_models if "vision" in m.capabilities]
            first_model = vision_models[0].id if vision_models else None

            # Use upsert to avoid race conditions under concurrent load
            upsert_stmt = (
                pg_insert(ExtractSettings)
                .values(id=1, default_model=first_model)
                .on_conflict_do_update(
                    index_elements=["id"], set_={"default_model": first_model}
                )
            )
            await db.execute(upsert_stmt)
            await db.commit()

            # Re-fetch the settings
            result = await db.execute(
                select(ExtractSettings).where(ExtractSettings.id == 1)
            )
            settings = result.scalar_one()

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize settings: {str(e)}",
            )

    return settings


@router.put("/settings", response_model=ExtractSettingsResponse)
async def update_settings(
    settings_data: ExtractSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update Extract settings.

    JWT authentication only (not available via API key).
    """
    stmt = select(ExtractSettings).where(ExtractSettings.id == 1)
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()

    if not settings:
        settings = ExtractSettings(id=1)
        db.add(settings)

    settings.default_model = settings_data.default_model
    await db.commit()
    await db.refresh(settings)

    return settings


# --- Health ---


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "module": "extract",
        "version": "1.0.0",
    }
