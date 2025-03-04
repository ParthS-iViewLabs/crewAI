from typing import Any, Dict, List, Optional

from crewai.memory.long_term.long_term_memory_item import LongTermMemoryItem
from crewai.memory.memory import Memory
from crewai.memory.storage.ltm_sqlite_storage import LTMSQLiteStorage


class LongTermMemory(Memory):
    """
    LongTermMemory class for managing cross runs data related to overall crew's
    execution and performance.
    Inherits from the Memory class and utilizes an instance of a class that
    adheres to the Storage for data storage, specifically working with
    LongTermMemoryItem instances.
    """

    def __init__(self, crew=None, embedder_config=None, storage=None, path=None):
        memory_provider = None
        memory_config = None
        
        if crew and hasattr(crew, "memory_config") and crew.memory_config is not None:
            memory_config = crew.memory_config
            memory_provider = memory_config.get("provider")
            
        # Initialize with basic parameters
        super().__init__(
            storage=storage,
            embedder_config=embedder_config,
            memory_provider=memory_provider
        )
        
        try:
            # Try to select storage using helper method
            self.storage = self._select_storage(
                storage=storage,
                memory_config=memory_config,
                storage_type="long_term",
                crew=crew,
                path=path,
                default_storage_factory=lambda path, crew: LTMSQLiteStorage(db_path=path) if path else LTMSQLiteStorage()
            )
        except ValueError:
            # Fallback to default storage
            self.storage = LTMSQLiteStorage(db_path=path) if path else LTMSQLiteStorage()

    def save(
        self,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
        agent: Optional[str] = None,
    ) -> None:
        """Saves a value into the memory."""
        if isinstance(value, LongTermMemoryItem):
            item = value
            item_metadata = item.metadata or {}
            item_metadata.update({"agent": item.agent, "expected_output": item.expected_output})
            
            # Handle special storage types like Mem0Storage
            if hasattr(self.storage, "save") and callable(getattr(self.storage, "save")) and hasattr(self.storage.save, "__code__") and "task_description" in self.storage.save.__code__.co_varnames:
                self.storage.save(
                    task_description=item.task,
                    score=item_metadata.get("quality", 0),
                    metadata=item_metadata,
                    datetime=item.datetime,
                )
            else:
                # Use standard storage interface
                self.storage.save(item.task, item_metadata)
        else:
            # Handle regular value and metadata
            super().save(value, metadata, agent)

    def search(
        self,
        query: str,
        limit: int = 3,
        score_threshold: float = 0.35,
    ) -> List[Any]:
        """Search for values in the memory."""
        # Try to use the standard storage interface first
        if hasattr(self.storage, "search") and callable(getattr(self.storage, "search")):
            return self.storage.search(query=query, limit=limit, score_threshold=score_threshold)
        # Fall back to load method for backward compatibility
        elif hasattr(self.storage, "load") and callable(getattr(self.storage, "load")):
            return self.storage.load(query, limit)
        else:
            raise AttributeError("Storage does not implement search or load method")

    def reset(self) -> None:
        self.storage.reset()
