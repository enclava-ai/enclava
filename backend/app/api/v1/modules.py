"""
Modules API endpoints
"""

from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from app.services.module_manager import module_manager, ModuleConfig
from app.core.logging import log_api_request
from app.core.security import get_current_user

router = APIRouter()


@router.get("/")
async def list_modules(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get list of all discovered modules with their status (enabled and disabled)"""
    log_api_request("list_modules", {})

    # Get all discovered modules including disabled ones
    all_modules = module_manager.list_all_modules()

    modules = []
    for module_info in all_modules:
        # Convert module_info to API format with status field
        name = module_info["name"]
        is_loaded = module_info["loaded"]  # Module is actually loaded in memory
        is_enabled = module_info["enabled"]  # Module is enabled in config

        # Determine status based on enabled + loaded state
        if is_enabled and is_loaded:
            status = "running"
        elif is_enabled and not is_loaded:
            status = "error"  # Enabled but failed to load
        else:  # not is_enabled (regardless of loaded state)
            status = "standby"  # Disabled

        api_module = {
            "name": name,
            "version": module_info["version"],
            "description": module_info["description"],
            "initialized": is_loaded,
            "enabled": is_enabled,
            "status": status,  # Add status field for frontend compatibility
        }

        # Get module statistics if available and module is loaded
        if module_info["loaded"] and module_info["name"] in module_manager.modules:
            module_instance = module_manager.modules[module_info["name"]]
            if hasattr(module_instance, "get_stats"):
                try:
                    import asyncio

                    if asyncio.iscoroutinefunction(module_instance.get_stats):
                        stats = await module_instance.get_stats()
                    else:
                        stats = module_instance.get_stats()
                    api_module["stats"] = (
                        stats.__dict__ if hasattr(stats, "__dict__") else stats
                    )
                except:
                    api_module["stats"] = {}

        modules.append(api_module)

    # Calculate stats
    loaded_count = sum(1 for m in modules if m["initialized"] and m["enabled"])

    return {
        "total": len(modules),
        "modules": modules,
        "module_count": loaded_count,
        "initialized": module_manager.initialized,
    }


@router.get("/status")
async def get_modules_status(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Get comprehensive module status - CONSOLIDATED endpoint"""
    log_api_request("get_modules_status", {})

    # Get all discovered modules including disabled ones
    all_modules = module_manager.list_all_modules()

    modules_with_status = []
    running_count = 0
    standby_count = 0
    failed_count = 0

    for module_info in all_modules:
        name = module_info["name"]
        is_loaded = module_info["loaded"]  # Module is actually loaded in memory
        is_enabled = module_info["enabled"]  # Module is enabled in config

        # Determine status based on enabled + loaded state
        if is_enabled and is_loaded:
            status = "running"
            running_count += 1
        elif is_enabled and not is_loaded:
            status = "failed"  # Enabled but failed to load
            failed_count += 1
        else:  # not is_enabled (regardless of loaded state)
            status = "standby"  # Disabled
            standby_count += 1

        # Get module statistics if available and loaded
        stats = {}
        if is_loaded and name in module_manager.modules:
            module_instance = module_manager.modules[name]
            if hasattr(module_instance, "get_stats"):
                try:
                    import asyncio

                    if asyncio.iscoroutinefunction(module_instance.get_stats):
                        stats_result = await module_instance.get_stats()
                    else:
                        stats_result = module_instance.get_stats()
                    stats = (
                        stats_result.__dict__
                        if hasattr(stats_result, "__dict__")
                        else stats_result
                    )
                except:
                    stats = {}

        modules_with_status.append(
            {
                "name": name,
                "version": module_info["version"],
                "description": module_info["description"],
                "status": status,
                "enabled": is_enabled,
                "loaded": is_loaded,
                "stats": stats,
            }
        )

    return {
        "modules": modules_with_status,
        "total": len(modules_with_status),
        "running": running_count,
        "standby": standby_count,
        "failed": failed_count,
        "system_initialized": module_manager.initialized,
    }


@router.get("/{module_name}")
async def get_module_info(
    module_name: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get detailed information about a specific module"""
    log_api_request("get_module_info", {"module_name": module_name})

    if module_name not in module_manager.modules:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

    module = module_manager.modules[module_name]
    module_info = {
        "name": module_name,
        "version": getattr(module, "version", "1.0.0"),
        "description": getattr(module, "description", ""),
        "initialized": getattr(module, "initialized", False),
        "enabled": module_manager.module_configs.get(
            module_name, ModuleConfig(module_name)
        ).enabled,
        "capabilities": [],
    }

    # Get module capabilities
    if hasattr(module, "get_module_info"):
        try:
            import asyncio

            if asyncio.iscoroutinefunction(module.get_module_info):
                info = await module.get_module_info()
            else:
                info = module.get_module_info()
            module_info.update(info)
        except:
            pass

    # Get module statistics
    if hasattr(module, "get_stats"):
        try:
            import asyncio

            if asyncio.iscoroutinefunction(module.get_stats):
                stats = await module.get_stats()
            else:
                stats = module.get_stats()
            module_info["stats"] = (
                stats.__dict__ if hasattr(stats, "__dict__") else stats
            )
        except:
            module_info["stats"] = {}

    # List available methods
    methods = []
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if callable(attr) and not attr_name.startswith("_"):
            methods.append(attr_name)
    module_info["methods"] = methods

    return module_info


@router.post("/{module_name}/enable")
async def enable_module(
    module_name: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Enable a module"""
    log_api_request("enable_module", {"module_name": module_name})

    if module_name not in module_manager.module_configs:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

    # Enable the module in config
    config = module_manager.module_configs[module_name]
    config.enabled = True

    # Load the module if not already loaded
    if module_name not in module_manager.modules:
        try:
            await module_manager._load_module(module_name, config)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to enable module '{module_name}': {str(e)}",
            )

    return {"message": f"Module '{module_name}' enabled successfully", "enabled": True}


@router.post("/{module_name}/disable")
async def disable_module(
    module_name: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Disable a module"""
    log_api_request("disable_module", {"module_name": module_name})

    if module_name not in module_manager.module_configs:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

    # Disable the module in config
    config = module_manager.module_configs[module_name]
    config.enabled = False

    # Unload the module if loaded
    if module_name in module_manager.modules:
        try:
            await module_manager.unload_module(module_name)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to disable module '{module_name}': {str(e)}",
            )

    return {
        "message": f"Module '{module_name}' disabled successfully",
        "enabled": False,
    }


@router.post("/all/reload")
async def reload_all_modules(current_user: Dict[str, Any] = Depends(get_current_user)):
    """Reload all modules"""
    log_api_request("reload_all_modules", {})

    results = {}
    failed_modules = []

    for module_name in list(module_manager.modules.keys()):
        try:
            success = await module_manager.reload_module(module_name)
            results[module_name] = {"success": success, "error": None}
            if not success:
                failed_modules.append(module_name)
        except Exception as e:
            results[module_name] = {"success": False, "error": str(e)}
            failed_modules.append(module_name)

    if failed_modules:
        return {
            "message": f"Reloaded {len(results) - len(failed_modules)}/{len(results)} modules successfully",
            "success": False,
            "results": results,
            "failed_modules": failed_modules,
        }
    else:
        return {
            "message": f"All {len(results)} modules reloaded successfully",
            "success": True,
            "results": results,
            "failed_modules": [],
        }


@router.post("/{module_name}/reload")
async def reload_module(
    module_name: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Reload a specific module"""
    log_api_request("reload_module", {"module_name": module_name})

    if module_name not in module_manager.modules:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

    success = await module_manager.reload_module(module_name)

    if not success:
        raise HTTPException(
            status_code=500, detail=f"Failed to reload module '{module_name}'"
        )

    return {
        "message": f"Module '{module_name}' reloaded successfully",
        "reloaded": True,
    }


@router.post("/{module_name}/restart")
async def restart_module(
    module_name: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Restart a specific module (alias for reload)"""
    log_api_request("restart_module", {"module_name": module_name})

    if module_name not in module_manager.modules:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

    success = await module_manager.reload_module(module_name)

    if not success:
        raise HTTPException(
            status_code=500, detail=f"Failed to restart module '{module_name}'"
        )

    return {
        "message": f"Module '{module_name}' restarted successfully",
        "restarted": True,
    }


@router.post("/{module_name}/start")
async def start_module(
    module_name: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Start a specific module (enable and load)"""
    log_api_request("start_module", {"module_name": module_name})

    if module_name not in module_manager.module_configs:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

    # Enable the module
    config = module_manager.module_configs[module_name]
    config.enabled = True

    # Load the module if not already loaded
    if module_name not in module_manager.modules:
        await module_manager._load_module(module_name, config)

    return {"message": f"Module '{module_name}' started successfully", "started": True}


@router.post("/{module_name}/stop")
async def stop_module(
    module_name: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Stop a specific module (disable and unload)"""
    log_api_request("stop_module", {"module_name": module_name})

    if module_name not in module_manager.module_configs:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

    # Disable the module
    config = module_manager.module_configs[module_name]
    config.enabled = False

    # Unload the module if loaded
    if module_name in module_manager.modules:
        await module_manager.unload_module(module_name)

    return {"message": f"Module '{module_name}' stopped successfully", "stopped": True}


@router.get("/{module_name}/stats")
async def get_module_stats(
    module_name: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get module statistics"""
    log_api_request("get_module_stats", {"module_name": module_name})

    if module_name not in module_manager.modules:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

    module = module_manager.modules[module_name]

    if not hasattr(module, "get_stats"):
        raise HTTPException(
            status_code=404,
            detail=f"Module '{module_name}' does not provide statistics",
        )

    try:
        import asyncio

        if asyncio.iscoroutinefunction(module.get_stats):
            stats = await module.get_stats()
        else:
            stats = module.get_stats()
        return {
            "module": module_name,
            "stats": stats.__dict__ if hasattr(stats, "__dict__") else stats,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get statistics: {str(e)}"
        )


@router.post("/{module_name}/execute")
async def execute_module_action(
    module_name: str,
    request_data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Execute a module action through the interceptor pattern"""
    log_api_request(
        "execute_module_action",
        {"module_name": module_name, "action": request_data.get("action")},
    )

    if module_name not in module_manager.modules:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

    module = module_manager.modules[module_name]

    # Check if module supports the new interceptor pattern
    if hasattr(module, "execute_with_interceptors"):
        try:
            # Prepare context (would normally come from authentication middleware)
            context = {
                "user_id": "test_user",  # Would come from authentication
                "api_key_id": "test_api_key",  # Would come from API key auth
                "ip_address": "127.0.0.1",  # Would come from request
                "user_permissions": [
                    f"modules:{module_name}:*"
                ],  # Would come from user/API key permissions
            }

            # Execute through interceptor chain
            response = await module.execute_with_interceptors(request_data, context)

            return {
                "module": module_name,
                "success": True,
                "response": response,
                "interceptor_pattern": True,
            }

        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Module execution failed: {str(e)}"
            )

    # Fallback for legacy modules
    else:
        action = request_data.get("action", "execute")

        if hasattr(module, action):
            try:
                method = getattr(module, action)
                if callable(method):
                    import asyncio

                    if asyncio.iscoroutinefunction(method):
                        response = await method(request_data)
                    else:
                        response = method(request_data)

                    return {
                        "module": module_name,
                        "success": True,
                        "response": response,
                        "interceptor_pattern": False,
                    }
                else:
                    raise HTTPException(
                        status_code=400, detail=f"'{action}' is not callable"
                    )
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Module execution failed: {str(e)}"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Action '{action}' not supported by module '{module_name}'",
            )


@router.get("/{module_name}/config")
async def get_module_config(
    module_name: str, current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Get module configuration schema and current values"""
    log_api_request("get_module_config", {"module_name": module_name})

    from app.services.module_config_manager import module_config_manager
    from app.services.llm.service import llm_service
    import copy

    # Get module manifest and schema
    manifest = module_config_manager.get_module_manifest(module_name)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

    schema = module_config_manager.get_module_schema(module_name)
    current_config = module_config_manager.get_module_config(module_name)

    # For Signal module, populate model options dynamically
    if module_name == "signal" and schema:
        try:
            # Get available models from LLM service
            models_data = await llm_service.get_models()
            model_ids = [model.id for model in models_data]

            if model_ids:
                # Create a copy of the schema to avoid modifying the original
                dynamic_schema = copy.deepcopy(schema)

                # Add enum options for the model field
                if (
                    "properties" in dynamic_schema
                    and "model" in dynamic_schema["properties"]
                ):
                    dynamic_schema["properties"]["model"]["enum"] = model_ids
                    # Set a sensible default if the current default isn't in the list
                    current_default = dynamic_schema["properties"]["model"].get(
                        "default", "gpt-3.5-turbo"
                    )
                    if current_default not in model_ids and model_ids:
                        dynamic_schema["properties"]["model"]["default"] = model_ids[0]

                schema = dynamic_schema

        except Exception as e:
            # If we can't get models, log warning but continue with original schema
            logger.warning(f"Failed to get dynamic models for Signal config: {e}")

    return {
        "module": module_name,
        "description": manifest.description,
        "schema": schema,
        "current_config": current_config,
        "has_schema": schema is not None,
    }


@router.post("/{module_name}/config")
async def update_module_config(
    module_name: str,
    config: dict,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Update module configuration"""
    log_api_request("update_module_config", {"module_name": module_name})

    from app.services.module_config_manager import module_config_manager

    # Validate module exists
    manifest = module_config_manager.get_module_manifest(module_name)
    if not manifest:
        raise HTTPException(status_code=404, detail=f"Module '{module_name}' not found")

    try:
        # Save configuration
        success = await module_config_manager.save_module_config(module_name, config)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save configuration")

        # Update module manager with new config
        success = await module_manager.update_module_config(module_name, config)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to apply configuration")

        return {
            "message": f"Configuration updated for module '{module_name}'",
            "config": config,
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
