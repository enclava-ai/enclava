"""
Module Protocols for Confidential Empire

This file defines the interface contracts that modules must implement for inter-module communication.
Using Python protocols provides compile-time type checking with zero runtime overhead.
"""

from typing import Protocol, Dict, List, Any, Optional, Union
from datetime import datetime
from abc import abstractmethod


class RAGServiceProtocol(Protocol):
    """Protocol for RAG (Retrieval-Augmented Generation) service interface"""

    @abstractmethod
    async def search(
        self, query: str, collection_name: str, top_k: int
    ) -> Dict[str, Any]:
        """
        Search for relevant documents

        Args:
            query: Search query string
            collection_name: Name of the collection to search in
            top_k: Number of top results to return

        Returns:
            Dictionary containing search results with 'results' key
        """
        ...

    @abstractmethod
    async def index_document(
        self, content: str, metadata: Dict[str, Any] = None
    ) -> str:
        """
        Index a document in the vector database

        Args:
            content: Document content to index
            metadata: Optional metadata for the document

        Returns:
            Document ID
        """
        ...

    @abstractmethod
    async def delete_document(self, document_id: str) -> bool:
        """
        Delete a document from the vector database

        Args:
            document_id: ID of document to delete

        Returns:
            True if successfully deleted
        """
        ...


class ChatbotServiceProtocol(Protocol):
    """Protocol for Chatbot service interface"""

    @abstractmethod
    async def chat_completion(self, request: Any, user_id: str, db: Any) -> Any:
        """
        Generate chat completion response

        Args:
            request: Chat request object
            user_id: ID of the user making the request
            db: Database session

        Returns:
            Chat response object
        """
        ...

    @abstractmethod
    async def create_chatbot(self, config: Any, user_id: str, db: Any) -> Any:
        """
        Create a new chatbot instance

        Args:
            config: Chatbot configuration
            user_id: ID of the user creating the chatbot
            db: Database session

        Returns:
            Created chatbot instance
        """
        ...


class LiteLLMClientProtocol(Protocol):
    """Protocol for LiteLLM client interface"""

    @abstractmethod
    async def completion(
        self, model: str, messages: List[Dict[str, str]], **kwargs
    ) -> Any:
        """
        Create a completion using the specified model

        Args:
            model: Model name to use
            messages: List of messages for the conversation
            **kwargs: Additional parameters for the completion

        Returns:
            Completion response object
        """
        ...

    @abstractmethod
    async def create_chat_completion(
        self,
        model: str,
        messages: List[Dict[str, str]],
        user_id: str,
        api_key_id: str,
        **kwargs,
    ) -> Any:
        """
        Create a chat completion with user tracking

        Args:
            model: Model name to use
            messages: List of messages for the conversation
            user_id: ID of the user making the request
            api_key_id: API key identifier
            **kwargs: Additional parameters

        Returns:
            Chat completion response
        """
        ...


class CacheServiceProtocol(Protocol):
    """Protocol for Cache service interface"""

    @abstractmethod
    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from cache

        Args:
            key: Cache key
            default: Default value if key not found

        Returns:
            Cached value or default
        """
        ...

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds

        Returns:
            True if successfully cached
        """
        ...

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Delete key from cache

        Args:
            key: Cache key to delete

        Returns:
            True if successfully deleted
        """
        ...


class SecurityServiceProtocol(Protocol):
    """Protocol for Security service interface"""

    @abstractmethod
    async def analyze_request(self, request: Any) -> Any:
        """
        Perform security analysis on a request

        Args:
            request: Request object to analyze

        Returns:
            Security analysis result
        """
        ...

    @abstractmethod
    async def validate_request(self, request: Any) -> bool:
        """
        Validate request for security compliance

        Args:
            request: Request object to validate

        Returns:
            True if request is valid/safe
        """
        ...


class WorkflowServiceProtocol(Protocol):
    """Protocol for Workflow service interface"""

    @abstractmethod
    async def execute_workflow(
        self, workflow: Any, input_data: Dict[str, Any] = None
    ) -> Any:
        """
        Execute a workflow definition

        Args:
            workflow: Workflow definition to execute
            input_data: Optional input data for the workflow

        Returns:
            Workflow execution result
        """
        ...

    @abstractmethod
    async def get_execution(self, execution_id: str) -> Any:
        """
        Get workflow execution status

        Args:
            execution_id: ID of the execution to retrieve

        Returns:
            Execution status object
        """
        ...


class ModuleServiceProtocol(Protocol):
    """Base protocol for all module services"""

    @abstractmethod
    async def initialize(self, **kwargs) -> None:
        """Initialize the module"""
        ...

    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup module resources"""
        ...

    @abstractmethod
    def get_required_permissions(self) -> List[Any]:
        """Get required permissions for this module"""
        ...


# Type aliases for common service combinations
ServiceRegistry = Dict[str, ModuleServiceProtocol]
ServiceDependencies = Dict[str, Optional[ModuleServiceProtocol]]
