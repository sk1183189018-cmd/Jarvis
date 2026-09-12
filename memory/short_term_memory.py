"""
JarvisOS - Short Term Memory

Handles temporary/session-based memory.

Short-term memory is useful for:
    - Current conversation
    - Current task
    - Recent user commands
    - Temporary context
    - Current application
    - Recent assistant responses

Long-term information should be stored through
LongTermMemory instead.
"""

from __future__ import annotations

import logging
import time
import uuid
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
class ShortTermItem:
    """One short-term memory item."""

    content: str
    role: Optional[str] = None
    session_id: Optional[str] = None
    memory_id: Optional[str] = None
    created_at: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert item to dictionary."""

        return {
            "id": self.memory_id,
            "content": self.content,
            "role": self.role,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "metadata": self.metadata or {},
        }


# ======================================================================
# SHORT TERM MEMORY
# ======================================================================


class ShortTermMemory:
    """
    Session-oriented temporary memory.

    It provides a clean interface over MemoryManager and keeps
    the most recent context available to JarvisOS.
    """

    DEFAULT_LIMIT = 20

    def __init__(
        self,
        memory_manager: Optional[
            MemoryManager
        ] = None,
        base_dir=None,
        db_path=None,
        max_items: int = DEFAULT_LIMIT,
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
                    max_short_term=max_items,
                )
            )

        self.max_items = max(
            1,
            int(max_items),
        )

        self.current_session_id = (
            self._new_session_id()
        )

        logger.info(
            "ShortTermMemory initialized. "
            "Session=%s",
            self.current_session_id,
        )

    # ==================================================================
    # SESSION
    # ==================================================================

    @staticmethod
    def _new_session_id() -> str:
        """Create a unique session ID."""

        return (
            "session-"
            + str(uuid.uuid4())
        )

    def new_session(
        self,
        clear_previous: bool = False,
    ) -> str:
        """
        Start a new temporary memory session.

        Args:
            clear_previous:
                If True, clear all short-term memory first.
        """

        if clear_previous:

            self.clear()

        self.current_session_id = (
            self._new_session_id()
        )

        logger.info(
            "New short-term session: %s",
            self.current_session_id,
        )

        return self.current_session_id

    def get_session_id(self) -> str:
        """Return current session ID."""

        return self.current_session_id

    def set_session_id(
        self,
        session_id: str,
    ) -> None:
        """Change the active session."""

        session_id = str(
            session_id
        ).strip()

        if not session_id:
            raise ValueError(
                "Session ID cannot be empty."
            )

        self.current_session_id = (
            session_id
        )

    # ==================================================================
    # ADD
    # ==================================================================

    def add(
        self,
        content: str,
        role: Optional[str] = None,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
        session_id: Optional[str] = None,
    ) -> ShortTermItem:
        """
        Add temporary information.

        Example:

            memory.add(
                "User wants to open Chrome",
                role="user"
            )
        """

        content = str(
            content
        ).strip()

        if not content:
            raise ValueError(
                "Short-term memory content "
                "cannot be empty."
            )

        active_session = (
            session_id
            or self.current_session_id
        )

        memory_id = (
            self.memory_manager.add_short_term(
                content=content,
                role=role,
                session_id=active_session,
                metadata=metadata or {},
            )
        )

        item = ShortTermItem(
            content=content,
            role=role,
            session_id=active_session,
            memory_id=memory_id,
            created_at=time.time(),
            metadata=metadata or {},
        )

        logger.debug(
            "Short-term memory added: %s",
            memory_id,
        )

        return item

    # ==================================================================
    # USER MESSAGE
    # ==================================================================

    def add_user_message(
        self,
        content: str,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ) -> ShortTermItem:
        """Add a user message."""

        return self.add(
            content=content,
            role="user",
            metadata=metadata,
        )

    # ==================================================================
    # ASSISTANT MESSAGE
    # ==================================================================

    def add_assistant_message(
        self,
        content: str,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ) -> ShortTermItem:
        """Add an assistant message."""

        return self.add(
            content=content,
            role="assistant",
            metadata=metadata,
        )

    # ==================================================================
    # SYSTEM MESSAGE
    # ==================================================================

    def add_system_message(
        self,
        content: str,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ) -> ShortTermItem:
        """Add a system message."""

        return self.add(
            content=content,
            role="system",
            metadata=metadata,
        )

    # ==================================================================
    # GET
    # ==================================================================

    def get(
        self,
        limit: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> List[
        ShortTermItem
    ]:
        """Return recent short-term memory."""

        if limit is None:
            limit = self.max_items

        limit = max(
            1,
            min(
                500,
                int(limit),
            ),
        )

        active_session = (
            session_id
            or self.current_session_id
        )

        records = (
            self.memory_manager.get_short_term(
                limit=limit,
                session_id=active_session,
            )
        )

        return [
            self._from_record(
                record
            )
            for record in records
        ]

    # ==================================================================
    # LAST ITEM
    # ==================================================================

    def last(
        self,
        session_id: Optional[str] = None,
    ) -> Optional[
        ShortTermItem
    ]:
        """Return the most recent item."""

        items = self.get(
            limit=1,
            session_id=session_id,
        )

        if not items:
            return None

        return items[-1]

    # ==================================================================
    # LAST USER MESSAGE
    # ==================================================================

    def last_user_message(
        self,
    ) -> Optional[
        ShortTermItem
    ]:
        """Return the most recent user message."""

        items = self.get(
            limit=self.max_items
        )

        for item in reversed(
            items
        ):

            if item.role == "user":
                return item

        return None

    # ==================================================================
    # LAST ASSISTANT MESSAGE
    # ==================================================================

    def last_assistant_message(
        self,
    ) -> Optional[
        ShortTermItem
    ]:
        """Return the most recent assistant message."""

        items = self.get(
            limit=self.max_items
        )

        for item in reversed(
            items
        ):

            if item.role == "assistant":
                return item

        return None

    # ==================================================================
    # CONVERSATION CONTEXT
    # ==================================================================

    def get_context(
        self,
        limit: Optional[int] = None,
    ) -> List[
        Dict[str, Any]
    ]:
        """
        Return short-term memory in AI-friendly format.
        """

        items = self.get(
            limit=limit
        )

        return [
            {
                "role": (
                    item.role
                    or "user"
                ),
                "content": item.content,
            }
            for item in items
        ]

    # ==================================================================
    # TEXT CONTEXT
    # ==================================================================

    def get_context_text(
        self,
        limit: Optional[int] = None,
    ) -> str:
        """
        Return temporary memory as readable text.
        """

        items = self.get(
            limit=limit
        )

        if not items:
            return ""

        lines = []

        for item in items:

            role = (
                item.role
                or "memory"
            )

            lines.append(
                f"{role}: {item.content}"
            )

        return "\n".join(
            lines
        )

    # ==================================================================
    # SEARCH CURRENT SESSION
    # ==================================================================

    def search(
        self,
        query: str,
        limit: int = 10,
    ) -> List[
        ShortTermItem
    ]:
        """
        Search current short-term context.

        MemoryManager's generic search operates on long-term memory,
        so this method performs an in-memory search over the active
        session.
        """

        query = str(
            query
        ).strip().lower()

        if not query:
            return []

        items = self.get(
            limit=self.max_items
        )

        matches = []

        for item in items:

            if query in item.content.lower():

                matches.append(item)

        return matches[
            :max(
                1,
                int(limit),
            )
        ]

    # ==================================================================
    # REMOVE LAST
    # ==================================================================

    def remove_last(
        self,
    ) -> bool:
        """
        Remove the latest short-term item.

        MemoryManager currently exposes clearing by session rather
        than individual short-term deletion. Therefore this method
        rebuilds the current session while preserving all but the
        latest item.
        """

        items = self.get(
            limit=self.max_items
        )

        if not items:
            return False

        items = items[:-1]

        self.clear()

        for item in items:

            self.add(
                content=item.content,
                role=item.role,
                metadata=item.metadata,
            )

        return True

    # ==================================================================
    # CLEAR
    # ==================================================================

    def clear(
        self,
        session_id: Optional[str] = None,
    ) -> int:
        """
        Clear short-term memory for a session.
        """

        active_session = (
            session_id
            or self.current_session_id
        )

        count = (
            self.memory_manager
            .clear_short_term(
                session_id=active_session
            )
        )

        logger.info(
            "Short-term memory cleared: "
            "session=%s count=%s",
            active_session,
            count,
        )

        return count

    # ==================================================================
    # CLEAR AND NEW SESSION
    # ==================================================================

    def reset(
        self,
    ) -> str:
        """Clear current memory and start a new session."""

        self.clear()

        return self.new_session(
            clear_previous=False
        )

    # ==================================================================
    # BUILD CHAT HISTORY
    # ==================================================================

    def build_chat_history(
        self,
        limit: Optional[int] = None,
    ) -> List[
        Dict[str, str]
    ]:
        """
        Return conversation history suitable for AI providers.
        """

        items = self.get(
            limit=limit
        )

        history = []

        for item in items:

            role = (
                item.role
                or "user"
            )

            if role not in {
                "system",
                "user",
                "assistant",
            }:

                role = "user"

            history.append(
                {
                    "role": role,
                    "content": item.content,
                }
            )

        return history

    # ==================================================================
    # SUMMARY
    # ==================================================================

    def summary(self) -> Dict[str, Any]:
        """Return current short-term memory summary."""

        items = self.get()

        role_counts = {
            "user": 0,
            "assistant": 0,
            "system": 0,
            "other": 0,
        }

        for item in items:

            role = item.role

            if role in role_counts:
                role_counts[role] += 1
            else:
                role_counts["other"] += 1

        return {
            "session_id": (
                self.current_session_id
            ),
            "items": len(items),
            "max_items": self.max_items,
            "roles": role_counts,
        }

    # ==================================================================
    # EXPORT
    # ==================================================================

    def export(
        self,
        session_id: Optional[str] = None,
    ) -> List[
        Dict[str, Any]
    ]:
        """Export current session memory."""

        items = self.get(
            session_id=session_id
        )

        return [
            item.to_dict()
            for item in items
        ]

    # ==================================================================
    # IMPORT
    # ==================================================================

    def import_items(
        self,
        items: List[
            Dict[str, Any]
        ],
        session_id: Optional[str] = None,
    ) -> int:
        """Import short-term memory items."""

        if not isinstance(
            items,
            list,
        ):
            raise TypeError(
                "items must be a list."
            )

        imported = 0

        for item in items:

            if not isinstance(
                item,
                dict,
            ):
                continue

            content = item.get(
                "content"
            )

            if not content:
                continue

            self.add(
                content=str(
                    content
                ),
                role=item.get(
                    "role"
                ),
                metadata=item.get(
                    "metadata",
                    {},
                ),
                session_id=(
                    session_id
                    or self.current_session_id
                ),
            )

            imported += 1

        return imported

    # ==================================================================
    # INTERNAL
    # ==================================================================

    @staticmethod
    def _from_record(
        record: Dict[str, Any],
    ) -> ShortTermItem:
        """Convert database record to ShortTermItem."""

        return ShortTermItem(
            content=record.get(
                "content",
                "",
            ),
            role=record.get(
                "role"
            ),
            session_id=record.get(
                "session_id"
            ),
            memory_id=record.get(
                "id"
            ),
            created_at=record.get(
                "created_at"
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
        """Close underlying memory manager."""

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
            "ShortTermMemory closed."
        )

    def __enter__(
        self,
    ) -> "ShortTermMemory":

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
    print("JARVIS OS - SHORT TERM MEMORY TEST")
    print("=" * 70)

    test_db = (
        "short_term_memory_test.db"
    )

    memory = ShortTermMemory(
        db_path=test_db,
        max_items=10,
    )

    # --------------------------------------------------------------
    # Add conversation
    # --------------------------------------------------------------

    print()
    print("1. Adding conversation...")

    memory.add_user_message(
        "Chrome kholo."
    )

    memory.add_assistant_message(
        "Bilkul, Chrome open karne ki taiyari hai."
    )

    memory.add_user_message(
        "Ab Google kholo."
    )

    memory.add_assistant_message(
        "Google open kar rahi hoon."
    )

    # --------------------------------------------------------------
    # Show context
    # --------------------------------------------------------------

    print()
    print("2. Current context:")

    for item in memory.get():

        print(
            f"{item.role}: "
            f"{item.content}"
        )

    # --------------------------------------------------------------
    # Chat history
    # --------------------------------------------------------------

    print()
    print("3. AI chat history:")

    for item in memory.build_chat_history():

        print(item)

    # --------------------------------------------------------------
    # Last user message
    # --------------------------------------------------------------

    print()
    print("4. Last user message:")

    last_user = (
        memory.last_user_message()
    )

    if last_user:

        print(
            last_user.content
        )

    # --------------------------------------------------------------
    # Search
    # --------------------------------------------------------------

    print()
    print("5. Search:")

    results = memory.search(
        "Google"
    )

    for item in results:

        print(
            item.content
        )

    # --------------------------------------------------------------
    # Summary
    # --------------------------------------------------------------

    print()
    print("6. Summary:")

    print(
        memory.summary()
    )

    # --------------------------------------------------------------
    # Reset
    # --------------------------------------------------------------

    print()
    print("7. Resetting session...")

    memory.reset()

    print(
        "New session:",
        memory.get_session_id(),
    )

    print()
    print("=" * 70)
    print("SHORT TERM MEMORY TEST COMPLETE")
    print("=" * 70)

    memory.close()
