ui/chat_window.py

"""
JarvisOS - Chat Window

Main text-chat fallback interface for JarvisOS.

Features:

- User message input
- AI response display
- Send button
- Enter to send
- Conversation history
- Clear chat
- Voice response through JarvisOS TTS when available
- Uses the existing CommandProcessor
  """

from future import annotations

import logging
import threading
import tkinter as tk
from datetime import datetime
from typing import Any, Optional

try:
import customtkinter as ctk
except ImportError:
ctk = None

logger = logging.getLogger("JarvisOS.ChatWindow")

class ChatWindow:
"""
JarvisOS chat interface.

Example:
    ChatWindow(parent=root, jarvis=jarvis)
"""

def __init__(
    self,
    parent: Optional[Any] = None,
    jarvis: Optional[Any] = None,
) -> None:

    self.parent = parent
    self.jarvis = jarvis

    self.window: Optional[Any] = None
    self.chat_box: Optional[Any] = None
    self.input_box: Optional[Any] = None
    self.status_label: Optional[Any] = None

    self._sending = False

    self._create_window()

# ========================================================
# UI HELPERS
# ========================================================

def _frame(self, parent: Any, **kwargs: Any) -> Any:
    if ctk is not None:
        return ctk.CTkFrame(parent, **kwargs)

    return tk.Frame(parent, **kwargs)

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
        "JarvisOS - Chat"
    )

    self.window.geometry(
        "850x700"
    )

    self.window.minsize(
        600,
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

    self.window.protocol(
        "WM_DELETE_WINDOW",
        self.close,
    )

# ========================================================
# BUILD UI
# ========================================================

def _build_ui(self) -> None:

    assert self.window is not None

    title = self._label(
        self.window,
        text="JarvisOS Chat",
        font=(
            "Segoe UI",
            24,
            "bold",
        ),
    )

    title.pack(
        anchor="w",
        padx=25,
        pady=(20, 2),
    )

    subtitle = self._label(
        self.window,
        text=(
            "Talk to JarvisOS using text. "
            "Voice remains available separately."
        ),
        font=(
            "Segoe UI",
            11,
        ),
    )

    subtitle.pack(
        anchor="w",
        padx=27,
        pady=(0, 12),
    )

    # ----------------------------------------------------
    # CHAT AREA
    # ----------------------------------------------------

    chat_frame = self._frame(
        self.window
    )

    chat_frame.pack(
        fill="both",
        expand=True,
        padx=20,
        pady=8,
    )

    if ctk is not None:

        self.chat_box = ctk.CTkTextbox(
            chat_frame,
            wrap="word",
            font=(
                "Segoe UI",
                12,
            ),
        )

    else:

        self.chat_box = tk.Text(
            chat_frame,
            wrap="word",
            font=(
                "Segoe UI",
                12,
            ),
        )

    self.chat_box.pack(
        fill="both",
        expand=True,
        padx=8,
        pady=8,
    )

    self.chat_box.configure(
        state="disabled"
    )

    # ----------------------------------------------------
    # INPUT
    # ----------------------------------------------------

    input_frame = self._frame(
        self.window
    )

    input_frame.pack(
        fill="x",
        padx=20,
        pady=8,
    )

    if ctk is not None:

        self.input_box = ctk.CTkEntry(
            input_frame,
            placeholder_text=(
                "Type a message to JarvisOS..."
            ),
            height=45,
            font=(
                "Segoe UI",
                12,
            ),
        )

    else:

        self.input_box = tk.Entry(
            input_frame,
            font=(
                "Segoe UI",
                12,
            ),
        )

    self.input_box.pack(
        side="left",
        fill="x",
        expand=True,
        padx=5,
        pady=5,
    )

    self.input_box.bind(
        "<Return>",
        self._on_enter,
    )

    self._button(
        input_frame,
        "Send",
        self.send_message,
        width=100,
        height=45,
    ).pack(
        side="left",
        padx=5,
    )

    # ----------------------------------------------------
    # CONTROLS
    # ----------------------------------------------------

    controls = self._frame(
        self.window
    )

    controls.pack(
        fill="x",
        padx=20,
        pady=5,
    )

    self._button(
        controls,
        "Clear Chat",
        self.clear_chat,
        width=110,
    ).pack(
        side="left",
        padx=5,
    )

    self._button(
        controls,
        "Speak Last Reply",
        self.speak_last_reply,
        width=150,
    ).pack(
        side="left",
        padx=5,
    )

    self._button(
        controls,
        "Close",
        self.close,
        width=100,
    ).pack(
        side="right",
        padx=5,
    )

    # ----------------------------------------------------
    # STATUS
    # ----------------------------------------------------

    self.status_label = self._label(
        self.window,
        text="Ready",
        font=(
            "Segoe UI",
            10,
        ),
    )

    self.status_label.pack(
        pady=(3, 15)
    )

    self._add_message(
        "JarvisOS",
        (
            "Hello! Main JarvisOS hoon. "
            "Aap mujhe yahan text mein command de sakte hain."
        ),
    )

# ========================================================
# ENTER
# ========================================================

def _on_enter(
    self,
    event: Any = None,
) -> str:

    self.send_message()

    return "break"

# ========================================================
# SEND MESSAGE
# ========================================================

def send_message(self) -> None:

    if self._sending:
        return

    if self.input_box is None:
        return

    try:
        message = self.input_box.get().strip()
    except Exception:
        return

    if not message:
        return

    try:
        self.input_box.delete(
            0,
            "end",
        )
    except Exception:
        pass

    self._add_message(
        "You",
        message,
    )

    self._set_status(
        "JarvisOS is thinking..."
    )

    self._sending = True

    thread = threading.Thread(
        target=self._process_message_worker,
        args=(message,),
        daemon=True,
    )

    thread.start()

# ========================================================
# PROCESS MESSAGE
# ========================================================

def _process_message_worker(
    self,
    message: str,
) -> None:

    response_text = ""

    try:

        processor = (
            self._get_command_processor()
        )

        if processor is None:

            response_text = (
                "Command processor is not available."
            )

        else:

            result = processor.process(
                message,
                language="auto",
                use_memory=True,
                execute_actions=False,
            )

            response_text = (
                self._extract_response(
                    result
                )
            )

    except Exception as exc:

        logger.exception(
            "Chat processing failed."
        )

        response_text = (
            "Sorry, command process karte waqt "
            f"error aa gaya: {exc}"
        )

    self._run_on_ui_thread(
        lambda: self._finish_response(
            response_text
        )
    )

# ========================================================
# COMMAND PROCESSOR
# ========================================================

def _get_command_processor(
    self,
) -> Optional[Any]:

    if self.jarvis is not None:

        processor = getattr(
            self.jarvis,
            "_command_processor",
            None,
        )

        if processor is None:

            processor = getattr(
                self.jarvis,
                "command_processor",
                None,
            )

        if processor is not None:
            return processor

    try:

        from brain.command_processor import (
            CommandProcessor,
        )

        memory_manager = None
        ai_router = None

        if self.jarvis is not None:

            memory_manager = getattr(
                self.jarvis,
                "_memory",
                None,
            )

            ai_router = getattr(
                self.jarvis,
                "_ai_router",
                None,
            )

        return CommandProcessor(
            ai_router=ai_router,
            memory_manager=memory_manager,
        )

    except Exception as exc:

        logger.error(
            "Could not create CommandProcessor: %s",
            exc,
        )

        return None

# ========================================================
# RESPONSE
# ========================================================

@staticmethod
def _extract_response(
    result: Any,
) -> str:

    if result is None:
        return "No response received."

    if isinstance(
        result,
        str,
    ):
        return result

    if isinstance(
        result,
        dict,
    ):

        for key in (
            "response",
            "text",
            "message",
            "answer",
        ):

            value = result.get(
                key
            )

            if value:
                return str(value)

        return str(result)

    for attribute in (
        "response",
        "text",
        "message",
        "answer",
    ):

        if hasattr(
            result,
            attribute,
        ):

            value = getattr(
                result,
                attribute,
            )

            if value:
                return str(value)

    return str(result)

# ========================================================
# FINISH RESPONSE
# ========================================================

def _finish_response(
    self,
    response: str,
) -> None:

    self._sending = False

    if not response:
        response = "No response."

    self._add_message(
        "JarvisOS",
        response,
    )

    self._set_status(
        "Ready"
    )

    # Voice response if the main JarvisOS
    # instance provides TTS.
    self._speak_response(
        response
    )

# ========================================================
# SPEECH
# ========================================================

def _speak_response(
    self,
    text: str,
) -> None:

    if self.jarvis is None:
        return

    try:

        speaker = getattr(
            self.jarvis,
            "_tts",
            None,
        )

        if speaker is None:

            speaker = getattr(
                self.jarvis,
                "tts",
                None,
            )

        if speaker is not None and hasattr(
            speaker,
            "speak_async",
        ):

            speaker.speak_async(
                text
            )

    except Exception as exc:

        logger.debug(
            "TTS response failed: %s",
            exc,
        )

# ========================================================
# SPEAK LAST REPLY
# ========================================================

def speak_last_reply(self) -> None:

    text = self._get_last_jarvis_message()

    if not text:

        self._set_status(
            "No JarvisOS reply available."
        )

        return

    if self.jarvis is None:

        self._set_status(
            "Voice system is unavailable."
        )

        return

    try:

        speaker = getattr(
            self.jarvis,
            "_tts",
            None,
        )

        if speaker is None:

            speaker = getattr(
                self.jarvis,
                "tts",
                None,
            )

        if speaker is None:

            self._set_status(
                "TTS is unavailable."
            )

            return

        speaker.speak_async(
            text
        )

        self._set_status(
            "Speaking..."
        )

    except Exception as exc:

        logger.error(
            "Could not speak reply: %s",
            exc,
        )

        self._set_status(
            "Could not start voice output."
        )

def _get_last_jarvis_message(
    self,
) -> str:

    if self.chat_box is None:
        return ""

    try:

        content = self.chat_box.get(
            "1.0",
            "end",
        )

        blocks = content.split(
            "\n\n"
        )

        for block in reversed(
            blocks
        ):

            if block.startswith(
                "JarvisOS:"
            ):

                return (
                    block.split(
                        ":",
                        1,
                    )[1]
                    .strip()
                )

    except Exception:
        pass

    return ""

# ========================================================
# ADD MESSAGE
# ========================================================

def _add_message(
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
        f"{sender} [{timestamp}]:\n"
        f"{message}\n\n"
    )

    def update() -> None:

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
                "Could not update chat: %s",
                exc,
            )

    self._run_on_ui_thread(
        update
    )

# ========================================================
# CLEAR
# ========================================================

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

        self._set_status(
            "Chat cleared."
        )

    except Exception as exc:

        logger.error(
            "Could not clear chat: %s",
            exc,
        )

# ========================================================
# UI THREAD
# ========================================================

def _run_on_ui_thread(
    self,
    callback: Any,
) -> None:

    if self.window is None:
        return

    try:

        self.window.after(
            0,
            callback,
        )

    except Exception:
        pass

# ========================================================
# STATUS
# ========================================================

def _set_status(
    self,
    text: str,
) -> None:

    def update() -> None:

        if self.status_label is None:
            return

        try:

            self.status_label.configure(
                text=text
            )

        except Exception:
            pass

    self._run_on_ui_thread(
        update
    )

# ========================================================
# STATUS INFO
# ========================================================

def get_status(
    self,
) -> dict[str, Any]:

    return {
        "window_open": (
            self.window is not None
        ),
        "sending": self._sending,
        "command_processor_available": (
            self._get_command_processor()
            is not None
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
            "Chat window close failed: %s",
            exc,
        )

    finally:

        self.window = None

def __enter__(
    self,
) -> "ChatWindow":

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
print("JARVIS OS - CHAT WINDOW TEST")
print("=" * 60)

window = ChatWindow()

print(
    window.get_status()
)

if window.window is not None:

    window.window.mainloop()
