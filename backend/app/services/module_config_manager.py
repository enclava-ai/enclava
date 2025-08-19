"""
Module-specific configuration management service
Works alongside the general ConfigManager for module discovery and schema validation
"""
import json
import yaml
from typing import Dict, List, Any, Optional
from pathlib import Path
from jsonschema import validate, ValidationError, draft7_format_checker
from dataclasses import dataclass, asdict

from app.core.logging import get_logger
from app.utils.exceptions import ConfigurationError

logger = get_logger(__name__)


@dataclass
class ModuleManifest:
    """Module manifest loaded from module.yaml"""
    name: str
    version: str
    description: str
    author: str
    category: str = "general"
    enabled: bool = True
    auto_start: bool = True
    dependencies: List[str] = None
    optional_dependencies: List[str] = None
    config_schema: Optional[str] = None
    ui_components: Optional[str] = None
    provides: List[str] = None
    consumes: List[str] = None
    endpoints: List[Dict] = None
    workflow_steps: List[Dict] = None
    permissions: List[Dict] = None
    analytics_events: List[Dict] = None
    health_checks: List[Dict] = None
    ui_config: Dict = None
    documentation: Dict = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []
        if self.optional_dependencies is None:
            self.optional_dependencies = []
        if self.provides is None:
            self.provides = []
        if self.consumes is None:
            self.consumes = []
        if self.endpoints is None:
            self.endpoints = []
        if self.workflow_steps is None:
            self.workflow_steps = []
        if self.permissions is None:
            self.permissions = []
        if self.analytics_events is None:
            self.analytics_events = []
        if self.health_checks is None:
            self.health_checks = []
        if self.ui_config is None:
            self.ui_config = {}
        if self.documentation is None:
            self.documentation = {}


class ModuleConfigManager:
    """Manages module configurations and JSON schema validation"""
    
    def __init__(self):
        self.manifests: Dict[str, ModuleManifest] = {}
        self.schemas: Dict[str, Dict] = {}
        self.configs: Dict[str, Dict] = {}
        
    async def discover_modules(self, modules_path: str = "modules") -> Dict[str, ModuleManifest]:
        """Discover modules from filesystem using module.yaml manifests"""
        discovered_modules = {}
        
        modules_dir = Path(modules_path)
        if not modules_dir.exists():
            logger.warning(f"Modules directory not found: {modules_path}")
            return discovered_modules
            
        logger.info(f"Discovering modules in: {modules_dir.absolute()}")
        
        for module_dir in modules_dir.iterdir():
            if not module_dir.is_dir():
                continue
                
            manifest_path = module_dir / "module.yaml"
            if not manifest_path.exists():
                # Try module.yml as fallback
                manifest_path = module_dir / "module.yml"
                if not manifest_path.exists():
                    # Check if it's a legacy module (has main.py but no manifest)
                    if (module_dir / "main.py").exists():
                        logger.info(f"Legacy module found (no manifest): {module_dir.name}")
                        # Create a basic manifest for legacy modules
                        manifest = ModuleManifest(
                            name=module_dir.name,
                            version="1.0.0",
                            description=f"Legacy {module_dir.name} module",
                            author="System",
                            category="legacy"
                        )
                        discovered_modules[manifest.name] = manifest
                    continue
            
            try:
                manifest = await self._load_module_manifest(manifest_path)
                discovered_modules[manifest.name] = manifest
                logger.info(f"Discovered module: {manifest.name} v{manifest.version}")
                
            except Exception as e:
                logger.error(f"Failed to load manifest for {module_dir.name}: {e}")
                continue
        
        self.manifests = discovered_modules
        return discovered_modules
    
    async def _load_module_manifest(self, manifest_path: Path) -> ModuleManifest:
        """Load and validate a module manifest file"""
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_data = yaml.safe_load(f)
            
            # Validate required fields
            required_fields = ['name', 'version', 'description', 'author']
            for field in required_fields:
                if field not in manifest_data:
                    raise ConfigurationError(f"Missing required field '{field}' in {manifest_path}")
            
            manifest = ModuleManifest(**manifest_data)
            
            # Load configuration schema if specified
            if manifest.config_schema:
                schema_path = manifest_path.parent / manifest.config_schema
                if schema_path.exists():
                    await self._load_module_schema(manifest.name, schema_path)
                else:
                    logger.warning(f"Config schema not found: {schema_path}")
            
            return manifest
            
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in {manifest_path}: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load manifest {manifest_path}: {e}")
    
    async def _load_module_schema(self, module_name: str, schema_path: Path):
        """Load JSON schema for module configuration"""
        try:
            with open(schema_path, 'r', encoding='utf-8') as f:
                schema = json.load(f)
            
            self.schemas[module_name] = schema
            logger.info(f"Loaded configuration schema for module: {module_name}")
            
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON schema in {schema_path}: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load schema {schema_path}: {e}")
    
    def get_module_manifest(self, module_name: str) -> Optional[ModuleManifest]:
        """Get module manifest by name"""
        return self.manifests.get(module_name)
    
    def get_module_schema(self, module_name: str) -> Optional[Dict]:
        """Get configuration schema for a module"""
        return self.schemas.get(module_name)
    
    def get_module_config(self, module_name: str) -> Dict:
        """Get current configuration for a module"""
        return self.configs.get(module_name, {})
    
    async def validate_config(self, module_name: str, config: Dict) -> Dict:
        """Validate module configuration against its schema"""
        schema = self.schemas.get(module_name)
        if not schema:
            logger.info(f"No schema found for module {module_name}, skipping validation")
            return {"valid": True, "errors": []}
        
        try:
            validate(instance=config, schema=schema, format_checker=draft7_format_checker)
            return {"valid": True, "errors": []}
            
        except ValidationError as e:
            return {
                "valid": False,
                "errors": [{
                    "path": list(e.path),
                    "message": e.message,
                    "invalid_value": e.instance
                }]
            }
        except Exception as e:
            return {
                "valid": False,
                "errors": [{"message": f"Schema validation failed: {str(e)}"}]
            }
    
    async def save_module_config(self, module_name: str, config: Dict) -> bool:
        """Save module configuration"""
        # Validate configuration first
        validation_result = await self.validate_config(module_name, config)
        if not validation_result["valid"]:
            error_messages = [error["message"] for error in validation_result["errors"]]
            raise ConfigurationError(f"Invalid configuration for {module_name}: {', '.join(error_messages)}")
        
        # Save configuration
        self.configs[module_name] = config
        
        # In production, this would persist to database
        # For now, we'll save to a local JSON file
        config_dir = Path("backend/storage/module_configs")
        config_dir.mkdir(parents=True, exist_ok=True)
        
        config_file = config_dir / f"{module_name}.json"
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            
            logger.info(f"Saved configuration for module: {module_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save config for {module_name}: {e}")
            return False
    
    async def load_saved_configs(self):
        """Load previously saved module configurations"""
        config_dir = Path("backend/storage/module_configs")
        if not config_dir.exists():
            return
        
        for config_file in config_dir.glob("*.json"):
            module_name = config_file.stem
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                self.configs[module_name] = config
                logger.info(f"Loaded saved configuration for module: {module_name}")
                
            except Exception as e:
                logger.error(f"Failed to load saved config for {module_name}: {e}")
    
    def list_available_modules(self) -> List[Dict]:
        """List all discovered modules with their metadata"""
        modules = []
        for name, manifest in self.manifests.items():
            modules.append({
                "name": manifest.name,
                "version": manifest.version,
                "description": manifest.description,
                "author": manifest.author,
                "category": manifest.category,
                "enabled": manifest.enabled,
                "dependencies": manifest.dependencies,
                "provides": manifest.provides,
                "consumes": manifest.consumes,
                "has_schema": name in self.schemas,
                "has_config": name in self.configs,
                "ui_config": manifest.ui_config
            })
        
        return modules
    
    def get_workflow_steps(self) -> Dict[str, List[Dict]]:
        """Get all available workflow steps from modules"""
        workflow_steps = {}
        
        for name, manifest in self.manifests.items():
            if manifest.workflow_steps:
                workflow_steps[name] = manifest.workflow_steps
        
        return workflow_steps
    
    async def update_module_status(self, module_name: str, enabled: bool) -> bool:
        """Update module enabled status"""
        manifest = self.manifests.get(module_name)
        if not manifest:
            return False
        
        manifest.enabled = enabled
        
        # Update the manifest file
        modules_dir = Path("modules")
        manifest_path = modules_dir / module_name / "module.yaml"
        
        if manifest_path.exists():
            try:
                manifest_dict = asdict(manifest)
                with open(manifest_path, 'w', encoding='utf-8') as f:
                    yaml.dump(manifest_dict, f, default_flow_style=False)
                
                logger.info(f"Updated module status: {module_name} enabled={enabled}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to update manifest for {module_name}: {e}")
                return False
        
        return False


# Global module config manager instance
module_config_manager = ModuleConfigManager()