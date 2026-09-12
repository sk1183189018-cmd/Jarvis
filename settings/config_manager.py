# settings/config_manager.py

"""
JARVIS OS - CONFIG MANAGER
==========================

Central configuration manager.

Features:
- JSON configuration storage
- Nested configuration values
- Environment variable support
- Default configuration
- Get / set / delete values
- Dot-notation access
- Configuration validation
- Import / export
- Atomic writes
- Change history
- Thread-safe access

Examples:
    config.get("ai.provider")
    config.set("ai.provider", "openai")
    config.get("voice.language")
"""

from __future__ import annotations

import copy
import json
import logging
import os
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


logger = logging.getLogger(
    "JarvisOS.ConfigManager"
)


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class ConfigChange:
    """Represents one configuration change."""

    key: str

    old_value: Any

    new_value: Any

    changed_at: str

    source: str = "application"


@dataclass
class ConfigResult:
    """Result of a configuration operation."""

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
# CONFIG MANAGER
# ============================================================

class ConfigManager:
    """
    Central JarvisOS configuration manager.

    Configuration is stored as JSON.

    Dot notation:

        ai.provider
        ai.model
        voice.language
        voice.enabled
        security.require_confirmation

    Environment variables can override selected values.

    Example:

        JARVIS_AI_PROVIDER=openai

    becomes:

        ai.provider = "openai"
    """

    DEFAULT_CONFIG: Dict[str, Any] = {

        "app": {
            "name": "JarvisOS",
            "version": "1.0.0",
            "language": "auto",
            "startup": True,
            "debug": False,
        },

        "ai": {
            "provider": "auto",
            "model": "",
            "temperature": 0.7,
            "max_tokens": 2048,
            "fallback_enabled": True,
        },

        "voice": {
            "enabled": True,
            "language": "auto",
            "wake_word_enabled": True,
            "wake_word": "jarvis",
            "speech_timeout": 5,
            "phrase_time_limit": 15,
            "tts_enabled": True,
            "tts_rate": 175,
            "tts_volume": 1.0,
        },

        "memory": {
            "enabled": True,
            "short_term_limit": 20,
            "auto_save": True,
            "save_conversations": True,
        },

        "security": {
            "require_confirmation": True,
            "allow_file_delete": False,
            "allow_system_shutdown": False,
            "allow_remote_commands": False,
            "allow_plugins": True,
            "allow_code_execution": False,
        },

        "web": {
            "enabled": True,
            "provider": "duckduckgo",
            "timeout": 15,
            "max_results": 10,
        },

        "vision": {
            "enabled": True,
            "ocr_enabled": True,
            "object_detection_enabled": False,
        },

        "mobile": {
            "android_enabled": False,
            "adb_path": "",
        },

        "communication": {
            "email_enabled": False,
            "whatsapp_enabled": False,
            "telegram_enabled": False,
            "sms_enabled": False,
        },

        "plugins": {
            "enabled": True,
            "auto_load": False,
            "allow_external": False,
        },

        "updates": {
            "enabled": True,
            "automatic": False,
            "check_interval_hours": 24,
        },

        "ui": {
            "theme": "system",
            "start_minimized": False,
            "show_notifications": True,
        },

        "logging": {
            "level": "INFO",
            "max_file_size_mb": 10,
            "backup_count": 5,
        },
    }

    # ========================================================
    # ENVIRONMENT MAPPING
    # ========================================================

    ENVIRONMENT_MAP = {
        "JARVIS_DEBUG": "app.debug",

        "JARVIS_LANGUAGE": "app.language",

        "AI_PROVIDER": "ai.provider",
        "AI_MODEL": "ai.model",

        "JARVIS_VOICE_ENABLED": "voice.enabled",
        "JARVIS_VOICE_LANGUAGE": "voice.language",

        "JARVIS_WAKEWORD_ENABLED":
            "voice.wake_word_enabled",

        "JARVIS_WAKEWORD_KEYWORD":
            "voice.wake_word",

        "JARVIS_MEMORY_ENABLED":
            "memory.enabled",

        "JARVIS_REQUIRE_CONFIRMATION":
            "security.require_confirmation",

        "JARVIS_WEB_ENABLED":
            "web.enabled",

        "JARVIS_WEB_PROVIDER":
            "web.provider",

        "JARVIS_UI_THEME":
            "ui.theme",

        "JARVIS_LOG_LEVEL":
            "logging.level",
    }

    # ========================================================
    # CONSTRUCTOR
    # ========================================================

    def __init__(
        self,
        config_path: Optional[
            str | Path
        ] = None,
        *,
        auto_create: bool = True,
        load_environment: bool = True,
    ):
        if config_path is None:

            self.config_path = (
                Path(__file__).resolve().parent
                / "config.json"
            )

        else:

            self.config_path = (
                Path(
                    config_path
                )
                .expanduser()
                .resolve()
            )

        self.config_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._lock = threading.RLock()

        self._config: Dict[str, Any] = (
            copy.deepcopy(
                self.DEFAULT_CONFIG
            )
        )

        self.history: list[
            ConfigChange
        ] = []

        self.max_history = 200

        self.loaded = False

        if self.config_path.exists():

            self.load()

        elif auto_create:

            self.save()

        if load_environment:

            self.apply_environment()

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
            )
            .isoformat()
        )

    # ========================================================
    # LOAD
    # ========================================================

    def load(
        self,
    ) -> ConfigResult:

        try:

            with self._lock:

                with open(
                    self.config_path,
                    "r",
                    encoding="utf-8",
                ) as file:

                    loaded = json.load(
                        file
                    )

                if not isinstance(
                    loaded,
                    dict,
                ):

                    raise ValueError(
                        "Configuration root must be a JSON object."
                    )

                self._config = (
                    self._deep_merge(
                        copy.deepcopy(
                            self.DEFAULT_CONFIG
                        ),
                        loaded,
                    )
                )

                self.loaded = True

            return ConfigResult(
                success=True,
                status="loaded",
                message=(
                    "Configuration loaded successfully."
                ),
                data={
                    "path": str(
                        self.config_path
                    )
                },
            )

        except Exception as exc:

            logger.error(
                "Configuration load failed: %s",
                exc,
            )

            return ConfigResult(
                success=False,
                status="load_error",
                message=(
                    "Could not load configuration."
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
    ) -> ConfigResult:

        try:

            with self._lock:

                payload = copy.deepcopy(
                    self._config
                )

                temporary = (
                    self.config_path.with_suffix(
                        ".tmp"
                    )
                )

                with open(
                    temporary,
                    "w",
                    encoding="utf-8",
                ) as file:

                    json.dump(
                        payload,
                        file,
                        indent=2,
                        ensure_ascii=False,
                    )

                    file.write(
                        "\n"
                    )

                temporary.replace(
                    self.config_path
                )

            return ConfigResult(
                success=True,
                status="saved",
                message=(
                    "Configuration saved successfully."
                ),
                data={
                    "path": str(
                        self.config_path
                    )
                },
            )

        except Exception as exc:

            logger.error(
                "Configuration save failed: %s",
                exc,
            )

            return ConfigResult(
                success=False,
                status="save_error",
                message=(
                    "Could not save configuration."
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
    # DOT-NOTATION HELPERS
    # ========================================================

    @staticmethod
    def _split_key(
        key: str,
    ) -> list[str]:

        normalized = (
            key or ""
        ).strip()

        if not normalized:

            raise ValueError(
                "Configuration key cannot be empty."
            )

        parts = [
            part.strip()
            for part in normalized.split(".")
        ]

        if any(
            not part
            for part in parts
        ):

            raise ValueError(
                f"Invalid configuration key: {key}"
            )

        return parts

    # ========================================================
    # GET
    # ========================================================

    def get(
        self,
        key: str,
        default: Any = None,
        *,
        environment_override: bool = True,
    ) -> Any:

        try:

            parts = self._split_key(
                key
            )

        except ValueError:

            return default

        with self._lock:

            current: Any = (
                self._config
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

            value = copy.deepcopy(
                current
            )

        if environment_override:

            environment_name = (
                self._environment_for_key(
                    key
                )
            )

            if environment_name:

                raw = os.getenv(
                    environment_name
                )

                if raw is not None:

                    return (
                        self._parse_environment_value(
                            raw,
                            value,
                        )
                    )

        return value

    # ========================================================
    # SET
    # ========================================================

    def set(
        self,
        key: str,
        value: Any,
        *,
        save: bool = True,
        source: str = "application",
    ) -> ConfigResult:

        try:

            parts = self._split_key(
                key
            )

            with self._lock:

                current = (
                    self._config
                )

                for part in parts[:-1]:

                    if part not in current:

                        current[part] = {}

                    if not isinstance(
                        current[part],
                        dict,
                    ):

                        raise ValueError(
                            f"Cannot create nested key under "
                            f"non-object value: {part}"
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

                new_value = (
                    copy.deepcopy(
                        value
                    )
                )

                current[
                    final_key
                ] = new_value

                self._record_change(
                    ConfigChange(
                        key=key,
                        old_value=old_value,
                        new_value=new_value,
                        changed_at=(
                            self._utc_now()
                        ),
                        source=source,
                    )
                )

                if save:

                    save_result = (
                        self.save()
                    )

                    if not save_result.success:

                        return save_result

            return ConfigResult(
                success=True,
                status="updated",
                message=(
                    "Configuration value updated."
                ),
                key=key,
                value=copy.deepcopy(
                    value
                ),
            )

        except Exception as exc:

            return ConfigResult(
                success=False,
                status="set_error",
                message=(
                    "Could not update configuration."
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
    ) -> ConfigResult:

        try:

            parts = self._split_key(
                key
            )

            with self._lock:

                current = (
                    self._config
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

                        return ConfigResult(
                            success=False,
                            status="not_found",
                            message=(
                                "Configuration key not found."
                            ),
                            key=key,
                        )

                    current = current[
                        part
                    ]

                final_key = parts[-1]

                if final_key not in current:

                    return ConfigResult(
                        success=False,
                        status="not_found",
                        message=(
                            "Configuration key not found."
                        ),
                        key=key,
                    )

                old_value = (
                    current.pop(
                        final_key
                    )
                )

                self._record_change(
                    ConfigChange(
                        key=key,
                        old_value=(
                            copy.deepcopy(
                                old_value
                            )
                        ),
                        new_value=None,
                        changed_at=(
                            self._utc_now()
                        ),
                        source="application",
                    )
                )

                if save:

                    save_result = (
                        self.save()
                    )

                    if not save_result.success:

                        return save_result

            return ConfigResult(
                success=True,
                status="deleted",
                message=(
                    "Configuration value deleted."
                ),
                key=key,
                value=old_value,
            )

        except Exception as exc:

            return ConfigResult(
                success=False,
                status="delete_error",
                message=(
                    "Could not delete configuration value."
                ),
                key=key,
                errors=[
                    str(exc)
                ],
            )

    # ========================================================
    # HAS
    # ========================================================

    def has(
        self,
        key: str,
    ) -> bool:

        sentinel = object()

        return (
            self.get(
                key,
                sentinel,
                environment_override=False,
            )
            is not sentinel
        )

    # ========================================================
    # RESET
    # ========================================================

    def reset(
        self,
        key: Optional[str] = None,
        *,
        save: bool = True,
    ) -> ConfigResult:

        if key is None:

            with self._lock:

                old = copy.deepcopy(
                    self._config
                )

                self._config = (
                    copy.deepcopy(
                        self.DEFAULT_CONFIG
                    )
                )

                self._record_change(
                    ConfigChange(
                        key="*",
                        old_value=old,
                        new_value=(
                            copy.deepcopy(
                                self._config
                            )
                        ),
                        changed_at=(
                            self._utc_now()
                        ),
                        source="reset",
                    )
                )

                if save:

                    return self.save()

            return ConfigResult(
                success=True,
                status="reset",
                message=(
                    "All configuration reset to defaults."
                ),
            )

        # Reset one key to its default value.
        default_value = self._get_from_dict(
            self.DEFAULT_CONFIG,
            key,
        )

        if default_value is None:

            return self.delete(
                key,
                save=save,
            )

        return self.set(
            key,
            default_value,
            save=save,
            source="reset",
        )

    # ========================================================
    # DEFAULT VALUE LOOKUP
    # ========================================================

    @classmethod
    def _get_from_dict(
        cls,
        data: Dict[str, Any],
        key: str,
    ) -> Any:

        try:

            parts = cls._split_key(
                key
            )

        except ValueError:

            return None

        current: Any = data

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

    # ========================================================
    # ENVIRONMENT
    # ========================================================

    @classmethod
    def _environment_for_key(
        cls,
        key: str,
    ) -> Optional[str]:

        normalized = (
            key.strip()
        )

        for env_name, mapped_key in (
            cls.ENVIRONMENT_MAP.items()
        ):

            if mapped_key == normalized:

                return env_name

        return None

    @staticmethod
    def _parse_environment_value(
        raw: str,
        current_value: Any,
    ) -> Any:

        value = raw.strip()

        if isinstance(
            current_value,
            bool,
        ):

            return value.lower() in {
                "1",
                "true",
                "yes",
                "on",
                "enabled",
            }

        if isinstance(
            current_value,
            int,
        ) and not isinstance(
            current_value,
            bool,
        ):

            try:

                return int(
                    value
                )

            except ValueError:

                return current_value

        if isinstance(
            current_value,
            float,
        ):

            try:

                return float(
                    value
                )

            except ValueError:

                return current_value

        if isinstance(
            current_value,
            (dict, list),
        ):

            try:

                return json.loads(
                    value
                )

            except Exception:

                return current_value

        return value

    def apply_environment(
        self,
    ) -> None:

        for environment_name, key in (
            self.ENVIRONMENT_MAP.items()
        ):

            raw = os.getenv(
                environment_name
            )

            if raw is None:
                continue

            current = self.get(
                key,
                None,
                environment_override=False,
            )

            parsed = (
                self._parse_environment_value(
                    raw,
                    current,
                )
            )

            with self._lock:

                parts = self._split_key(
                    key
                )

                target = (
                    self._config
                )

                for part in parts[:-1]:

                    if not isinstance(
                        target.get(
                            part
                        ),
                        dict,
                    ):

                        target[
                            part
                        ] = {}

                    target = target[
                        part
                    ]

                target[
                    parts[-1]
                ] = parsed

    # ========================================================
    # VALIDATION
    # ========================================================

    def validate(
        self,
    ) -> ConfigResult:

        errors = []

        checks = [
            (
                "ai.temperature",
                0.0,
                2.0,
            ),
            (
                "ai.max_tokens",
                1,
                1_000_000,
            ),
            (
                "voice.speech_timeout",
                0,
                120,
            ),
            (
                "voice.phrase_time_limit",
                1,
                300,
            ),
            (
                "voice.tts_rate",
                50,
                500,
            ),
            (
                "voice.tts_volume",
                0.0,
                1.0,
            ),
            (
                "web.timeout",
                1,
                300,
            ),
            (
                "web.max_results",
                1,
                100,
            ),
        ]

        for key, minimum, maximum in checks:

            value = self.get(
                key,
                None,
            )

            if value is None:

                errors.append(
                    f"{key} is missing."
                )

                continue

            if not isinstance(
                value,
                (int, float),
            ):

                errors.append(
                    f"{key} must be numeric."
                )

                continue

            if not (
                minimum
                <= value
                <= maximum
            ):

                errors.append(
                    f"{key} must be between "
                    f"{minimum} and {maximum}."
                )

        ai_provider = self.get(
            "ai.provider"
        )

        if ai_provider not in {
            "auto",
            "openai",
            "gemini",
            "claude",
        }:

            errors.append(
                "ai.provider must be "
                "auto, openai, gemini, or claude."
            )

        theme = self.get(
            "ui.theme"
        )

        if theme not in {
            "system",
            "light",
            "dark",
        }:

            errors.append(
                "ui.theme must be "
                "system, light, or dark."
            )

        if errors:

            return ConfigResult(
                success=False,
                status="invalid",
                message=(
                    "Configuration validation failed."
                ),
                errors=errors,
            )

        return ConfigResult(
            success=True,
            status="valid",
            message=(
                "Configuration is valid."
            ),
        )

    # ========================================================
    # GET ALL
    # ========================================================

    def all(
        self,
    ) -> Dict[str, Any]:

        with self._lock:

            return copy.deepcopy(
                self._config
            )

    # ========================================================
    # SECTION
    # ========================================================

    def get_section(
        self,
        section: str,
    ) -> Dict[str, Any]:

        value = self.get(
            section,
            {},
            environment_override=False,
        )

        if not isinstance(
            value,
            dict,
        ):

            return {}

        return value

    # ========================================================
    # IMPORT
    # ========================================================

    def import_file(
        self,
        source_path: str | Path,
        *,
        merge: bool = True,
        save: bool = True,
    ) -> ConfigResult:

        source = (
            Path(
                source_path
            )
            .expanduser()
            .resolve()
        )

        try:

            with open(
                source,
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
                    "Imported configuration must be a JSON object."
                )

            with self._lock:

                old = copy.deepcopy(
                    self._config
                )

                if merge:

                    self._config = (
                        self._deep_merge(
                            self._config,
                            data,
                        )
                    )

                else:

                    self._config = (
                        self._deep_merge(
                            copy.deepcopy(
                                self.DEFAULT_CONFIG
                            ),
                            data,
                        )
                    )

                self._record_change(
                    ConfigChange(
                        key="*",
                        old_value=old,
                        new_value=(
                            copy.deepcopy(
                                self._config
                            )
                        ),
                        changed_at=(
                            self._utc_now()
                        ),
                        source="import",
                    )
                )

                if save:

                    save_result = (
                        self.save()
                    )

                    if not save_result.success:

                        return save_result

            return ConfigResult(
                success=True,
                status="imported",
                message=(
                    "Configuration imported successfully."
                ),
                data={
                    "source": str(
                        source
                    )
                },
            )

        except Exception as exc:

            return ConfigResult(
                success=False,
                status="import_error",
                message=(
                    "Could not import configuration."
                ),
                errors=[
                    str(exc)
                ],
            )

    # ========================================================
    # EXPORT
    # ========================================================

    def export_file(
        self,
        destination_path: str | Path,
        *,
        include_defaults: bool = True,
    ) -> ConfigResult:

        destination = (
            Path(
                destination_path
            )
            .expanduser()
            .resolve()
        )

        try:

            if include_defaults:

                data = copy.deepcopy(
                    self._config
                )

            else:

                data = copy.deepcopy(
                    self._config
                )

            destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            temporary = (
                destination.with_suffix(
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
                destination
            )

            return ConfigResult(
                success=True,
                status="exported",
                message=(
                    "Configuration exported successfully."
                ),
                data={
                    "path": str(
                        destination
                    )
                },
            )

        except Exception as exc:

            return ConfigResult(
                success=False,
                status="export_error",
                message=(
                    "Could not export configuration."
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
        change: ConfigChange,
    ) -> None:

        self.history.append(
            change
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
    ) -> list[ConfigChange]:

        with self._lock:

            return list(
                self.history
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
            "config_path": str(
                self.config_path
            ),
            "exists": (
                self.config_path.exists()
            ),
            "valid": validation.success,
            "validation_errors": (
                validation.errors
            ),
            "history_count": len(
                self.history
            ),
            "environment_overrides": {
                name: key
                for name, key in (
                    self.ENVIRONMENT_MAP.items()
                )
                if os.getenv(name) is not None
            },
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
    ) -> "ConfigManager":

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

_config_manager: Optional[
    ConfigManager
] = None

_config_manager_lock = (
    threading.Lock()
)


def get_config_manager() -> ConfigManager:

    global _config_manager

    with _config_manager_lock:

        if _config_manager is None:

            _config_manager = (
                ConfigManager()
            )

        return _config_manager


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def get_config(
    key: str,
    default: Any = None,
) -> Any:

    return (
        get_config_manager()
        .get(
            key,
            default,
        )
    )


def set_config(
    key: str,
    value: Any,
) -> ConfigResult:

    return (
        get_config_manager()
        .set(
            key,
            value,
        )
    )


def save_config() -> ConfigResult:

    return (
        get_config_manager()
        .save()
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
        "JARVIS OS - CONFIG MANAGER TEST"
    )
    print("=" * 60)

    manager = ConfigManager(
        config_path=(
            Path(__file__).resolve().parent
            / "config.test.json"
        )
    )

    print("\nAI Provider:")

    print(
        manager.get(
            "ai.provider"
        )
    )

    print("\nVoice language:")

    print(
        manager.get(
            "voice.language"
        )
    )

    print("\nConfiguration validation:")

    print(
        json.dumps(
            manager.validate().to_dict(),
            indent=2,
            ensure_ascii=False,
        )
    )

    print("\nStatus:")

    print(
        json.dumps(
            manager.get_status(),
            indent=2,
            ensure_ascii=False,
        )
    )

    print(
        "\nConfig manager test completed."
    )

    # Test file cleanup.
    test_path = (
        Path(__file__).resolve().parent
        / "config.test.json"
    )

    try:

        if test_path.exists():

            test_path.unlink()

    except Exception:
        pass

    manager.close()
