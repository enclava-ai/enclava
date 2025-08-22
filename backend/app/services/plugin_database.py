"""
Plugin Database Isolation Infrastructure
Provides isolated database schemas and secure database access for plugins
"""
import asyncio
import hashlib
import concurrent.futures
import time
from typing import Dict, Any, List, Optional, AsyncGenerator
from sqlalchemy import create_engine, text, MetaData, inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
import tempfile
import os
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.models.plugin import Plugin, PluginConfiguration
from app.db.database import get_db
from app.utils.exceptions import PluginError, DatabaseError


logger = get_logger("plugin.database")


class PluginDatabaseManager:
    """Manages isolated database schemas for plugins"""
    
    def __init__(self):
        self.plugin_engines: Dict[str, Any] = {}
        self.plugin_sessions: Dict[str, Any] = {}
        self.schema_cache: Dict[str, bool] = {}
        
    async def create_plugin_schema(self, plugin_id: str, manifest_data: Dict[str, Any]) -> bool:
        """Create isolated database schema for plugin"""
        try:
            schema_name = f"plugin_{plugin_id}"
            
            # Validate schema name
            if not self._validate_schema_name(schema_name):
                raise PluginError(f"Invalid schema name: {schema_name}")
            
            # Create schema if it doesn't exist
            await self._create_schema_if_not_exists(schema_name)
            
            # Create plugin-specific engine and session
            await self._create_plugin_database_connection(plugin_id, schema_name)
            
            # Run migrations if specified
            database_spec = manifest_data.get("spec", {}).get("database")
            if database_spec and database_spec.get("auto_migrate", True):
                await self._run_plugin_migrations(plugin_id, database_spec)
            
            self.schema_cache[plugin_id] = True
            logger.info(f"Created database schema for plugin {plugin_id}: {schema_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create plugin schema for {plugin_id}: {e}")
            raise PluginError(f"Database schema creation failed: {e}")
    
    async def delete_plugin_schema(self, plugin_id: str) -> bool:
        """Delete plugin database schema (DANGEROUS - used for uninstall)"""
        try:
            schema_name = f"plugin_{plugin_id}"
            
            # Close connections first
            await self._close_plugin_connections(plugin_id)
            
            # Drop schema and all its contents
            await self._drop_schema(schema_name)
            
            # Clean up cache
            if plugin_id in self.schema_cache:
                del self.schema_cache[plugin_id]
            
            logger.warning(f"Deleted database schema for plugin {plugin_id}: {schema_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete plugin schema for {plugin_id}: {e}")
            return False
    
    async def get_plugin_session(self, plugin_id: str) -> Optional[AsyncSession]:
        """Get database session for plugin"""
        if plugin_id not in self.plugin_sessions:
            logger.error(f"No database session for plugin {plugin_id}")
            return None
        
        return self.plugin_sessions[plugin_id]()
    
    async def get_plugin_engine(self, plugin_id: str):
        """Get database engine for plugin"""
        return self.plugin_engines.get(plugin_id)
    
    def _validate_schema_name(self, schema_name: str) -> bool:
        """Validate schema name for security"""
        if not schema_name.startswith("plugin_"):
            return False
        
        plugin_part = schema_name[7:]  # Remove "plugin_" prefix
        
        # Only allow alphanumeric and underscores
        if not plugin_part.replace("_", "").isalnum():
            return False
        
        # Check length
        if len(schema_name) > 63:  # PostgreSQL limit
            return False
        
        return True
    
    async def _create_schema_if_not_exists(self, schema_name: str):
        """Create database schema if it doesn't exist"""
        # Use synchronous database connection
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import create_engine
        
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        try:
            # Check if schema exists
            result = db.execute(
                text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = :schema_name"),
                {"schema_name": schema_name}
            )
            
            if result.fetchone():
                logger.debug(f"Schema {schema_name} already exists")
                return
            
            # Create schema
            db.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
            db.commit()
            
            logger.info(f"Created database schema: {schema_name}")
            
        except Exception as e:
            db.rollback()
            raise DatabaseError(f"Failed to create schema {schema_name}: {e}")
        finally:
            db.close()
    
    async def _drop_schema(self, schema_name: str):
        """Drop database schema and all its contents"""
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import create_engine
        
        engine = create_engine(settings.DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        try:
            # Drop schema with CASCADE to remove all objects
            db.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
            db.commit()
            
            logger.warning(f"Dropped database schema: {schema_name}")
            
        except Exception as e:
            db.rollback()
            raise DatabaseError(f"Failed to drop schema {schema_name}: {e}")
        finally:
            db.close()
    
    async def _create_plugin_database_connection(self, plugin_id: str, schema_name: str):
        """Create database engine and session for plugin"""
        try:
            # Create engine with schema-specific connection
            database_url = settings.DATABASE_URL
            
            # For PostgreSQL, set search_path to plugin schema
            if database_url.startswith("postgresql"):
                plugin_url = f"{database_url}?options=-csearch_path%3D{schema_name}"
            else:
                # For other databases, might need different approach
                plugin_url = database_url
            
            # Create async engine
            engine = create_async_engine(
                plugin_url,
                echo=False,
                pool_pre_ping=True,
                pool_recycle=3600,
                pool_size=5,
                max_overflow=10
            )
            
            # Create session factory
            async_session = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Store engine and session
            self.plugin_engines[plugin_id] = engine
            self.plugin_sessions[plugin_id] = async_session
            
            logger.debug(f"Created database connection for plugin {plugin_id}")
            
        except Exception as e:
            raise DatabaseError(f"Failed to create database connection for plugin {plugin_id}: {e}")
    
    async def _close_plugin_connections(self, plugin_id: str):
        """Close database connections for plugin"""
        try:
            if plugin_id in self.plugin_engines:
                await self.plugin_engines[plugin_id].dispose()
                del self.plugin_engines[plugin_id]
            
            if plugin_id in self.plugin_sessions:
                del self.plugin_sessions[plugin_id]
            
            logger.debug(f"Closed database connections for plugin {plugin_id}")
            
        except Exception as e:
            logger.error(f"Error closing connections for plugin {plugin_id}: {e}")
    
    async def _run_plugin_migrations(self, plugin_id: str, database_spec: Dict[str, Any]):
        """Run database migrations for plugin"""
        try:
            migrations_path = database_spec.get("migrations_path", "./migrations")
            
            # Use migration manager to run migrations
            migration_manager = PluginMigrationManager(self)
            success = await migration_manager.run_plugin_migrations(plugin_id, Path(migrations_path).parent)
            
            if not success:
                raise PluginError(f"Migration execution failed for plugin {plugin_id}")
            
            logger.info(f"Successfully ran migrations for plugin {plugin_id} from {migrations_path}")
            
        except Exception as e:
            logger.error(f"Failed to run migrations for plugin {plugin_id}: {e}")
            raise PluginError(f"Migration failed: {e}")
    
    async def backup_plugin_data(self, plugin_id: str) -> Optional[str]:
        """Create backup of plugin data"""
        try:
            schema_name = f"plugin_{plugin_id}"
            
            # Create secure backup directory
            backup_dir = Path("/data/plugin_backups")
            backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate backup filename with timestamp
            timestamp = int(time.time())
            backup_file = backup_dir / f"plugin_{plugin_id}_backup_{timestamp}.sql"
            encrypted_backup_file = backup_dir / f"plugin_{plugin_id}_backup_{timestamp}.sql.enc"
            
            # Use pg_dump to export schema data
            import subprocess
            
            # Parse database URL for pg_dump
            db_url = settings.DATABASE_URL
            if db_url.startswith("postgresql://"):
                # Extract connection details
                import urllib.parse
                parsed = urllib.parse.urlparse(db_url)
                
                # Build pg_dump command
                pg_dump_cmd = [
                    "pg_dump",
                    "-h", parsed.hostname or "localhost",
                    "-p", str(parsed.port or 5432),
                    "-U", parsed.username,
                    "-d", parsed.path.lstrip('/'),
                    "-n", schema_name,  # Only backup this schema
                    "--data-only",  # Only data, not structure
                    "-f", str(backup_file)
                ]
                
                # Set password via environment
                env = os.environ.copy()
                if parsed.password:
                    env["PGPASSWORD"] = parsed.password
                
                # Execute pg_dump
                result = subprocess.run(
                    pg_dump_cmd,
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
                
                if result.returncode != 0:
                    logger.error(f"pg_dump failed: {result.stderr}")
                    return None
                
                # Encrypt backup file
                from app.services.plugin_security import plugin_token_manager
                
                with open(backup_file, 'rb') as f:
                    backup_data = f.read()
                
                encrypted_data = plugin_token_manager.cipher_suite.encrypt(backup_data)
                
                with open(encrypted_backup_file, 'wb') as f:
                    f.write(encrypted_data)
                
                # Remove unencrypted backup
                backup_file.unlink()
                
                # Clean up old backups (keep last 5)
                await self._cleanup_old_backups(plugin_id, backup_dir)
                
                logger.info(f"Backup created for plugin {plugin_id}: {encrypted_backup_file}")
                return str(encrypted_backup_file)
            
            else:
                logger.error(f"Unsupported database type for backup: {db_url}")
                return None
            
        except Exception as e:
            logger.error(f"Failed to backup plugin data for {plugin_id}: {e}")
            return None
    
    async def restore_plugin_data(self, plugin_id: str, backup_file: str) -> bool:
        """Restore plugin data from backup"""
        try:
            schema_name = f"plugin_{plugin_id}"
            backup_path = Path(backup_file)
            
            # Validate backup file exists
            if not backup_path.exists():
                logger.error(f"Backup file not found: {backup_file}")
                return False
            
            # Validate backup file is encrypted
            if not backup_path.name.endswith('.sql.enc'):
                logger.error(f"Backup file must be encrypted (.sql.enc): {backup_file}")
                return False
            
            # Decrypt backup file
            from app.services.plugin_security import plugin_token_manager
            
            try:
                with open(backup_path, 'rb') as f:
                    encrypted_data = f.read()
                
                decrypted_data = plugin_token_manager.cipher_suite.decrypt(encrypted_data)
                
                # Create temporary file for restore
                temp_backup = backup_path.parent / f"temp_restore_{plugin_id}_{int(time.time())}.sql"
                with open(temp_backup, 'wb') as f:
                    f.write(decrypted_data)
                
            except Exception as e:
                logger.error(f"Failed to decrypt backup file: {e}")
                return False
            
            try:
                # Drop existing schema (WARNING: destructive operation)
                await self._drop_schema(schema_name)
                
                # Create fresh schema
                await self._create_schema_if_not_exists(schema_name)
                
                # Restore data using psql
                import subprocess
                import urllib.parse
                
                db_url = settings.DATABASE_URL
                if db_url.startswith("postgresql://"):
                    parsed = urllib.parse.urlparse(db_url)
                    
                    # Build psql command
                    psql_cmd = [
                        "psql",
                        "-h", parsed.hostname or "localhost",
                        "-p", str(parsed.port or 5432),
                        "-U", parsed.username,
                        "-d", parsed.path.lstrip('/'),
                        "-f", str(temp_backup)
                    ]
                    
                    # Set password via environment
                    env = os.environ.copy()
                    if parsed.password:
                        env["PGPASSWORD"] = parsed.password
                    
                    # Execute psql restore
                    result = subprocess.run(
                        psql_cmd,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=600  # 10 minute timeout
                    )
                    
                    if result.returncode != 0:
                        logger.error(f"psql restore failed: {result.stderr}")
                        return False
                    
                    # Verify data integrity by checking table count
                    stats = await self.get_plugin_database_stats(plugin_id)
                    if stats.get('table_count', 0) > 0:
                        logger.info(f"Restore completed for plugin {plugin_id}. Tables: {stats['table_count']}")
                        return True
                    else:
                        logger.warning(f"Restore completed but no tables found for plugin {plugin_id}")
                        return True  # Empty schema is valid
                    
                else:
                    logger.error(f"Unsupported database type for restore: {db_url}")
                    return False
                    
            finally:
                # Clean up temporary file
                temp_backup.unlink(missing_ok=True)
            
        except Exception as e:
            logger.error(f"Failed to restore plugin data for {plugin_id}: {e}")
            return False
    
    async def _cleanup_old_backups(self, plugin_id: str, backup_dir: Path, keep_count: int = 5):
        """Clean up old backup files, keeping only the most recent ones"""
        try:
            # Find all backup files for this plugin
            backup_pattern = f"plugin_{plugin_id}_backup_*.sql.enc"
            backup_files = list(backup_dir.glob(backup_pattern))
            
            if len(backup_files) <= keep_count:
                return  # No cleanup needed
            
            # Sort by creation time (newest first)
            backup_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            # Remove oldest backups
            files_to_remove = backup_files[keep_count:]
            for old_backup in files_to_remove:
                try:
                    old_backup.unlink()
                    logger.debug(f"Removed old backup: {old_backup.name}")
                except Exception as e:
                    logger.warning(f"Failed to remove old backup {old_backup.name}: {e}")
            
            logger.info(f"Cleaned up {len(files_to_remove)} old backups for plugin {plugin_id}")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old backups for plugin {plugin_id}: {e}")
    
    async def list_plugin_backups(self, plugin_id: str) -> List[Dict[str, Any]]:
        """List available backups for a plugin"""
        try:
            backup_dir = Path("/data/plugin_backups")
            if not backup_dir.exists():
                return []
            
            # Find all backup files for this plugin
            backup_pattern = f"plugin_{plugin_id}_backup_*.sql.enc"
            backup_files = list(backup_dir.glob(backup_pattern))
            
            backups = []
            for backup_file in backup_files:
                try:
                    # Extract timestamp from filename
                    filename = backup_file.stem  # Remove .enc extension
                    timestamp_str = filename.split('_')[-1]
                    backup_timestamp = int(timestamp_str)
                    
                    stat = backup_file.stat()
                    
                    backups.append({
                        "file_path": str(backup_file),
                        "filename": backup_file.name,
                        "timestamp": backup_timestamp,
                        "created_at": datetime.fromtimestamp(backup_timestamp, tz=timezone.utc).isoformat(),
                        "size_bytes": stat.st_size,
                        "size_mb": round(stat.st_size / (1024 * 1024), 2)
                    })
                    
                except Exception as e:
                    logger.warning(f"Failed to process backup file {backup_file.name}: {e}")
                    continue
            
            # Sort by timestamp (newest first)
            backups.sort(key=lambda b: b['timestamp'], reverse=True)
            
            return backups
            
        except Exception as e:
            logger.error(f"Failed to list backups for plugin {plugin_id}: {e}")
            return []
    
    async def get_plugin_database_stats(self, plugin_id: str) -> Dict[str, Any]:
        """Get database statistics for plugin"""
        try:
            schema_name = f"plugin_{plugin_id}"
            
            # Use synchronous database connection for stats
            from sqlalchemy.orm import sessionmaker
            from sqlalchemy import create_engine
            
            engine = create_engine(settings.DATABASE_URL)
            SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            db = SessionLocal()
            
            try:
                # Get table count
                result = db.execute(
                    text("""
                        SELECT COUNT(*) as table_count 
                        FROM information_schema.tables 
                        WHERE table_schema = :schema_name
                    """),
                    {"schema_name": schema_name}
                )
                table_count = result.fetchone()[0]
                
                # Get schema size (PostgreSQL specific)
                result = db.execute(
                    text("""
                        SELECT COALESCE(SUM(pg_total_relation_size(c.oid)), 0) as total_size
                        FROM pg_class c
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        WHERE n.nspname = :schema_name
                    """),
                    {"schema_name": schema_name}
                )
                
                size_bytes = result.fetchone()[0] or 0
                total_size = f"{size_bytes} bytes"
                
                return {
                    "schema_name": schema_name,
                    "table_count": table_count,
                    "total_size": total_size,
                    "plugin_id": plugin_id
                }
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to get database stats for plugin {plugin_id}: {e}")
            return {
                "schema_name": f"plugin_{plugin_id}",
                "table_count": 0,
                "total_size": "unknown",
                "plugin_id": plugin_id,
                "error": str(e)
            }


class PluginDatabaseSession:
    """Context manager for plugin database sessions"""
    
    def __init__(self, plugin_id: str, db_manager: PluginDatabaseManager):
        self.plugin_id = plugin_id
        self.db_manager = db_manager
        self.session = None
    
    async def __aenter__(self) -> AsyncSession:
        """Enter async context and get database session"""
        self.session = await self.db_manager.get_plugin_session(self.plugin_id)
        if not self.session:
            raise PluginError(f"No database session available for plugin {self.plugin_id}")
        
        return self.session
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context and cleanup session"""
        if self.session:
            if exc_type:
                await self.session.rollback()
            else:
                await self.session.commit()
            await self.session.close()


class PluginMigrationManager:
    """Manages database migrations for plugins"""
    
    def __init__(self, db_manager: PluginDatabaseManager):
        self.db_manager = db_manager
    
    async def create_migration_environment(self, plugin_id: str, plugin_dir: Path) -> bool:
        """Create Alembic migration environment for plugin"""
        try:
            migrations_dir = plugin_dir / "migrations"
            migrations_dir.mkdir(exist_ok=True)
            
            # Create alembic.ini
            alembic_ini_content = f"""
[alembic]
script_location = migrations
sqlalchemy.url = {settings.DATABASE_URL}?options=-csearch_path%3Dplugin_{plugin_id}

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
"""
            
            alembic_ini_path = plugin_dir / "alembic.ini"
            with open(alembic_ini_path, 'w') as f:
                f.write(alembic_ini_content)
            
            # Create env.py
            env_py_content = f"""
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# Import plugin models here
# from your_plugin.models import Base

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata for autogenerate support
target_metadata = None  # Set to your plugin's Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={{"paramstyle": "named"}},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
"""
            
            env_py_path = migrations_dir / "env.py"
            with open(env_py_path, 'w') as f:
                f.write(env_py_content)
            
            # Create script.py.mako
            script_mako_content = '''"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
'''
            
            script_mako_path = migrations_dir / "script.py.mako"
            with open(script_mako_path, 'w') as f:
                f.write(script_mako_content)
            
            logger.info(f"Created migration environment for plugin {plugin_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create migration environment for plugin {plugin_id}: {e}")
            return False
    
    async def run_plugin_migrations(self, plugin_id: str, plugin_dir: Path) -> bool:
        """Run pending migrations for plugin"""
        try:
            alembic_ini_path = plugin_dir / "alembic.ini"
            migrations_dir = plugin_dir / "migrations"
            
            # Check if migrations exist
            if not alembic_ini_path.exists() or not migrations_dir.exists():
                logger.info(f"No migrations found for plugin {plugin_id}, skipping")
                return True  # No migrations to run
            
            # Create migration environment if it doesn't exist
            if not (migrations_dir / "env.py").exists():
                await self.create_migration_environment(plugin_id, plugin_dir)
            
            # Get the plugin engine
            engine = await self.db_manager.get_plugin_engine(plugin_id)
            if not engine:
                raise PluginError(f"No database engine for plugin {plugin_id}")
            
            # Run migrations using Alembic programmatically
            await self._execute_alembic_upgrade(plugin_id, plugin_dir, engine)
            
            logger.info(f"Successfully completed migrations for plugin {plugin_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to run migrations for plugin {plugin_id}: {e}")
            return False
    
    async def _execute_alembic_upgrade(self, plugin_id: str, plugin_dir: Path, engine):
        """Execute Alembic upgrade command for plugin"""
        try:
            # Create Alembic config
            alembic_cfg = Config(str(plugin_dir / "alembic.ini"))
            
            # Set the schema-specific database URL
            schema_name = f"plugin_{plugin_id}"
            alembic_cfg.set_main_option(
                "sqlalchemy.url", 
                f"{settings.DATABASE_URL}?options=-csearch_path%3D{schema_name}"
            )
            
            # Set script location
            alembic_cfg.set_main_option("script_location", str(plugin_dir / "migrations"))
            
            # Run upgrade in a separate thread to avoid blocking
            import concurrent.futures
            
            def run_upgrade():
                try:
                    command.upgrade(alembic_cfg, "head")
                    return True
                except Exception as e:
                    logger.error(f"Alembic upgrade failed for plugin {plugin_id}: {e}")
                    return False
            
            # Execute in thread pool
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                success = await loop.run_in_executor(executor, run_upgrade)
            
            if not success:
                raise PluginError(f"Alembic upgrade command failed for plugin {plugin_id}")
            
            logger.info(f"Alembic upgrade completed for plugin {plugin_id}")
            
        except Exception as e:
            logger.error(f"Failed to execute Alembic upgrade for plugin {plugin_id}: {e}")
            raise
    
    async def get_migration_status(self, plugin_id: str, plugin_dir: Path) -> Dict[str, Any]:
        """Get migration status for plugin"""
        try:
            alembic_ini_path = plugin_dir / "alembic.ini"
            if not alembic_ini_path.exists():
                return {
                    "plugin_id": plugin_id,
                    "has_migrations": False,
                    "current_revision": None,
                    "pending_migrations": []
                }
            
            # Get current revision
            alembic_cfg = Config(str(alembic_ini_path))
            schema_name = f"plugin_{plugin_id}"
            alembic_cfg.set_main_option(
                "sqlalchemy.url", 
                f"{settings.DATABASE_URL}?options=-csearch_path%3D{schema_name}"
            )
            
            # Get migration context
            engine = await self.db_manager.get_plugin_engine(plugin_id)
            if not engine:
                return {
                    "plugin_id": plugin_id,
                    "has_migrations": True,
                    "error": "No database engine available"
                }
            
            # Use synchronous connection for Alembic
            sync_engine = create_engine(f"{settings.DATABASE_URL}?options=-csearch_path%3D{schema_name}")
            
            with sync_engine.connect() as connection:
                context = MigrationContext.configure(connection)
                current_rev = context.get_current_revision()
                
                # Get all available revisions
                from alembic.script import ScriptDirectory
                script_dir = ScriptDirectory.from_config(alembic_cfg)
                revisions = [rev.revision for rev in script_dir.walk_revisions()]
                
                return {
                    "plugin_id": plugin_id,
                    "has_migrations": True,
                    "current_revision": current_rev,
                    "available_revisions": revisions,
                    "schema_name": schema_name
                }
            
        except Exception as e:
            logger.error(f"Failed to get migration status for plugin {plugin_id}: {e}")
            return {
                "plugin_id": plugin_id,
                "has_migrations": False,
                "error": str(e)
            }


# Global plugin database manager
plugin_db_manager = PluginDatabaseManager()
plugin_migration_manager = PluginMigrationManager(plugin_db_manager)