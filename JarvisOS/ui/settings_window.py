ui/settings_window.py

"""
JarvisOS - Settings Window

Graphical settings window for JarvisOS.

Manages:

- AI provider
- AI model
- Voice language
- Wake word
- Memory
- Confirmation policy
- Web access
- UI theme
- Debug mode

The window uses the existing:

- ConfigManager
- UserPreferences
- ApiKeyManager

No API key is displayed in plain text.
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
"JarvisOS.SettingsWindow"
)

============================================================

SETTINGS WINDOW

============================================================

class SettingsWindow:
"""
JarvisOS settings window.

Example:

    SettingsWindow(
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

    self.config_manager: Optional[Any] = None
    self.preferences: Optional[Any] = None
    self.api_keys: Optional[Any] = None

    self.provider_var: Optional[Any] = None
    self.model_var: Optional[Any] = None
    self.language_var: Optional[Any] = None
    self.wakeword_var: Optional[Any] = None
    self.memory_var: Optional[Any] = None
    self.confirmation_var: Optional[Any] = None
    self.web_var: Optional[Any] = None
    self.theme_var: Optional[Any] = None
    self.debug_var: Optional[Any] = None

    self.status_label: Optional[Any] = None

    self._load_managers()
    self._create_window()
    self._load_settings()

# ========================================================
# MANAGERS
# ========================================================

def _load_managers(self) -> None:

    try:

        from settings.config_manager import (
            ConfigManager,
        )

        self.config_manager = (
            ConfigManager()
        )

    except Exception as exc:

        logger.error(
            "ConfigManager unavailable: %s",
            exc,
        )

    try:

        from settings.user_preferences import (
            UserPreferences,
        )

        self.preferences = (
            UserPreferences()
        )

    except Exception as exc:

        logger.error(
            "UserPreferences unavailable: %s",
            exc,
        )

    try:

        from settings.api_key_manager import (
            ApiKeyManager,
        )

        self.api_keys = (
            ApiKeyManager()
        )

    except Exception as exc:

        logger.error(
            "ApiKeyManager unavailable: %s",
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
        "JarvisOS - Settings"
    )

    self.window.geometry(
        "650x700"
    )

    self.window.minsize(
        560,
        600,
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
        text="JarvisOS Settings",
        font=(
            "Segoe UI",
            24,
            "bold",
        ),
    )

    title.pack(
        anchor="w",
        padx=25,
        pady=(22, 4),
    )

    subtitle = self._label(
        self.window,
        text=(
            "Configure AI, voice, memory and security."
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
    # AI
    # ----------------------------------------------------

    ai_frame = self._frame(
        self.window
    )

    ai_frame.pack(
        fill="x",
        padx=20,
        pady=8,
    )

    self._label(
        ai_frame,
        text="AI SETTINGS",
        font=(
            "Segoe UI",
            14,
            "bold",
        ),
    ).pack(
        anchor="w",
        padx=15,
        pady=(12, 8),
    )

    self.provider_var = tk.StringVar(
        value="auto"
    )

    self._create_option(
        ai_frame,
        "AI Provider",
        self.provider_var,
        [
            "auto",
            "openai",
            "gemini",
            "claude",
        ],
    )

    self.model_var = tk.StringVar()

    self._create_entry(
        ai_frame,
        "AI Model",
        self.model_var,
    )

    # ----------------------------------------------------
    # VOICE
    # ----------------------------------------------------

    voice_frame = self._frame(
        self.window
    )

    voice_frame.pack(
        fill="x",
        padx=20,
        pady=8,
    )

    self._label(
        voice_frame,
        text="VOICE",
        font=(
            "Segoe UI",
            14,
            "bold",
        ),
    ).pack(
        anchor="w",
        padx=15,
        pady=(12, 8),
    )

    self.language_var = tk.StringVar(
        value="auto"
    )

    self._create_option(
        voice_frame,
        "Voice Language",
        self.language_var,
        [
            "auto",
            "english",
            "hindi",
            "hinglish",
        ],
    )

    self.wakeword_var = tk.BooleanVar(
        value=True
    )

    self._create_checkbox(
        voice_frame,
        "Enable Wake Word",
        self.wakeword_var,
    )

    # ----------------------------------------------------
    # MEMORY
    # ----------------------------------------------------

    memory_frame = self._frame(
        self.window
    )

    memory_frame.pack(
        fill="x",
        padx=20,
        pady=8,
    )

    self._label(
        memory_frame,
        text="MEMORY",
        font=(
            "Segoe UI",
            14,
            "bold",
        ),
    ).pack(
        anchor="w",
        padx=15,
        pady=(12, 8),
    )

    self.memory_var = tk.BooleanVar(
        value=True
    )

    self._create_checkbox(
        memory_frame,
        "Enable Jarvis Memory",
        self.memory_var,
    )

    # ----------------------------------------------------
    # SECURITY
    # ----------------------------------------------------

    security_frame = self._frame(
        self.window
    )

    security_frame.pack(
        fill="x",
        padx=20,
        pady=8,
    )

    self._label(
        security_frame,
        text="SECURITY",
        font=(
            "Segoe UI",
            14,
            "bold",
        ),
    ).pack(
        anchor="w",
        padx=15,
        pady=(12, 8),
    )

    self.confirmation_var = tk.BooleanVar(
        value=True
    )

    self._create_checkbox(
        security_frame,
        "Ask confirmation for risky actions",
        self.confirmation_var,
    )

    # ----------------------------------------------------
    # WEB
    # ----------------------------------------------------

    web_frame = self._frame(
        self.window
    )

    web_frame.pack(
        fill="x",
        padx=20,
        pady=8,
    )

    self._label(
        web_frame,
        text="WEB",
        font=(
            "Segoe UI",
            14,
            "bold",
        ),
    ).pack(
        anchor="w",
        padx=15,
        pady=(12, 8),
    )

    self.web_var = tk.BooleanVar(
        value=True
    )

    self._create_checkbox(
        web_frame,
        "Enable web access",
        self.web_var,
    )

    # ----------------------------------------------------
    # UI
    # ----------------------------------------------------

    ui_frame = self._frame(
        self.window
    )

    ui_frame.pack(
        fill="x",
        padx=20,
        pady=8,
    )

    self._label(
        ui_frame,
        text="INTERFACE",
        font=(
            "Segoe UI",
            14,
            "bold",
        ),
    ).pack(
        anchor="w",
        padx=15,
        pady=(12, 8),
    )

    self.theme_var = tk.StringVar(
        value="dark"
    )

    self._create_option(
        ui_frame,
        "Theme",
        self.theme_var,
        [
            "dark",
            "light",
            "system",
        ],
    )

    self.debug_var = tk.BooleanVar(
        value=False
    )

    self._create_checkbox(
        ui_frame,
        "Debug mode",
        self.debug_var,
    )

    # ----------------------------------------------------
    # BUTTONS
    # ----------------------------------------------------

    button_frame = self._frame(
        self.window
    )

    button_frame.pack(
        fill="x",
        padx=20,
        pady=(15, 10),
    )

    self._button(
        button_frame,
        "Save Settings",
        self.save_settings,
        height=42,
    ).pack(
        side="left",
        expand=True,
        fill="x",
        padx=5,
    )

    self._button(
        button_frame,
        "Reset",
        self.reset_settings,
        height=42,
    ).pack(
        side="left",
        expand=True,
        fill="x",
        padx=5,
    )

    self._button(
        button_frame,
        "Close",
        self.close,
        height=42,
    ).pack(
        side="left",
        expand=True,
        fill="x",
        padx=5,
    )

    self.status_label = self._label(
        self.window,
        text="Ready",
        font=(
            "Segoe UI",
            10,
        ),
    )

    self.status_label.pack(
        pady=(0, 15)
    )

# ========================================================
# FIELD HELPERS
# ========================================================

def _create_option(
    self,
    parent: Any,
    label: str,
    variable: Any,
    values: list[str],
) -> None:

    row = self._frame(
        parent
    )

    row.pack(
        fill="x",
        padx=15,
        pady=5,
    )

    self._label(
        row,
        text=label,
    ).pack(
        side="left"
    )

    if ctk is not None:

        widget = ctk.CTkOptionMenu(
            row,
            variable=variable,
            values=values,
            width=180,
        )

    else:

        widget = tk.OptionMenu(
            row,
            variable,
            *values,
        )

    widget.pack(
        side="right"
    )

def _create_entry(
    self,
    parent: Any,
    label: str,
    variable: Any,
) -> None:

    row = self._frame(
        parent
    )

    row.pack(
        fill="x",
        padx=15,
        pady=5,
    )

    self._label(
        row,
        text=label,
    ).pack(
        side="left"
    )

    if ctk is not None:

        widget = ctk.CTkEntry(
            row,
            textvariable=variable,
            width=180,
        )

    else:

        widget = tk.Entry(
            row,
            textvariable=variable,
            width=24,
        )

    widget.pack(
        side="right"
    )

def _create_checkbox(
    self,
    parent: Any,
    text: str,
    variable: Any,
) -> None:

    if ctk is not None:

        widget = ctk.CTkCheckBox(
            parent,
            text=text,
            variable=variable,
        )

    else:

        widget = tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
        )

    widget.pack(
        anchor="w",
        padx=15,
        pady=5,
    )

# ========================================================
# CONFIG GET/SET
# ========================================================

def _config_get(
    self,
    key: str,
    default: Any = None,
) -> Any:

    if self.config_manager is None:
        return default

    try:

        return self.config_manager.get(
            key,
            default,
        )

    except Exception:

        return default

def _config_set(
    self,
    key: str,
    value: Any,
) -> bool:

    if self.config_manager is None:
        return False

    try:

        result = (
            self.config_manager.set(
                key,
                value,
                save=True,
            )
        )

        if hasattr(
            result,
            "success",
        ):

            return bool(
                result.success
            )

        return True

    except TypeError:

        try:

            self.config_manager.set(
                key,
                value,
            )

            return True

        except Exception:
            return False

    except Exception:

        return False

# ========================================================
# LOAD SETTINGS
# ========================================================

def _load_settings(self) -> None:

    try:

        provider = self._config_get(
            "ai.provider",
            "auto",
        )

        model = self._config_get(
            "ai.model",
            "",
        )

        language = self._config_get(
            "voice.language",
            "auto",
        )

        wakeword = self._config_get(
            "voice.wake_word_enabled",
            True,
        )

        memory = self._config_get(
            "memory.enabled",
            True,
        )

        confirmation = self._config_get(
            "security.require_confirmation",
            True,
        )

        web = self._config_get(
            "web.enabled",
            True,
        )

        theme = self._config_get(
            "ui.theme",
            "dark",
        )

        debug = self._config_get(
            "app.debug",
            False,
        )

        if self.provider_var:
            self.provider_var.set(
                str(provider)
            )

        if self.model_var:
            self.model_var.set(
                str(model or "")
            )

        if self.language_var:
            self.language_var.set(
                self._normalize_language(
                    str(language)
                )
            )

        if self.wakeword_var:
            self.wakeword_var.set(
                bool(wakeword)
            )

        if self.memory_var:
            self.memory_var.set(
                bool(memory)
            )

        if self.confirmation_var:
            self.confirmation_var.set(
                bool(confirmation)
            )

        if self.web_var:
            self.web_var.set(
                bool(web)
            )

        if self.theme_var:
            self.theme_var.set(
                self._normalize_theme(
                    str(theme)
                )
            )

        if self.debug_var:
            self.debug_var.set(
                bool(debug)
            )

        self._set_status(
            "Settings loaded."
        )

    except Exception as exc:

        logger.error(
            "Could not load settings: %s",
            exc,
        )

        self._set_status(
            "Could not load settings."
        )

# ========================================================
# SAVE SETTINGS
# ========================================================

def save_settings(self) -> None:

    try:

        provider = (
            self.provider_var.get()
            if self.provider_var
            else "auto"
        )

        model = (
            self.model_var.get().strip()
            if self.model_var
            else ""
        )

        language = (
            self.language_var.get()
            if self.language_var
            else "auto"
        )

        wakeword = (
            bool(
                self.wakeword_var.get()
            )
            if self.wakeword_var
            else True
        )

        memory = (
            bool(
                self.memory_var.get()
            )
            if self.memory_var
            else True
        )

        confirmation = (
            bool(
                self.confirmation_var.get()
            )
            if self.confirmation_var
            else True
        )

        web = (
            bool(
                self.web_var.get()
            )
            if self.web_var
            else True
        )

        theme = (
            self.theme_var.get()
            if self.theme_var
            else "dark"
        )

        debug = (
            bool(
                self.debug_var.get()
            )
            if self.debug_var
            else False
        )

        language = (
            self._normalize_language(
                language
            )
        )

        theme = (
            self._normalize_theme(
                theme
            )
        )

        success = True

        settings = {
            "ai.provider": provider,
            "ai.model": model,
            "voice.language": language,
            "voice.wake_word_enabled": wakeword,
            "memory.enabled": memory,
            "security.require_confirmation": confirmation,
            "web.enabled": web,
            "ui.theme": theme,
            "app.debug": debug,
        }

        for key, value in settings.items():

            if not self._config_set(
                key,
                value,
            ):

                success = False

        # Update user preferences too.
        self._save_user_preferences(
            language=language,
            theme=theme,
            provider=provider,
            wakeword=wakeword,
            memory=memory,
            confirmation=confirmation,
        )

        # Apply theme immediately.
        self._apply_theme(
            theme
        )

        # Apply AI provider to the running router
        # when possible.
        self._apply_ai_provider(
            provider
        )

        if success:

            self._set_status(
                "Settings saved successfully."
            )

        else:

            self._set_status(
                "Some settings could not be saved."
            )

    except Exception as exc:

        logger.exception(
            "Failed to save settings."
        )

        self._set_status(
            f"Save failed: {exc}"
        )

# ========================================================
# USER PREFERENCES
# ========================================================

def _save_user_preferences(
    self,
    *,
    language: str,
    theme: str,
    provider: str,
    wakeword: bool,
    memory: bool,
    confirmation: bool,
) -> None:

    if self.preferences is None:
        return

    try:

        operations = [
            (
                "voice.language",
                language,
            ),
            (
                "ui.theme",
                theme,
            ),
            (
                "ai.provider",
                provider,
            ),
            (
                "voice.wake_word_enabled",
                wakeword,
            ),
            (
                "privacy.memory_enabled",
                memory,
            ),
            (
                "behavior.confirmation_required",
                confirmation,
            ),
        ]

        for key, value in operations:

            try:

                self.preferences.set(
                    key,
                    value,
                )

            except Exception:

                # Some versions of UserPreferences
                # may expose a different interface.
                pass

    except Exception as exc:

        logger.debug(
            "User preferences update failed: %s",
            exc,
        )

# ========================================================
# APPLY AI
# ========================================================

def _apply_ai_provider(
    self,
    provider: str,
) -> None:

    if self.jarvis is None:
        return

    router = getattr(
        self.jarvis,
        "_ai_router",
        None,
    )

    if router is None:

        router = getattr(
            self.jarvis,
            "ai_router",
            None,
        )

    if router is None:
        return

    try:

        if hasattr(
            router,
            "set_provider",
        ):

            router.set_provider(
                provider
            )

    except Exception as exc:

        logger.debug(
            "Could not apply AI provider: %s",
            exc,
        )

# ========================================================
# THEME
# ========================================================

def _apply_theme(
    self,
    theme: str,
) -> None:

    if ctk is None:
        return

    try:

        if theme == "system":

            ctk.set_appearance_mode(
                "system"
            )

        elif theme == "light":

            ctk.set_appearance_mode(
                "light"
            )

        else:

            ctk.set_appearance_mode(
                "dark"
            )

    except Exception as exc:

        logger.debug(
            "Could not apply theme: %s",
            exc,
        )

# ========================================================
# RESET
# ========================================================

def reset_settings(self) -> None:

    try:

        if self.config_manager is not None:

            try:

                self.config_manager.reset(
                    save=True
                )

            except TypeError:

                self.config_manager.reset()

        self._load_settings()

        self._set_status(
            "Settings reset to defaults."
        )

    except Exception as exc:

        logger.error(
            "Settings reset failed: %s",
            exc,
        )

        self._set_status(
            "Reset failed."
        )

# ========================================================
# VALIDATION
# ========================================================

@staticmethod
def _normalize_language(
    value: str,
) -> str:

    value = (
        str(value)
        .strip()
        .lower()
    )

    aliases = {
        "en": "english",
        "en-in": "english",
        "english": "english",
        "hi": "hindi",
        "hi-in": "hindi",
        "hindi": "hindi",
        "hinglish": "hinglish",
        "auto": "auto",
    }

    return aliases.get(
        value,
        "auto",
    )

@staticmethod
def _normalize_theme(
    value: str,
) -> str:

    value = (
        str(value)
        .strip()
        .lower()
    )

    if value not in {
        "dark",
        "light",
        "system",
    }:

        return "dark"

    return value

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
        "provider": (
            self.provider_var.get()
            if self.provider_var
            else ""
        ),
        "model": (
            self.model_var.get()
            if self.model_var
            else ""
        ),
        "language": (
            self.language_var.get()
            if self.language_var
            else ""
        ),
        "wake_word_enabled": (
            self.wakeword_var.get()
            if self.wakeword_var
            else False
        ),
        "memory_enabled": (
            self.memory_var.get()
            if self.memory_var
            else False
        ),
        "confirmation_required": (
            self.confirmation_var.get()
            if self.confirmation_var
            else True
        ),
        "web_enabled": (
            self.web_var.get()
            if self.web_var
            else False
        ),
        "theme": (
            self.theme_var.get()
            if self.theme_var
            else ""
        ),
        "debug": (
            self.debug_var.get()
            if self.debug_var
            else False
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
            "Settings window close failed: %s",
            exc,
        )

    finally:

        self.window = None

def __enter__(
    self,
) -> "SettingsWindow":

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
print("JARVIS OS - SETTINGS WINDOW TEST")
print("=" * 60)

window = SettingsWindow()

print(
    "Current settings:"
)

print(
    window.get_status()
)

if window.window is not None:

    window.window.mainloop()
