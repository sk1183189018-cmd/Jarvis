"""
JarvisOS - Long Term Memory

Permanent memory layer for JarvisOS.

This module provides a higher-level interface over MemoryManager
for information that should remain available across sessions.

Examples:
    - User preferences
    - Important facts
    - Favorite applications
    - Frequently used settings
    - Personal workflow preferences
    - Important project information

Safety:
    This module does not automatically store sensitive information
    unless explicitly requested by the caller.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

try:
    from .memory_manager import MemoryManager
except ImportError:
    from memory_manager import MemoryManager


logger = logging.getLogger(__name__)


# ======================================================================
# DATA MODEL
# ======================================================================


@dataclass
class LongTermMemory:
    """Represents one permanent memory item."""

    key: str
    value: Any
    category: str = "general"
    importance: int = 5
    source: str = "user"
    memory_id: Optional[str] = None
    created_at: Optional[float] = None
    updated_at: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert memory object into a dictionary."""

        return {
            "id": self.memory_id,
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "importance": self.importance,
            "source": self.source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata or {},
        }


# ======================================================================
# LONG TERM MEMORY
# ======================================================================


class LongTermMemory:
    """
    Permanent memory service for JarvisOS.

    This class intentionally keeps the API simple so other modules
    such as the AI brain, command processor and memory search system
    can use it without knowing database details.
    """

    DEFAULT_IMPORTANCE = 5

    VALID_CATEGORIES = {
        "general",
        "preference",
        "personal",
        "work",
        "project",
        "coding",
        "device",
        "application",
        "workflow",
        "instruction",
        "fact",
        "other",
    }

    def __init__(
        self,
        memory_manager: Optional[
            MemoryManager
        ] = None,
        base_dir=None,
        db_path=None,
    ) -> None:

        if memory_manager is not None:

            self.memory_manager = (
                memory_manager
            )

        else:

            self.memory_manager = (
                MemoryManager(
                    base_dir=base_dir,
                    db_path=db_path,
                )
            )

        logger.info(
            "LongTermMemory initialized."
        )

    # ==================================================================
    # SAVE
    # ==================================================================

    def save(
        self,
        key: str,
        value: Any,
        category: str = "general",
        importance: int = DEFAULT_IMPORTANCE,
        source: str = "user",
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ) -> LongTermMemory:
        """
        Save permanent memory.

        If the same key already exists, it is updated.
        """

        key = self._clean_key(
            key
        )

        if not key:
            raise ValueError(
                "Memory key cannot be empty."
            )

        category = (
            self._normalize_category(
                category
            )
        )

        importance = self._normalize_importance(
            importance
        )

        memory_id = (
            self.memory_manager.remember(
                key=key,
                value=value,
                category=category,
                importance=importance,
                source=source,
                metadata=metadata or {},
            )
        )

        record = (
            self.memory_manager.get_memory(
                memory_id
            )
        )

        if record is None:

            return LongTermMemory(
                key=key,
                value=value,
                category=category,
                importance=importance,
                source=source,
                memory_id=memory_id,
                metadata=metadata or {},
            )

        return self._from_record(
            record
        )

    # ==================================================================
    # SAVE USER PREFERENCE
    # ==================================================================

    def save_preference(
        self,
        key: str,
        value: Any,
        importance: int = 8,
    ) -> LongTermMemory:
        """
        Save a user preference.

        Example:
            save_preference(
                "favorite_browser",
                "Chrome"
            )
        """

        return self.save(
            key=key,
            value=value,
            category="preference",
            importance=importance,
            source="user",
        )

    # ==================================================================
    # SAVE PROJECT MEMORY
    # ==================================================================

    def save_project_memory(
        self,
        key: str,
        value: Any,
        importance: int = 7,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ) -> LongTermMemory:
        """Save information related to a project."""

        return self.save(
            key=key,
            value=value,
            category="project",
            importance=importance,
            source="project",
            metadata=metadata,
        )

    # ==================================================================
    # SAVE WORKFLOW
    # ==================================================================

    def save_workflow(
        self,
        key: str,
        value: Any,
        importance: int = 7,
    ) -> LongTermMemory:
        """Save a preferred workflow."""

        return self.save(
            key=key,
            value=value,
            category="workflow",
            importance=importance,
            source="user",
        )

    # ==================================================================
    # GET
    # ==================================================================

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """Get the value of a permanent memory."""

        return self.memory_manager.recall(
            key,
            default,
        )

    # ==================================================================
    # GET RECORD
    # ==================================================================

    def get_record(
        self,
        key: str,
    ) -> Optional[
        LongTermMemory
    ]:
        """Get complete memory information."""

        results = (
            self.memory_manager.search(
                key,
                limit=20,
            )
        )

        for record in results:

            if record.get("key") == key:

                return self._from_record(
                    record
                )

        return None

    # ==================================================================
    # CHECK
    # ==================================================================

    def exists(
        self,
        key: str,
    ) -> bool:
        """Check whether a memory exists."""

        sentinel = object()

        value = self.get(
            key,
            sentinel,
        )

        return value is not sentinel

    # ==================================================================
    # SEARCH
    # ==================================================================

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[
        LongTermMemory
    ]:
        """Search permanent memories."""

        records = (
            self.memory_manager.search(
                query=query,
                category=category,
                limit=limit,
            )
        )

        return [
            self._from_record(
                record
            )
            for record in records
        ]

    # ==================================================================
    # CATEGORY
    # ==================================================================

    def get_category(
        self,
        category: str,
        limit: int = 100,
    ) -> List[
        LongTermMemory
    ]:
        """Return memories from one category."""

        category = (
            self._normalize_category(
                category
            )
        )

        records = (
            self.memory_manager.get_all_memories(
                category=category,
                limit=limit,
            )
        )

        return [
            self._from_record(
                record
            )
            for record in records
        ]

    # ==================================================================
    # IMPORTANT MEMORIES
    # ==================================================================

    def get_important(
        self,
        minimum_importance: int = 8,
        limit: int = 20,
    ) -> List[
        LongTermMemory
    ]:
        """
        Return important memories.

        MemoryManager stores importance from 1-10.
        """

        minimum_importance = max(
            1,
            min(
                10,
                int(
                    minimum_importance
                ),
            ),
        )

        all_memories = (
            self.memory_manager.get_all_memories(
                limit=1000
            )
        )

        filtered = [
            record
            for record in all_memories
            if int(
                record.get(
                    "importance",
                    0,
                )
            )
            >= minimum_importance
        ]

        filtered.sort(
            key=lambda item: (
                item.get(
                    "importance",
                    0,
                ),
                item.get(
                    "updated_at",
                    0,
                ),
            ),
            reverse=True,
        )

        return [
            self._from_record(
                record
            )
            for record in filtered[
                :limit
            ]
        ]

    # ==================================================================
    # FORGET
    # ==================================================================

    def forget(
        self,
        key: str,
    ) -> bool:
        """
        Forget one permanent memory.
        """

        result = (
            self.memory_manager.forget(
                key
            )
        )

        if result:

            logger.info(
                "Long-term memory forgotten: %s",
                key,
            )

        return result

    # ==================================================================
    # FORGET CATEGORY
    # ==================================================================

    def forget_category(
        self,
        category: str,
    ) -> int:
        """
        Forget all memories from one category.
        """

        category = (
            self._normalize_category(
                category
            )
        )

        count = (
            self.memory_manager.clear_all(
                category=category
            )
        )

        logger.info(
            "Forgot %s memories from category '%s'.",
            count,
            category,
        )

        return count

    # ==================================================================
    # FORGET EVERYTHING
    # ==================================================================

    def forget_all(
        self,
    ) -> int:
        """
        Forget all long-term memories.

        Conversation history is not deleted.
        """

        count = (
            self.memory_manager.clear_all()
        )

        logger.warning(
            "All long-term memories cleared: %s",
            count,
        )

        return count

    # ==================================================================
    # BUILD AI MEMORY CONTEXT
    # ==================================================================

    def build_context(
        self,
        query: Optional[str] = None,
        limit: int = 10,
    ) -> str:
        """
        Build a readable memory context for an AI prompt.

        Example result:

            Known user information:
            - favorite_browser: Chrome
            - preferred_language: Hindi
        """

        if query:

            memories = self.search(
                query=query,
                limit=limit,
            )

        else:

            memories = (
                self.memory_manager
                .get_all_memories(
                    limit=limit
                )
            )

            memories = [
                self._from_record(
                    record
                )
                for record in memories
            ]

        if not memories:

            return (
                "No relevant long-term "
                "memory found."
            )

        lines = [
            "Known long-term memory:"
        ]

        for memory in memories:

            lines.append(
                "- "
                f"{memory.key}: "
                f"{self._format_value(memory.value)}"
            )

        return "\n".join(
            lines
        )

    # ==================================================================
    # MEMORY SUMMARY
    # ==================================================================

    def summary(
        self,
    ) -> Dict[str, Any]:
        """Return a summary of long-term memory."""

        stats = (
            self.memory_manager.get_stats()
        )

        return {
            "total_memories": (
                stats.get(
                    "active_memories",
                    0,
                )
            ),
            "categories": stats.get(
                "categories",
                {},
            ),
            "database": stats.get(
                "database"
            ),
        }

    # ==================================================================
    # EXPORT
    # ==================================================================

    def export(
        self,
        category: Optional[str] = None,
    ) -> List[
        Dict[str, Any]
    ]:
        """
        Export memories as dictionaries.

        Useful for backup or future UI.
        """

        memories = (
            self.memory_manager
            .get_all_memories(
                category=category,
                limit=1000,
            )
        )

        return memories

    # ==================================================================
    # IMPORT
    # ==================================================================

    def import_memories(
        self,
        memories: List[
            Dict[str, Any]
        ],
        source: str = "import",
    ) -> int:
        """
        Import previously exported memories.

        Existing keys are updated.
        """

        if not isinstance(
            memories,
            list,
        ):
            raise TypeError(
                "memories must be a list."
            )

        imported = 0

        for item in memories:

            if not isinstance(
                item,
                dict,
            ):
                continue

            key = item.get(
                "key"
            )

            if not key:
                continue

            self.save(
                key=key,
                value=item.get(
                    "value"
                ),
                category=item.get(
                    "category",
                    "general",
                ),
                importance=item.get(
                    "importance",
                    5,
                ),
                source=source,
                metadata=item.get(
                    "metadata",
                    {},
                ),
            )

            imported += 1

        logger.info(
            "Imported %s long-term memories.",
            imported,
        )

        return imported

    # ==================================================================
    # RECENT
    # ==================================================================

    def recent(
        self,
        limit: int = 10,
    ) -> List[
        LongTermMemory
    ]:
        """Return recently updated memories."""

        records = (
            self.memory_manager
            .get_all_memories(
                limit=limit
            )
        )

        records.sort(
            key=lambda item: item.get(
                "updated_at",
                0,
            ),
            reverse=True,
        )

        return [
            self._from_record(
                record
            )
            for record in records[
                :limit
            ]
        ]

    # ==================================================================
    # INTERNAL HELPERS
    # ==================================================================

    @staticmethod
    def _clean_key(
        key: str,
    ) -> str:

        return (
            str(key)
            .strip()
            .lower()
            .replace(" ", "_")
        )

    def _normalize_category(
        self,
        category: str,
    ) -> str:

        category = (
            str(category)
            .strip()
            .lower()
            .replace(" ", "_")
        )

        if category not in self.VALID_CATEGORIES:

            return "general"

        return category

    @staticmethod
    def _normalize_importance(
        importance: int,
    ) -> int:

        try:

            importance = int(
                importance
            )

        except (
            TypeError,
            ValueError,
        ):

            importance = 5

        return max(
            1,
            min(
                10,
                importance,
            ),
        )

    @staticmethod
    def _format_value(
        value: Any,
    ) -> str:

        if isinstance(
            value,
            (dict, list, tuple),
        ):

            return str(
                value
            )

        return str(
            value
        )

    @staticmethod
    def _from_record(
        record: Dict[str, Any],
    ) -> LongTermMemory:

        return LongTermMemory(
            key=record.get(
                "key",
                "",
            ),
            value=record.get(
                "value"
            ),
            category=record.get(
                "category",
                "general",
            ),
            importance=int(
                record.get(
                    "importance",
                    5,
                )
            ),
            source=record.get(
                "source",
                "user",
            ),
            memory_id=record.get(
                "id"
            ),
            created_at=record.get(
                "created_at"
            ),
            updated_at=record.get(
                "updated_at"
            ),
            metadata=record.get(
                "metadata",
                {},
            ),
        )

    # ==================================================================
    # CLOSE
    # ==================================================================

    def close(self) -> None:
        """Close underlying memory service."""

        close_method = getattr(
            self.memory_manager,
            "close",
            None,
        )

        if callable(
            close_method
        ):

            close_method()

        logger.info(
            "LongTermMemory closed."
        )

    def __enter__(
        self,
    ) -> "LongTermMemory":

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:

        self.close()


# ======================================================================
# DIRECT TEST
# ======================================================================


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(message)s"
        ),
    )

    print()
    print("=" * 70)
    print("JARVIS OS - LONG TERM MEMORY TEST")
    print("=" * 70)

    test_db = (
        "long_term_memory_test.db"
    )

    memory = LongTermMemory(
        db_path=test_db
    )

    # --------------------------------------------------------------
    # Save preference
    # --------------------------------------------------------------

    print()
    print("1. Saving preference...")

    saved = (
        memory.save_preference(
            "favorite_browser",
            "Chrome",
        )
    )

    print(
        "Key:",
        saved.key,
    )

    print(
        "Value:",
        saved.value,
    )

    # --------------------------------------------------------------
    # Read
    # --------------------------------------------------------------

    print()
    print("2. Reading memory...")

    print(
        "Favorite browser:",
        memory.get(
            "favorite_browser"
        ),
    )

    # --------------------------------------------------------------
    # Save project memory
    # --------------------------------------------------------------

    print()
    print("3. Saving project memory...")

    project = (
        memory.save_project_memory(
            "current_project",
            "JarvisOS",
            importance=9,
        )
    )

    print(
        project.to_dict()
    )

    # --------------------------------------------------------------
    # Search
    # --------------------------------------------------------------

    print()
    print("4. Searching...")

    results = memory.search(
        "browser"
    )

    for item in results:

        print(
            f"{item.key} = "
            f"{item.value}"
        )

    # --------------------------------------------------------------
    # Important memories
    # --------------------------------------------------------------

    print()
    print("5. Important memories...")

    important = (
        memory.get_important(
            minimum_importance=8
        )
    )

    for item in important:

        print(
            f"{item.key} = "
            f"{item.value} "
            f"(importance={item.importance})"
        )

    # --------------------------------------------------------------
    # AI context
    # --------------------------------------------------------------

    print()
    print("6. AI memory context:")

    print(
        memory.build_context()
    )

    # --------------------------------------------------------------
    # Summary
    # --------------------------------------------------------------

    print()
    print("7. Summary:")

    print(
        memory.summary()
    )

    # --------------------------------------------------------------
    # Forget test
    # --------------------------------------------------------------

    print()
    print("8. Forgetting test memory...")

    result = memory.forget(
        "favorite_browser"
    )

    print(
        "Forgot:",
        result,
    )

    print()
    print("=" * 70)
    print("LONG TERM MEMORY TEST COMPLETE")
    print("=" * 70)
