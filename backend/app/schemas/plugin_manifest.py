"""
Plugin Manifest Schema and Validation
Defines the structure and validation for plugin manifest files
"""
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, validator, HttpUrl
from enum import Enum
import yaml
import hashlib
import os
from pathlib import Path


class PluginRuntimeSpec(BaseModel):
    """Plugin runtime requirements and dependencies"""
    python_version: str = Field("3.11", description="Required Python version")
    dependencies: List[str] = Field(default_factory=list, description="Required Python packages")
    environment_variables: Dict[str, str] = Field(default_factory=dict, description="Required environment variables")
    
    @validator('python_version')
    def validate_python_version(cls, v):
        if not v.startswith(('3.9', '3.10', '3.11', '3.12')):
            raise ValueError('Python version must be 3.9, 3.10, 3.11, or 3.12')
        return v


class PluginPermissions(BaseModel):
    """Plugin permission specifications"""
    platform_apis: List[str] = Field(default_factory=list, description="Platform API access scopes")
    plugin_scopes: List[str] = Field(default_factory=list, description="Plugin-specific permission scopes")
    external_domains: List[str] = Field(default_factory=list, description="Allowed external domains")
    
    @validator('platform_apis')
    def validate_platform_apis(cls, v):
        allowed_apis = [
            'chatbot:invoke', 'chatbot:manage', 'chatbot:read',
            'rag:query', 'rag:manage', 'rag:read',
            'llm:completion', 'llm:embeddings', 'llm:models',
            'workflow:execute', 'workflow:read',
            'cache:read', 'cache:write'
        ]
        for api in v:
            if api not in allowed_apis and not api.endswith(':*'):
                raise ValueError(f'Invalid platform API scope: {api}')
        return v


class PluginDatabaseSpec(BaseModel):
    """Plugin database configuration"""
    schema: str = Field(..., description="Database schema name")
    migrations_path: str = Field("./migrations", description="Path to migration files")
    auto_migrate: bool = Field(True, description="Auto-run migrations on startup")
    
    @validator('schema')
    def validate_schema_name(cls, v):
        if not v.startswith('plugin_'):
            raise ValueError('Database schema must start with "plugin_"')
        if not v.replace('plugin_', '').replace('_', '').isalnum():
            raise ValueError('Schema name must contain only alphanumeric characters and underscores')
        return v


class PluginAPIEndpoint(BaseModel):
    """Plugin API endpoint specification"""
    path: str = Field(..., description="API endpoint path")
    methods: List[str] = Field(default=['GET'], description="Allowed HTTP methods")
    description: str = Field("", description="Endpoint description")
    auth_required: bool = Field(True, description="Whether authentication is required")
    
    @validator('methods')
    def validate_methods(cls, v):
        allowed_methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS']
        for method in v:
            if method not in allowed_methods:
                raise ValueError(f'Invalid HTTP method: {method}')
        return v
    
    @validator('path')
    def validate_path(cls, v):
        if not v.startswith('/'):
            raise ValueError('API path must start with "/"')
        return v


class PluginCronJob(BaseModel):
    """Plugin scheduled job specification"""
    name: str = Field(..., description="Job name")
    schedule: str = Field(..., description="Cron expression")
    function: str = Field(..., description="Function to execute")
    description: str = Field("", description="Job description")
    enabled: bool = Field(True, description="Whether job is enabled by default")
    timeout_seconds: int = Field(300, description="Job timeout in seconds")
    max_retries: int = Field(3, description="Maximum retry attempts")
    
    @validator('schedule')
    def validate_cron_expression(cls, v):
        # Basic cron validation - should have 5 parts
        parts = v.split()
        if len(parts) != 5:
            raise ValueError('Cron expression must have 5 parts (minute hour day month weekday)')
        return v


class PluginUIConfig(BaseModel):
    """Plugin UI configuration"""
    configuration_schema: str = Field("./config_schema.json", description="JSON schema for configuration")
    ui_components: str = Field("./ui/components", description="Path to UI components")
    pages: List[Dict[str, str]] = Field(default_factory=list, description="Plugin pages")
    
    @validator('pages')
    def validate_pages(cls, v):
        required_fields = ['name', 'path', 'component']
        for page in v:
            for field in required_fields:
                if field not in page:
                    raise ValueError(f'Page must have {field} field')
        return v


class PluginExternalServices(BaseModel):
    """Plugin external service configuration"""
    allowed_domains: List[str] = Field(default_factory=list, description="Allowed external domains")
    webhooks: List[Dict[str, str]] = Field(default_factory=list, description="Webhook configurations")
    rate_limits: Dict[str, int] = Field(default_factory=dict, description="Rate limits per domain")


class PluginMetadata(BaseModel):
    """Plugin metadata information"""
    name: str = Field(..., description="Plugin name (must be unique)")
    version: str = Field(..., description="Plugin version (semantic versioning)")
    description: str = Field(..., description="Plugin description")
    author: str = Field(..., description="Plugin author")
    license: str = Field("MIT", description="Plugin license")
    homepage: Optional[HttpUrl] = Field(None, description="Plugin homepage URL")
    repository: Optional[HttpUrl] = Field(None, description="Plugin repository URL")
    tags: List[str] = Field(default_factory=list, description="Plugin tags for discovery")
    
    @validator('name')
    def validate_name(cls, v):
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Plugin name must contain only alphanumeric characters, hyphens, and underscores')
        if len(v) < 3 or len(v) > 50:
            raise ValueError('Plugin name must be between 3 and 50 characters')
        return v.lower()
    
    @validator('version')
    def validate_version(cls, v):
        # Basic semantic versioning validation
        parts = v.split('.')
        if len(parts) != 3:
            raise ValueError('Version must follow semantic versioning (x.y.z)')
        for part in parts:
            if not part.isdigit():
                raise ValueError('Version parts must be numeric')
        return v


class PluginManifest(BaseModel):
    """Complete plugin manifest specification"""
    apiVersion: str = Field("v1", description="Manifest API version")
    kind: str = Field("Plugin", description="Resource kind")
    metadata: PluginMetadata = Field(..., description="Plugin metadata")
    spec: "PluginSpec" = Field(..., description="Plugin specification")
    
    @validator('apiVersion')
    def validate_api_version(cls, v):
        if v not in ['v1']:
            raise ValueError('Unsupported API version')
        return v
    
    @validator('kind')
    def validate_kind(cls, v):
        if v != 'Plugin':
            raise ValueError('Kind must be "Plugin"')
        return v


class PluginSpec(BaseModel):
    """Plugin specification details"""
    runtime: PluginRuntimeSpec = Field(default_factory=PluginRuntimeSpec, description="Runtime requirements")
    permissions: PluginPermissions = Field(default_factory=PluginPermissions, description="Permission requirements")
    database: Optional[PluginDatabaseSpec] = Field(None, description="Database configuration")
    api_endpoints: List[PluginAPIEndpoint] = Field(default_factory=list, description="API endpoints")
    cron_jobs: List[PluginCronJob] = Field(default_factory=list, description="Scheduled jobs")
    ui_config: Optional[PluginUIConfig] = Field(None, description="UI configuration")
    external_services: Optional[PluginExternalServices] = Field(None, description="External service configuration")
    config_schema: Dict[str, Any] = Field(default_factory=dict, description="Plugin configuration JSON schema")


# Update forward reference
PluginManifest.model_rebuild()


class PluginManifestValidator:
    """Plugin manifest validation and parsing utilities"""
    
    REQUIRED_FILES = [
        'manifest.yaml',
        'main.py',
        'requirements.txt'
    ]
    
    OPTIONAL_FILES = [
        'config_schema.json',
        'README.md',
        'ui/components',
        'migrations',
        'tests'
    ]
    
    @classmethod
    def load_from_file(cls, manifest_path: Union[str, Path]) -> PluginManifest:
        """Load and validate plugin manifest from YAML file"""
        manifest_path = Path(manifest_path)
        
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")
        
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in manifest file: {e}")
        
        try:
            manifest = PluginManifest(**manifest_data)
        except Exception as e:
            raise ValueError(f"Invalid manifest structure: {e}")
        
        # Additional validation
        cls._validate_plugin_structure(manifest_path.parent, manifest)
        
        return manifest
    
    @classmethod
    def _validate_plugin_structure(cls, plugin_dir: Path, manifest: PluginManifest):
        """Validate plugin directory structure and required files"""
        
        # Check required files
        for required_file in cls.REQUIRED_FILES:
            file_path = plugin_dir / required_file
            if not file_path.exists():
                raise FileNotFoundError(f"Required file missing: {required_file}")
        
        # Validate main.py contains plugin class
        main_py_path = plugin_dir / 'main.py'
        with open(main_py_path, 'r', encoding='utf-8') as f:
            main_content = f.read()
            
        if 'BasePlugin' not in main_content:
            raise ValueError("main.py must contain a class inheriting from BasePlugin")
        
        # Validate requirements.txt format
        requirements_path = plugin_dir / 'requirements.txt'
        with open(requirements_path, 'r', encoding='utf-8') as f:
            requirements = f.read().strip()
            
        if requirements and not all(line.strip() for line in requirements.split('\n')):
            raise ValueError("Invalid requirements.txt format")
        
        # Validate config schema if specified
        if manifest.spec.ui_config and manifest.spec.ui_config.configuration_schema:
            schema_path = plugin_dir / manifest.spec.ui_config.configuration_schema
            if schema_path.exists():
                try:
                    import json
                    with open(schema_path, 'r', encoding='utf-8') as f:
                        json.load(f)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON schema: {e}")
        
        # Validate migrations if database is specified
        if manifest.spec.database:
            migrations_path = plugin_dir / manifest.spec.database.migrations_path
            if migrations_path.exists() and not migrations_path.is_dir():
                raise ValueError("Migrations path must be a directory")
    
    @classmethod
    def validate_plugin_compatibility(cls, manifest: PluginManifest) -> Dict[str, Any]:
        """Validate plugin compatibility with platform"""
        
        compatibility_report = {
            "compatible": True,
            "warnings": [],
            "errors": [],
            "platform_version": "1.0.0"
        }
        
        # Check platform API compatibility
        unsupported_apis = []
        for api in manifest.spec.permissions.platform_apis:
            if not cls._is_platform_api_supported(api):
                unsupported_apis.append(api)
        
        if unsupported_apis:
            compatibility_report["errors"].append(
                f"Unsupported platform APIs: {', '.join(unsupported_apis)}"
            )
            compatibility_report["compatible"] = False
        
        # Check Python version compatibility
        required_version = manifest.spec.runtime.python_version
        if not cls._is_python_version_supported(required_version):
            compatibility_report["errors"].append(
                f"Unsupported Python version: {required_version}"
            )
            compatibility_report["compatible"] = False
        
        # Check dependency compatibility
        for dependency in manifest.spec.runtime.dependencies:
            if cls._is_dependency_conflicting(dependency):
                compatibility_report["warnings"].append(
                    f"Potential dependency conflict: {dependency}"
                )
        
        return compatibility_report
    
    @classmethod
    def _is_platform_api_supported(cls, api: str) -> bool:
        """Check if platform API is supported"""
        supported_apis = [
            'chatbot:invoke', 'chatbot:manage', 'chatbot:read',
            'rag:query', 'rag:manage', 'rag:read',
            'llm:completion', 'llm:embeddings', 'llm:models',
            'workflow:execute', 'workflow:read',
            'cache:read', 'cache:write'
        ]
        
        # Support wildcard permissions
        if api.endswith(':*'):
            base_api = api[:-2]
            return any(supported.startswith(base_api + ':') for supported in supported_apis)
        
        return api in supported_apis
    
    @classmethod
    def _is_python_version_supported(cls, version: str) -> bool:
        """Check if Python version is supported"""
        supported_versions = ['3.9', '3.10', '3.11', '3.12']
        return any(version.startswith(v) for v in supported_versions)
    
    @classmethod
    def _is_dependency_conflicting(cls, dependency: str) -> bool:
        """Check if dependency might conflict with platform"""
        # Extract package name (before ==, >=, etc.)
        package_name = dependency.split('==')[0].split('>=')[0].split('<=')[0].split('>')[0].split('<')[0].strip()
        
        # Known conflicting packages
        conflicting_packages = [
            'sqlalchemy',  # Platform uses specific version
            'fastapi',     # Platform uses specific version
            'pydantic',    # Platform uses specific version
            'alembic'      # Platform migration system
        ]
        
        return package_name.lower() in conflicting_packages
    
    @classmethod
    def generate_manifest_hash(cls, manifest: PluginManifest) -> str:
        """Generate hash for manifest content verification"""
        manifest_dict = manifest.dict()
        manifest_str = yaml.dump(manifest_dict, sort_keys=True, default_flow_style=False)
        return hashlib.sha256(manifest_str.encode('utf-8')).hexdigest()
    
    @classmethod
    def create_example_manifest(cls, plugin_name: str) -> PluginManifest:
        """Create an example plugin manifest for development"""
        return PluginManifest(
            metadata=PluginMetadata(
                name=plugin_name,
                version="1.0.0",
                description=f"Example {plugin_name} plugin for Enclava platform",
                author="Enclava Team",
                license="MIT",
                tags=["integration", "example"]
            ),
            spec=PluginSpec(
                runtime=PluginRuntimeSpec(
                    python_version="3.11",
                    dependencies=[
                        "aiohttp>=3.8.0",
                        "pydantic>=2.0.0"
                    ]
                ),
                permissions=PluginPermissions(
                    platform_apis=["chatbot:invoke", "rag:query"],
                    plugin_scopes=["read", "write"]
                ),
                database=PluginDatabaseSpec(
                    schema=f"plugin_{plugin_name}",
                    migrations_path="./migrations"
                ),
                api_endpoints=[
                    PluginAPIEndpoint(
                        path="/status",
                        methods=["GET"],
                        description="Plugin health status"
                    )
                ],
                ui_config=PluginUIConfig(
                    configuration_schema="./config_schema.json",
                    pages=[
                        {
                            "name": "dashboard",
                            "path": f"/plugins/{plugin_name}",
                            "component": f"{plugin_name.title()}Dashboard"
                        }
                    ]
                )
            )
        )


def validate_manifest_file(manifest_path: Union[str, Path]) -> Dict[str, Any]:
    """Validate a plugin manifest file and return validation results"""
    try:
        manifest = PluginManifestValidator.load_from_file(manifest_path)
        compatibility = PluginManifestValidator.validate_plugin_compatibility(manifest)
        manifest_hash = PluginManifestValidator.generate_manifest_hash(manifest)
        
        return {
            "valid": True,
            "manifest": manifest,
            "compatibility": compatibility,
            "hash": manifest_hash,
            "errors": []
        }
    
    except Exception as e:
        return {
            "valid": False,
            "manifest": None,
            "compatibility": None,
            "hash": None,
            "errors": [str(e)]
        }