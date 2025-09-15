#!/usr/bin/env python3
"""
Script to clean up orphaned plugin registrations from the database
when plugin files have been manually removed from the filesystem.

Usage:
    python cleanup_orphaned_plugin.py [plugin_name_or_id]
    
    If no plugin name/id is provided, it will list all orphaned plugins
    and prompt for confirmation to clean them up.
"""

import sys
import os
import asyncio
from pathlib import Path
from uuid import UUID

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import async_session_factory, engine
from app.models.plugin import Plugin
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("plugin.cleanup")


async def find_orphaned_plugins(session: AsyncSession):
    """Find plugins registered in database but missing from filesystem"""
    plugins_dir = Path(settings.PLUGINS_DIR or "/plugins")
    
    # Get all plugins from database
    stmt = select(Plugin)
    result = await session.execute(stmt)
    all_plugins = result.scalars().all()
    
    orphaned = []
    for plugin in all_plugins:
        # Check if plugin directory exists
        plugin_path = plugins_dir / str(plugin.id)
        if not plugin_path.exists():
            orphaned.append(plugin)
            logger.info(f"Found orphaned plugin: {plugin.name} (ID: {plugin.id})")
    
    return orphaned


async def cleanup_plugin(session: AsyncSession, plugin: Plugin, keep_data: bool = True):
    """Clean up a single orphaned plugin registration"""
    try:
        logger.info(f"Cleaning up plugin: {plugin.name} (ID: {plugin.id})")
        
        # Delete plugin configurations if they exist
        try:
            from app.models.plugin_configuration import PluginConfiguration
            config_stmt = delete(PluginConfiguration).where(
                PluginConfiguration.plugin_id == plugin.id
            )
            await session.execute(config_stmt)
            logger.info(f"Deleted configurations for plugin {plugin.id}")
        except ImportError:
            pass  # Plugin configuration model might not exist
        
        # Delete the plugin record
        await session.delete(plugin)
        await session.commit()
        
        logger.info(f"Successfully cleaned up plugin: {plugin.name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to cleanup plugin {plugin.name}: {e}")
        await session.rollback()
        return False


async def main():
    """Main cleanup function"""
    target_plugin = sys.argv[1] if len(sys.argv) > 1 else None
    
    async with async_session_factory() as session:
        if target_plugin:
            # Clean up specific plugin
            try:
                # Try to parse as UUID first
                plugin_id = UUID(target_plugin)
                stmt = select(Plugin).where(Plugin.id == plugin_id)
            except ValueError:
                # Not a UUID, search by name
                stmt = select(Plugin).where(Plugin.name == target_plugin)
            
            result = await session.execute(stmt)
            plugin = result.scalar_one_or_none()
            
            if not plugin:
                print(f"Plugin '{target_plugin}' not found in database")
                return
            
            # Check if plugin directory exists
            plugins_dir = Path(settings.PLUGINS_DIR or "/plugins")
            plugin_path = plugins_dir / str(plugin.id)
            
            if plugin_path.exists():
                print(f"Plugin directory exists at {plugin_path}")
                response = input("Plugin files exist. Are you sure you want to cleanup the database entry? (y/N): ")
                if response.lower() != 'y':
                    print("Cleanup cancelled")
                    return
            
            print(f"\nFound plugin:")
            print(f"  Name: {plugin.name}")
            print(f"  ID: {plugin.id}")
            print(f"  Version: {plugin.version}")
            print(f"  Status: {plugin.status}")
            print(f"  Directory: {plugin_path} (exists: {plugin_path.exists()})")
            
            response = input("\nProceed with cleanup? (y/N): ")
            if response.lower() == 'y':
                success = await cleanup_plugin(session, plugin)
                if success:
                    print("✓ Plugin cleaned up successfully")
                else:
                    print("✗ Failed to cleanup plugin")
            else:
                print("Cleanup cancelled")
        
        else:
            # List all orphaned plugins
            orphaned = await find_orphaned_plugins(session)
            
            if not orphaned:
                print("No orphaned plugins found")
                return
            
            print(f"\nFound {len(orphaned)} orphaned plugin(s):")
            for plugin in orphaned:
                plugins_dir = Path(settings.PLUGINS_DIR or "/plugins")
                plugin_path = plugins_dir / str(plugin.id)
                print(f"\n  • {plugin.name}")
                print(f"    ID: {plugin.id}")
                print(f"    Version: {plugin.version}")
                print(f"    Status: {plugin.status}")
                print(f"    Expected path: {plugin_path}")
            
            response = input(f"\nCleanup all {len(orphaned)} orphaned plugin(s)? (y/N): ")
            if response.lower() == 'y':
                success_count = 0
                for plugin in orphaned:
                    if await cleanup_plugin(session, plugin):
                        success_count += 1
                
                print(f"\n✓ Cleaned up {success_count}/{len(orphaned)} plugin(s)")
            else:
                print("Cleanup cancelled")


if __name__ == "__main__":
    asyncio.run(main())