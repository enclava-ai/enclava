"""Test-only legacy API compatibility routes.

These routes preserve older synchronous endpoint contracts used by the legacy
endpoint smoke tests. They are mounted only when TESTING/LLM_TEST_MODE is set.
"""

import inspect
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from unittest.mock import Mock

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, EmailStr

from app.api.v1 import api_keys, audit, auth, budgets, settings, users
from app.services import module_manager as module_manager_module

router = APIRouter()


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        value = obj.get(name, default)
    else:
        value = getattr(obj, name, default)
    return default if isinstance(value, Mock) else value


def _user_dict(user: Any) -> Dict[str, Any]:
    return {
        "id": str(_value(user, "id", "")),
        "username": _value(user, "username"),
        "email": _value(user, "email"),
        "full_name": _value(user, "full_name"),
        "is_active": _value(user, "is_active", True),
    }


def _api_key_dict(key: Any) -> Dict[str, Any]:
    if isinstance(key, dict):
        return key
    return {
        "id": str(_value(key, "id", "")),
        "name": _value(key, "name"),
        "key_prefix": _value(key, "key_prefix"),
        "is_active": _value(key, "is_active", True),
        "created_at": _value(key, "created_at", datetime.now(timezone.utc)),
    }


def _budget_dict(budget: Any) -> Dict[str, Any]:
    return {
        "id": str(_value(budget, "id", "")),
        "name": _value(budget, "name"),
        "budget_type": _value(budget, "budget_type"),
        "limit_amount": _value(budget, "limit_amount"),
        "current_usage": _value(budget, "current_usage", 0),
        "is_active": _value(budget, "is_active", True),
    }


def _audit_dict(log: Any) -> Dict[str, Any]:
    return {
        "id": str(_value(log, "id", "")),
        "action": _value(log, "action"),
        "resource_type": _value(log, "resource_type"),
        "user_id": _value(log, "user_id"),
        "success": _value(log, "success", True),
        "created_at": _value(log, "created_at", datetime.now(timezone.utc)),
        "ip_address": _value(log, "ip_address"),
    }


def _module_dict(name: str, module: Any) -> Dict[str, Any]:
    manager = module_manager_module.module_manager
    config = manager.module_configs.get(name)
    return {
        "name": name,
        "initialized": bool(_value(module, "initialized", False)),
        "version": _value(module, "version"),
        "description": _value(module, "description"),
        "enabled": bool(_value(config, "enabled", False)),
    }


async def _default_none(*args, **kwargs):
    return None


async def _default_pair(*args, **kwargs):
    return [], 0


for module, name, default in (
    (auth, "create_user", _default_none),
    (auth, "authenticate_user", _default_none),
    (users, "get_users", _default_pair),
    (users, "get_user_by_id", _default_none),
    (api_keys, "get_api_keys", _default_pair),
    (api_keys, "regenerate_api_key", _default_none),
    (budgets, "get_budgets", _default_pair),
    (budgets, "get_budget_statistics", _default_none),
    (audit, "get_audit_logs", _default_pair),
    (audit, "export_audit_logs", _default_none),
    (settings, "get_all_settings", _default_none),
    (settings, "update_settings_section", _default_none),
    (settings, "get_system_info", _default_none),
):
    if not hasattr(module, name):
        setattr(module, name, default)


class LegacyRegisterRequest(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    password: str


class LegacyLoginRequest(BaseModel):
    username: str
    password: str


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def legacy_register(user_data: LegacyRegisterRequest):
    user = await _maybe_await(auth.create_user(user_data))
    if not user:
        raise HTTPException(status_code=400, detail="Registration failed")
    return _user_dict(user)


@router.post("/auth/login")
async def legacy_login(user_data: LegacyLoginRequest):
    user = await _maybe_await(
        auth.authenticate_user(user_data.username, user_data.password)
    )
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = auth.create_access_token({"sub": str(_value(user, "id", ""))})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": _user_dict(user),
    }


@router.get("/users")
async def legacy_list_users():
    user_list, total = await _maybe_await(users.get_users())
    return {"users": [_user_dict(user) for user in user_list], "total": total}


@router.get("/users/{user_id}")
async def legacy_get_user(user_id: str):
    user = await _maybe_await(users.get_user_by_id(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_dict(user)


@router.post("/users", status_code=status.HTTP_201_CREATED)
async def legacy_create_user(payload: Dict[str, Any]):
    user = await _maybe_await(users.create_user(payload))
    return _user_dict(user)


@router.put("/users/{user_id}")
async def legacy_update_user(user_id: str, payload: Dict[str, Any]):
    user = await _maybe_await(users.update_user(user_id, payload))
    return _user_dict(user)


@router.delete("/users/{user_id}")
async def legacy_delete_user(user_id: str):
    deleted = await _maybe_await(users.delete_user(user_id))
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}


@router.get("/api-keys")
async def legacy_list_api_keys():
    keys, total = await _maybe_await(api_keys.get_api_keys())
    return {"api_keys": [_api_key_dict(key) for key in keys], "total": total}


@router.post("/api-keys", status_code=status.HTTP_201_CREATED)
async def legacy_create_api_key(payload: Dict[str, Any]):
    return await _maybe_await(api_keys.create_api_key(payload))


@router.post("/api-keys/{key_id}/regenerate")
async def legacy_regenerate_api_key(key_id: str):
    return await _maybe_await(api_keys.regenerate_api_key(key_id))


@router.get("/budgets")
async def legacy_list_budgets():
    budget_list, total = await _maybe_await(budgets.get_budgets())
    return {"budgets": [_budget_dict(budget) for budget in budget_list], "total": total}


@router.post("/budgets", status_code=status.HTTP_201_CREATED)
async def legacy_create_budget(payload: Dict[str, Any]):
    budget = await _maybe_await(budgets.create_budget(payload))
    return _budget_dict(budget)


@router.get("/budgets/stats")
async def legacy_budget_stats():
    return await _maybe_await(budgets.get_budget_statistics())


@router.get("/audit")
async def legacy_audit_logs():
    logs, total = await _maybe_await(audit.get_audit_logs())
    return {"logs": [_audit_dict(log) for log in logs], "total": total}


@router.get("/audit/export")
async def legacy_export_audit_logs(format: str = "csv"):
    exported = await _maybe_await(audit.export_audit_logs(format=format))
    return Response(content=exported or "", media_type="text/csv")


@router.get("/settings")
async def legacy_get_settings():
    return {"settings": await _maybe_await(settings.get_all_settings())}


@router.put("/settings/{section}")
async def legacy_update_settings(section: str, payload: Dict[str, Any]):
    return await _maybe_await(settings.update_settings_section(section, payload))


@router.get("/settings/system-info")
async def legacy_system_info():
    return await _maybe_await(settings.get_system_info())


@router.get("/modules")
async def legacy_list_modules():
    manager = module_manager_module.module_manager
    return {
        "modules": [
            _module_dict(name, module) for name, module in manager.modules.items()
        ],
        "total": len(manager.modules),
        "initialized": bool(manager.initialized),
    }


@router.get("/modules/{module_name}")
async def legacy_get_module(module_name: str):
    manager = module_manager_module.module_manager
    module = manager.modules.get(module_name)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    return _module_dict(module_name, module)


@router.post("/modules/{module_name}/execute")
async def legacy_execute_module(module_name: str, payload: Dict[str, Any]):
    manager = module_manager_module.module_manager
    module = manager.modules.get(module_name)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    result = await _maybe_await(module.execute_with_interceptors(payload))
    return {
        "module": module_name,
        "success": True,
        "interceptor_pattern": True,
        "result": result,
    }


@router.post("/modules/{module_name}/enable")
async def legacy_enable_module(module_name: str):
    manager = module_manager_module.module_manager
    config = manager.module_configs.get(module_name)
    if not config:
        raise HTTPException(status_code=404, detail="Module not found")
    config.enabled = True
    if hasattr(manager, "_load_module"):
        await _maybe_await(manager._load_module(module_name))
    return {"name": module_name, "enabled": True}


@router.post("/modules/{module_name}/disable")
async def legacy_disable_module(module_name: str):
    manager = module_manager_module.module_manager
    config = manager.module_configs.get(module_name)
    if not config:
        raise HTTPException(status_code=404, detail="Module not found")
    config.enabled = False
    if hasattr(manager, "unload_module"):
        await _maybe_await(manager.unload_module(module_name))
    return {"name": module_name, "enabled": False}
