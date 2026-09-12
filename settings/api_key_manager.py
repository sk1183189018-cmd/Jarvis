# settings/api_key_manager.py

"""
JARVIS OS - API KEY MANAGER
===========================

Secure local management of AI/provider API keys.

Supported providers:
- OpenAI
- Gemini
- Claude
- Picovoice
- Telegram
- Email

Features:
- Save API keys
- Read API keys
- Update/remove keys
- Environment-variable support
- Masked status
- Optional encrypted storage
- Import/export of configuration metadata
- Never exposes full keys in status output

Security:
- Keys are never logged.
- Export does NOT include raw API keys.
- Encryption uses Fernet when available.
- The encryption key itself should be protected by the
  operating system in a production application.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from cryptography.fernet import Fernet, InvalidToken

    CRYPTOGRAPHY_AVAILABLE = True

except ImportError:
    Fernet = None
    InvalidToken = Exception
    CRYPTOGRAPHY_AVAILABLE = False


logger = logging.getLogger(
    "JarvisOS.ApiKeyManager"
)


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class ApiKeyInfo:
    """Information about a stored API key."""

    provider: str

    environment_variable: str

    configured: bool = False

    source: str = "none"

    masked_key: str = ""

    updated_at: str = ""

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class ApiKeyResult:
    """Result of an API-key operation."""

    success: bool

    status: str

    message: str

    provider: str = ""

    configured: bool = False

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
        return {
            "success": self.success,
            "status": self.status,
            "message": self.message,
            "provider": self.provider,
            "configured": self.configured,
            "errors": self.errors,
            "warnings": self.warnings,
            "data": self.data,
        }


# ============================================================
# API KEY MANAGER
# ============================================================

class ApiKeyManager:
    """
    Central API-key manager for JarvisOS.

    Stored keys are encrypted when cryptography is available.

    Environment variables always take priority over stored
    values. This allows deployment through environment
    configuration without copying secrets into the database.
    """

    PROVIDERS = {
        "openai": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "google": "GEMINI_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "picovoice": "PICOVOICE_ACCESS_KEY",
        "telegram": "JARVIS_TELEGRAM_BOT_TOKEN",
        "email": "JARVIS_EMAIL_APP_PASSWORD",
    }

    STORAGE_FILE = "api_keys.enc"

    KEY_FILE = "api_keys.key"

    def __init__(
        self,
        storage_dir: Optional[
            str | Path
        ] = None,
    ):
        if storage_dir is None:

            self.storage_dir = (
                Path(__file__).resolve().parent
            )

        else:

            self.storage_dir = (
                Path(
                    storage_dir
                )
                .expanduser()
                .resolve()
            )

        self.storage_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.storage_path = (
            self.storage_dir
            / self.STORAGE_FILE
        )

        self.key_path = (
            self.storage_dir
            / self.KEY_FILE
        )

        self._lock = threading.RLock()

        self._keys: Dict[str, str] = {}

        self._metadata: Dict[
            str,
            Dict[str, Any],
        ] = {}

        self.history: list[
            ApiKeyResult
        ] = []

        self.max_history = 100

        self._fernet = None

        self._initialize_encryption()

        self._load()

    # ========================================================
    # PROVIDER NORMALIZATION
    # ========================================================

    @classmethod
    def normalize_provider(
        cls,
        provider: str,
    ) -> str:

        value = (
            provider or ""
        ).strip().lower()

        aliases = {
            "google": "gemini",
            "google_ai": "gemini",
            "anthropic": "claude",
            "picovoice_access": "picovoice",
            "telegram_bot": "telegram",
        }

        value = aliases.get(
            value,
            value,
        )

        if value not in cls.PROVIDERS:

            raise ValueError(
                f"Unsupported API-key provider: {provider}"
            )

        return value

    @classmethod
    def get_environment_variable(
        cls,
        provider: str,
    ) -> str:

        normalized = (
            cls.normalize_provider(
                provider
            )
        )

        return cls.PROVIDERS[
            normalized
        ]

    # ========================================================
    # ENCRYPTION
    # ========================================================

    def _initialize_encryption(
        self,
    ) -> None:

        if not CRYPTOGRAPHY_AVAILABLE:

            logger.warning(
                "cryptography is not installed. "
                "Encrypted API-key storage is unavailable."
            )

            return

        try:

            if self.key_path.exists():

                key = (
                    self.key_path.read_bytes()
                )

                self._fernet = (
                    Fernet(key)
                )

            else:

                key = Fernet.generate_key()

                self.key_path.write_bytes(
                    key
                )

                self._fernet = (
                    Fernet(key)
                )

                self._protect_file(
                    self.key_path
                )

        except Exception as exc:

            logger.error(
                "Could not initialize API-key encryption: %s",
                exc,
            )

            self._fernet = None

    @staticmethod
    def _protect_file(
        path: Path,
    ) -> None:

        try:

            path.chmod(
                0o600
            )

        except Exception:
            pass

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
    # MASKING
    # ========================================================

    @staticmethod
    def mask_key(
        value: str,
    ) -> str:

        if not value:
            return ""

        value = value.strip()

        if len(value) <= 8:

            return "*" * len(
                value
            )

        return (
            value[:4]
            + ("*" * max(
                4,
                len(value) - 8,
            ))
            + value[-4:]
        )

    # ========================================================
    # LOAD
    # ========================================================

    def _load(
        self,
    ) -> None:

        if not self.storage_path.exists():
            return

        try:

            raw = (
                self.storage_path.read_bytes()
            )

            if self._fernet is not None:

                decrypted = (
                    self._fernet.decrypt(
                        raw
                    )
                )

            else:

                # Legacy/plain storage fallback is supported
                # only so the application can migrate old
                # installations. New data is never intentionally
                # written here without encryption.
                decrypted = raw

            data = json.loads(
                decrypted.decode(
                    "utf-8"
                )
            )

            if not isinstance(
                data,
                dict,
            ):
                return

            keys = data.get(
                "keys",
                {},
            )

            metadata = data.get(
                "metadata",
                {},
            )

            if isinstance(
                keys,
                dict,
            ):

                self._keys = {
                    str(k): str(v)
                    for k, v in keys.items()
                    if isinstance(v, str)
                }

            if isinstance(
                metadata,
                dict,
            ):

                self._metadata = metadata

        except InvalidToken:

            logger.error(
                "API-key storage could not be decrypted."
            )

        except Exception as exc:

            logger.warning(
                "Could not load API-key storage: %s",
                exc,
            )

    # ========================================================
    # SAVE
    # ========================================================

    def _save(
        self,
    ) -> None:

        payload = {
            "version": 1,
            "updated_at": self._utc_now(),
            "keys": self._keys,
            "metadata": self._metadata,
        }

        raw = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
        ).encode(
            "utf-8"
        )

        if self._fernet is not None:

            data = (
                self._fernet.encrypt(
                    raw
                )
            )

        else:

            raise RuntimeError(
                "Encrypted API-key storage is unavailable. "
                "Install the cryptography package."
            )

        temporary = (
            self.storage_path.with_suffix(
                ".tmp"
            )
        )

        temporary.write_bytes(
            data
        )

        self._protect_file(
            temporary
        )

        temporary.replace(
            self.storage_path
        )

        self._protect_file(
            self.storage_path
        )

    # ========================================================
    # SET KEY
    # ========================================================

    def set_key(
        self,
        provider: str,
        api_key: str,
        *,
        overwrite: bool = True,
    ) -> ApiKeyResult:

        try:

            normalized = (
                self.normalize_provider(
                    provider
                )
            )

            value = (
                api_key or ""
            ).strip()

            if not value:

                return self._record(
                    ApiKeyResult(
                        success=False,
                        status="empty_key",
                        message=(
                            "API key cannot be empty."
                        ),
                        provider=normalized,
                        errors=[
                            "empty_api_key"
                        ],
                    )
                )

            with self._lock:

                if (
                    normalized in self._keys
                    and not overwrite
                ):

                    return self._record(
                        ApiKeyResult(
                            success=False,
                            status="already_configured",
                            message=(
                                "An API key is already "
                                "configured for this provider."
                            ),
                            provider=normalized,
                            configured=True,
                        )
                    )

                self._keys[
                    normalized
                ] = value

                self._metadata[
                    normalized
                ] = {
                    "environment_variable": (
                        self.get_environment_variable(
                            normalized
                        )
                    ),
                    "updated_at": (
                        self._utc_now()
                    ),
                    "source": "stored",
                    "fingerprint": (
                        hashlib.sha256(
                            value.encode(
                                "utf-8"
                            )
                        ).hexdigest()
                    ),
                }

                self._save()

            return self._record(
                ApiKeyResult(
                    success=True,
                    status="saved",
                    message=(
                        "API key saved securely."
                    ),
                    provider=normalized,
                    configured=True,
                    data={
                        "masked_key": (
                            self.mask_key(
                                value
                            )
                        ),
                    },
                )
            )

        except Exception as exc:

            return self._record(
                ApiKeyResult(
                    success=False,
                    status="save_error",
                    message=(
                        "Could not save API key."
                    ),
                    provider=(
                        str(provider)
                    ),
                    errors=[
                        str(exc)
                    ],
                )
            )

    # ========================================================
    # GET KEY
    # ========================================================

    def get_key(
        self,
        provider: str,
        *,
        allow_environment: bool = True,
    ) -> Optional[str]:

        try:

            normalized = (
                self.normalize_provider(
                    provider
                )
            )

        except ValueError:

            return None

        environment_variable = (
            self.get_environment_variable(
                normalized
            )
        )

        if allow_environment:

            environment_value = os.getenv(
                environment_variable
            )

            if environment_value:

                return (
                    environment_value.strip()
                )

        with self._lock:

            value = self._keys.get(
                normalized
            )

            return (
                value.strip()
                if value
                else None
            )

    # ========================================================
    # HAS KEY
    # ========================================================

    def has_key(
        self,
        provider: str,
    ) -> bool:

        return bool(
            self.get_key(
                provider
            )
        )

    # ========================================================
    # REMOVE
    # ========================================================

    def remove_key(
        self,
        provider: str,
        *,
        remove_environment: bool = False,
        confirm: bool = False,
    ) -> ApiKeyResult:

        try:

            normalized = (
                self.normalize_provider(
                    provider
                )
            )

            if not confirm:

                return self._record(
                    ApiKeyResult(
                        success=False,
                        status="confirmation_required",
                        message=(
                            "Removing an API key "
                            "requires confirmation."
                        ),
                        provider=normalized,
                        configured=(
                            self.has_key(
                                normalized
                            )
                        ),
                        errors=[
                            "confirmation_required"
                        ],
                    )
                )

            with self._lock:

                existed = (
                    normalized
                    in self._keys
                )

                self._keys.pop(
                    normalized,
                    None,
                )

                self._metadata.pop(
                    normalized,
                    None,
                )

                self._save()

            environment_variable = (
                self.get_environment_variable(
                    normalized
                )
            )

            if remove_environment:

                os.environ.pop(
                    environment_variable,
                    None,
                )

            return self._record(
                ApiKeyResult(
                    success=True,
                    status=(
                        "removed"
                        if existed
                        else "not_found"
                    ),
                    message=(
                        "API key removed."
                        if existed
                        else "No stored API key was found."
                    ),
                    provider=normalized,
                    configured=False,
                )
            )

        except Exception as exc:

            return self._record(
                ApiKeyResult(
                    success=False,
                    status="remove_error",
                    message=(
                        "Could not remove API key."
                    ),
                    provider=str(
                        provider
                    ),
                    errors=[
                        str(exc)
                    ],
                )
            )

    # ========================================================
    # ENVIRONMENT HELPERS
    # ========================================================

    def set_environment_key(
        self,
        provider: str,
        api_key: str,
    ) -> ApiKeyResult:

        try:

            normalized = (
                self.normalize_provider(
                    provider
                )
            )

            value = (
                api_key or ""
            ).strip()

            if not value:

                raise ValueError(
                    "API key cannot be empty."
                )

            environment_variable = (
                self.get_environment_variable(
                    normalized
                )
            )

            os.environ[
                environment_variable
            ] = value

            return self._record(
                ApiKeyResult(
                    success=True,
                    status="environment_set",
                    message=(
                        "API key loaded into the "
                        "current process environment."
                    ),
                    provider=normalized,
                    configured=True,
                )
            )

        except Exception as exc:

            return self._record(
                ApiKeyResult(
                    success=False,
                    status="environment_error",
                    message=(
                        "Could not set environment API key."
                    ),
                    provider=str(
                        provider
                    ),
                    errors=[
                        str(exc)
                    ],
                )
            )

    # ========================================================
    # INFO
    # ========================================================

    def get_info(
        self,
        provider: str,
    ) -> ApiKeyInfo:

        normalized = (
            self.normalize_provider(
                provider
            )
        )

        environment_variable = (
            self.get_environment_variable(
                normalized
            )
        )

        environment_value = os.getenv(
            environment_variable
        )

        stored_value = (
            self._keys.get(
                normalized
            )
        )

        if environment_value:

            source = "environment"

            value = (
                environment_value
            )

        elif stored_value:

            source = "stored"

            value = (
                stored_value
            )

        else:

            source = "none"

            value = ""

        metadata = dict(
            self._metadata.get(
                normalized,
                {},
            )
        )

        metadata.pop(
            "fingerprint",
            None,
        )

        return ApiKeyInfo(
            provider=normalized,
            environment_variable=(
                environment_variable
            ),
            configured=bool(
                value
            ),
            source=source,
            masked_key=(
                self.mask_key(
                    value
                )
            ),
            updated_at=str(
                metadata.get(
                    "updated_at",
                    "",
                )
            ),
            metadata=metadata,
        )

    # ========================================================
    # LIST
    # ========================================================

    def list_providers(
        self,
    ) -> list[ApiKeyInfo]:

        result = []

        for provider in sorted(
            set(
                self.PROVIDERS.keys()
            )
        ):

            # Hide aliases from the main list.
            if provider in {
                "google",
                "anthropic",
            }:

                continue

            result.append(
                self.get_info(
                    provider
                )
            )

        return result

    # ========================================================
    # STATUS
    # ========================================================

    def get_status(
        self,
    ) -> Dict[str, Any]:

        providers = {}

        for info in self.list_providers():

            providers[
                info.provider
            ] = {
                "configured": (
                    info.configured
                ),
                "source": info.source,
                "masked_key": (
                    info.masked_key
                ),
                "environment_variable": (
                    info.environment_variable
                ),
                "updated_at": (
                    info.updated_at
                ),
            }

        return {
            "cryptography_available": (
                CRYPTOGRAPHY_AVAILABLE
            ),
            "encrypted_storage_available": (
                self._fernet is not None
            ),
            "storage_file": str(
                self.storage_path
            ),
            "key_file": str(
                self.key_path
            ),
            "providers": providers,
            "history_count": len(
                self.history
            ),
        }

    # ========================================================
    # EXPORT SAFE CONFIG
    # ========================================================

    def export_metadata(
        self,
        output_path: str | Path,
    ) -> ApiKeyResult:

        destination = (
            Path(
                output_path
            )
            .expanduser()
            .resolve()
        )

        try:

            providers = {}

            for info in self.list_providers():

                providers[
                    info.provider
                ] = {
                    "configured": (
                        info.configured
                    ),
                    "source": info.source,
                    "masked_key": (
                        info.masked_key
                    ),
                    "environment_variable": (
                        info.environment_variable
                    ),
                    "updated_at": (
                        info.updated_at
                    ),
                }

            payload = {
                "product": "JarvisOS",
                "exported_at": (
                    self._utc_now()
                ),
                "providers": providers,
            }

            destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with open(
                destination,
                "w",
                encoding="utf-8",
            ) as file:

                json.dump(
                    payload,
                    file,
                    indent=2,
                    ensure_ascii=False,
                )

            return self._record(
                ApiKeyResult(
                    success=True,
                    status="exported",
                    message=(
                        "Safe API-key metadata exported."
                    ),
                    data={
                        "path": str(
                            destination
                        )
                    },
                )
            )

        except Exception as exc:

            return self._record(
                ApiKeyResult(
                    success=False,
                    status="export_error",
                    message=(
                        "Could not export API-key metadata."
                    ),
                    errors=[
                        str(exc)
                    ],
                )
            )

    # ========================================================
    # HISTORY
    # ========================================================

    def _record(
        self,
        result: ApiKeyResult,
    ) -> ApiKeyResult:

        with self._lock:

            self.history.append(
                result
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

        return result

    def get_history(
        self,
    ) -> list[ApiKeyResult]:

        with self._lock:

            return list(
                self.history
            )

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self) -> None:
        """
        Clear in-memory API keys.

        Persistent encrypted storage remains available for
        the next application start.
        """

        with self._lock:

            self._keys.clear()

    def __enter__(
        self,
    ) -> "ApiKeyManager":

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

_api_key_manager: Optional[
    ApiKeyManager
] = None

_api_key_manager_lock = (
    threading.Lock()
)


def get_api_key_manager() -> ApiKeyManager:

    global _api_key_manager

    with _api_key_manager_lock:

        if _api_key_manager is None:

            _api_key_manager = (
                ApiKeyManager()
            )

        return _api_key_manager


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def get_api_key(
    provider: str,
) -> Optional[str]:

    return (
        get_api_key_manager()
        .get_key(provider)
    )


def set_api_key(
    provider: str,
    api_key: str,
) -> ApiKeyResult:

    return (
        get_api_key_manager()
        .set_key(
            provider,
            api_key,
        )
    )


def has_api_key(
    provider: str,
) -> bool:

    return (
        get_api_key_manager()
        .has_key(provider)
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
        "JARVIS OS - API KEY MANAGER TEST"
    )
    print("=" * 60)

    manager = ApiKeyManager()

    print("\nStatus:")

    print(
        json.dumps(
            manager.get_status(),
            indent=2,
            ensure_ascii=False,
        )
    )

    print("\nConfigured providers:")

    for info in manager.list_providers():

        print(
            f"- {info.provider}: "
            f"{'YES' if info.configured else 'NO'} "
            f"({info.source})"
        )

    print(
        "\nNo API key is created or printed "
        "during this test."
    )

    manager.close()

    print(
        "\nAPI key manager test completed."
  )
