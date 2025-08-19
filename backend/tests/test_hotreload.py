"""
Test module for hot-reload functionality
"""
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

class TestHotReloadModule:
    """A simple test module to verify hot-reload functionality"""
    
    def __init__(self):
        self.name = "test_hotreload"
        self.version = "2.0.0"
        self.description = "Test module for hot-reload functionality - UPDATED!"
        self.created_at = datetime.now()
        logger.info(f"TestHotReloadModule initialized at {self.created_at}")
    
    def get_info(self) -> Dict[str, Any]:
        """Return module information"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "status": "active"
        }
    
    def process_data(self, data: str) -> str:
        """Process some data - initial version"""
        return f"Processed: {data} (version 1.0.0)"

# Module entry point
def get_module():
    """Return an instance of the module"""
    return TestHotReloadModule()

# Module metadata
MODULE_METADATA = {
    "name": "test_hotreload",
    "version": "1.0.0",
    "description": "Test module for hot-reload functionality",
    "dependencies": [],
    "entry_point": "get_module"
}