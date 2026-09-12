ui/memory_window.py

"""
JarvisOS - Memory Window

Graphical interface for viewing and managing JarvisOS memory.

Features:

- View saved memories
- Search memories
- Add memory
- Delete selected memory
- Clear all memories with confirmation
- View memory statistics
- Refresh memory list
- Works with the existing MemoryManager
  """

from future import annotations

import logging
import tkinter as tk
from typing import Any, Optional

try:
import customtkinter as ctk
except ImportError:
ctk = None

logger = logging.getLogger(
"JarvisOS.MemoryWindow"
)

============================================================

MEMORY WINDOW

============================================================

class MemoryWindow:
"""
JarvisOS memory management window.

Example:

    MemoryWindow(
        parent=root,
        jarvis=jarvis,
    )
"""

def __init__(
    self,
    parent: Optional[Any] = None,
    jarvis: Optional[Any] = None,
) -> None:

    self.parent = parent
    self.jarvis = jarvis

    self.window: Optional[Any] = None
    self.memory_manager: Optional[Any] = None

    self.search_var: Optional[Any] = None
    self.key_var: Optional[Any] = None
    self.value_var: Optional[Any] = None

    self.memory_list: Optional[Any] = None
    self.status_label: Optional[Any] = None
    self.stats_label: Optional[Any] = None

    self._memories: list[dict[str, Any]] = []

    self._load_memory_manager()
    self._create_window()
    self.refresh()

# ========================================================
# MEMORY MANAGER
# ========================================================

def _load_memory_manager(self) -> None:

    # Prefer the manager already used by JarvisOS.
    if self.jarvis is not None:

        manager = getattr(
            self.jarvis,
            "_memory",
            None,
        )

        if manager is None:

            manager = getattr(
                self.jarvis,
                "memory",
                None,
            )

        if manager is not None:

            self.memory_manager = manager
            return

    try:

        from memory.memory_manager import (
            MemoryManager,
        )

        self.memory_manager = (
            MemoryManager()
        )

    except Exception as exc:

        logger.error(
            "Could not initialize MemoryManager: %s",
            exc,
        )

# ========================================================
# UI HELPERS
# ========================================================

def _frame(
    self,
    parent: Any,
    **kwargs: Any,
) -> Any:

    if ctk is not None:

        return ctk.CTkFrame(
            parent,
            **kwargs,
        )

    return tk.Frame(
        parent,
        **kwargs,
    )

def _label(
    self,
    parent: Any,
    text: str = "",
    **kwargs: Any,
) -> Any:

    if ctk is not None:

        return ctk.CTkLabel(
            parent,
            text=text,
            **kwargs,
        )

    return tk.Label(
        parent,
        text=text,
        **kwargs,
    )

def _button(
    self,
    parent: Any,
    text: str,
    command: Any,
    **kwargs: Any,
) -> Any:

    if ctk is not None:

        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            **kwargs,
        )

    return tk.Button(
        parent,
        text=text,
        command=command,
        **kwargs,
    )

# ========================================================
# WINDOW
# ========================================================

def _create_window(self) -> None:

    if ctk is not None:

        self.window = ctk.CTkToplevel(
            self.parent
        )

    else:

        self.window = tk.Toplevel(
            self.parent
        )

    self.window.title(
        "JarvisOS - Memory"
    )

    self.window.geometry(
        "800x650"
    )

    self.window.minsize(
        650,
        500,
    )

    if self.parent is not None:

        try:

            self.window.transient(
                self.parent
            )

        except Exception:
            pass

    self._build_ui()

# ========================================================
# BUILD UI
# ========================================================

def _build_ui(self) -> None:

    assert self.window is not None

    title = self._label(
        self.window,
        text="JarvisOS Memory",
        font=(
            "Segoe UI",
            24,
            "bold",
        ),
    )

    title.pack(
        anchor="w",
        padx=25,
        pady=(20, 3),
    )

    subtitle = self._label(
        self.window,
        text=(
            "View, search and manage what JarvisOS remembers."
        ),
        font=(
            "Segoe UI",
            11,
        ),
    )

    subtitle.pack(
        anchor="w",
        padx=27,
        pady=(0, 15),
    )

    # ----------------------------------------------------
    # SEARCH
    # ----------------------------------------------------

    search_frame = self._frame(
        self.window
    )

    search_frame.pack(
        fill="x",
        padx=20,
        pady=8,
    )

    self.search_var = tk.StringVar()

    if ctk is not None:

        search_entry = ctk.CTkEntry(
            search_frame,
            textvariable=self.search_var,
            placeholder_text=(
                "Search memories..."
            ),
            height=40,
        )

    else:

        search_entry = tk.Entry(
            search_frame,
            textvariable=self.search_var,
            font=(
                "Segoe UI",
                12,
            ),
        )

    search_entry.pack(
        side="left",
        fill="x",
        expand=True,
        padx=8,
        pady=8,
    )

    search_entry.bind(
        "<Return>",
        lambda event: self.search(),
    )

    self._button(
        search_frame,
        "Search",
        self.search,
        height=40,
        width=100,
    ).pack(
        side="left",
        padx=5,
    )

    self._button(
        search_frame,
        "Refresh",
        self.refresh,
        height=40,
        width=100,
    ).pack(
        side="left",
        padx=5,
    )

    # ----------------------------------------------------
    # MEMORY LIST
    # ----------------------------------------------------

    list_frame = self._frame(
        self.window
    )

    list_frame.pack(
        fill="both",
        expand=True,
        padx=20,
        pady=8,
    )

    if ctk is not None:

        self.memory_list = ctk.CTkTextbox(
            list_frame,
            wrap="word",
            font=(
                "Consolas",
                11,
            ),
        )

    else:

        self.memory_list = tk.Text(
            list_frame,
            wrap="word",
            font=(
                "Consolas",
                11,
            ),
        )

    self.memory_list.pack(
        fill="both",
        expand=True,
        padx=8,
        pady=8,
    )

    self.memory_list.configure(
        state="disabled"
    )

    # ----------------------------------------------------
    # ADD MEMORY
    # ----------------------------------------------------

    add_frame = self._frame(
        self.window
    )

    add_frame.pack(
        fill="x",
        padx=20,
        pady=8,
    )

    self.key_var = tk.StringVar()

    self.value_var = tk.StringVar()

    if ctk is not None:

        key_entry = ctk.CTkEntry(
            add_frame,
            textvariable=self.key_var,
            placeholder_text="Memory key",
            width=180,
        )

        value_entry = ctk.CTkEntry(
            add_frame,
            textvariable=self.value_var,
            placeholder_text="Memory value",
        )

    else:

        key_entry = tk.Entry(
            add_frame,
            textvariable=self.key_var,
            width=22,
        )

        value_entry = tk.Entry(
            add_frame,
            textvariable=self.value_var,
        )

    key_entry.pack(
        side="left",
        padx=5,
        pady=8,
    )

    value_entry.pack(
        side="left",
        fill="x",
        expand=True,
        padx=5,
        pady=8,
    )

    self._button(
        add_frame,
        "Add Memory",
        self.add_memory,
        width=120,
        height=38,
    ).pack(
        side="left",
        padx=5,
    )

    # ----------------------------------------------------
    # ACTIONS
    # ----------------------------------------------------

    action_frame = self._frame(
        self.window
    )

    action_frame.pack(
        fill="x",
        padx=20,
        pady=(5, 8),
    )

    self._button(
        action_frame,
        "Delete Memory",
        self.delete_selected,
        height=40,
    ).pack(
        side="left",
        padx=5,
    )

    self._button(
        action_frame,
        "Clear All Memory",
        self.clear_all,
        height=40,
    ).pack(
        side="left",
        padx=5,
    )

    self._button(
        action_frame,
        "Close",
        self.close,
        height=40,
    ).pack(
        side="right",
        padx=5,
    )

    # ----------------------------------------------------
    # STATUS
    # ----------------------------------------------------

    bottom = self._frame(
        self.window
    )

    bottom.pack(
        fill="x",
        padx=20,
        pady=(3, 15),
    )

    self.stats_label = self._label(
        bottom,
        text="Memories: 0",
    )

    self.stats_label.pack(
        side="left",
        padx=8,
    )

    self.status_label = self._label(
        bottom,
        text="Ready",
    )

    self.status_label.pack(
        side="right",
        padx=8,
    )

# ========================================================
# GET MEMORIES
# ========================================================

def _get_memories(
    self,
    query: str = "",
) -> list[dict[str, Any]]:

    if self.memory_manager is None:

        return []

    try:

        if query:

            result = (
                self.memory_manager.search(
                    query,
                    limit=100,
                )
            )

        else:

            result = (
                self.memory_manager
                .get_all_memories()
            )

        if result is None:
            return []

        if isinstance(
            result,
            dict,
        ):

            return [
                result
            ]

        memories = []

        for item in result:

            if isinstance(
                item,
                dict,
            ):

                memories.append(
                    item
                )

            elif hasattr(
                item,
                "to_dict",
            ):

                memories.append(
                    item.to_dict()
                )

            else:

                memories.append(
                    {
                        "value": str(
                            item
                        )
                    }
                )

        return memories

    except TypeError:

        # Compatibility with a manager whose search()
        # does not accept limit.
        try:

            result = (
                self.memory_manager.search(
                    query
                )
            )

            if isinstance(
                result,
                list,
            ):

                return result

        except Exception:
            pass

    except Exception as exc:

        logger.error(
            "Could not retrieve memories: %s",
            exc,
        )

    return []

# ========================================================
# REFRESH
# ========================================================

def refresh(self) -> None:

    self._memories = (
        self._get_memories()
    )

    self._display_memories(
        self._memories
    )

    self._update_stats()

    self._set_status(
        "Memory list refreshed."
    )

# ========================================================
# SEARCH
# ========================================================

def search(self) -> None:

    query = ""

    if self.search_var is not None:

        query = (
            self.search_var
            .get()
            .strip()
        )

    if not query:

        self.refresh()
        return

    self._memories = (
        self._get_memories(
            query
        )
    )

    self._display_memories(
        self._memories
    )

    self._set_status(
        f"Search results: {len(self._memories)}"
    )

# ========================================================
# DISPLAY
# ========================================================

def _display_memories(
    self,
    memories: list[dict[str, Any]],
) -> None:

    if self.memory_list is None:
        return

    try:

        self.memory_list.configure(
            state="normal"
        )

        self.memory_list.delete(
            "1.0",
            "end",
        )

        if not memories:

            self.memory_list.insert(
                "end",
                "No memories found.\n"
            )

        else:

            for index, memory in enumerate(
                memories,
                start=1,
            ):

                key = (
                    memory.get(
                        "key",
                        ""
                    )
                )

                value = (
                    memory.get(
                        "value",
                        ""
                    )
                )

                category = (
                    memory.get(
                        "category",
                        ""
                    )
                )

                memory_id = (
                    memory.get(
                        "id",
                        index
                    )
                )

                created = (
                    memory.get(
                        "created_at",
                        ""
                    )
                )

                self.memory_list.insert(
                    "end",
                    (
                        f"[{index}] "
                        f"ID: {memory_id}\n"
                        f"Key: {key}\n"
                        f"Value: {value}\n"
                        f"Category: {category}\n"
                        f"Created: {created}\n"
                        + "-" * 60
                        + "\n\n"
                    ),
                )

        self.memory_list.configure(
            state="disabled"
        )

    except Exception as exc:

        logger.error(
            "Could not display memories: %s",
            exc,
        )

# ========================================================
# ADD
# ========================================================

def add_memory(self) -> None:

    if self.memory_manager is None:

        self._set_status(
            "Memory manager unavailable."
        )

        return

    key = ""

    value = ""

    if self.key_var:

        key = (
            self.key_var
            .get()
            .strip()
        )

    if self.value_var:

        value = (
            self.value_var
            .get()
            .strip()
        )

    if not key:

        self._set_status(
            "Memory key is required."
        )

        return

    if not value:

        self._set_status(
            "Memory value is required."
        )

        return

    try:

        result = (
            self.memory_manager.remember(
                key=key,
                value=value,
                category="user",
            )
        )

        success = True

        if hasattr(
            result,
            "success",
        ):

            success = bool(
                result.success
            )

        if success:

            if self.key_var:
                self.key_var.set("")

            if self.value_var:
                self.value_var.set("")

            self.refresh()

            self._set_status(
                "Memory added."
            )

        else:

            self._set_status(
                "Memory could not be added."
            )

    except TypeError:

        # Compatibility fallback.
        try:

            self.memory_manager.remember(
                key,
                value,
            )

            if self.key_var:
                self.key_var.set("")

            if self.value_var:
                self.value_var.set("")

            self.refresh()

            self._set_status(
                "Memory added."
            )

        except Exception as exc:

            logger.error(
                "Add memory failed: %s",
                exc,
            )

            self._set_status(
                "Could not add memory."
            )

    except Exception as exc:

        logger.error(
            "Add memory failed: %s",
            exc,
        )

        self._set_status(
            "Could not add memory."
        )

# ========================================================
# DELETE
# ========================================================

def _get_selected_index(
    self,
) -> Optional[int]:

    if self.memory_list is None:
        return None

    try:

        selected = (
            self.memory_list.get(
                "sel.first",
                "sel.last",
            )
        )

    except Exception:

        return None

    if not selected:
        return None

    try:

        line_number = int(
            selected.split(
                "."
            )[0]
        )

        text = (
            self.memory_list
            .get(
                f"{line_number}.0",
                f"{line_number}.end",
            )
        )

        marker = "["

        if marker not in text:
            return None

        number_text = (
            text.split(
                "]",
                1,
            )[0]
            .replace(
                "[",
                "",
            )
            .strip()
        )

        index = int(
            number_text
        )

        return index - 1

    except Exception:

        return None

def delete_selected(self) -> None:

    index = (
        self._get_selected_index()
    )

    if index is None:

        self._set_status(
            "Select a memory first."
        )

        return

    if index < 0 or index >= len(
        self._memories
    ):

        self._set_status(
            "Invalid memory selection."
        )

        return

    memory = (
        self._memories[index]
    )

    memory_id = memory.get(
        "id"
    )

    key = memory.get(
        "key",
        "",
    )

    if self.window is None:
        return

    confirmed = tk.messagebox.askyesno(
        "Delete Memory",
        (
            "Delete this memory?\n\n"
            f"Key: {key}"
        ),
        parent=self.window,
    )

    if not confirmed:
        return

    try:

        if memory_id is not None:

            result = (
                self.memory_manager
                .forget_by_id(
                    int(memory_id)
                )
            )

        else:

            result = (
                self.memory_manager
                .forget(
                    key
                )
            )

        if hasattr(
            result,
            "success",
        ):

            success = bool(
                result.success
            )

        else:

            success = True

        if success:

            self.refresh()

            self._set_status(
                "Memory deleted."
            )

        else:

            self._set_status(
                "Memory could not be deleted."
            )

    except Exception as exc:

        logger.error(
            "Delete memory failed: %s",
            exc,
        )

        self._set_status(
            "Could not delete memory."
        )

# ========================================================
# CLEAR ALL
# ========================================================

def clear_all(self) -> None:

    if self.memory_manager is None:
        return

    if self.window is None:
        return

    confirmed = tk.messagebox.askyesno(
        "Clear All Memory",
        (
            "This will permanently delete "
            "all saved memories.\n\n"
            "Are you sure?"
        ),
        parent=self.window,
        icon="warning",
    )

    if not confirmed:
        return

    try:

        result = (
            self.memory_manager
            .clear_all(
                confirm=True
            )
        )

        if hasattr(
            result,
            "success",
        ):

            success = bool(
                result.success
            )

        else:

            success = True

        if success:

            self.refresh()

            self._set_status(
                "All memories cleared."
            )

        else:

            self._set_status(
                "Memory could not be cleared."
            )

    except TypeError:

        try:

            self.memory_manager.clear_all(
                True
            )

            self.refresh()

            self._set_status(
                "All memories cleared."
            )

        except Exception as exc:

            logger.error(
                "Clear memory failed: %s",
                exc,
            )

            self._set_status(
                "Could not clear memory."
            )

    except Exception as exc:

        logger.error(
            "Clear memory failed: %s",
            exc,
        )

        self._set_status(
            "Could not clear memory."
        )

# ========================================================
# STATISTICS
# ========================================================

def _update_stats(self) -> None:

    count = len(
        self._memories
    )

    if self.memory_manager is not None:

        try:

            stats = (
                self.memory_manager
                .get_stats()
            )

            if isinstance(
                stats,
                dict,
            ):

                count = int(
                    stats.get(
                        "memory_count",
                        stats.get(
                            "memories",
                            count,
                        ),
                    )
                )

        except Exception:
            pass

    if self.stats_label is not None:

        try:

            self.stats_label.configure(
                text=(
                    f"Memories: {count}"
                )
            )

        except Exception:
            pass

# ========================================================
# STATUS
# ========================================================

def _set_status(
    self,
    message: str,
) -> None:

    if self.status_label is not None:

        try:

            self.status_label.configure(
                text=message
            )

        except Exception:
            pass

def get_status(
    self,
) -> dict[str, Any]:

    return {
        "window_open": (
            self.window is not None
        ),
        "memory_manager_available": (
            self.memory_manager is not None
        ),
        "memory_count": len(
            self._memories
        ),
        "search": (
            self.search_var.get()
            if self.search_var
            else ""
        ),
    }

# ========================================================
# CLOSE
# ========================================================

def close(self) -> None:

    try:

        if self.window is not None:

            self.window.destroy()

    except Exception as exc:

        logger.debug(
            "Memory window close failed: %s",
            exc,
        )

    finally:

        self.window = None

def __enter__(
    self,
) -> "MemoryWindow":

    return self

def __exit__(
    self,
    exc_type: Any,
    exc_value: Any,
    traceback_value: Any,
) -> None:

    self.close()

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
print("JARVIS OS - MEMORY WINDOW TEST")
print("=" * 60)

window = MemoryWindow()

print(
    "Memory window status:"
)

print(
    window.get_status()
)

if window.window is not None:

    window.window.mainloop()
