"""
JarvisOS - Memory Search

Advanced search layer for JarvisOS memory.

Responsibilities:
    - Search long-term memory
    - Search short-term memory
    - Search conversation history
    - Rank relevant memories
    - Filter by category
    - Filter by importance
    - Build AI-ready context
    - Return clean search results

This module does not modify memory unless explicitly requested.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
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
class MemorySearchResult:
    """One search result."""

    source: str
    content: str
    score: float
    memory_id: Optional[str] = None
    key: Optional[str] = None
    category: Optional[str] = None
    importance: int = 0
    role: Optional[str] = None
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert search result to dictionary."""

        return {
            "source": self.source,
            "content": self.content,
            "score": self.score,
            "memory_id": self.memory_id,
            "key": self.key,
            "category": self.category,
            "importance": self.importance,
            "role": self.role,
            "metadata": self.metadata,
        }


# ======================================================================
# MEMORY SEARCH ENGINE
# ======================================================================


class MemorySearch:
    """
    Search engine for JarvisOS memory.

    The search system uses lightweight local ranking so that
    it works without an external vector database.

    Ranking considers:

        - Exact key match
        - Exact phrase match
        - Individual word matches
        - Category match
        - Importance
        - Recency
    """

    STOP_WORDS = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "am",
        "to",
        "of",
        "in",
        "on",
        "for",
        "and",
        "or",
        "with",
        "my",
        "me",
        "i",
        "you",
        "hai",
        "h",
        "ka",
        "ki",
        "ke",
        "ko",
        "se",
        "mein",
        "mujhe",
        "mera",
        "meri",
        "mere",
        "karo",
        "karna",
        "please",
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
            "MemorySearch initialized."
        )

    # ==================================================================
    # MAIN SEARCH
    # ==================================================================

    def search(
        self,
        query: str,
        limit: int = 10,
        category: Optional[str] = None,
        minimum_importance: int = 0,
        include_short_term: bool = True,
        include_conversation: bool = True,
        session_id: Optional[str] = None,
    ) -> List[
        MemorySearchResult
    ]:
        """
        Search all available memory sources.

        Args:
            query:
                Text to search.

            limit:
                Maximum number of results.

            category:
                Optional long-term memory category.

            minimum_importance:
                Ignore long-term memories below this value.

            include_short_term:
                Search current temporary memory.

            include_conversation:
                Search conversation history.

            session_id:
                Optional conversation/session filter.
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

        minimum_importance = max(
            0,
            min(
                10,
                int(
                    minimum_importance
                ),
            ),
        )

        tokens = self._tokenize(
            query
        )

        results: List[
            MemorySearchResult
        ] = []

        # --------------------------------------------------------------
        # Long-term memory
        # --------------------------------------------------------------

        long_term = (
            self._search_long_term(
                query=query,
                tokens=tokens,
                category=category,
                minimum_importance=(
                    minimum_importance
                ),
            )
        )

        results.extend(
            long_term
        )

        # --------------------------------------------------------------
        # Short-term memory
        # --------------------------------------------------------------

        if include_short_term:

            short_term = (
                self._search_short_term(
                    query=query,
                    tokens=tokens,
                    session_id=session_id,
                )
            )

            results.extend(
                short_term
            )

        # --------------------------------------------------------------
        # Conversation
        # --------------------------------------------------------------

        if include_conversation:

            conversation = (
                self._search_conversation(
                    query=query,
                    tokens=tokens,
                    session_id=session_id,
                )
            )

            results.extend(
                conversation
            )

        # --------------------------------------------------------------
        # Sort and return
        # --------------------------------------------------------------

        results.sort(
            key=lambda item: item.score,
            reverse=True,
        )

        return results[
            :limit
        ]

    # ==================================================================
    # LONG TERM SEARCH
    # ==================================================================

    def _search_long_term(
        self,
        query: str,
        tokens: List[str],
        category: Optional[str],
        minimum_importance: int,
    ) -> List[
        MemorySearchResult
    ]:

        records = (
            self.memory_manager
            .get_all_memories(
                category=category,
                limit=1000,
            )
        )

        results = []

        for record in records:

            importance = int(
                record.get(
                    "importance",
                    0,
                )
            )

            if (
                importance
                < minimum_importance
            ):
                continue

            key = str(
                record.get(
                    "key",
                    "",
                )
            )

            value = self._stringify(
                record.get(
                    "value"
                )
            )

            memory_category = str(
                record.get(
                    "category",
                    "",
                )
            )

            searchable = (
                f"{key} "
                f"{value} "
                f"{memory_category}"
            ).lower()

            score = self._calculate_score(
                query=query,
                tokens=tokens,
                text=searchable,
                key=key,
                category=memory_category,
                importance=importance,
                updated_at=record.get(
                    "updated_at"
                ),
            )

            if score <= 0:
                continue

            results.append(
                MemorySearchResult(
                    source="long_term",
                    content=(
                        f"{key}: {value}"
                    ),
                    score=score,
                    memory_id=record.get(
                        "id"
                    ),
                    key=key,
                    category=memory_category,
                    importance=importance,
                    metadata=record.get(
                        "metadata",
                        {},
                    ),
                )
            )

        return results

    # ==================================================================
    # SHORT TERM SEARCH
    # ==================================================================

    def _search_short_term(
        self,
        query: str,
        tokens: List[str],
        session_id: Optional[str],
    ) -> List[
        MemorySearchResult
    ]:

        records = (
            self.memory_manager
            .get_short_term(
                limit=500,
                session_id=session_id,
            )
        )

        results = []

        for record in records:

            content = str(
                record.get(
                    "content",
                    "",
                )
            )

            score = self._calculate_score(
                query=query,
                tokens=tokens,
                text=content,
                importance=5,
                updated_at=record.get(
                    "created_at"
                ),
            )

            if score <= 0:
                continue

            results.append(
                MemorySearchResult(
                    source="short_term",
                    content=content,
                    score=score,
                    memory_id=record.get(
                        "id"
                    ),
                    role=record.get(
                        "role"
                    ),
                    metadata=record.get(
                        "metadata",
                        {},
                    ),
                )
            )

        return results

    # ==================================================================
    # CONVERSATION SEARCH
    # ==================================================================

    def _search_conversation(
        self,
        query: str,
        tokens: List[str],
        session_id: Optional[str],
    ) -> List[
        MemorySearchResult
    ]:

        records = (
            self.memory_manager
            .get_conversation(
                session_id=session_id,
                limit=500,
            )
        )

        results = []

        for record in records:

            content = str(
                record.get(
                    "content",
                    "",
                )
            )

            score = self._calculate_score(
                query=query,
                tokens=tokens,
                text=content,
                importance=3,
                updated_at=record.get(
                    "created_at"
                ),
            )

            if score <= 0:
                continue

            results.append(
                MemorySearchResult(
                    source="conversation",
                    content=content,
                    score=score,
                    memory_id=record.get(
                        "id"
                    ),
                    role=record.get(
                        "role"
                    ),
                    metadata=record.get(
                        "metadata",
                        {},
                    ),
                )
            )

        return results

    # ==================================================================
    # RANKING
    # ==================================================================

    def _calculate_score(
        self,
        query: str,
        tokens: List[str],
        text: str,
        key: str = "",
        category: str = "",
        importance: int = 0,
        updated_at: Optional[float] = None,
    ) -> float:
        """Calculate relevance score."""

        if not text:
            return 0.0

        query_lower = query.lower().strip()
        text_lower = text.lower()

        score = 0.0

        # --------------------------------------------------------------
        # Exact phrase
        # --------------------------------------------------------------

        if query_lower in text_lower:

            score += 50.0

        # --------------------------------------------------------------
        # Exact key
        # --------------------------------------------------------------

        if key:

            key_lower = key.lower()

            if query_lower == key_lower:

                score += 80.0

            elif query_lower in key_lower:

                score += 30.0

        # --------------------------------------------------------------
        # Token matching
        # --------------------------------------------------------------

        if tokens:

            matched = 0

            for token in tokens:

                if token in text_lower:

                    matched += 1

            ratio = (
                matched
                / len(tokens)
            )

            score += (
                ratio * 40.0
            )

        # --------------------------------------------------------------
        # Category
        # --------------------------------------------------------------

        if category:

            category_lower = (
                category.lower()
            )

            if query_lower == category_lower:

                score += 20.0

            elif query_lower in category_lower:

                score += 10.0

        # --------------------------------------------------------------
        # Importance
        # --------------------------------------------------------------

        if importance:

            score += (
                float(importance)
                * 1.5
            )

        # --------------------------------------------------------------
        # Recency
        # --------------------------------------------------------------

        if updated_at:

            age_days = max(
                0.0,
                (
                    __import__(
                        "time"
                    ).time()
                    - float(
                        updated_at
                    )
                )
                / 86400.0,
            )

            if age_days < 1:

                score += 10.0

            elif age_days < 7:

                score += 6.0

            elif age_days < 30:

                score += 3.0

        return round(
            score,
            3,
        )

    # ==================================================================
    # TOKENIZATION
    # ==================================================================

    def _tokenize(
        self,
        text: str,
    ) -> List[str]:
        """Convert query into searchable words."""

        text = text.lower()

        words = re.findall(
            r"[a-zA-Z0-9\u0900-\u097F]+",
            text,
        )

        tokens = []

        for word in words:

            word = word.strip()

            if not word:
                continue

            if word in self.STOP_WORDS:
                continue

            if len(word) < 2:
                continue

            if word not in tokens:

                tokens.append(
                    word
                )

        return tokens

    # ==================================================================
    # SPECIALIZED SEARCH
    # ==================================================================

    def search_preferences(
        self,
        query: str,
        limit: int = 10,
    ) -> List[
        MemorySearchResult
    ]:
        """Search user preferences."""

        return self.search(
            query=query,
            limit=limit,
            category="preference",
            include_short_term=False,
            include_conversation=False,
        )

    def search_projects(
        self,
        query: str,
        limit: int = 10,
    ) -> List[
        MemorySearchResult
    ]:
        """Search project memories."""

        return self.search(
            query=query,
            limit=limit,
            category="project",
            include_short_term=False,
            include_conversation=False,
        )

    def search_current_session(
        self,
        query: str,
        session_id: str,
        limit: int = 10,
    ) -> List[
        MemorySearchResult
    ]:
        """Search only the current session."""

        return self.search(
            query=query,
            limit=limit,
            include_short_term=True,
            include_conversation=True,
            session_id=session_id,
        )

    # ==================================================================
    # BEST MEMORY
    # ==================================================================

    def best_match(
        self,
        query: str,
        **kwargs,
    ) -> Optional[
        MemorySearchResult
    ]:
        """Return the highest-ranked result."""

        results = self.search(
            query=query,
            limit=1,
            **kwargs,
        )

        if not results:
            return None

        return results[0]

    # ==================================================================
    # AI CONTEXT
    # ==================================================================

    def build_context(
        self,
        query: str,
        limit: int = 8,
        max_characters: int = 5000,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Build compact memory context for AI.

        The returned text is intentionally limited in size so
        large memory databases do not overwhelm the AI prompt.
        """

        results = self.search(
            query=query,
            limit=limit,
            session_id=session_id,
        )

        if not results:

            return (
                "No relevant memory found."
            )

        lines = [
            "Relevant JarvisOS memory:"
        ]

        current_length = len(
            lines[0]
        )

        for index, result in enumerate(
            results,
            start=1,
        ):

            source = result.source

            line = (
                f"{index}. "
                f"[{source}] "
                f"{result.content}"
            )

            if (
                current_length
                + len(line)
                + 1
                > max_characters
            ):
                break

            lines.append(
                line
            )

            current_length += (
                len(line)
                + 1
            )

        return "\n".join(
            lines
        )

    # ==================================================================
    # CONTEXT OBJECT
    # ==================================================================

    def build_context_data(
        self,
        query: str,
        limit: int = 8,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return structured AI context."""

        results = self.search(
            query=query,
            limit=limit,
            session_id=session_id,
        )

        return {
            "query": query,
            "count": len(results),
            "results": [
                result.to_dict()
                for result in results
            ],
        }

    # ==================================================================
    # STRING HELPERS
    # ==================================================================

    @staticmethod
    def _stringify(
        value: Any,
    ) -> str:
        """Convert any value to searchable text."""

        if isinstance(
            value,
            dict,
        ):

            return " ".join(
                f"{key} {value}"
                for key, value in value.items()
            )

        if isinstance(
            value,
            (list, tuple, set),
        ):

            return " ".join(
                str(item)
                for item in value
            )

        return str(
            value
        )

    # ==================================================================
    # STATUS
    # ==================================================================

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """Return search engine status."""

        try:

            stats = (
                self.memory_manager.get_stats()
            )

        except Exception as exc:

            logger.error(
                "Could not get memory stats: %s",
                exc,
            )

            stats = {}

        return {
            "engine": "local_ranked_search",
            "database": stats.get(
                "database"
            ),
            "active_memories": stats.get(
                "active_memories",
                0,
            ),
            "conversation_items": stats.get(
                "conversations",
                0,
            ),
            "short_term_items": stats.get(
                "short_term_items",
                0,
            ),
        }

    # ==================================================================
    # CLOSE
    # ==================================================================

    def close(self) -> None:
        """Close memory manager."""

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
            "MemorySearch closed."
        )


# ======================================================================
# DIRECT TEST
# ======================================================================


if __name__ == "__main__":

    import os

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
    print("JARVIS OS - MEMORY SEARCH TEST")
    print("=" * 70)

    test_db = (
        "memory_search_test.db"
    )

    memory = MemoryManager(
        db_path=test_db
    )

    search_engine = MemorySearch(
        memory_manager=memory
    )

    # --------------------------------------------------------------
    # Add test memories
    # --------------------------------------------------------------

    print()
    print("1. Creating test memories...")

    memory.remember(
        key="favorite_browser",
        value="Google Chrome",
        category="preference",
        importance=9,
    )

    memory.remember(
        key="current_project",
        value="JarvisOS AI Assistant",
        category="project",
        importance=10,
    )

    memory.remember(
        key="preferred_language",
        value="Hindi and Hinglish",
        category="preference",
        importance=8,
    )

    memory.add_short_term(
        "User wants JarvisOS to respond by voice.",
        role="user",
        session_id="test-session",
    )

    memory.store_conversation(
        role="user",
        content="JarvisOS mein voice control chahiye.",
        session_id="test-session",
    )

    # --------------------------------------------------------------
    # Search
    # --------------------------------------------------------------

    print()
    print("2. Searching for browser...")

    results = search_engine.search(
        "browser",
        limit=5,
    )

    for result in results:

        print(
            f"[{result.source}] "
            f"{result.content} "
            f"(score={result.score})"
        )

    # --------------------------------------------------------------
    # Project search
    # --------------------------------------------------------------

    print()
    print("3. Searching projects...")

    results = (
        search_engine.search_projects(
            "Jarvis"
        )
    )

    for result in results:

        print(
            result.content,
            "score=",
            result.score,
        )

    # --------------------------------------------------------------
    # Session search
    # --------------------------------------------------------------

    print()
    print("4. Searching current session...")

    results = (
        search_engine.search_current_session(
            "voice",
            session_id="test-session",
        )
    )

    for result in results:

        print(
            f"[{result.source}] "
            f"{result.content}"
        )

    # --------------------------------------------------------------
    # AI context
    # --------------------------------------------------------------

    print()
    print("5. AI context:")

    print(
        search_engine.build_context(
            "JarvisOS voice"
        )
    )

    # --------------------------------------------------------------
    # Best result
    # --------------------------------------------------------------

    print()
    print("6. Best match:")

    best = (
        search_engine.best_match(
            "favorite browser"
        )
    )

    if best:

        print(
            best.to_dict()
        )

    # --------------------------------------------------------------
    # Status
    # --------------------------------------------------------------

    print()
    print("7. Status:")

    print(
        search_engine.get_status()
    )

    search_engine.close()

    # --------------------------------------------------------------
    # Remove test database
    # --------------------------------------------------------------

    try:

        if os.path.exists(
            test_db
        ):
            os.remove(
                test_db
            )

        # SQLite WAL/SHM files can exist.
        for suffix in (
            "-wal",
            "-shm",
        ):

            extra = (
                test_db
                + suffix
            )

            if os.path.exists(
                extra
            ):

                os.remove(
                    extra
                )

    except OSError:
        pass

    print()
    print("=" * 70)
    print("MEMORY SEARCH TEST COMPLETE")
    print("=" * 70)
