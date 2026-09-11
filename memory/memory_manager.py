"""
JarvisOS - Memory Manager

Main controller for JarvisOS memory.

Responsibilities:
    - Store memories
    - Retrieve memories
    - Update memories
    - Delete memories
    - Store conversation history
    - Search memories
    - Manage short-term and long-term memory
    - Provide a simple interface to the rest of JarvisOS

Storage:
    memory/memory.db

This module uses SQLite from Python's standard library.
No external database server is required.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Central memory controller for JarvisOS.

    Example:

        memory = MemoryManager()

        memory.remember(
            "favorite_browser",
            "Chrome",
            category="preference"
        )

        result = memory.recall(
            "favorite_browser"
        )
    """

    DEFAULT_DB_NAME = "memory.db"

    def __init__(
        self,
        base_dir: Optional[str | Path] = None,
        db_path: Optional[str | Path] = None,
        max_short_term: int = 20,
    ) -> None:

        # --------------------------------------------------------------
        # Base directory
        # --------------------------------------------------------------

        if base_dir is None:
            self.base_dir = Path(__file__).resolve().parent
        else:
            self.base_dir = Path(base_dir).resolve()

        self.base_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        # --------------------------------------------------------------
        # Database path
        # --------------------------------------------------------------

        if db_path is None:
            self.db_path = (
                self.base_dir
                / self.DEFAULT_DB_NAME
            )
        else:
            self.db_path = Path(
                db_path
            ).resolve()

            self.db_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

        self.max_short_term = max(
            1,
            int(max_short_term),
        )

        self._lock = threading.RLock()

        self._initialize_database()

        logger.info(
            "MemoryManager initialized: %s",
            self.db_path,
        )

    # ==================================================================
    # DATABASE
    # ==================================================================

    def _connect(self) -> sqlite3.Connection:
        """
        Create a new SQLite connection.

        A separate connection is used for each operation.
        This is safer when JarvisOS later uses multiple threads.
        """

        connection = sqlite3.connect(
            str(self.db_path),
            timeout=10,
        )

        connection.row_factory = (
            sqlite3.Row
        )

        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        connection.execute(
            "PRAGMA journal_mode = WAL"
        )

        return connection

    def _initialize_database(self) -> None:
        """Create all required memory tables."""

        with self._lock:

            connection = self._connect()

            try:

                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS memories (
                        id TEXT PRIMARY KEY,
                        memory_key TEXT NOT NULL,
                        memory_value TEXT NOT NULL,
                        category TEXT NOT NULL DEFAULT 'general',
                        importance INTEGER NOT NULL DEFAULT 5,
                        source TEXT NOT NULL DEFAULT 'user',
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        expires_at REAL,
                        metadata TEXT NOT NULL DEFAULT '{}',
                        is_active INTEGER NOT NULL DEFAULT 1
                    );

                    CREATE INDEX IF NOT EXISTS
                    idx_memories_key
                    ON memories(memory_key);

                    CREATE INDEX IF NOT EXISTS
                    idx_memories_category
                    ON memories(category);

                    CREATE INDEX IF NOT EXISTS
                    idx_memories_active
                    ON memories(is_active);

                    CREATE TABLE IF NOT EXISTS conversations (
                        id TEXT PRIMARY KEY,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        session_id TEXT,
                        created_at REAL NOT NULL,
                        metadata TEXT NOT NULL DEFAULT '{}'
                    );

                    CREATE INDEX IF NOT EXISTS
                    idx_conversations_session
                    ON conversations(session_id);

                    CREATE INDEX IF NOT EXISTS
                    idx_conversations_created
                    ON conversations(created_at);

                    CREATE TABLE IF NOT EXISTS
                    short_term_memory (
                        id TEXT PRIMARY KEY,
                        content TEXT NOT NULL,
                        role TEXT,
                        session_id TEXT,
                        created_at REAL NOT NULL,
                        metadata TEXT NOT NULL DEFAULT '{}'
                    );

                    CREATE INDEX IF NOT EXISTS
                    idx_short_term_created
                    ON short_term_memory(created_at);

                    CREATE TABLE IF NOT EXISTS
                    memory_events (
                        id TEXT PRIMARY KEY,
                        event_type TEXT NOT NULL,
                        memory_id TEXT,
                        details TEXT NOT NULL DEFAULT '{}',
                        created_at REAL NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS
                    idx_memory_events_created
                    ON memory_events(created_at);
                    """
                )

                connection.commit()

            finally:
                connection.close()

    # ==================================================================
    # UTILITY
    # ==================================================================

    @staticmethod
    def _now() -> float:
        """Return current Unix timestamp."""

        return time.time()

    @staticmethod
    def _new_id() -> str:
        """Generate unique ID."""

        return str(
            uuid.uuid4()
        )

    @staticmethod
    def _json_dumps(
        value: Any,
    ) -> str:
        """Safely convert Python data to JSON."""

        try:

            return json.dumps(
                value,
                ensure_ascii=False,
                default=str,
            )

        except Exception:

            return json.dumps(
                str(value),
                ensure_ascii=False,
            )

    @staticmethod
    def _json_loads(
        value: Optional[str],
        default: Any = None,
    ) -> Any:
        """Safely parse JSON."""

        if not value:
            return default

        try:
            return json.loads(value)

        except (
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ):
            return default

    # ==================================================================
    # MEMORY WRITE
    # ==================================================================

    def remember(
        self,
        key: str,
        value: Any,
        category: str = "general",
        importance: int = 5,
        source: str = "user",
        expires_at: Optional[float] = None,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ) -> str:
        """
        Store or update a long-term memory.

        Example:

            memory.remember(
                "favorite_browser",
                "Chrome",
                category="preference"
            )
        """

        key = str(
            key
        ).strip()

        if not key:
            raise ValueError(
                "Memory key cannot be empty."
            )

        category = (
            str(category)
            .strip()
            .lower()
            or "general"
        )

        source = (
            str(source)
            .strip()
            or "user"
        )

        importance = max(
            1,
            min(
                10,
                int(importance),
            ),
        )

        now = self._now()

        value_json = self._json_dumps(
            value
        )

        metadata_json = self._json_dumps(
            metadata or {}
        )

        with self._lock:

            connection = self._connect()

            try:

                existing = connection.execute(
                    """
                    SELECT id
                    FROM memories
                    WHERE memory_key = ?
                      AND is_active = 1
                    LIMIT 1
                    """,
                    (key,),
                ).fetchone()

                if existing:

                    memory_id = existing[
                        "id"
                    ]

                    connection.execute(
                        """
                        UPDATE memories
                        SET memory_value = ?,
                            category = ?,
                            importance = ?,
                            source = ?,
                            updated_at = ?,
                            expires_at = ?,
                            metadata = ?,
                            is_active = 1
                        WHERE id = ?
                        """,
                        (
                            value_json,
                            category,
                            importance,
                            source,
                            now,
                            expires_at,
                            metadata_json,
                            memory_id,
                        ),
                    )

                    event_type = (
                        "updated"
                    )

                else:

                    memory_id = (
                        self._new_id()
                    )

                    connection.execute(
                        """
                        INSERT INTO memories (
                            id,
                            memory_key,
                            memory_value,
                            category,
                            importance,
                            source,
                            created_at,
                            updated_at,
                            expires_at,
                            metadata,
                            is_active
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                        """,
                        (
                            memory_id,
                            key,
                            value_json,
                            category,
                            importance,
                            source,
                            now,
                            now,
                            expires_at,
                            metadata_json,
                        ),
                    )

                    event_type = (
                        "created"
                    )

                self._record_event(
                    connection,
                    event_type,
                    memory_id,
                    {
                        "key": key,
                        "category": category,
                    },
                )

                connection.commit()

                logger.info(
                    "Memory %s: %s",
                    event_type,
                    key,
                )

                return memory_id

            finally:
                connection.close()

    # ==================================================================
    # MEMORY READ
    # ==================================================================

    def recall(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Retrieve a memory by exact key.
        """

        key = str(
            key
        ).strip()

        if not key:
            return default

        self.cleanup_expired()

        with self._lock:

            connection = self._connect()

            try:

                row = connection.execute(
                    """
                    SELECT memory_value
                    FROM memories
                    WHERE memory_key = ?
                      AND is_active = 1
                    LIMIT 1
                    """,
                    (key,),
                ).fetchone()

                if row is None:
                    return default

                return self._json_loads(
                    row["memory_value"],
                    default,
                )

            finally:
                connection.close()

    def get_memory(
        self,
        memory_id: str,
    ) -> Optional[
        Dict[str, Any]
    ]:
        """Retrieve a complete memory by ID."""

        with self._lock:

            connection = self._connect()

            try:

                row = connection.execute(
                    """
                    SELECT *
                    FROM memories
                    WHERE id = ?
                    LIMIT 1
                    """,
                    (memory_id,),
                ).fetchone()

                if row is None:
                    return None

                return self._memory_row_to_dict(
                    row
                )

            finally:
                connection.close()

    # ==================================================================
    # MEMORY SEARCH
    # ==================================================================

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[
        Dict[str, Any]
    ]:
        """
        Search memories using SQLite text matching.

        Example:

            memory.search("browser")
        """

        query = str(
            query
        ).strip()

        if not query:
            return []

        limit = max(
            1,
            min(
                100,
                int(limit),
            ),
        )

        self.cleanup_expired()

        pattern = f"%{query}%"

        with self._lock:

            connection = self._connect()

            try:

                if category:

                    rows = connection.execute(
                        """
                        SELECT *
                        FROM memories
                        WHERE is_active = 1
                          AND category = ?
                          AND (
                              memory_key LIKE ?
                              OR memory_value LIKE ?
                          )
                        ORDER BY
                            importance DESC,
                            updated_at DESC
                        LIMIT ?
                        """,
                        (
                            category,
                            pattern,
                            pattern,
                            limit,
                        ),
                    ).fetchall()

                else:

                    rows = connection.execute(
                        """
                        SELECT *
                        FROM memories
                        WHERE is_active = 1
                          AND (
                              memory_key LIKE ?
                              OR memory_value LIKE ?
                              OR category LIKE ?
                          )
                        ORDER BY
                            importance DESC,
                            updated_at DESC
                        LIMIT ?
                        """,
                        (
                            pattern,
                            pattern,
                            pattern,
                            limit,
                        ),
                    ).fetchall()

                return [
                    self._memory_row_to_dict(
                        row
                    )
                    for row in rows
                ]

            finally:
                connection.close()

    # ==================================================================
    # GET ALL MEMORIES
    # ==================================================================

    def get_all_memories(
        self,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> List[
        Dict[str, Any]
    ]:
        """Return stored active memories."""

        limit = max(
            1,
            min(
                1000,
                int(limit),
            ),
        )

        self.cleanup_expired()

        with self._lock:

            connection = self._connect()

            try:

                if category:

                    rows = connection.execute(
                        """
                        SELECT *
                        FROM memories
                        WHERE is_active = 1
                          AND category = ?
                        ORDER BY
                            importance DESC,
                            updated_at DESC
                        LIMIT ?
                        """,
                        (
                            category,
                            limit,
                        ),
                    ).fetchall()

                else:

                    rows = connection.execute(
                        """
                        SELECT *
                        FROM memories
                        WHERE is_active = 1
                        ORDER BY
                            importance DESC,
                            updated_at DESC
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()

                return [
                    self._memory_row_to_dict(
                        row
                    )
                    for row in rows
                ]

            finally:
                connection.close()

    # ==================================================================
    # MEMORY DELETE
    # ==================================================================

    def forget(
        self,
        key: str,
    ) -> bool:
        """
        Delete/deactivate a memory by key.
        """

        key = str(
            key
        ).strip()

        if not key:
            return False

        with self._lock:

            connection = self._connect()

            try:

                row = connection.execute(
                    """
                    SELECT id
                    FROM memories
                    WHERE memory_key = ?
                      AND is_active = 1
                    LIMIT 1
                    """,
                    (key,),
                ).fetchone()

                if row is None:
                    return False

                memory_id = row[
                    "id"
                ]

                connection.execute(
                    """
                    UPDATE memories
                    SET is_active = 0,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        self._now(),
                        memory_id,
                    ),
                )

                self._record_event(
                    connection,
                    "deleted",
                    memory_id,
                    {
                        "key": key
                    },
                )

                connection.commit()

                logger.info(
                    "Memory forgotten: %s",
                    key,
                )

                return True

            finally:
                connection.close()

    def forget_by_id(
        self,
        memory_id: str,
    ) -> bool:
        """Delete/deactivate a memory by ID."""

        with self._lock:

            connection = self._connect()

            try:

                cursor = connection.execute(
                    """
                    UPDATE memories
                    SET is_active = 0,
                        updated_at = ?
                    WHERE id = ?
                      AND is_active = 1
                    """,
                    (
                        self._now(),
                        memory_id,
                    ),
                )

                if cursor.rowcount == 0:
                    connection.rollback()
                    return False

                self._record_event(
                    connection,
                    "deleted",
                    memory_id,
                    {},
                )

                connection.commit()

                return True

            finally:
                connection.close()

    def clear_all(
        self,
        category: Optional[str] = None,
    ) -> int:
        """
        Deactivate all memories.

        Returns number of memories removed.

        This method only affects memory records.
        Conversation history is preserved.
        """

        with self._lock:

            connection = self._connect()

            try:

                if category:

                    cursor = connection.execute(
                        """
                        UPDATE memories
                        SET is_active = 0,
                            updated_at = ?
                        WHERE category = ?
                          AND is_active = 1
                        """,
                        (
                            self._now(),
                            category,
                        ),
                    )

                else:

                    cursor = connection.execute(
                        """
                        UPDATE memories
                        SET is_active = 0,
                            updated_at = ?
                        WHERE is_active = 1
                        """,
                        (
                            self._now(),
                        ),
                    )

                count = cursor.rowcount

                self._record_event(
                    connection,
                    "clear",
                    None,
                    {
                        "category": category,
                        "count": count,
                    },
                )

                connection.commit()

                return count

            finally:
                connection.close()

    # ==================================================================
    # CONVERSATION MEMORY
    # ==================================================================

    def store_conversation(
        self,
        role: str,
        content: str,
        session_id: Optional[str] = None,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ) -> str:
        """
        Store a conversation message.

        Roles normally include:
            user
            assistant
            system
        """

        role = str(
            role
        ).strip().lower()

        content = str(
            content
        ).strip()

        if not content:
            raise ValueError(
                "Conversation content "
                "cannot be empty."
            )

        if not role:
            role = "user"

        message_id = (
            self._new_id()
        )

        now = self._now()

        with self._lock:

            connection = self._connect()

            try:

                connection.execute(
                    """
                    INSERT INTO conversations (
                        id,
                        role,
                        content,
                        session_id,
                        created_at,
                        metadata
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        message_id,
                        role,
                        content,
                        session_id,
                        now,
                        self._json_dumps(
                            metadata or {}
                        ),
                    ),
                )

                connection.commit()

                return message_id

            finally:
                connection.close()

    def get_conversation(
        self,
        session_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[
        Dict[str, Any]
    ]:
        """Return recent conversation messages."""

        limit = max(
            1,
            min(
                500,
                int(limit),
            ),
        )

        with self._lock:

            connection = self._connect()

            try:

                if session_id:

                    rows = connection.execute(
                        """
                        SELECT *
                        FROM conversations
                        WHERE session_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                        """,
                        (
                            session_id,
                            limit,
                        ),
                    ).fetchall()

                else:

                    rows = connection.execute(
                        """
                        SELECT *
                        FROM conversations
                        ORDER BY created_at DESC
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()

                rows = list(
                    reversed(rows)
                )

                return [
                    {
                        "id": row["id"],
                        "role": row["role"],
                        "content": row[
                            "content"
                        ],
                        "session_id": row[
                            "session_id"
                        ],
                        "created_at": row[
                            "created_at"
                        ],
                        "metadata": (
                            self._json_loads(
                                row["metadata"],
                                {},
                            )
                        ),
                    }
                    for row in rows
                ]

            finally:
                connection.close()

    # ==================================================================
    # SHORT-TERM MEMORY
    # ==================================================================

    def add_short_term(
        self,
        content: str,
        role: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ) -> str:
        """
        Add an item to short-term memory.

        Old entries are automatically removed
        when the configured limit is exceeded.
        """

        content = str(
            content
        ).strip()

        if not content:
            raise ValueError(
                "Short-term memory content "
                "cannot be empty."
            )

        item_id = (
            self._new_id()
        )

        with self._lock:

            connection = self._connect()

            try:

                connection.execute(
                    """
                    INSERT INTO short_term_memory (
                        id,
                        content,
                        role,
                        session_id,
                        created_at,
                        metadata
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item_id,
                        content,
                        role,
                        session_id,
                        self._now(),
                        self._json_dumps(
                            metadata or {}
                        ),
                    ),
                )

                # Keep only newest entries.
                connection.execute(
                    """
                    DELETE FROM short_term_memory
                    WHERE id NOT IN (
                        SELECT id
                        FROM short_term_memory
                        ORDER BY created_at DESC
                        LIMIT ?
                    )
                    """,
                    (
                        self.max_short_term,
                    ),
                )

                connection.commit()

                return item_id

            finally:
                connection.close()

    def get_short_term(
        self,
        limit: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> List[
        Dict[str, Any]
    ]:
        """Return recent short-term memories."""

        if limit is None:
            limit = self.max_short_term

        limit = max(
            1,
            min(
                500,
                int(limit),
            ),
        )

        with self._lock:

            connection = self._connect()

            try:

                if session_id:

                    rows = connection.execute(
                        """
                        SELECT *
                        FROM short_term_memory
                        WHERE session_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                        """,
                        (
                            session_id,
                            limit,
                        ),
                    ).fetchall()

                else:

                    rows = connection.execute(
                        """
                        SELECT *
                        FROM short_term_memory
                        ORDER BY created_at DESC
                        LIMIT ?
                        """,
                        (limit,),
                    ).fetchall()

                rows = list(
                    reversed(rows)
                )

                return [
                    {
                        "id": row["id"],
                        "content": row[
                            "content"
                        ],
                        "role": row["role"],
                        "session_id": row[
                            "session_id"
                        ],
                        "created_at": row[
                            "created_at"
                        ],
                        "metadata": (
                            self._json_loads(
                                row["metadata"],
                                {},
                            )
                        ),
                    }
                    for row in rows
                ]

            finally:
                connection.close()

    def clear_short_term(
        self,
        session_id: Optional[str] = None,
    ) -> int:
        """Clear short-term memory."""

        with self._lock:

            connection = self._connect()

            try:

                if session_id:

                    cursor = connection.execute(
                        """
                        DELETE FROM
                        short_term_memory
                        WHERE session_id = ?
                        """,
                        (session_id,),
                    )

                else:

                    cursor = connection.execute(
                        """
                        DELETE FROM
                        short_term_memory
                        """
                    )

                count = cursor.rowcount

                connection.commit()

                return count

            finally:
                connection.close()

    # ==================================================================
    # COMBINED CONTEXT
    # ==================================================================

    def get_context(
        self,
        query: Optional[str] = None,
        session_id: Optional[str] = None,
        memory_limit: int = 10,
        conversation_limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Build a context package for the AI brain.
        """

        if query:

            relevant_memories = self.search(
                query,
                limit=memory_limit,
            )

        else:

            relevant_memories = (
                self.get_all_memories(
                    limit=memory_limit
                )
            )

        conversation = (
            self.get_conversation(
                session_id=session_id,
                limit=conversation_limit,
            )
        )

        short_term = (
            self.get_short_term(
                session_id=session_id,
                limit=self.max_short_term,
            )
        )

        return {
            "memories": relevant_memories,
            "conversation": conversation,
            "short_term": short_term,
        }

    # ==================================================================
    # EXPIRATION
    # ==================================================================

    def cleanup_expired(self) -> int:
        """
        Deactivate expired memories.

        Returns number of expired records.
        """

        now = self._now()

        with self._lock:

            connection = self._connect()

            try:

                cursor = connection.execute(
                    """
                    UPDATE memories
                    SET is_active = 0,
                        updated_at = ?
                    WHERE is_active = 1
                      AND expires_at IS NOT NULL
                      AND expires_at <= ?
                    """,
                    (
                        now,
                        now,
                    ),
                )

                count = cursor.rowcount

                if count:

                    self._record_event(
                        connection,
                        "expiration_cleanup",
                        None,
                        {
                            "count": count
                        },
                    )

                connection.commit()

                return count

            finally:
                connection.close()

    # ==================================================================
    # EVENTS
    # ==================================================================

    def _record_event(
        self,
        connection: sqlite3.Connection,
        event_type: str,
        memory_id: Optional[str],
        details: Dict[str, Any],
    ) -> None:
        """Record a memory event."""

        connection.execute(
            """
            INSERT INTO memory_events (
                id,
                event_type,
                memory_id,
                details,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                self._new_id(),
                event_type,
                memory_id,
                self._json_dumps(
                    details
                ),
                self._now(),
            ),
        )

    def get_events(
        self,
        limit: int = 50,
    ) -> List[
        Dict[str, Any]
    ]:
        """Return recent memory events."""

        limit = max(
            1,
            min(
                500,
                int(limit),
            ),
        )

        with self._lock:

            connection = self._connect()

            try:

                rows = connection.execute(
                    """
                    SELECT *
                    FROM memory_events
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

                return [
                    {
                        "id": row["id"],
                        "event_type": row[
                            "event_type"
                        ],
                        "memory_id": row[
                            "memory_id"
                        ],
                        "details": (
                            self._json_loads(
                                row["details"],
                                {},
                            )
                        ),
                        "created_at": row[
                            "created_at"
                        ],
                    }
                    for row in rows
                ]

            finally:
                connection.close()

    # ==================================================================
    # INTERNAL CONVERSION
    # ==================================================================

    def _memory_row_to_dict(
        self,
        row: sqlite3.Row,
    ) -> Dict[str, Any]:
        """Convert SQLite memory row to dictionary."""

        return {
            "id": row["id"],
            "key": row[
                "memory_key"
            ],
            "value": self._json_loads(
                row["memory_value"]
            ),
            "category": row[
                "category"
            ],
            "importance": row[
                "importance"
            ],
            "source": row[
                "source"
            ],
            "created_at": row[
                "created_at"
            ],
            "updated_at": row[
                "updated_at"
            ],
            "expires_at": row[
                "expires_at"
            ],
            "metadata": (
                self._json_loads(
                    row["metadata"],
                    {},
                )
            ),
            "is_active": bool(
                row["is_active"]
            ),
        }

    # ==================================================================
    # STATISTICS
    # ==================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Return memory database statistics."""

        with self._lock:

            connection = self._connect()

            try:

                memories = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM memories
                    WHERE is_active = 1
                    """
                ).fetchone()[0]

                conversations = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM conversations
                    """
                ).fetchone()[0]

                short_term = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM short_term_memory
                    """
                ).fetchone()[0]

                categories = connection.execute(
                    """
                    SELECT category, COUNT(*) AS count
                    FROM memories
                    WHERE is_active = 1
                    GROUP BY category
                    ORDER BY count DESC
                    """
                ).fetchall()

                return {
                    "database": str(
                        self.db_path
                    ),
                    "active_memories": memories,
                    "conversations": conversations,
                    "short_term_items": short_term,
                    "max_short_term": (
                        self.max_short_term
                    ),
                    "categories": {
                        row["category"]: row[
                            "count"
                        ]
                        for row in categories
                    },
                }

            finally:
                connection.close()

    # ==================================================================
    # COMPATIBILITY HELPERS
    # ==================================================================

    def add_memory(
        self,
        key: str,
        value: Any,
        **kwargs: Any,
    ) -> str:
        """
        Compatibility alias for remember().
        """

        return self.remember(
            key,
            value,
            **kwargs,
        )

    def get_memory_by_key(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Compatibility alias for recall().
        """

        return self.recall(
            key,
            default,
        )

    def delete_memory(
        self,
        key: str,
    ) -> bool:
        """
        Compatibility alias for forget().
        """

        return self.forget(key)

    # ==================================================================
    # CLOSE
    # ==================================================================

    def close(self) -> None:
        """
        Close method kept for compatibility.

        Connections are opened and closed per operation,
        so there is no persistent database connection.
        """

        logger.info(
            "MemoryManager closed."
        )

    def __enter__(
        self,
    ) -> "MemoryManager":

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
    print("JARVIS OS - MEMORY MANAGER TEST")
    print("=" * 70)

    # Use a temporary test database beside this file.
    test_database = (
        Path(__file__).resolve()
        / "memory_test.db"
    )

    # Remove old test database.
    if test_database.exists():

        try:
            test_database.unlink()

        except OSError:
            pass

    memory = MemoryManager(
        db_path=test_database
    )

    # --------------------------------------------------------------
    # Long-term memory
    # --------------------------------------------------------------

    print()
    print("1. Saving memory...")

    memory_id = memory.remember(
        key="favorite_browser",
        value="Chrome",
        category="preference",
        importance=8,
    )

    print(
        "Memory ID:",
        memory_id,
    )

    # --------------------------------------------------------------
    # Read memory
    # --------------------------------------------------------------

    print()
    print("2. Reading memory...")

    value = memory.recall(
        "favorite_browser"
    )

    print(
        "Favorite browser:",
        value,
    )

    # --------------------------------------------------------------
    # Search
    # --------------------------------------------------------------

    print()
    print("3. Searching memory...")

    results = memory.search(
        "browser"
    )

    for item in results:

        print(
            item["key"],
            "=>",
            item["value"],
        )

    # --------------------------------------------------------------
    # Conversation
    # --------------------------------------------------------------

    print()
    print("4. Saving conversation...")

    session_id = (
        "test-session"
    )

    memory.store_conversation(
        role="user",
        content="Hello Jarvis",
        session_id=session_id,
    )

    memory.store_conversation(
        role="assistant",
        content="Hello! How can I help you?",
        session_id=session_id,
    )

    conversation = (
        memory.get_conversation(
            session_id=session_id
        )
    )

    for message in conversation:

        print(
            f'{message["role"]}: '
            f'{message["content"]}'
        )

    # --------------------------------------------------------------
    # Short-term memory
    # --------------------------------------------------------------

    print()
    print("5. Short-term memory...")

    memory.add_short_term(
        "User wants JarvisOS to respond by voice.",
        role="user",
        session_id=session_id,
    )

    short_term = (
        memory.get_short_term(
            session_id=session_id
        )
    )

    for item in short_term:

        print(
            item["content"]
        )

    # --------------------------------------------------------------
    # Context
    # --------------------------------------------------------------

    print()
    print("6. Building AI context...")

    context = memory.get_context(
        query="browser",
        session_id=session_id,
    )

    print(
        "Memories:",
        len(
            context["memories"]
        ),
    )

    print(
        "Conversation:",
        len(
            context["conversation"]
        ),
    )

    print(
        "Short-term:",
        len(
            context["short_term"]
        ),
    )

    # --------------------------------------------------------------
    # Statistics
    # --------------------------------------------------------------

    print()
    print("7. Statistics...")

    stats = memory.get_stats()

    for key, value in stats.items():

        print(
            f"{key}: {value}"
        )

    # --------------------------------------------------------------
    # Delete
    # --------------------------------------------------------------

    print()
    print("8. Forgetting memory...")

    deleted = memory.forget(
        "favorite_browser"
    )

    print(
        "Deleted:",
        deleted,
    )

    print(
        "After deletion:",
        memory.recall(
            "favorite_browser",
            "Not found",
        ),
    )

    # --------------------------------------------------------------
    # Cleanup test DB
    # --------------------------------------------------------------

    memory.close()

    try:
        if test_database.exists():
            test_database.unlink()

    except OSError:
        pass

    print()
    print("=" * 70)
    print("MEMORY MANAGER TEST COMPLETE")
    print("=" * 70)
