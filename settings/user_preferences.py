# settings/user_preferences.py

"""
JARVIS OS - USER PREFERENCES
============================

User-facing preferences for JarvisOS.

This module stores preferences such as:
- User name
- Preferred language
- Voice settings
- AI provider
- Theme
- Notifications
- Memory preference
- Wake-word preference
- Startup behavior
- Response style

It works independently from ConfigManager:
- ConfigManager -> application/system configuration
- UserPreferences -> user-facing personal preferences

No API keys are stored here.
"""

from __future__ import annotations

import copy
import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from .config_manager import ConfigManager
except ImportError:
    try:
        from settings.config_manager import ConfigManager
    except ImportError:
        ConfigManager = None


logger = logging.getLogger(
    "JarvisOS.UserPreferences"
)


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class UserProfile:
    """Basic user profile."""

    name: str = ""

    nickname: str = ""

    preferred_language: str = "auto"

    timezone: str = ""

    response_style: str = "friendly"


@dataclass
class VoicePreferences:
    """Voice-related preferences."""

    enabled: bool = True

    language: str = "auto"

    wake_word_enabled: bool = True

    wake_word: str = "jarvis"

    speech_rate: int = 175

    volume: float = 1.0

    voice_id: str = ""

    interrupt_enabled: bool = True


@dataclass
class AIPreferences:
    """AI behavior preferences."""

    provider: str = "auto"

    model: str = ""

    temperature: float = 0.7

    response_length: str = "normal"

    use_memory: bool = True

    automatic_fallback: bool = True


@dataclass
class UIPreferences:
    """User interface preferences."""

    theme: str = "system"

    start_minimized: bool = False

    show_notifications: bool = True

    show_voice_animation: bool = True

    compact_mode: bool = False


@dataclass
class PrivacyPreferences:
    """Privacy-related user preferences."""

    memory_enabled: bool = True

    save_conversations: bool = True

    screen_access_enabled: bool = False

    microphone_enabled: bool = True

    telemetry_enabled: bool = False

    remember_commands: bool = True


@dataclass
class UserPreferencesResult:
    """Operation result."""

    success: bool

    status: str

    message: str

    key: str = ""

    value: Any = None

    errors: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )

    data: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# USER PREFERENCES
# ============================================================

class UserPreferences:
    """
    Manages user-facing JarvisOS preferences.

    Preferences are stored locally in JSON format.

    Example:

        prefs.get("profile.name")

        prefs.set(
            "profile.name",
            "Rahul"
        )

        prefs.set_language("hinglish")

        prefs.set_theme("dark")
    """

    DEFAULT_PREFERENCES = {

        "profile": asdict(
            UserProfile()
        ),

        "voice": asdict(
            VoicePreferences()
        ),

        "ai": asdict(
            AIPreferences()
        ),

        "ui": asdict(
            UIPreferences()
        ),

        "privacy": asdict(
            PrivacyPreferences()
        ),

        "startup": {
            "launch_on_windows_start": False,
            "start_voice_mode": True,
            "start_minimized": False,
        },

        "behavior": {
            "confirmation_before_dangerous_actions": True,
            "speak_action_confirmation": True,
            "show_action_results": True,
            "automatic_web_search": False,
            "automatic_file_organization": False,
        },
    }

    # ========================================================
    # ALLOWED VALUES
    # ========================================================

    ALLOWED_LANGUAGES = {
        "auto",
        "english",
        "hindi",
        "hinglish",
    }

    ALLOWED_THEMES = {
        "system",
        "light",
        "dark",
    }

    ALLOWED_RESPONSE_STYLES = {
        "friendly",
        "professional",
        "concise",
        "detailed",
    }

    ALLOWED_RESPONSE_LENGTHS = {
        "short",
        "normal",
        "long",
    }

    ALLOWED_AI_PROVIDERS = {
        "auto",
        "openai",
        "gemini",
        "claude",
    }

    # ========================================================
    # CONSTRUCTOR
    # ========================================================

    def __init__(
        self,
        preferences_path: Optional[
            str | Path
        ] = None,
        *,
        config_manager: Optional[
            ConfigManager
        ] = None,
        auto_create: bool = True,
    ):

        if preferences_path is None:

            self.preferences_path = (
                Path(__file__).resolve().parent
                / "user_preferences.json"
            )

        else:

            self.preferences_path = (
                Path(
                    preferences_path
                )
                .expanduser()
                .resolve()
            )

        self.preferences_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.config_manager = (
            config_manager
        )

        self._lock = (
            threading.RLock()
        )

        self._preferences = (
            copy.deepcopy(
                self.DEFAULT_PREFERENCES
            )
        )

        self.history: list[
            Dict[str, Any]
        ] = []

        self.max_history = 200

        self.loaded = False

        if self.preferences_path.exists():

            self.load()

        elif auto_create:

            self.save()

    # ========================================================
    # TIME
    # ========================================================

    @staticmethod
    def _utc_now() -> str:

        from datetime import (
            datetime,
            timezone,
        )

        return (
            datetime.now(
                timezone.utc
            ).isoformat()
        )

    # ========================================================
    # NORMALIZE LANGUAGE
    # ========================================================

    @classmethod
    def normalize_language(
        cls,
        language: str,
    ) -> str:

        value = (
            language or ""
        ).strip().lower()

        aliases = {
            "en": "english",
            "en-in": "english",
            "en-us": "english",
            "hi": "hindi",
            "hi-in": "hindi",
            "mix": "hinglish",
        }

        value = aliases.get(
            value,
            value,
        )

        if value not in cls.ALLOWED_LANGUAGES:

            raise ValueError(
                f"Unsupported language: {language}"
            )

        return value

    # ========================================================
    # LOAD
    # ========================================================

    def load(
        self,
    ) -> UserPreferencesResult:

        try:

            with self._lock:

                with open(
                    self.preferences_path,
                    "r",
                    encoding="utf-8",
                ) as file:

                    data = json.load(
                        file
                    )

                if not isinstance(
                    data,
                    dict,
                ):

                    raise ValueError(
                        "Preferences must be a JSON object."
                    )

                self._preferences = (
                    self._deep_merge(
                        copy.deepcopy(
                            self.DEFAULT_PREFERENCES
                        ),
                        data,
                    )
                )

                self.loaded = True

            return UserPreferencesResult(
                success=True,
                status="loaded",
                message=(
                    "User preferences loaded."
                ),
                data={
                    "path": str(
                        self.preferences_path
                    )
                },
            )

        except Exception as exc:

            logger.error(
                "Could not load user preferences: %s",
                exc,
            )

            return UserPreferencesResult(
                success=False,
                status="load_error",
                message=(
                    "Could not load user preferences."
                ),
                errors=[
                    str(exc)
                ],
            )

    # ========================================================
    # SAVE
    # ========================================================

    def save(
        self,
    ) -> UserPreferencesResult:

        try:

            with self._lock:

                data = copy.deepcopy(
                    self._preferences
                )

                temporary = (
                    self.preferences_path.with_suffix(
                        ".tmp"
                    )
                )

                with open(
                    temporary,
                    "w",
                    encoding="utf-8",
                ) as file:

                    json.dump(
                        data,
                        file,
                        indent=2,
                        ensure_ascii=False,
                    )

                    file.write(
                        "\n"
                    )

                temporary.replace(
                    self.preferences_path
                )

            return UserPreferencesResult(
                success=True,
                status="saved",
                message=(
                    "User preferences saved."
                ),
            )

        except Exception as exc:

            logger.error(
                "Could not save user preferences: %s",
                exc,
            )

            return UserPreferencesResult(
                success=False,
                status="save_error",
                message=(
                    "Could not save user preferences."
                ),
                errors=[
                    str(exc)
                ],
            )

    # ========================================================
    # DEEP MERGE
    # ========================================================

    @classmethod
    def _deep_merge(
        cls,
        base: Dict[str, Any],
        override: Dict[str, Any],
    ) -> Dict[str, Any]:

        result = copy.deepcopy(
            base
        )

        for key, value in override.items():

            if (
                key in result
                and isinstance(
                    result[key],
                    dict,
                )
                and isinstance(
                    value,
                    dict,
                )
            ):

                result[key] = (
                    cls._deep_merge(
                        result[key],
                        value,
                    )
                )

            else:

                result[key] = (
                    copy.deepcopy(
                        value
                    )
                )

        return result

    # ========================================================
    # KEY HELPERS
    # ========================================================

    @staticmethod
    def _split_key(
        key: str,
    ) -> list[str]:

        value = (
            key or ""
        ).strip()

        if not value:

            raise ValueError(
                "Preference key cannot be empty."
            )

        parts = [
            part.strip()
            for part in value.split(".")
        ]

        if any(
            not part
            for part in parts
        ):

            raise ValueError(
                f"Invalid preference key: {key}"
            )

        return parts

    # ========================================================
    # GET
    # ========================================================

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:

        try:

            parts = self._split_key(
                key
            )

        except ValueError:

            return default

        with self._lock:

            current: Any = (
                self._preferences
            )

            for part in parts:

                if not isinstance(
                    current,
                    dict,
                ):

                    return default

                if part not in current:

                    return default

                current = current[
                    part
                ]

            return copy.deepcopy(
                current
            )

    # ========================================================
    # SET
    # ========================================================

    def set(
        self,
        key: str,
        value: Any,
        *,
        save: bool = True,
    ) -> UserPreferencesResult:

        try:

            parts = self._split_key(
                key
            )

            with self._lock:

                current = (
                    self._preferences
                )

                for part in parts[:-1]:

                    if part not in current:

                        current[part] = {}

                    if not isinstance(
                        current[part],
                        dict,
                    ):

                        raise ValueError(
                            f"Cannot create preference under "
                            f"non-object key: {part}"
                        )

                    current = current[
                        part
                    ]

                final_key = parts[-1]

                old_value = (
                    copy.deepcopy(
                        current.get(
                            final_key
                        )
                    )
                )

                current[
                    final_key
                ] = copy.deepcopy(
                    value
                )

                self._record_change(
                    key=key,
                    old_value=old_value,
                    new_value=value,
                )

                if save:

                    result = self.save()

                    if not result.success:

                        return result

            return UserPreferencesResult(
                success=True,
                status="updated",
                message=(
                    "Preference updated."
                ),
                key=key,
                value=copy.deepcopy(
                    value
                ),
            )

        except Exception as exc:

            return UserPreferencesResult(
                success=False,
                status="set_error",
                message=(
                    "Could not update preference."
                ),
                key=key,
                errors=[
                    str(exc)
                ],
            )

    # ========================================================
    # DELETE
    # ========================================================

    def delete(
        self,
        key: str,
        *,
        save: bool = True,
    ) -> UserPreferencesResult:

        try:

            parts = self._split_key(
                key
            )

            with self._lock:

                current = (
                    self._preferences
                )

                for part in parts[:-1]:

                    if (
                        not isinstance(
                            current,
                            dict,
                        )
                        or part
                        not in current
                    ):

                        return UserPreferencesResult(
                            success=False,
                            status="not_found",
                            message=(
                                "Preference not found."
                            ),
                            key=key,
                        )

                    current = current[
                        part
                    ]

                final_key = parts[-1]

                if final_key not in current:

                    return UserPreferencesResult(
                        success=False,
                        status="not_found",
                        message=(
                            "Preference not found."
                        ),
                        key=key,
                    )

                old_value = (
                    current.pop(
                        final_key
                    )
                )

                self._record_change(
                    key=key,
                    old_value=old_value,
                    new_value=None,
                )

                if save:

                    result = self.save()

                    if not result.success:

                        return result

            return UserPreferencesResult(
                success=True,
                status="deleted",
                message=(
                    "Preference deleted."
                ),
                key=key,
                value=old_value,
            )

        except Exception as exc:

            return UserPreferencesResult(
                success=False,
                status="delete_error",
                message=(
                    "Could not delete preference."
                ),
                key=key,
                errors=[
                    str(exc)
                ],
            )

    # ========================================================
    # USER PROFILE
    # ========================================================

    def set_user_name(
        self,
        name: str,
    ) -> UserPreferencesResult:

        value = (
            name or ""
        ).strip()

        if len(value) > 100:

            return UserPreferencesResult(
                success=False,
                status="invalid",
                message=(
                    "User name is too long."
                ),
                key="profile.name",
            )

        return self.set(
            "profile.name",
            value,
        )

    def get_user_name(
        self,
    ) -> str:

        return str(
            self.get(
                "profile.name",
                "",
            )
        )

    def set_nickname(
        self,
        nickname: str,
    ) -> UserPreferencesResult:

        value = (
            nickname or ""
        ).strip()

        return self.set(
            "profile.nickname",
            value,
        )

    # ========================================================
    # LANGUAGE
    # ========================================================

    def set_language(
        self,
        language: str,
    ) -> UserPreferencesResult:

        try:

            normalized = (
                self.normalize_language(
                    language
                )
            )

            result = self.set(
                "profile.preferred_language",
                normalized,
                save=False,
            )

            if not result.success:

                return result

            result = self.set(
                "voice.language",
                normalized,
                save=True,
            )

            return result

        except ValueError as exc:

            return UserPreferencesResult(
                success=False,
                status="invalid_language",
                message=str(
                    exc
                ),
                key="profile.preferred_language",
                errors=[
                    str(exc)
                ],
            )

    def get_language(
        self,
    ) -> str:

        return str(
            self.get(
                "profile.preferred_language",
                "auto",
            )
        )

    # ========================================================
    # AI
    # ========================================================

    def set_ai_provider(
        self,
        provider: str,
    ) -> UserPreferencesResult:

        value = (
            provider or ""
        ).strip().lower()

        aliases = {
            "anthropic": "claude",
            "google": "gemini",
        }

        value = aliases.get(
            value,
            value,
        )

        if value not in (
            self.ALLOWED_AI_PROVIDERS
        ):

            return UserPreferencesResult(
                success=False,
                status="invalid_provider",
                message=(
                    "Unsupported AI provider."
                ),
                key="ai.provider",
                errors=[
                    (
                        "Allowed providers: "
                        "auto, openai, gemini, claude."
                    )
                ],
            )

        return self.set(
            "ai.provider",
            value,
        )

    def get_ai_provider(
        self,
    ) -> str:

        return str(
            self.get(
                "ai.provider",
                "auto",
            )
        )

    # ========================================================
    # THEME
    # ========================================================

    def set_theme(
        self,
        theme: str,
    ) -> UserPreferencesResult:

        value = (
            theme or ""
        ).strip().lower()

        if value not in (
            self.ALLOWED_THEMES
        ):

            return UserPreferencesResult(
                success=False,
                status="invalid_theme",
                message=(
                    "Theme must be system, light, or dark."
                ),
                key="ui.theme",
            )

        return self.set(
            "ui.theme",
            value,
        )

    def get_theme(
        self,
    ) -> str:

        return str(
            self.get(
                "ui.theme",
                "system",
            )
        )

    # ========================================================
    # VOICE
    # ========================================================

    def set_voice_enabled(
        self,
        enabled: bool,
    ) -> UserPreferencesResult:

        return self.set(
            "voice.enabled",
            bool(enabled),
        )

    def set_wake_word_enabled(
        self,
        enabled: bool,
    ) -> UserPreferencesResult:

        return self.set(
            "voice.wake_word_enabled",
            bool(enabled),
        )

    def set_wake_word(
        self,
        wake_word: str,
    ) -> UserPreferencesResult:

        value = (
            wake_word or ""
        ).strip().lower()

        if not value:

            return UserPreferencesResult(
                success=False,
                status="invalid",
                message=(
                    "Wake word cannot be empty."
                ),
                key="voice.wake_word",
            )

        if len(value) > 50:

            return UserPreferencesResult(
                success=False,
                status="invalid",
                message=(
                    "Wake word is too long."
                ),
                key="voice.wake_word",
            )

        return self.set(
            "voice.wake_word",
            value,
        )

    # ========================================================
    # PRIVACY
    # ========================================================

    def set_memory_enabled(
        self,
        enabled: bool,
    ) -> UserPreferencesResult:

        return self.set(
            "privacy.memory_enabled",
            bool(enabled),
        )

    def set_screen_access(
        self,
        enabled: bool,
    ) -> UserPreferencesResult:

        return self.set(
            "privacy.screen_access_enabled",
            bool(enabled),
        )

    def set_microphone_enabled(
        self,
        enabled: bool,
    ) -> UserPreferencesResult:

        return self.set(
            "privacy.microphone_enabled",
            bool(enabled),
        )

    # ========================================================
    # CONFIRMATION
    # ========================================================

    def set_confirmation_required(
        self,
        enabled: bool,
    ) -> UserPreferencesResult:

        return self.set(
            "behavior.confirmation_before_dangerous_actions",
            bool(enabled),
        )

    def confirmation_required(
        self,
    ) -> bool:

        return bool(
            self.get(
                "behavior.confirmation_before_dangerous_actions",
                True,
            )
        )

    # ========================================================
    # RESET
    # ========================================================

    def reset(
        self,
        key: Optional[str] = None,
        *,
        save: bool = True,
    ) -> UserPreferencesResult:

        try:

            if key is None:

                with self._lock:

                    old = copy.deepcopy(
                        self._preferences
                    )

                    self._preferences = (
                        copy.deepcopy(
                            self.DEFAULT_PREFERENCES
                        )
                    )

                    self._record_change(
                        key="*",
                        old_value=old,
                        new_value=(
                            self._preferences
                        ),
                    )

                    if save:

                        return self.save()

                return UserPreferencesResult(
                    success=True,
                    status="reset",
                    message=(
                        "All user preferences reset."
                    ),
                )

            default = self._get_default(
                key
            )

            if default is None:

                return self.delete(
                    key,
                    save=save,
                )

            return self.set(
                key,
                default,
                save=save,
            )

        except Exception as exc:

            return UserPreferencesResult(
                success=False,
                status="reset_error",
                message=(
                    "Could not reset preference."
                ),
                key=key or "",
                errors=[
                    str(exc)
                ],
            )

    def _get_default(
        self,
        key: str,
    ) -> Any:

        try:

            parts = self._split_key(
                key
            )

            current: Any = (
                self.DEFAULT_PREFERENCES
            )

            for part in parts:

                if not isinstance(
                    current,
                    dict,
                ):

                    return None

                if part not in current:

                    return None

                current = current[
                    part
                ]

            return copy.deepcopy(
                current
            )

        except Exception:

            return None

    # ========================================================
    # VALIDATION
    # ========================================================

    def validate(
        self,
    ) -> UserPreferencesResult:

        errors = []

        language = self.get_language()

        if language not in (
            self.ALLOWED_LANGUAGES
        ):

            errors.append(
                "Invalid preferred language."
            )

        theme = self.get_theme()

        if theme not in (
            self.ALLOWED_THEMES
        ):

            errors.append(
                "Invalid UI theme."
            )

        provider = (
            self.get_ai_provider()
        )

        if provider not in (
            self.ALLOWED_AI_PROVIDERS
        ):

            errors.append(
                "Invalid AI provider."
            )

        rate = self.get(
            "voice.speech_rate",
            175,
        )

        if not isinstance(
            rate,
            int,
        ) or not (
            50 <= rate <= 500
        ):

            errors.append(
                "Voice speech rate must be "
                "between 50 and 500."
            )

        volume = self.get(
            "voice.volume",
            1.0,
        )

        if not isinstance(
            volume,
            (int, float),
        ) or not (
            0.0 <= volume <= 1.0
        ):

            errors.append(
                "Voice volume must be "
                "between 0.0 and 1.0."
            )

        temperature = self.get(
            "ai.temperature",
            0.7,
        )

        if not isinstance(
            temperature,
            (int, float),
        ) or not (
            0.0 <= temperature <= 2.0
        ):

            errors.append(
                "AI temperature must be "
                "between 0.0 and 2.0."
            )

        if errors:

            return UserPreferencesResult(
                success=False,
                status="invalid",
                message=(
                    "User preferences are invalid."
                ),
                errors=errors,
            )

        return UserPreferencesResult(
            success=True,
            status="valid",
            message=(
                "User preferences are valid."
            ),
        )

    # ========================================================
    # EXPORT
    # ========================================================

    def export_file(
        self,
        destination: str | Path,
    ) -> UserPreferencesResult:

        target = (
            Path(
                destination
            )
            .expanduser()
            .resolve()
        )

        try:

            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with self._lock:

                data = copy.deepcopy(
                    self._preferences
                )

            temporary = (
                target.with_suffix(
                    ".tmp"
                )
            )

            with open(
                temporary,
                "w",
                encoding="utf-8",
            ) as file:

                json.dump(
                    data,
                    file,
                    indent=2,
                    ensure_ascii=False,
                )

                file.write(
                    "\n"
                )

            temporary.replace(
                target
            )

            return UserPreferencesResult(
                success=True,
                status="exported",
                message=(
                    "User preferences exported."
                ),
                data={
                    "path": str(
                        target
                    )
                },
            )

        except Exception as exc:

            return UserPreferencesResult(
                success=False,
                status="export_error",
                message=(
                    "Could not export preferences."
                ),
                errors=[
                    str(exc)
                ],
            )

    # ========================================================
    # CHANGE HISTORY
    # ========================================================

    def _record_change(
        self,
        *,
        key: str,
        old_value: Any,
        new_value: Any,
    ) -> None:

        self.history.append(
            {
                "key": key,
                "old_value": copy.deepcopy(
                    old_value
                ),
                "new_value": copy.deepcopy(
                    new_value
                ),
                "changed_at": (
                    self._utc_now()
                ),
            }
        )

        if (
            len(self.history)
            > self.max_history
        ):

            self.history = (
                self.history[
                    -self.max_history:
                ]
            )

    def get_history(
        self,
    ) -> list[Dict[str, Any]]:

        with self._lock:

            return copy.deepcopy(
                self.history
            )

    # ========================================================
    # ALL
    # ========================================================

    def all(
        self,
    ) -> Dict[str, Any]:

        with self._lock:

            return copy.deepcopy(
                self._preferences
            )

    # ========================================================
    # PROFILE
    # ========================================================

    def get_profile(
        self,
    ) -> UserProfile:

        data = self.get(
            "profile",
            {},
        )

        return UserProfile(
            name=str(
                data.get(
                    "name",
                    "",
                )
            ),
            nickname=str(
                data.get(
                    "nickname",
                    "",
                )
            ),
            preferred_language=str(
                data.get(
                    "preferred_language",
                    "auto",
                )
            ),
            timezone=str(
                data.get(
                    "timezone",
                    "",
                )
            ),
            response_style=str(
                data.get(
                    "response_style",
                    "friendly",
                )
            ),
        )

    def get_voice_preferences(
        self,
    ) -> VoicePreferences:

        data = self.get(
            "voice",
            {},
        )

        return VoicePreferences(
            enabled=bool(
                data.get(
                    "enabled",
                    True,
                )
            ),
            language=str(
                data.get(
                    "language",
                    "auto",
                )
            ),
            wake_word_enabled=bool(
                data.get(
                    "wake_word_enabled",
                    True,
                )
            ),
            wake_word=str(
                data.get(
                    "wake_word",
                    "jarvis",
                )
            ),
            speech_rate=int(
                data.get(
                    "speech_rate",
                    175,
                )
            ),
            volume=float(
                data.get(
                    "volume",
                    1.0,
                )
            ),
            voice_id=str(
                data.get(
                    "voice_id",
                    "",
                )
            ),
            interrupt_enabled=bool(
                data.get(
                    "interrupt_enabled",
                    True,
                )
            ),
        )

    # ========================================================
    # STATUS
    # ========================================================

    def get_status(
        self,
    ) -> Dict[str, Any]:

        validation = (
            self.validate()
        )

        return {
            "loaded": self.loaded,
            "path": str(
                self.preferences_path
            ),
            "exists": (
                self.preferences_path.exists()
            ),
            "valid": validation.success,
            "validation_errors": (
                validation.errors
            ),
            "user_name": (
                self.get_user_name()
            ),
            "language": (
                self.get_language()
            ),
            "ai_provider": (
                self.get_ai_provider()
            ),
            "theme": (
                self.get_theme()
            ),
            "voice_enabled": bool(
                self.get(
                    "voice.enabled",
                    True,
                )
            ),
            "wake_word_enabled": bool(
                self.get(
                    "voice.wake_word_enabled",
                    True,
                )
            ),
            "memory_enabled": bool(
                self.get(
                    "privacy.memory_enabled",
                    True,
                )
            ),
            "history_count": len(
                self.history
            ),
        }

    # ========================================================
    # CLOSE
    # ========================================================

    def close(
        self,
    ) -> None:

        self.save()

    def __enter__(
        self,
    ) -> "UserPreferences":

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback_value,
    ) -> None:

        self.close()


# ============================================================
# SHARED INSTANCE
# ============================================================

_user_preferences: Optional[
    UserPreferences
] = None

_user_preferences_lock = (
    threading.Lock()
)


def get_user_preferences() -> UserPreferences:

    global _user_preferences

    with _user_preferences_lock:

        if _user_preferences is None:

            _user_preferences = (
                UserPreferences()
            )

        return _user_preferences


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def get_preference(
    key: str,
    default: Any = None,
) -> Any:

    return (
        get_user_preferences()
        .get(
            key,
            default,
        )
    )


def set_preference(
    key: str,
    value: Any,
) -> UserPreferencesResult:

    return (
        get_user_preferences()
        .set(
            key,
            value,
        )
    )


def get_user_name() -> str:

    return (
        get_user_preferences()
        .get_user_name()
    )


def set_user_name(
    name: str,
) -> UserPreferencesResult:

    return (
        get_user_preferences()
        .set_user_name(
            name
        )
    )


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

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
    print(
        "JARVIS OS - USER PREFERENCES TEST"
    )
    print("=" * 60)

    test_path = (
        Path(__file__).resolve().parent
        / "user_preferences.test.json"
    )

    preferences = UserPreferences(
        preferences_path=test_path
    )

    print("\nDefault profile:")

    print(
        json.dumps(
            asdict(
                preferences.get_profile()
            ),
            indent=2,
            ensure_ascii=False,
        )
    )

    print("\nDefault voice settings:")

    print(
        json.dumps(
            asdict(
                preferences.get_voice_preferences()
            ),
            indent=2,
            ensure_ascii=False,
        )
    )

    print("\nValidation:")

    print(
        json.dumps(
            preferences.validate().to_dict(),
            indent=2,
            ensure_ascii=False,
        )
    )

    print("\nStatus:")

    print(
        json.dumps(
            preferences.get_status(),
            indent=2,
            ensure_ascii=False,
        )
    )

    preferences.close()

    try:

        if test_path.exists():

            test_path.unlink()

    except Exception:
        pass

    print(
        "\nUser preferences test completed."
  )
