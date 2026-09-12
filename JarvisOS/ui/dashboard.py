ui/dashboard.py

"""
JarvisOS - Main Dashboard

Main desktop interface for JarvisOS.

Features:

- Voice assistant start/stop
- Text fallback
- AI provider status
- Memory status
- Activity log
- Quick actions
- Settings window integration
- Dark/light appearance
- Safe shutdown/restart controls

The dashboard does not directly perform dangerous system
operations. Such operations should go through the security
and permission layers.
"""

from future import annotations

import logging
import threading
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

try:
import customtkinter as ctk
except ImportError:
ctk = None

logger = logging.getLogger("JarvisOS.Dashboard")

============================================================

DATA

============================================================

@dataclass
class DashboardStatus:
"""Current dashboard status."""

assistant_running: bool = False
listening: bool = False
speaking: bool = False
ai_provider: str = "unknown"
memory_enabled: bool = True
microphone_available: bool = False
message: str = "Ready"

============================================================

DASHBOARD

============================================================

class Dashboard:
"""
Main JarvisOS graphical dashboard.

The class can receive an existing JarvisOS instance:

    Dashboard(jarvis=jarvis)

It can also be opened independently for UI testing:

    Dashboard().run()
"""

def __init__(
    self,
    jarvis: Optional[Any] = None,
    *,
    width: int = 1100,
    height: int = 700,
    title: str = "JarvisOS",
) -> None:

    self.jarvis = jarvis

    self.width = width
    self.height = height
    self.title = title

    self.status = DashboardStatus()

    self._running = False
    self._closing = False

    self._assistant_thread: Optional[
        threading.Thread
    ] = None

    self._activity: list[str] = []

    self.root: Optional[Any] = None

    self.status_label: Optional[Any] = None
    self.provider_label: Optional[Any] = None
    self.memory_label: Optional[Any] = None
    self.mic_label: Optional[Any] = None
    self.message_label: Optional[Any] = None

    self.chat_box: Optional[Any] = None
    self.command_entry: Optional[Any] = None

    self.start_button: Optional[Any] = None
    self.stop_button: Optional[Any] = None

# ========================================================
# UI TOOLKIT
# ========================================================

def _create_root(self) -> Any:

    if ctk is not None:

        ctk.set_appearance_mode(
            "dark"
        )

        ctk.set_default_color_theme(
            "blue"
        )

        root = ctk.CTk()

    else:

        root = tk.Tk()

    root.title(self.title)

    root.geometry(
        f"{self.width}x{self.height}"
    )

    root.minsize(
        850,
        550,
    )

    root.protocol(
        "WM_DELETE_WINDOW",
        self.close,
    )

    return root

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
    command: Callable[[], None],
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
# BUILD UI
# ========================================================

def build(self) -> Any:

    if self.root is not None:
        return self.root

    self.root = self._create_root()

    self._build_header()
    self._build_sidebar()
    self._build_chat()
    self._build_status_bar()

    self._refresh_status()

    return self.root

# ========================================================
# HEADER
# ========================================================

def _build_header(self) -> None:

    assert self.root is not None

    header = self._frame(
        self.root,
        height=75,
    )

    header.pack(
        fill="x",
        padx=12,
        pady=(12, 6),
    )

    header.pack_propagate(
        False
    )

    title = self._label(
        header,
        text="JARVIS OS",
        font=(
            "Segoe UI",
            24,
            "bold",
        ),
    )

    title.pack(
        side="left",
        padx=18,
        pady=15,
    )

    subtitle = self._label(
        header,
        text="Personal AI Assistant",
        font=(
            "Segoe UI",
            12,
        ),
    )

    subtitle.pack(
        side="left",
        padx=4,
        pady=20,
    )

    self.status_label = self._label(
        header,
        text="● Ready",
        font=(
            "Segoe UI",
            12,
            "bold",
        ),
    )

    self.status_label.pack(
        side="right",
        padx=20,
    )

# ========================================================
# SIDEBAR
# ========================================================

def _build_sidebar(self) -> None:

    assert self.root is not None

    sidebar = self._frame(
        self.root,
        width=220,
    )

    sidebar.pack(
        side="left",
        fill="y",
        padx=(12, 6),
        pady=6,
    )

    sidebar.pack_propagate(
        False
    )

    menu_title = self._label(
        sidebar,
        text="CONTROL",
        font=(
            "Segoe UI",
            13,
            "bold",
        ),
    )

    menu_title.pack(
        anchor="w",
        padx=18,
        pady=(20, 12),
    )

    self.start_button = self._button(
        sidebar,
        "🎙 Start Jarvis",
        self.start_assistant,
        height=42,
    )

    self.start_button.pack(
        fill="x",
        padx=15,
        pady=6,
    )

    self.stop_button = self._button(
        sidebar,
        "⏹ Stop Jarvis",
        self.stop_assistant,
        height=42,
    )

    self.stop_button.pack(
        fill="x",
        padx=15,
        pady=6,
    )

    self._button(
        sidebar,
        "🧠 Memory",
        self.open_memory,
        height=40,
    ).pack(
        fill="x",
        padx=15,
        pady=6,
    )

    self._button(
        sidebar,
        "⚙ Settings",
        self.open_settings,
        height=40,
    ).pack(
        fill="x",
        padx=15,
        pady=6,
    )

    self._button(
        sidebar,
        "🖥 System Info",
        self.show_system_info,
        height=40,
    ).pack(
        fill="x",
        padx=15,
        pady=6,
    )

    self._button(
        sidebar,
        "🧹 Clear Chat",
        self.clear_chat,
        height=40,
    ).pack(
        fill="x",
        padx=15,
        pady=6,
    )

    self._label(
        sidebar,
        text=(
            "\nJarvisOS\n"
            "Voice-first AI\n\n"
            "LOW  → automatic\n"
            "MEDIUM → notify\n"
            "HIGH → confirm"
        ),
        justify="left",
        font=(
            "Segoe UI",
            10,
        ),
    ).pack(
        anchor="w",
        padx=18,
        pady=25,
    )

# ========================================================
# CHAT
# ========================================================

def _build_chat(self) -> None:

    assert self.root is not None

    main = self._frame(
        self.root,
    )

    main.pack(
        side="left",
        fill="both",
        expand=True,
        padx=(6, 12),
        pady=6,
    )

    chat_title = self._label(
        main,
        text="Conversation",
        font=(
            "Segoe UI",
            18,
            "bold",
        ),
    )

    chat_title.pack(
        anchor="w",
        padx=15,
        pady=(12, 8),
    )

    if ctk is not None:

        self.chat_box = ctk.CTkTextbox(
            main,
            wrap="word",
            font=(
                "Segoe UI",
                13,
            ),
        )

    else:

        self.chat_box = tk.Text(
            main,
            wrap="word",
            font=(
                "Segoe UI",
                13,
            ),
        )

    self.chat_box.pack(
        fill="both",
        expand=True,
        padx=12,
        pady=8,
    )

    self.chat_box.configure(
        state="disabled"
    )

    input_frame = self._frame(
        main,
    )

    input_frame.pack(
        fill="x",
        padx=12,
        pady=(4, 12),
    )

    if ctk is not None:

        self.command_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text=(
                "Type a command or ask Jarvis..."
            ),
            height=42,
        )

    else:

        self.command_entry = tk.Entry(
            input_frame,
            font=(
                "Segoe UI",
                12,
            ),
        )

    self.command_entry.pack(
        side="left",
        fill="x",
        expand=True,
    )

    self.command_entry.bind(
        "<Return>",
        self._entry_submit,
    )

    self._button(
        input_frame,
        "Send",
        self.send_command,
        width=100,
        height=42,
    ).pack(
        side="left",
        padx=(8, 0),
    )

    self.add_chat_message(
        "JarvisOS",
        (
            "Hello! Main JarvisOS hoon. "
            "Aap voice ya text command de sakte hain."
        ),
    )

# ========================================================
# STATUS BAR
# ========================================================

def _build_status_bar(self) -> None:

    assert self.root is not None

    bar = self._frame(
        self.root,
        height=45,
    )

    bar.pack(
        side="bottom",
        fill="x",
        padx=12,
        pady=(0, 12),
    )

    bar.pack_propagate(
        False
    )

    self.provider_label = self._label(
        bar,
        text="AI: checking...",
    )

    self.provider_label.pack(
        side="left",
        padx=15,
        pady=10,
    )

    self.memory_label = self._label(
        bar,
        text="Memory: checking...",
    )

    self.memory_label.pack(
        side="left",
        padx=15,
        pady=10,
    )

    self.mic_label = self._label(
        bar,
        text="Mic: checking...",
    )

    self.mic_label.pack(
        side="left",
        padx=15,
        pady=10,
    )

    self.message_label = self._label(
        bar,
        text="Ready",
    )

    self.message_label.pack(
        side="right",
        padx=15,
        pady=10,
    )

# ========================================================
# CHAT FUNCTIONS
# ========================================================

def add_chat_message(
    self,
    sender: str,
    message: str,
) -> None:

    if self.chat_box is None:
        return

    timestamp = datetime.now().strftime(
        "%H:%M"
    )

    text = (
        f"[{timestamp}] "
        f"{sender}: {message}\n\n"
    )

    try:

        self.chat_box.configure(
            state="normal"
        )

        self.chat_box.insert(
            "end",
            text,
        )

        self.chat_box.see(
            "end"
        )

        self.chat_box.configure(
            state="disabled"
        )

    except Exception as exc:

        logger.debug(
            "Unable to update chat: %s",
            exc,
        )

def clear_chat(self) -> None:

    if self.chat_box is None:
        return

    try:

        self.chat_box.configure(
            state="normal"
        )

        self.chat_box.delete(
            "1.0",
            "end",
        )

        self.chat_box.configure(
            state="disabled"
        )

        self.add_chat_message(
            "JarvisOS",
            "Chat cleared.",
        )

    except Exception as exc:

        logger.error(
            "Could not clear chat: %s",
            exc,
        )

def _entry_submit(
    self,
    event: Any = None,
) -> None:

    self.send_command()

def send_command(self) -> None:

    if self.command_entry is None:
        return

    command = (
        self.command_entry.get()
        .strip()
    )

    if not command:
        return

    self.command_entry.delete(
        0,
        "end",
    )

    self.add_chat_message(
        "You",
        command,
    )

    self._set_message(
        "Processing..."
    )

    thread = threading.Thread(
        target=self._process_command,
        args=(command,),
        daemon=True,
    )

    thread.start()

def _process_command(
    self,
    command: str,
) -> None:

    try:

        if self.jarvis is not None:

            if hasattr(
                self.jarvis,
                "process_text_command",
            ):

                result = (
                    self.jarvis
                    .process_text_command(
                        command
                    )
                )

            else:

                result = (
                    "JarvisOS command processor "
                    "is not available."
                )

        else:

            result = (
                "JarvisOS backend is not connected."
            )

        if hasattr(
            result,
            "response",
        ):

            response = result.response

        elif isinstance(
            result,
            dict,
        ):

            response = (
                result.get(
                    "response"
                )
                or result.get(
                    "text"
                )
                or str(result)
            )

        else:

            response = str(
                result
            )

        self._ui(
            lambda: self.add_chat_message(
                "Jarvis",
                response,
            )
        )

        self._ui(
            lambda: self._set_message(
                "Ready"
            )
        )

    except Exception as exc:

        logger.exception(
            "Command processing failed."
        )

        self._ui(
            lambda: self.add_chat_message(
                "Jarvis",
                f"Error: {exc}",
            )
        )

        self._ui(
            lambda: self._set_message(
                "Error"
            )
        )

# ========================================================
# ASSISTANT CONTROL
# ========================================================

def start_assistant(self) -> None:

    if self._running:
        return

    self._running = True

    self.status.assistant_running = True
    self.status.message = "Starting..."

    self._set_message(
        "Starting Jarvis..."
    )

    self._assistant_thread = (
        threading.Thread(
            target=self._assistant_worker,
            daemon=True,
        )
    )

    self._assistant_thread.start()

def _assistant_worker(self) -> None:

    try:

        if self.jarvis is None:

            self._ui(
                lambda: self._set_message(
                    "Backend not connected"
                )
            )

            return

        self._ui(
            lambda: self._set_message(
                "Jarvis is running"
            )
        )

        run_method = getattr(
            self.jarvis,
            "run",
            None,
        )

        if callable(run_method):

            run_method()

        else:

            self._ui(
                lambda: self._set_message(
                    "Run method unavailable"
                )
            )

    except Exception as exc:

        logger.exception(
            "Assistant worker failed."
        )

        self._ui(
            lambda: self._set_message(
                f"Assistant error: {exc}"
            )
        )

    finally:

        self._running = False
        self.status.assistant_running = False

        self._ui(
            lambda: self._set_message(
                "Jarvis stopped"
            )
        )

def stop_assistant(self) -> None:

    if self.jarvis is not None:

        stop_method = getattr(
            self.jarvis,
            "stop",
            None,
        )

        if callable(stop_method):

            try:
                stop_method()

            except Exception as exc:

                logger.error(
                    "Unable to stop Jarvis: %s",
                    exc,
                )

    self._running = False

    self.status.assistant_running = False

    self._set_message(
        "Jarvis stopped"
    )

# ========================================================
# STATUS
# ========================================================

def _refresh_status(self) -> None:

    if self.root is None:
        return

    try:

        ai_status = (
            self._get_ai_status()
        )

        self.status.ai_provider = (
            ai_status
        )

        memory_status = (
            self._get_memory_status()
        )

        self.status.memory_enabled = (
            memory_status
        )

        microphone_status = (
            self._get_microphone_status()
        )

        self.status.microphone_available = (
            microphone_status
        )

        if self.provider_label:

            self.provider_label.configure(
                text=(
                    "AI: "
                    + ai_status
                )
            )

        if self.memory_label:

            self.memory_label.configure(
                text=(
                    "Memory: "
                    + (
                        "ON"
                        if memory_status
                        else "OFF"
                    )
                )
            )

        if self.mic_label:

            self.mic_label.configure(
                text=(
                    "Mic: "
                    + (
                        "Ready"
                        if microphone_status
                        else "Unavailable"
                    )
                )
            )

        if self.status_label:

            self.status_label.configure(
                text=(
                    "● "
                    + (
                        "Running"
                        if self._running
                        else "Ready"
                    )
                )
            )

    except Exception as exc:

        logger.debug(
            "Status refresh failed: %s",
            exc,
        )

    if not self._closing:

        self.root.after(
            3000,
            self._refresh_status,
        )

def _get_ai_status(self) -> str:

    if self.jarvis is None:
        return "Not connected"

    router = getattr(
        self.jarvis,
        "ai_router",
        None,
    )

    if router is None:

        try:

            router = (
                getattr(
                    self.jarvis,
                    "_ai_router",
                    None,
                )
            )

        except Exception:
            router = None

    if router is None:
        return "Unavailable"

    try:

        status = router.status()

        if isinstance(
            status,
            dict,
        ):

            provider = (
                status.get(
                    "active_provider"
                )
                or status.get(
                    "provider"
                )
                or status.get(
                    "active"
                )
            )

            if provider:
                return str(
                    provider
                )

        return "Available"

    except Exception:

        return "Available"

def _get_memory_status(self) -> bool:

    if self.jarvis is None:
        return True

    memory = getattr(
        self.jarvis,
        "memory",
        None,
    )

    if memory is None:

        memory = getattr(
            self.jarvis,
            "_memory",
            None,
        )

    return memory is not None

def _get_microphone_status(self) -> bool:

    if self.jarvis is None:
        return False

    mic = getattr(
        self.jarvis,
        "microphone_manager",
        None,
    )

    if mic is None:

        mic = getattr(
            self.jarvis,
            "_microphone_manager",
            None,
        )

    if mic is None:
        return False

    try:

        if hasattr(
            mic,
            "get_status",
        ):

            status = (
                mic.get_status()
            )

            if isinstance(
                status,
                dict,
            ):

                return bool(
                    status.get(
                        "available",
                        True,
                    )
                )

        return True

    except Exception:

        return False

# ========================================================
# QUICK WINDOWS
# ========================================================

def show_system_info(self) -> None:

    try:

        from actions.system_control import (
            SystemControl,
        )

        controller = (
            SystemControl()
        )

        info = (
            controller
            .get_system_info()
        )

        if hasattr(
            info,
            "data",
        ):

            data = info.data

        elif isinstance(
            info,
            dict,
        ):

            data = info

        else:

            data = str(info)

        self.add_chat_message(
            "System",
            str(data),
        )

    except Exception as exc:

        self.add_chat_message(
            "System",
            f"Unable to read system info: {exc}",
        )

# ========================================================
# WINDOWS
# ========================================================

def open_settings(self) -> None:

    try:

        from ui.settings_window import (
            SettingsWindow,
        )

        SettingsWindow(
            parent=self.root,
            jarvis=self.jarvis,
        )

    except Exception as exc:

        logger.exception(
            "Could not open settings."
        )

        self.add_chat_message(
            "System",
            f"Settings unavailable: {exc}",
        )

def open_memory(self) -> None:

    try:

        from ui.memory_window import (
            MemoryWindow,
        )

        MemoryWindow(
            parent=self.root,
            jarvis=self.jarvis,
        )

    except Exception as exc:

        logger.exception(
            "Could not open memory window."
        )

        self.add_chat_message(
            "System",
            f"Memory window unavailable: {exc}",
        )

# ========================================================
# HELPERS
# ========================================================

def _set_message(
    self,
    message: str,
) -> None:

    self.status.message = message

    if self.message_label is not None:

        self._ui(
            lambda: self.message_label.configure(
                text=message
            )
        )

def _ui(
    self,
    callback: Callable[[], None],
) -> None:

    if self.root is None:
        return

    try:

        self.root.after(
            0,
            callback,
        )

    except Exception:

        pass

# ========================================================
# RUN / CLOSE
# ========================================================

def run(self) -> None:

    if self.root is None:

        self.build()

    if self.root is None:
        return

    self.root.mainloop()

def close(self) -> None:

    if self._closing:
        return

    self._closing = True

    try:

        self.stop_assistant()

    except Exception:
        pass

    if self.root is not None:

        try:

            self.root.destroy()

        except Exception:
            pass

    self.root = None

def get_status(
    self,
) -> Dict[str, Any]:

    return {
        "assistant_running": (
            self.status.assistant_running
        ),
        "listening": (
            self.status.listening
        ),
        "speaking": (
            self.status.speaking
        ),
        "ai_provider": (
            self.status.ai_provider
        ),
        "memory_enabled": (
            self.status.memory_enabled
        ),
        "microphone_available": (
            self.status.microphone_available
        ),
        "message": (
            self.status.message
        ),
        "window_open": (
            self.root is not None
        ),
    }

def __enter__(
    self,
) -> "Dashboard":

    self.build()

    return self

def __exit__(
    self,
    exc_type: Any,
    exc_value: Any,
    traceback_value: Any,
) -> None:

    self.close()

============================================================

CONVENIENCE FUNCTION

============================================================

def create_dashboard(
jarvis: Optional[Any] = None,
) -> Dashboard:

dashboard = Dashboard(
    jarvis=jarvis
)

dashboard.build()

return dashboard

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
print("JARVIS OS - DASHBOARD TEST")
print("=" * 60)

dashboard = Dashboard()

print(
    "Dashboard status:"
)

print(
    dashboard.get_status()
)

print(
    "\nOpening dashboard..."
)

dashboard.run()
