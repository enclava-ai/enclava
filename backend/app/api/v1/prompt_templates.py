"""
Prompt Template API endpoints
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime
import uuid

from app.db.database import get_db
from app.models.prompt_template import PromptTemplate, ChatbotPromptVariable
from app.core.security import get_current_user
from app.models.user import User
from app.core.logging import log_api_request
from app.services.llm.service import llm_service
from app.services.llm.models import ChatRequest as LLMChatRequest, ChatMessage as LLMChatMessage

router = APIRouter()


class PromptTemplateRequest(BaseModel):
    name: str
    type_key: str
    description: Optional[str] = None
    system_prompt: str
    is_active: bool = True


class PromptTemplateResponse(BaseModel):
    id: str
    name: str
    type_key: str
    description: Optional[str]
    system_prompt: str
    is_default: bool
    is_active: bool
    version: int
    created_at: str
    updated_at: str


class PromptVariableResponse(BaseModel):
    id: str
    variable_name: str
    description: Optional[str]
    example_value: Optional[str]
    is_active: bool


class ImprovePromptRequest(BaseModel):
    current_prompt: str
    chatbot_type: str
    improvement_instructions: Optional[str] = None


@router.get("/templates", response_model=List[PromptTemplateResponse])
async def list_prompt_templates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all prompt templates"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    log_api_request("list_prompt_templates", {"user_id": user_id})
    
    try:
        result = await db.execute(
            select(PromptTemplate)
            .where(PromptTemplate.is_active == True)
            .order_by(PromptTemplate.name)
        )
        templates = result.scalars().all()
        
        template_list = []
        for template in templates:
            template_dict = {
                "id": template.id,
                "name": template.name,
                "type_key": template.type_key,
                "description": template.description,
                "system_prompt": template.system_prompt,
                "is_default": template.is_default,
                "is_active": template.is_active,
                "version": template.version,
                "created_at": template.created_at.isoformat() if template.created_at else None,
                "updated_at": template.updated_at.isoformat() if template.updated_at else None
            }
            template_list.append(template_dict)
        
        return template_list
        
    except Exception as e:
        log_api_request("list_prompt_templates_error", {"error": str(e), "user_id": user_id})
        raise HTTPException(status_code=500, detail=f"Failed to fetch prompt templates: {str(e)}")


@router.get("/templates/{type_key}", response_model=PromptTemplateResponse)
async def get_prompt_template(
    type_key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific prompt template by type key"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    log_api_request("get_prompt_template", {"user_id": user_id, "type_key": type_key})
    
    try:
        result = await db.execute(
            select(PromptTemplate)
            .where(PromptTemplate.type_key == type_key)
            .where(PromptTemplate.is_active == True)
        )
        template = result.scalar_one_or_none()
        
        if not template:
            raise HTTPException(status_code=404, detail="Prompt template not found")
        
        return {
            "id": template.id,
            "name": template.name,
            "type_key": template.type_key,
            "description": template.description,
            "system_prompt": template.system_prompt,
            "is_default": template.is_default,
            "is_active": template.is_active,
            "version": template.version,
            "created_at": template.created_at.isoformat() if template.created_at else None,
            "updated_at": template.updated_at.isoformat() if template.updated_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_api_request("get_prompt_template_error", {"error": str(e), "user_id": user_id})
        raise HTTPException(status_code=500, detail=f"Failed to fetch prompt template: {str(e)}")


@router.put("/templates/{type_key}")
async def update_prompt_template(
    type_key: str,
    request: PromptTemplateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a prompt template"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    log_api_request("update_prompt_template", {
        "user_id": user_id,
        "type_key": type_key,
        "name": request.name
    })
    
    try:
        # Get existing template
        result = await db.execute(
            select(PromptTemplate)
            .where(PromptTemplate.type_key == type_key)
            .where(PromptTemplate.is_active == True)
        )
        template = result.scalar_one_or_none()
        
        if not template:
            raise HTTPException(status_code=404, detail="Prompt template not found")
        
        # Update the template
        await db.execute(
            update(PromptTemplate)
            .where(PromptTemplate.type_key == type_key)
            .values(
                name=request.name,
                description=request.description,
                system_prompt=request.system_prompt,
                is_active=request.is_active,
                version=template.version + 1,
                updated_at=datetime.utcnow()
            )
        )
        
        await db.commit()
        
        # Return updated template
        updated_result = await db.execute(
            select(PromptTemplate)
            .where(PromptTemplate.type_key == type_key)
        )
        updated_template = updated_result.scalar_one()
        
        return {
            "id": updated_template.id,
            "name": updated_template.name,
            "type_key": updated_template.type_key,
            "description": updated_template.description,
            "system_prompt": updated_template.system_prompt,
            "is_default": updated_template.is_default,
            "is_active": updated_template.is_active,
            "version": updated_template.version,
            "created_at": updated_template.created_at.isoformat() if updated_template.created_at else None,
            "updated_at": updated_template.updated_at.isoformat() if updated_template.updated_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log_api_request("update_prompt_template_error", {"error": str(e), "user_id": user_id})
        raise HTTPException(status_code=500, detail=f"Failed to update prompt template: {str(e)}")


@router.post("/templates/create")
async def create_prompt_template(
    request: PromptTemplateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new prompt template"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    log_api_request("create_prompt_template", {
        "user_id": user_id,
        "type_key": request.type_key,
        "name": request.name
    })
    
    try:
        # Check if template already exists
        existing_result = await db.execute(
            select(PromptTemplate)
            .where(PromptTemplate.type_key == request.type_key)
        )
        if existing_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Prompt template with this type key already exists")
        
        # Create new template
        template = PromptTemplate(
            id=str(uuid.uuid4()),
            name=request.name,
            type_key=request.type_key,
            description=request.description,
            system_prompt=request.system_prompt,
            is_default=False,
            is_active=request.is_active,
            version=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(template)
        await db.commit()
        await db.refresh(template)
        
        return {
            "id": template.id,
            "name": template.name,
            "type_key": template.type_key,
            "description": template.description,
            "system_prompt": template.system_prompt,
            "is_default": template.is_default,
            "is_active": template.is_active,
            "version": template.version,
            "created_at": template.created_at.isoformat() if template.created_at else None,
            "updated_at": template.updated_at.isoformat() if template.updated_at else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        log_api_request("create_prompt_template_error", {"error": str(e), "user_id": user_id})
        raise HTTPException(status_code=500, detail=f"Failed to create prompt template: {str(e)}")


@router.get("/variables", response_model=List[PromptVariableResponse])
async def list_prompt_variables(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all available prompt variables"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    log_api_request("list_prompt_variables", {"user_id": user_id})
    
    try:
        result = await db.execute(
            select(ChatbotPromptVariable)
            .where(ChatbotPromptVariable.is_active == True)
            .order_by(ChatbotPromptVariable.variable_name)
        )
        variables = result.scalars().all()
        
        variable_list = []
        for variable in variables:
            variable_dict = {
                "id": variable.id,
                "variable_name": variable.variable_name,
                "description": variable.description,
                "example_value": variable.example_value,
                "is_active": variable.is_active
            }
            variable_list.append(variable_dict)
        
        return variable_list
        
    except Exception as e:
        log_api_request("list_prompt_variables_error", {"error": str(e), "user_id": user_id})
        raise HTTPException(status_code=500, detail=f"Failed to fetch prompt variables: {str(e)}")


@router.post("/templates/{type_key}/reset")
async def reset_prompt_template(
    type_key: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Reset a prompt template to its default"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    log_api_request("reset_prompt_template", {"user_id": user_id, "type_key": type_key})
    
    # Define default prompts (same as in migration)
    default_prompts = {
        "assistant": "You are a helpful AI assistant. Provide accurate, concise, and friendly responses. Always aim to be helpful while being honest about your limitations. When you don't know something, say so clearly. Be professional but approachable in your communication style.",
        "customer_support": "You are a professional customer support representative. Be empathetic, professional, and solution-focused in all interactions. Always try to understand the customer's issue fully before providing solutions. Use the knowledge base to provide accurate information. When you cannot resolve an issue, explain clearly how the customer can escalate or get further help. Maintain a helpful and patient tone even in difficult situations.",
        "teacher": "You are an experienced educational tutor and learning facilitator. Break down complex concepts into understandable, digestible parts. Use analogies, examples, and step-by-step explanations to help students learn. Encourage critical thinking through thoughtful questions. Be patient, supportive, and encouraging. Adapt your teaching style to different learning preferences. When a student makes mistakes, guide them to the correct answer rather than just providing it.",
        "researcher": "You are a thorough research assistant with a focus on accuracy and evidence-based information. Provide well-researched, factual information with sources when possible. Be thorough in your analysis and present multiple perspectives when relevant topics have different viewpoints. Always distinguish between established facts, current research, and opinions. When information is uncertain or contested, clearly communicate the level of confidence and supporting evidence.",
        "creative_writer": "You are an experienced creative writing mentor and storytelling expert. Help with brainstorming ideas, character development, plot structure, dialogue, and creative expression. Be imaginative and inspiring while providing constructive, actionable feedback. Encourage experimentation with different writing styles and techniques. When reviewing work, balance praise for strengths with specific suggestions for improvement. Help writers find their unique voice while mastering fundamental storytelling principles.",
        "custom": "You are a helpful AI assistant. Your personality, expertise, and behavior will be defined by the user through custom instructions. Follow the user's guidance on how to respond, what tone to use, and what role to play. Be adaptable and responsive to the specific needs and preferences outlined in your configuration."
    }
    
    if type_key not in default_prompts:
        raise HTTPException(status_code=404, detail="Unknown prompt template type")
    
    try:
        # Update the template to default
        await db.execute(
            update(PromptTemplate)
            .where(PromptTemplate.type_key == type_key)
            .values(
                system_prompt=default_prompts[type_key],
                version=PromptTemplate.version + 1,
                updated_at=datetime.utcnow()
            )
        )
        
        await db.commit()
        
        return {"message": "Prompt template reset to default successfully"}
        
    except Exception as e:
        await db.rollback()
        log_api_request("reset_prompt_template_error", {"error": str(e), "user_id": user_id})
        raise HTTPException(status_code=500, detail=f"Failed to reset prompt template: {str(e)}")


@router.post("/improve")
async def improve_prompt_with_ai(
    request: ImprovePromptRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Improve a prompt using AI"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    log_api_request("improve_prompt_with_ai", {
        "user_id": user_id,
        "chatbot_type": request.chatbot_type
    })
    
    try:
        # Create system message for improvement
        system_message = """You are an expert prompt engineer. Your task is to improve the given prompt to make it more effective, clear, and specific for the intended chatbot type.

Guidelines for improvement:
1. Make the prompt more specific and actionable
2. Add relevant context and constraints
3. Improve clarity and reduce ambiguity
4. Include appropriate tone and personality instructions
5. Add specific behavior examples when helpful
6. Ensure the prompt aligns with the chatbot type
7. Keep the prompt professional and ethical
8. Make it concise but comprehensive

Return ONLY the improved prompt text without any additional explanation or formatting."""

        # Create user message with current prompt and context
        user_message = f"""Chatbot Type: {request.chatbot_type}

Current Prompt:
{request.current_prompt}

{f"Additional Instructions: {request.improvement_instructions}" if request.improvement_instructions else ""}

Please improve this prompt to make it more effective for a {request.chatbot_type} chatbot."""

        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message}
        ]

        # Get available models to use a default model
        models = await llm_service.get_models()
        if not models:
            raise HTTPException(status_code=503, detail="No LLM models available")
        
        # Use the first available model (you might want to make this configurable)
        default_model = models[0].id
        
        # Prepare the chat request for the new LLM service
        chat_request = LLMChatRequest(
            model=default_model,
            messages=[LLMChatMessage(role=msg["role"], content=msg["content"]) for msg in messages],
            temperature=0.3,
            max_tokens=1000,
            user_id=str(user_id),
            api_key_id=1  # Using default API key, you might want to make this dynamic
        )
        
        # Make the AI call
        response = await llm_service.create_chat_completion(chat_request)
        
        # Extract the improved prompt from the response
        improved_prompt = response.choices[0].message.content.strip()
        
        return {
            "improved_prompt": improved_prompt,
            "original_prompt": request.current_prompt,
            "model_used": default_model
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log_api_request("improve_prompt_with_ai_error", {"error": str(e), "user_id": user_id})
        raise HTTPException(status_code=500, detail=f"Failed to improve prompt: {str(e)}")


@router.post("/seed-defaults")
async def seed_default_templates(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Seed default prompt templates for all chatbot types"""
    user_id = current_user.get("id") if isinstance(current_user, dict) else current_user.id
    log_api_request("seed_default_templates", {"user_id": user_id})
    
    # Define default prompts (same as in reset)
    default_prompts = {
        "assistant": {
            "name": "General Assistant",
            "description": "A helpful, accurate, and friendly AI assistant",
            "prompt": "You are a helpful AI assistant. Provide accurate, concise, and friendly responses. Always aim to be helpful while being honest about your limitations. When you don't know something, say so clearly. Be professional but approachable in your communication style."
        },
        "customer_support": {
            "name": "Customer Support Agent",
            "description": "Professional customer service representative focused on solving problems",
            "prompt": "You are a professional customer support representative. Be empathetic, professional, and solution-focused in all interactions. Always try to understand the customer's issue fully before providing solutions. Use the knowledge base to provide accurate information. When you cannot resolve an issue, explain clearly how the customer can escalate or get further help. Maintain a helpful and patient tone even in difficult situations."
        },
        "teacher": {
            "name": "Educational Tutor",
            "description": "Patient and encouraging educational facilitator",
            "prompt": "You are an experienced educational tutor and learning facilitator. Break down complex concepts into understandable, digestible parts. Use analogies, examples, and step-by-step explanations to help students learn. Encourage critical thinking through thoughtful questions. Be patient, supportive, and encouraging. Adapt your teaching style to different learning preferences. When a student makes mistakes, guide them to the correct answer rather than just providing it."
        },
        "researcher": {
            "name": "Research Assistant",
            "description": "Thorough researcher focused on evidence-based information",
            "prompt": "You are a thorough research assistant with a focus on accuracy and evidence-based information. Provide well-researched, factual information with sources when possible. Be thorough in your analysis and present multiple perspectives when relevant topics have different viewpoints. Always distinguish between established facts, current research, and opinions. When information is uncertain or contested, clearly communicate the level of confidence and supporting evidence."
        },
        "creative_writer": {
            "name": "Creative Writing Mentor",
            "description": "Imaginative storytelling expert and writing coach",
            "prompt": "You are an experienced creative writing mentor and storytelling expert. Help with brainstorming ideas, character development, plot structure, dialogue, and creative expression. Be imaginative and inspiring while providing constructive, actionable feedback. Encourage experimentation with different writing styles and techniques. When reviewing work, balance praise for strengths with specific suggestions for improvement. Help writers find their unique voice while mastering fundamental storytelling principles."
        },
        "custom": {
            "name": "Custom Chatbot",
            "description": "Customizable AI assistant with user-defined behavior",
            "prompt": "You are a helpful AI assistant. Your personality, expertise, and behavior will be defined by the user through custom instructions. Follow the user's guidance on how to respond, what tone to use, and what role to play. Be adaptable and responsive to the specific needs and preferences outlined in your configuration."
        }
    }
    
    created_templates = []
    updated_templates = []
    
    try:
        for type_key, template_data in default_prompts.items():
            # Check if template already exists
            existing = await db.execute(
                select(PromptTemplate).where(PromptTemplate.type_key == type_key)
            )
            existing_template = existing.scalar_one_or_none()

            if existing_template:
                # Only update if it's still the default (version 1)
                if existing_template.version == 1 and existing_template.is_default:
                    existing_template.name = template_data["name"]
                    existing_template.description = template_data["description"]
                    existing_template.system_prompt = template_data["prompt"]
                    existing_template.updated_at = datetime.utcnow()
                    updated_templates.append(type_key)
            else:
                # Check if any inactive template exists with this type_key
                inactive_result = await db.execute(
                    select(PromptTemplate)
                    .where(PromptTemplate.type_key == type_key)
                    .where(PromptTemplate.is_active == False)
                )
                inactive_template = inactive_result.scalar_one_or_none()

                if inactive_template:
                    # Reactivate the inactive template
                    inactive_template.is_active = True
                    inactive_template.name = template_data["name"]
                    inactive_template.description = template_data["description"]
                    inactive_template.system_prompt = template_data["prompt"]
                    inactive_template.is_default = True
                    inactive_template.version = 1
                    inactive_template.updated_at = datetime.utcnow()
                    updated_templates.append(type_key)
                else:
                    # Create new template, gracefully skipping if another request created it first
                    now = datetime.utcnow()
                    stmt = (
                        insert(PromptTemplate)
                        .values(
                            id=str(uuid.uuid4()),
                            name=template_data["name"],
                            type_key=type_key,
                            description=template_data["description"],
                            system_prompt=template_data["prompt"],
                            is_default=True,
                            is_active=True,
                            version=1,
                            created_at=now,
                            updated_at=now,
                        )
                        .on_conflict_do_nothing(index_elements=[PromptTemplate.type_key])
                    )

                    result = await db.execute(stmt)
                    if result.rowcount:
                        created_templates.append(type_key)
                    else:
                        log_api_request(
                            "prompt_template_seed_skipped",
                            {"type_key": type_key, "reason": "already_exists"},
                        )
        
        await db.commit()
        
        return {
            "message": "Default templates seeded successfully",
            "created": created_templates,
            "updated": updated_templates,
            "total": len(created_templates) + len(updated_templates)
        }
        
    except Exception as e:
        await db.rollback()
        log_api_request("seed_default_templates_error", {"error": str(e), "user_id": user_id})
        raise HTTPException(status_code=500, detail=f"Failed to seed default templates: {str(e)}")
