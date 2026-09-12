memory/memory_search.py

"""
JarvisOS - Memory Search

Unified memory search layer.

Searches:

- Long-term memories
- Short-term session memory
- Conversation history

Features:

- Keyword search
- Category filtering
- Importance filtering
- Relevance scoring
- Result ranking
- Pagination
- Unified context search
- Safe read-only operations
  """

from future import annotations

import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Optional

try:
from memory.memory_manager import MemoryManager
except ImportError:
MemoryManager = None

try:
from memory.long_term_memory import LongTermMemory
except ImportError:
LongTermMemory = None

try:
from memory.short_term_memory import ShortTermMemory
except ImportError:
ShortTermMemory = None

logger = logging.getLogger(
"JarvisOS.MemorySearch"
)

============================================================

DATA CLASS

============================================================

@dataclass
class MemorySearchResult:
"""
One unified memory search result.
"""

source: str
memory_id: Any = None
key: str = ""
value: str = ""
category: str = ""
importance: int = 0
score: float = 0.0
timestamp: str = ""
metadata: Optional[dict[str, Any]] = None

def to_dict(self) -> dict[str, Any]:
    return asdict(self)

============================================================

SEARCH SERVICE

============================================================

class MemorySearch:
"""
Unified search service for JarvisOS memory.
"""

def __init__(
    self,
    memory_manager: Optional[Any] = None,
    long_term_memory: Optional[Any] = None,
    short_term_memory: Optional[Any] = None,
) -> None:

    self.memory_manager = (
        memory_manager
        if memory_manager is not None
        else (
            MemoryManager()
            if MemoryManager is not None
            else None
        )
    )

    self.long_term_memory = (
        long_term_memory
    )

    if (
        self.long_term_memory is None
        and LongTermMemory is not None
        and self.memory_manager is not None
    ):

        try:

            self.long_term_memory = (
                LongTermMemory(
                    memory_manager=(
                        self.memory_manager
                    )
                )
            )

        except TypeError:

            try:

                self.long_term_memory = (
                    LongTermMemory(
                        self.memory_manager
                    )
                )

            except Exception:

                self.long_term_memory = None

        except Exception:

            self.long_term_memory = None

    self.short_term_memory = (
        short_term_memory
    )

    if (
        self.short_term_memory is None
        and ShortTermMemory is not None
        and self.memory_manager is not None
    ):

        try:

            self.short_term_memory = (
                ShortTermMemory(
                    memory_manager=(
                        self.memory_manager
                    )
                )
            )

        except Exception:

            self.short_term_memory = None

    self.history: list[
        dict[str, Any]
    ] = []

# ========================================================
# NORMALIZATION
# ========================================================

@staticmethod
def _normalize(
    value: Any,
) -> str:

    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()

@staticmethod
def _tokens(
    text: str,
) -> list[str]:

    text = (
        str(text)
        .lower()
    )

    return re.findall(
        r"[a-zA-Z0-9\u0900-\u097F]+",
        text,
    )

# ========================================================
# SCORE
# ========================================================

def _score(
    self,
    query: str,
    key: str,
    value: str,
    category: str = "",
) -> float:

    query = self._normalize(
        query
    ).lower()

    if not query:
        return 0.0

    query_tokens = set(
        self._tokens(
            query
        )
    )

    if not query_tokens:
        return 0.0

    key_text = self._normalize(
        key
    ).lower()

    value_text = self._normalize(
        value
    ).lower()

    category_text = self._normalize(
        category
    ).lower()

    score = 0.0

    # Exact full-text match.
    if query in key_text:

        score += 5.0

    if query in value_text:

        score += 4.0

    if query in category_text:

        score += 2.0

    # Token matches.
    key_tokens = set(
        self._tokens(
            key_text
        )
    )

    value_tokens = set(
        self._tokens(
            value_text
        )
    )

    category_tokens = set(
        self._tokens(
            category_text
        )
    )

    for token in query_tokens:

        if token in key_tokens:
            score += 3.0

        if token in value_tokens:
            score += 2.0

        if token in category_tokens:
            score += 1.0

    # Small bonus for matching multiple query terms.
    all_text = " ".join(
        [
            key_text,
            value_text,
            category_text,
        ]
    )

    matched = sum(
        1
        for token in query_tokens
        if token in all_text
    )

    if matched:

        score += (
            matched
            / len(query_tokens)
        )

    return round(
        score,
        4,
    )

# ========================================================
# MEMORY MANAGER SEARCH
# ========================================================

def _search_memory_manager(
    self,
    query: str,
    category: Optional[str],
    limit: int,
) -> list[MemorySearchResult]:

    if self.memory_manager is None:
        return []

    results: list[
        MemorySearchResult
    ] = []

    # Prefer the MemoryManager's native search.
    try:

        if hasattr(
            self.memory_manager,
            "search",
        ):

            raw = self.memory_manager.search(
                query
            )

            if raw is None:
                raw = []

            for item in raw:

                result = self._convert_item(
                    item,
                    source="long_term",
                    query=query,
                )

                if result is None:
                    continue

                if (
                    category
                    and result.category.lower()
                    != category.lower()
                ):

                    continue

                results.append(
                    result
                )

    except Exception as exc:

        logger.debug(
            "MemoryManager.search failed: %s",
            exc,
        )

    # If native search returned nothing, inspect all
    # memories as a compatibility fallback.
    if not results:

        try:

            if hasattr(
                self.memory_manager,
                "get_all_memories",
            ):

                raw_items = (
                    self.memory_manager
                    .get_all_memories()
                )

            elif hasattr(
                self.memory_manager,
                "get_memory",
            ):

                raw_items = []

            else:

                raw_items = []

            if raw_items:

                for item in raw_items:

                    result = (
                        self._convert_item(
                            item,
                            source="long_term",
                            query=query,
                        )
                    )

                    if result is None:
                        continue

                    if (
                        category
                        and result.category.lower()
                        != category.lower()
                    ):

                        continue

                    if result.score > 0:

                        results.append(
                            result
                        )

        except Exception as exc:

            logger.debug(
                "Memory fallback search failed: %s",
                exc,
            )

    return results[:limit]

# ========================================================
# LONG TERM SEARCH
# ========================================================

def _search_long_term(
    self,
    query: str,
    category: Optional[str],
    limit: int,
) -> list[MemorySearchResult]:

    if self.long_term_memory is None:
        return []

    results: list[
        MemorySearchResult
    ] = []

    try:

        if hasattr(
            self.long_term_memory,
            "search",
        ):

            raw = (
                self.long_term_memory.search(
                    query
                )
            )

            if raw is None:
                raw = []

            for item in raw:

                result = self._convert_item(
                    item,
                    source="long_term",
                    query=query,
                )

                if result is None:
                    continue

                if (
                    category
                    and result.category.lower()
                    != category.lower()
                ):

                    continue

                results.append(
                    result
                )

    except Exception as exc:

        logger.debug(
            "LongTermMemory search failed: %s",
            exc,
        )

    return results[:limit]

# ========================================================
# SHORT TERM SEARCH
# ========================================================

def _search_short_term(
    self,
    query: str,
    limit: int,
) -> list[MemorySearchResult]:

    if self.short_term_memory is None:
        return []

    results: list[
        MemorySearchResult
    ] = []

    try:

        if hasattr(
            self.short_term_memory,
            "search",
        ):

            raw = (
                self.short_term_memory.search(
                    query
                )
            )

            if raw is None:
                raw = []

            for item in raw:

                result = self._convert_item(
                    item,
                    source="short_term",
                    query=query,
                )

                if result is None:
                    continue

                results.append(
                    result
                )

    except Exception as exc:

        logger.debug(
            "ShortTermMemory search failed: %s",
            exc,
        )

    return results[:limit]

# ========================================================
# CONVERSATION SEARCH
# ========================================================

def _search_conversations(
    self,
    query: str,
    limit: int,
) -> list[MemorySearchResult]:

    if self.memory_manager is None:
        return []

    results: list[
        MemorySearchResult
    ] = []

    raw_items: list[Any] = []

    try:

        if hasattr(
            self.memory_manager,
            "get_conversation",
        ):

            raw = (
                self.memory_manager
                .get_conversation()
            )

            if isinstance(
                raw,
                list,
            ):

                raw_items = raw

    except Exception as exc:

        logger.debug(
            "Conversation retrieval failed: %s",
            exc,
        )

    for item in raw_items:

        if isinstance(
            item,
            dict,
        ):

            user_text = self._normalize(
                item.get(
                    "user",
                    item.get(
                        "user_message",
                        "",
                    ),
                )
            )

            assistant_text = self._normalize(
                item.get(
                    "assistant",
                    item.get(
                        "assistant_message",
                        "",
                    ),
                )
            )

            combined = (
                f"{user_text} "
                f"{assistant_text}"
            )

            score = self._score(
                query,
                "conversation",
                combined,
            )

            if score <= 0:
                continue

            timestamp = self._normalize(
                item.get(
                    "timestamp",
                    item.get(
                        "created_at",
                        "",
                    ),
                )
            )

            results.append(
                MemorySearchResult(
                    source="conversation",
                    memory_id=item.get(
                        "id"
                    ),
                    key="conversation",
                    value=combined,
                    category="conversation",
                    importance=0,
                    score=score,
                    timestamp=timestamp,
                    metadata=item,
                )
            )

    return results[:limit]

# ========================================================
# CONVERT
# ========================================================

def _convert_item(
    self,
    item: Any,
    source: str,
    query: str,
) -> Optional[MemorySearchResult]:

    if isinstance(
        item,
        MemorySearchResult,
    ):

        return item

    if isinstance(
        item,
        dict,
    ):

        memory_id = item.get(
            "id",
            item.get(
                "memory_id"
            ),
        )

        key = self._normalize(
            item.get(
                "key",
                item.get(
                    "name",
                    "",
                ),
            )
        )

        value = self._normalize(
            item.get(
                "value",
                item.get(
                    "content",
                    item.get(
                        "text",
                        item.get(
                            "message",
                            "",
                        ),
                    ),
                ),
            )
        )

        category = self._normalize(
            item.get(
                "category",
                "",
            )
        )

        importance_raw = item.get(
            "importance",
            0,
        )

        try:

            importance = int(
                importance_raw
            )

        except (
            TypeError,
            ValueError,
        ):

            importance = 0

        timestamp = self._normalize(
            item.get(
                "timestamp",
                item.get(
                    "created_at",
                    item.get(
                        "updated_at",
                        "",
                    ),
                ),
            )
        )

        metadata = item.get(
            "metadata"
        )

        score = self._score(
            query,
            key,
            value,
            category,
        )

        return MemorySearchResult(
            source=source,
            memory_id=memory_id,
            key=key,
            value=value,
            category=category,
            importance=importance,
            score=score,
            timestamp=timestamp,
            metadata=(
                metadata
                if isinstance(
                    metadata,
                    dict,
                )
                else item
            ),
        )

    # Dataclass/object compatibility.
    key = self._normalize(
        getattr(
            item,
            "key",
            getattr(
                item,
                "name",
                "",
            ),
        )
    )

    value = self._normalize(
        getattr(
            item,
            "value",
            getattr(
                item,
                "content",
                getattr(
                    item,
                    "text",
                    "",
                ),
            ),
        )
    )

    category = self._normalize(
        getattr(
            item,
            "category",
            "",
        )
    )

    if not key and not value:
        return None

    try:

        importance = int(
            getattr(
                item,
                "importance",
                0,
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        importance = 0

    score = self._score(
        query,
        key,
        value,
        category,
    )

    return MemorySearchResult(
        source=source,
        memory_id=getattr(
            item,
            "id",
            None,
        ),
        key=key,
        value=value,
        category=category,
        importance=importance,
        score=score,
        timestamp=self._normalize(
            getattr(
                item,
                "timestamp",
                "",
            )
        ),
        metadata=None,
    )

# ========================================================
# UNIFIED SEARCH
# ========================================================

def search(
    self,
    query: str,
    category: Optional[str] = None,
    min_importance: Optional[int] = None,
    sources: Optional[list[str]] = None,
    limit: int = 20,
    offset: int = 0,
) -> list[MemorySearchResult]:

    query = self._normalize(
        query
    )

    if not query:
        return []

    try:

        limit = max(
            1,
            min(
                int(limit),
                500,
            ),
        )

    except (
        TypeError,
        ValueError,
    ):

        limit = 20

    try:

        offset = max(
            0,
            int(offset),
        )

    except (
        TypeError,
        ValueError,
    ):

        offset = 0

    allowed_sources = (
        set(
            source.lower()
            for source in sources
        )
        if sources
        else {
            "long_term",
            "short_term",
            "conversation",
        }
    )

    # Gather more than the final limit so ranking
    # has enough candidates.
    candidate_limit = min(
        500,
        max(
            limit * 5,
            50,
        ),
    )

    all_results: list[
        MemorySearchResult
    ] = []

    if "long_term" in allowed_sources:

        all_results.extend(
            self._search_memory_manager(
                query,
                category,
                candidate_limit,
            )
        )

        # Avoid unnecessary duplicate long-term
        # searches when MemoryManager already supplied data.
        if not all_results:

            all_results.extend(
                self._search_long_term(
                    query,
                    category,
                    candidate_limit,
                )
            )

    if "short_term" in allowed_sources:

        all_results.extend(
            self._search_short_term(
                query,
                candidate_limit,
            )
        )

    if "conversation" in allowed_sources:

        all_results.extend(
            self._search_conversations(
                query,
                candidate_limit,
            )
        )

    # Apply importance filter.
    if min_importance is not None:

        try:

            minimum = int(
                min_importance
            )

        except (
            TypeError,
            ValueError,
        ):

            minimum = 0

        all_results = [
            item
            for item in all_results
            if item.importance >= minimum
        ]

    # Remove obvious duplicates.
    unique: dict[
        tuple[str, str, str],
        MemorySearchResult,
    ] = {}

    for item in all_results:

        identity = (
            item.source,
            str(
                item.memory_id
                if item.memory_id is not None
                else item.key
            ),
            item.value,
        )

        existing = unique.get(
            identity
        )

        if (
            existing is None
            or item.score > existing.score
        ):

            unique[identity] = item

    ranked = list(
        unique.values()
    )

    # Ranking:
    # 1. relevance
    # 2. importance
    # 3. newer timestamps
    ranked.sort(
        key=lambda item: (
            item.score,
            item.importance,
            item.timestamp,
        ),
        reverse=True,
    )

    final = ranked[
        offset : offset + limit
    ]

    self.history.append(
        {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "results": len(final),
        }
    )

    if len(
        self.history
    ) > 500:

        self.history = (
            self.history[-500:]
        )

    return final

# ========================================================
# SIMPLE SEARCH
# ========================================================

def find(
    self,
    query: str,
    limit: int = 10,
) -> list[dict[str, Any]]:

    return [
        item.to_dict()
        for item in self.search(
            query=query,
            limit=limit,
        )
    ]

# ========================================================
# CATEGORY SEARCH
# ========================================================

def search_category(
    self,
    query: str,
    category: str,
    limit: int = 20,
) -> list[MemorySearchResult]:

    return self.search(
        query=query,
        category=category,
        limit=limit,
    )

# ========================================================
# IMPORTANT MEMORY SEARCH
# ========================================================

def search_important(
    self,
    query: str,
    minimum_importance: int = 7,
    limit: int = 20,
) -> list[MemorySearchResult]:

    return self.search(
        query=query,
        min_importance=minimum_importance,
        limit=limit,
    )

# ========================================================
# CONTEXT
# ========================================================

def build_context(
    self,
    query: str,
    limit: int = 10,
    max_chars: int = 6000,
) -> str:

    results = self.search(
        query=query,
        limit=limit,
    )

    if not results:
        return ""

    lines = [
        "Relevant JarvisOS memory:"
    ]

    total = len(
        lines[0]
    )

    for item in results:

        if item.key:

            line = (
                f"- {item.key}: "
                f"{item.value}"
            )

        else:

            line = (
                f"- {item.value}"
            )

        if (
            item.category
        ):

            line += (
                f" "
                f"[{item.category}]"
            )

        if (
            total
            + len(line)
            + 1
            > max_chars
        ):

            break

        lines.append(
            line
        )

        total += (
            len(line)
            + 1
        )

    return "\n".join(
        lines
    )

# ========================================================
# BEST MATCH
# ========================================================

def best_match(
    self,
    query: str,
) -> Optional[MemorySearchResult]:

    results = self.search(
        query=query,
        limit=1,
    )

    return (
        results[0]
        if results
        else None
    )

# ========================================================
# COUNT
# ========================================================

def count(
    self,
    query: str = "",
) -> int:

    if not query:

        if self.memory_manager is not None:

            try:

                stats = (
                    self.memory_manager
                    .stats()
                )

                if isinstance(
                    stats,
                    dict,
                ):

                    return int(
                        stats.get(
                            "memory_count",
                            stats.get(
                                "memories",
                                0,
                            ),
                        )
                    )

            except Exception:
                pass

        return 0

    return len(
        self.search(
            query,
            limit=500,
        )
    )

# ========================================================
# STATUS
# ========================================================

def get_status(
    self,
) -> dict[str, Any]:

    return {
        "memory_manager": (
            self.memory_manager
            is not None
        ),
        "long_term_memory": (
            self.long_term_memory
            is not None
        ),
        "short_term_memory": (
            self.short_term_memory
            is not None
        ),
        "searches": len(
            self.history
        ),
    }

def get_history(
    self,
    limit: int = 50,
) -> list[dict[str, Any]]:

    try:

        limit = max(
            1,
            min(
                int(limit),
                500,
            ),
        )

    except (
        TypeError,
        ValueError,
    ):

        limit = 50

    return list(
        reversed(
            self.history[-limit:]
        )
    )

# ========================================================
# CLOSE
# ========================================================

def close(self) -> None:

    # The underlying memory manager may be shared
    # by other JarvisOS components, so we deliberately
    # do not close it here.
    self.history.clear()

def __enter__(
    self,
) -> "MemorySearch":

    return self

def __exit__(
    self,
    exc_type: Any,
    exc_value: Any,
    traceback_value: Any,
) -> None:

    self.close()

============================================================

SHARED INSTANCE

============================================================

_memory_search: Optional[
MemorySearch
] = None

def get_memory_search() -> MemorySearch:

global _memory_search

if _memory_search is None:

    _memory_search = (
        MemorySearch()
    )

return _memory_search

============================================================

CONVENIENCE FUNCTION

============================================================

def search_memory(
query: str,
limit: int = 20,
) -> list[dict[str, Any]]:

return get_memory_search().find(
    query=query,
    limit=limit,
)

============================================================

DIRECT TEST

============================================================

if name == "main":

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    ),
)

print("=" * 60)
print("JARVIS OS - MEMORY SEARCH TEST")
print("=" * 60)

service = MemorySearch()

print(
    "Status:"
)

print(
    service.get_status()
)

print(
    "\nSearching for: Jarvis"
)

results = service.search(
    "Jarvis",
    limit=5,
)

for result in results:

    print(
        json_safe(result.to_dict())
    )

service.close()

def json_safe(
value: Any,
) -> str:

"""
Small JSON formatter used only by the direct test.
"""

return json.dumps(
    value,
    ensure_ascii=False,
    indent=2,
    default=str,
)
