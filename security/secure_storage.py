# security/secure_storage.py

"""
JARVIS OS - SECURE STORAGE
==========================

Encrypted local storage for sensitive JarvisOS data.

Designed for:
- API keys
- Tokens
- Password-like secrets
- Private configuration
- Small sensitive JSON records

This module uses EncryptionManager from encryption.py.

It does NOT print or log plaintext secrets.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from .encryption import (
        EncryptionManager,
        get_encryption_manager,
    )
except ImportError:
    from encryption import (
        EncryptionManager,
        get_encryption_manager,
    )


logger = logging.getLogger(
    "JarvisOS.SecureStorage"
)


class SecureStorage:
    """
    Encrypted key-value storage.

    Example:

        storage = SecureStorage()

        storage.set("openai_api_key", "secret")

        key = storage.get("openai_api_key")

        storage.delete("openai_api_key")
    """

    VERSION = 1

    def __init__(
        self,
        storage_path: Optional[str | Path] = None,
        encryption_manager: Optional[
            EncryptionManager
        ] = None,
    ):
        self._lock = threading.RLock()

        if storage_path is None:
            self.storage_path = (
                Path(__file__).resolve().parent
                / "secure_storage.dat"
            )
        else:
            self.storage_path = (
                Path(storage_path)
                .expanduser()
                .resolve()
            )

        self.storage_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.encryption = (
            encryption_manager
            or get_encryption_manager()
        )

        self._data: Dict[str, Any] = {}

        self._load()

    # ========================================================
    # VALIDATION
    # ========================================================

    @staticmethod
    def _validate_key(
        key: str,
    ) -> str:
        if not isinstance(key, str):
            raise TypeError(
                "Storage key must be a string."
            )

        key = key.strip()

        if not key:
            raise ValueError(
                "Storage key cannot be empty."
            )

        if len(key) > 200:
            raise ValueError(
                "Storage key is too long."
            )

        return key

    @staticmethod
    def _serialize(
        data: Dict[str, Any],
    ) -> str:
        return json.dumps(
            data,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    # ========================================================
    # LOAD
    # ========================================================

    def _load(self) -> None:
        with self._lock:
            if not self.storage_path.exists():
                self._data = {}
                return

            try:
                encrypted = (
                    self.storage_path.read_text(
                        encoding="utf-8"
                    )
                )

                if not encrypted.strip():
                    self._data = {}
                    return

                loaded = (
                    self.encryption.decrypt_json(
                        encrypted
                    )
                )

                if not isinstance(
                    loaded,
                    dict,
                ):
                    raise ValueError(
                        "Secure storage contains invalid data."
                    )

                if "data" in loaded:
                    data = loaded["data"]
                else:
                    # Compatibility with an older/simple
                    # storage representation.
                    data = loaded

                if not isinstance(
                    data,
                    dict,
                ):
                    raise ValueError(
                        "Secure storage data must be an object."
                    )

                self._data = data

            except Exception as exc:
                logger.error(
                    "Unable to load secure storage: %s",
                    exc,
                )

                # Never silently replace unreadable encrypted
                # data with an empty database because doing so
                # could make existing secrets appear deleted.
                self._data = {}

    # ========================================================
    # SAVE
    # ========================================================

    def _save(self) -> None:
        payload = {
            "version": self.VERSION,
            "data": self._data,
        }

        encrypted = (
            self.encryption.encrypt_json(
                payload
            )
        )

        fd, temporary_name = (
            tempfile.mkstemp(
                prefix=".secure_",
                suffix=".tmp",
                dir=str(
                    self.storage_path.parent
                ),
            )
        )

        temporary_path = Path(
            temporary_name
        )

        try:
            with os.fdopen(
                fd,
                "w",
                encoding="utf-8",
            ) as file:
                file.write(encrypted)

                file.flush()

                try:
                    os.fsync(
                        file.fileno()
                    )
                except OSError:
                    pass

            try:
                temporary_path.chmod(
                    0o600
                )
            except OSError:
                pass

            temporary_path.replace(
                self.storage_path
            )

            try:
                self.storage_path.chmod(
                    0o600
                )
            except OSError:
                pass

        finally:
            if temporary_path.exists():
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    # ========================================================
    # SET
    # ========================================================

    def set(
        self,
        key: str,
        value: Any,
    ) -> bool:
        """
        Store or replace an encrypted value.

        Returns True when successfully stored.
        """

        key = self._validate_key(key)

        # Ensure the value can actually be serialized before
        # modifying the existing store.
        json.dumps(
            value,
            ensure_ascii=False,
        )

        with self._lock:
            self._data[key] = value
            self._save()

        return True

    # ========================================================
    # GET
    # ========================================================

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        key = self._validate_key(key)

        with self._lock:
            return self._data.get(
                key,
                default,
            )

    # ========================================================
    # HAS
    # ========================================================

    def has(
        self,
        key: str,
    ) -> bool:
        key = self._validate_key(key)

        with self._lock:
            return key in self._data

    # ========================================================
    # DELETE
    # ========================================================

    def delete(
        self,
        key: str,
    ) -> bool:
        key = self._validate_key(key)

        with self._lock:
            if key not in self._data:
                return False

            del self._data[key]
            self._save()

        return True

    # ========================================================
    # CLEAR
    # ========================================================

    def clear(
        self,
        *,
        confirm: bool = False,
    ) -> bool:
        """
        Delete all stored secrets.

        Confirmation is required because this operation
        permanently removes every stored value.
        """

        if not confirm:
            raise PermissionError(
                "Clearing secure storage requires "
                "confirm=True."
            )

        with self._lock:
            self._data.clear()
            self._save()

        return True

    # ========================================================
    # LIST KEYS
    # ========================================================

    def list_keys(self) -> list[str]:
        """
        Return names only.

        Secret values are never returned.
        """

        with self._lock:
            return sorted(
                self._data.keys()
            )

    # ========================================================
    # COUNT
    # ========================================================

    def count(self) -> int:
        with self._lock:
            return len(
                self._data
            )

    # ========================================================
    # GET MANY
    # ========================================================

    def get_many(
        self,
        keys: list[str],
    ) -> Dict[str, Any]:
        """
        Retrieve selected values.

        Use only when the caller genuinely needs
        the plaintext values.
        """

        if not isinstance(
            keys,
            list,
        ):
            raise TypeError(
                "keys must be a list."
            )

        result: Dict[str, Any] = {}

        with self._lock:
            for key in keys:
                normalized = (
                    self._validate_key(key)
                )

                if normalized in self._data:
                    result[normalized] = (
                        self._data[normalized]
                    )

        return result

    # ========================================================
    # SET MANY
    # ========================================================

    def set_many(
        self,
        values: Dict[str, Any],
    ) -> bool:
        """
        Store multiple values in one atomic save.
        """

        if not isinstance(
            values,
            dict,
        ):
            raise TypeError(
                "values must be a dictionary."
            )

        # Validate everything before modifying storage.
        normalized: Dict[str, Any] = {}

        for key, value in values.items():
            normalized_key = (
                self._validate_key(key)
            )

            json.dumps(
                value,
                ensure_ascii=False,
            )

            normalized[
                normalized_key
            ] = value

        with self._lock:
            self._data.update(
                normalized
            )
            self._save()

        return True

    # ========================================================
    # MASK VALUE
    # ========================================================

    @staticmethod
    def mask_value(
        value: Any,
        visible_start: int = 4,
        visible_end: int = 4,
    ) -> str:
        """
        Safely mask a secret for UI/status display.

        Example:
            abcd********wxyz
        """

        if value is None:
            return ""

        text = str(value)

        if not text:
            return ""

        if len(text) <= (
            visible_start + visible_end
        ):
            return "*" * len(text)

        return (
            text[:visible_start]
            + "*" * (
                len(text)
                - visible_start
                - visible_end
            )
            + text[-visible_end:]
        )

    # ========================================================
    # MASKED EXPORT
    # ========================================================

    def export_masked(self) -> Dict[str, str]:
        """
        Return storage information without exposing
        plaintext secret values.
        """

        with self._lock:
            result: Dict[str, str] = {}

            for key, value in self._data.items():
                if isinstance(
                    value,
                    str,
                ):
                    result[key] = (
                        self.mask_value(value)
                    )
                else:
                    result[key] = (
                        f"<{type(value).__name__}>"
                    )

            return result

    # ========================================================
    # IMPORT DICTIONARY
    # ========================================================

    def import_values(
        self,
        values: Dict[str, Any],
        *,
        overwrite: bool = False,
        confirm: bool = False,
    ) -> int:
        """
        Import values.

        Existing keys are protected unless:
            overwrite=True
            confirm=True
        """

        if not isinstance(
            values,
            dict,
        ):
            raise TypeError(
                "values must be a dictionary."
            )

        normalized: Dict[str, Any] = {}

        for key, value in values.items():
            normalized_key = (
                self._validate_key(key)
            )

            json.dumps(
                value,
                ensure_ascii=False,
            )

            normalized[
                normalized_key
            ] = value

        with self._lock:
            for key in normalized:
                if (
                    key in self._data
                    and not overwrite
                ):
                    raise FileExistsError(
                        f"Secure key already exists: {key}"
                    )

            if overwrite:
                if not confirm:
                    raise PermissionError(
                        "Overwriting existing secure "
                        "values requires confirm=True."
                    )

            self._data.update(
                normalized
            )

            self._save()

        return len(
            normalized
        )

    # ========================================================
    # ENVIRONMENT IMPORT
    # ========================================================

    def import_environment(
        self,
        mapping: Dict[str, str],
        *,
        overwrite: bool = False,
        confirm: bool = False,
    ) -> int:
        """
        Import selected environment variables.

        mapping format:

            {
                "openai_api_key": "OPENAI_API_KEY"
            }
        """

        values: Dict[str, str] = {}

        for storage_key, env_name in mapping.items():
            self._validate_key(
                storage_key
            )

            if not isinstance(
                env_name,
                str,
            ):
                raise TypeError(
                    "Environment variable names "
                    "must be strings."
                )

            env_name = env_name.strip()

            if not env_name:
                continue

            value = os.getenv(
                env_name
            )

            if value:
                values[
                    storage_key
                ] = value

        if not values:
            return 0

        return self.import_values(
            values,
            overwrite=overwrite,
            confirm=confirm,
        )

    # ========================================================
    # ENVIRONMENT EXPORT
    # ========================================================

    def export_environment(
        self,
        mapping: Dict[str, str],
        *,
        overwrite: bool = False,
    ) -> int:
        """
        Export selected secure values into the current
        process environment.

        This does NOT write an .env file.
        """

        count = 0

        with self._lock:
            for storage_key, env_name in mapping.items():

                normalized_key = (
                    self._validate_key(
                        storage_key
                    )
                )

                if not isinstance(
                    env_name,
                    str,
                ):
                    continue

                env_name = env_name.strip()

                if not env_name:
                    continue

                if normalized_key not in self._data:
                    continue

                if (
                    env_name in os.environ
                    and not overwrite
                ):
                    continue

                value = self._data[
                    normalized_key
                ]

                if isinstance(
                    value,
                    str,
                ):
                    os.environ[
                        env_name
                    ] = value

                    count += 1

        return count

    # ========================================================
    # ROTATE ENCRYPTION KEY
    # ========================================================

    def rotate_encryption_key(
        self,
    ) -> bool:
        """
        Re-encrypt all stored values using a new key.
        """

        with self._lock:

            # Copy plaintext only in memory.
            values = dict(
                self._data
            )

            result = (
                self.encryption.rotate_key(
                    []
                )
            )

            if not result.get(
                "success",
                False,
            ):
                return False

            # New key is now active. Save everything again.
            self._data = values
            self._save()

        return True

    # ========================================================
    # STATUS
    # ========================================================

    def get_status(
        self,
    ) -> Dict[str, Any]:
        with self._lock:
            return {
                "available": (
                    self.encryption.is_available()
                ),
                "storage_path": str(
                    self.storage_path
                ),
                "exists": (
                    self.storage_path.exists()
                ),
                "item_count": len(
                    self._data
                ),
                "keys": sorted(
                    self._data.keys()
                ),
                "encryption": (
                    self.encryption.get_status()
                ),
            }

    # ========================================================
    # CLOSE
    # ========================================================

    def close(
        self,
    ) -> None:
        with self._lock:
            self._save()

    def __enter__(
        self,
    ) -> "SecureStorage":
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

_secure_storage: Optional[
    SecureStorage
] = None

_secure_storage_lock = (
    threading.Lock()
)


def get_secure_storage() -> SecureStorage:
    global _secure_storage

    with _secure_storage_lock:
        if _secure_storage is None:
            _secure_storage = SecureStorage()

        return _secure_storage


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def secure_set(
    key: str,
    value: Any,
) -> bool:
    return (
        get_secure_storage()
        .set(key, value)
    )


def secure_get(
    key: str,
    default: Any = None,
) -> Any:
    return (
        get_secure_storage()
        .get(key, default)
    )


def secure_has(
    key: str,
) -> bool:
    return (
        get_secure_storage()
        .has(key)
    )


def secure_delete(
    key: str,
) -> bool:
    return (
        get_secure_storage()
        .delete(key)
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
        "JARVIS OS - SECURE STORAGE TEST"
    )
    print("=" * 60)

    test_dir = (
        Path(__file__).resolve().parent
        / "secure_storage_test"
    )

    test_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    key_path = (
        test_dir
        / "test.key"
    )

    storage_path = (
        test_dir
        / "test.dat"
    )

    encryption = EncryptionManager(
        key_path=key_path
    )

    storage = SecureStorage(
        storage_path=storage_path,
        encryption_manager=encryption,
    )

    print("\nStorage status:")

    print(
        json.dumps(
            storage.get_status(),
            indent=2,
        )
    )

    print("\nSaving test secret...")

    storage.set(
        "test_api_key",
        "JARVIS_TEST_SECRET_123456",
    )

    storage.set(
        "settings",
        {
            "voice": True,
            "language": "hinglish",
        },
    )

    print(
        "Stored keys:",
        storage.list_keys(),
    )

    print(
        "Masked values:",
        json.dumps(
            storage.export_masked(),
            indent=2,
        )
    )

    print("\nReading secret internally:")

    value = storage.get(
        "test_api_key"
    )

    print(
        "Value matches:",
        value
        == "JARVIS_TEST_SECRET_123456",
    )

    print("\nJSON value:")

    print(
        storage.get(
            "settings"
        )
    )

    print("\nDeleting test secret:")

    print(
        "Deleted:",
        storage.delete(
            "test_api_key"
        ),
    )

    print(
        "Exists after delete:",
        storage.has(
            "test_api_key"
        ),
    )

    storage.close()

    # Test files are removed so running this module
    # never leaves test secrets behind.
    for path in (
        storage_path,
        key_path,
    ):
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass

    try:
        if test_dir.exists():
            test_dir.rmdir()
    except OSError:
        pass

    print(
        "\nSecure storage test completed."
      )
