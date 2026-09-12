# security/encryption.py

"""
JARVIS OS - ENCRYPTION ENGINE
=============================

Provides authenticated encryption for sensitive local data.

Uses Fernet from the cryptography package.

Features:
- Generate encryption keys
- Encrypt/decrypt text
- Encrypt/decrypt bytes
- Encrypt/decrypt JSON objects
- File encryption/decryption
- SHA-256 hashing
- HMAC-style fingerprints
- Secure random tokens
- Key rotation support
- No plaintext secret logging

IMPORTANT:
This module provides application-level encryption.
For production Windows deployments, the encryption key should
ideally be protected with Windows Credential Manager / DPAPI
or another OS-backed secret store.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import threading
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from cryptography.fernet import (
        Fernet,
        InvalidToken,
    )

    CRYPTOGRAPHY_AVAILABLE = True

except ImportError:
    Fernet = None
    InvalidToken = Exception
    CRYPTOGRAPHY_AVAILABLE = False


logger = logging.getLogger(
    "JarvisOS.Encryption"
)


# ============================================================
# ENCRYPTION ENGINE
# ============================================================

class EncryptionManager:
    """
    Application-level encryption manager.

    Example:

        encryption = EncryptionManager()

        encrypted = encryption.encrypt_text(
            "secret message"
        )

        plain = encryption.decrypt_text(
            encrypted
        )
    """

    KEY_SIZE_BYTES = 32

    HASH_ALGORITHM = "sha256"

    VERSION = 1

    def __init__(
        self,
        key: Optional[
            bytes | str
        ] = None,
        key_path: Optional[
            str | Path
        ] = None,
    ):

        self._lock = (
            threading.RLock()
        )

        self.key_path = (
            Path(key_path).expanduser().resolve()
            if key_path
            else None
        )

        self._fernet = None

        self._key_fingerprint = ""

        if not CRYPTOGRAPHY_AVAILABLE:

            logger.error(
                "cryptography package is unavailable."
            )

            return

        try:

            if key is not None:

                normalized_key = (
                    self._normalize_key(
                        key
                    )
                )

            elif self.key_path is not None:

                normalized_key = (
                    self._load_or_create_key(
                        self.key_path
                    )
                )

            else:

                normalized_key = (
                    Fernet.generate_key()
                )

            self._fernet = (
                Fernet(
                    normalized_key
                )
            )

            self._key_fingerprint = (
                self.hash_bytes(
                    normalized_key
                )
            )

        except Exception as exc:

            logger.error(
                "Encryption initialization failed: %s",
                exc,
            )

    # ========================================================
    # KEY HELPERS
    # ========================================================

    @staticmethod
    def generate_key() -> bytes:

        if not CRYPTOGRAPHY_AVAILABLE:

            raise RuntimeError(
                "cryptography package is required."
            )

        return Fernet.generate_key()

    @staticmethod
    def _normalize_key(
        key: bytes | str,
    ) -> bytes:

        if isinstance(
            key,
            str,
        ):

            key = key.encode(
                "utf-8"
            )

        if not isinstance(
            key,
            bytes,
        ):

            raise TypeError(
                "Encryption key must be bytes or string."
            )

        # A valid Fernet key is 32 raw bytes
        # encoded using URL-safe base64.
        try:

            decoded = base64.urlsafe_b64decode(
                key
            )

            if len(decoded) == 32:

                return key

        except Exception:
            pass

        # Allow exactly 32 raw bytes.
        if len(key) == 32:

            return base64.urlsafe_b64encode(
                key
            )

        raise ValueError(
            "Invalid encryption key. "
            "Use a Fernet key or 32 raw bytes."
        )

    @staticmethod
    def _load_or_create_key(
        path: Path,
    ) -> bytes:

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if path.exists():

            key = path.read_bytes()

            # Validate before using.
            EncryptionManager._normalize_key(
                key
            )

            return key

        key = (
            Fernet.generate_key()
        )

        temporary = (
            path.with_suffix(
                ".tmp"
            )
        )

        temporary.write_bytes(
            key
        )

        try:

            temporary.chmod(
                0o600
            )

        except Exception:
            pass

        temporary.replace(
            path
        )

        try:

            path.chmod(
                0o600
            )

        except Exception:
            pass

        return key

    # ========================================================
    # STATUS
    # ========================================================

    def is_available(
        self,
    ) -> bool:

        return (
            self._fernet is not None
        )

    def get_key_fingerprint(
        self,
    ) -> str:

        return self._key_fingerprint

    def get_status(
        self,
    ) -> Dict[str, Any]:

        return {
            "available": self.is_available(),
            "cryptography_installed": (
                CRYPTOGRAPHY_AVAILABLE
            ),
            "key_configured": (
                self._fernet is not None
            ),
            "key_persistent": (
                self.key_path is not None
            ),
            "key_fingerprint": (
                self._key_fingerprint[:16]
                if self._key_fingerprint
                else ""
            ),
            "algorithm": (
                "Fernet"
                if self._fernet
                else None
            ),
            "hash_algorithm": (
                self.HASH_ALGORITHM
            ),
            "version": self.VERSION,
        }

    def _require_available(
        self,
    ) -> None:

        if self._fernet is None:

            raise RuntimeError(
                "Encryption is unavailable. "
                "Install the cryptography package "
                "and configure a valid key."
            )

    # ========================================================
    # ENCRYPT BYTES
    # ========================================================

    def encrypt_bytes(
        self,
        data: bytes,
    ) -> bytes:

        self._require_available()

        if not isinstance(
            data,
            bytes,
        ):

            raise TypeError(
                "encrypt_bytes() requires bytes."
            )

        with self._lock:

            return self._fernet.encrypt(
                data
            )

    # ========================================================
    # DECRYPT BYTES
    # ========================================================

    def decrypt_bytes(
        self,
        encrypted_data: bytes,
    ) -> bytes:

        self._require_available()

        if not isinstance(
            encrypted_data,
            bytes,
        ):

            raise TypeError(
                "decrypt_bytes() requires bytes."
            )

        try:

            with self._lock:

                return self._fernet.decrypt(
                    encrypted_data
                )

        except InvalidToken as exc:

            raise ValueError(
                "Encrypted data is invalid, "
                "corrupted, or was encrypted "
                "with another key."
            ) from exc

    # ========================================================
    # ENCRYPT TEXT
    # ========================================================

    def encrypt_text(
        self,
        text: str,
    ) -> str:

        if not isinstance(
            text,
            str,
        ):

            raise TypeError(
                "encrypt_text() requires a string."
            )

        encrypted = (
            self.encrypt_bytes(
                text.encode(
                    "utf-8"
                )
            )
        )

        return encrypted.decode(
            "utf-8"
        )

    # ========================================================
    # DECRYPT TEXT
    # ========================================================

    def decrypt_text(
        self,
        encrypted_text: str,
    ) -> str:

        if not isinstance(
            encrypted_text,
            str,
        ):

            raise TypeError(
                "decrypt_text() requires a string."
            )

        decrypted = (
            self.decrypt_bytes(
                encrypted_text.encode(
                    "utf-8"
                )
            )
        )

        return decrypted.decode(
            "utf-8"
        )

    # ========================================================
    # ENCRYPT JSON
    # ========================================================

    def encrypt_json(
        self,
        data: Any,
    ) -> str:

        serialized = json.dumps(
            data,
            ensure_ascii=False,
            separators=(
                ",",
                ":",
            ),
        )

        return self.encrypt_text(
            serialized
        )

    # ========================================================
    # DECRYPT JSON
    # ========================================================

    def decrypt_json(
        self,
        encrypted_data: str,
    ) -> Any:

        text = self.decrypt_text(
            encrypted_data
        )

        return json.loads(
            text
        )

    # ========================================================
    # ENCRYPT FILE
    # ========================================================

    def encrypt_file(
        self,
        input_path: str | Path,
        output_path: Optional[
            str | Path
        ] = None,
        *,
        overwrite: bool = False,
    ) -> Path:

        self._require_available()

        source = (
            Path(
                input_path
            )
            .expanduser()
            .resolve()
        )

        if not source.exists():

            raise FileNotFoundError(
                f"Input file not found: {source}"
            )

        if not source.is_file():

            raise ValueError(
                "Input path must be a file."
            )

        if output_path is None:

            destination = (
                source.with_name(
                    source.name
                    + ".encrypted"
                )
            )

        else:

            destination = (
                Path(
                    output_path
                )
                .expanduser()
                .resolve()
            )

        if (
            destination.exists()
            and not overwrite
        ):

            raise FileExistsError(
                f"Output file already exists: "
                f"{destination}"
            )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = source.read_bytes()

        encrypted = (
            self.encrypt_bytes(
                data
            )
        )

        temporary = (
            destination.with_suffix(
                destination.suffix
                + ".tmp"
            )
        )

        temporary.write_bytes(
            encrypted
        )

        temporary.replace(
            destination
        )

        return destination

    # ========================================================
    # DECRYPT FILE
    # ========================================================

    def decrypt_file(
        self,
        input_path: str | Path,
        output_path: Optional[
            str | Path
        ] = None,
        *,
        overwrite: bool = False,
    ) -> Path:

        self._require_available()

        source = (
            Path(
                input_path
            )
            .expanduser()
            .resolve()
        )

        if not source.exists():

            raise FileNotFoundError(
                f"Encrypted file not found: "
                f"{source}"
            )

        if not source.is_file():

            raise ValueError(
                "Input path must be a file."
            )

        if output_path is None:

            if source.name.endswith(
                ".encrypted"
            ):

                destination = (
                    source.with_name(
                        source.name[
                            :-len(".encrypted")
                        ]
                    )
                )

            else:

                destination = (
                    source.with_suffix(
                        ".decrypted"
                    )
                )

        else:

            destination = (
                Path(
                    output_path
                )
                .expanduser()
                .resolve()
            )

        if (
            destination.exists()
            and not overwrite
        ):

            raise FileExistsError(
                f"Output file already exists: "
                f"{destination}"
            )

        encrypted = (
            source.read_bytes()
        )

        decrypted = (
            self.decrypt_bytes(
                encrypted
            )
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = (
            destination.with_suffix(
                destination.suffix
                + ".tmp"
            )
        )

        temporary.write_bytes(
            decrypted
        )

        temporary.replace(
            destination
        )

        return destination

    # ========================================================
    # HASHING
    # ========================================================

    @staticmethod
    def hash_bytes(
        data: bytes,
    ) -> str:

        if not isinstance(
            data,
            bytes,
        ):

            raise TypeError(
                "hash_bytes() requires bytes."
            )

        return hashlib.sha256(
            data
        ).hexdigest()

    @staticmethod
    def hash_text(
        text: str,
    ) -> str:

        if not isinstance(
            text,
            str,
        ):

            raise TypeError(
                "hash_text() requires a string."
            )

        return hashlib.sha256(
            text.encode(
                "utf-8"
            )
        ).hexdigest()

    @staticmethod
    def hash_file(
        file_path: str | Path,
        chunk_size: int = 1024 * 1024,
    ) -> str:

        path = (
            Path(
                file_path
            )
            .expanduser()
            .resolve()
        )

        if not path.exists():

            raise FileNotFoundError(
                str(path)
            )

        if not path.is_file():

            raise ValueError(
                "Path must point to a file."
            )

        digest = hashlib.sha256()

        with open(
            path,
            "rb",
        ) as file:

            while True:

                chunk = file.read(
                    chunk_size
                )

                if not chunk:
                    break

                digest.update(
                    chunk
                )

        return digest.hexdigest()

    # ========================================================
    # CONSTANT-TIME COMPARISON
    # ========================================================

    @staticmethod
    def secure_compare(
        first: str,
        second: str,
    ) -> bool:

        return hmac.compare_digest(
            str(first),
            str(second),
        )

    # ========================================================
    # RANDOM TOKENS
    # ========================================================

    @staticmethod
    def random_token(
        length: int = 32,
    ) -> str:

        if length < 16:

            raise ValueError(
                "Token length must be at least 16."
            )

        return secrets.token_urlsafe(
            length
        )

    @staticmethod
    def random_hex(
        length: int = 32,
    ) -> str:

        if length < 16:

            raise ValueError(
                "Hex length must be at least 16."
            )

        return secrets.token_hex(
            length
        )

    # ========================================================
    # KEY ROTATION
    # ========================================================

    def rotate_key(
        self,
        encrypted_values: Optional[
            list[str]
        ] = None,
    ) -> Dict[str, Any]:

        self._require_available()

        values = (
            encrypted_values or []
        )

        old_fernet = (
            self._fernet
        )

        old_values: list[str] = []

        try:

            for encrypted in values:

                decrypted = (
                    old_fernet.decrypt(
                        encrypted.encode(
                            "utf-8"
                        )
                    )
                )

                old_values.append(
                    decrypted.decode(
                        "utf-8"
                    )
                )

            new_key = (
                Fernet.generate_key()
            )

            new_fernet = (
                Fernet(
                    new_key
                )
            )

            reencrypted = [
                new_fernet.encrypt(
                    value.encode(
                        "utf-8"
                    )
                ).decode(
                    "utf-8"
                )
                for value in old_values
            ]

            if self.key_path is not None:

                temporary = (
                    self.key_path.with_suffix(
                        ".tmp"
                    )
                )

                temporary.write_bytes(
                    new_key
                )

                try:

                    temporary.chmod(
                        0o600
                    )

                except Exception:
                    pass

                temporary.replace(
                    self.key_path
                )

                try:

                    self.key_path.chmod(
                        0o600
                    )

                except Exception:
                    pass

            self._fernet = (
                new_fernet
            )

            self._key_fingerprint = (
                self.hash_bytes(
                    new_key
                )
            )

            return {
                "success": True,
                "reencrypted": reencrypted,
                "key_fingerprint": (
                    self._key_fingerprint
                ),
            }

        except Exception:

            # Never leave the manager with a partially
            # rotated in-memory key.
            self._fernet = (
                old_fernet
            )

            raise

    # ========================================================
    # CLOSE
    # ========================================================

    def close(
        self,
    ) -> None:

        with self._lock:

            self._fernet = None

            self._key_fingerprint = ""

    def __enter__(
        self,
    ) -> "EncryptionManager":

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback_value,
    ) -> None:

        self.close()


# ============================================================
# DEFAULT KEY PATH
# ============================================================

def _default_key_path() -> Path:

    return (
        Path(__file__).resolve().parent
        / "jarvis_encryption.key"
    )


# ============================================================
# SHARED INSTANCE
# ============================================================

_encryption_manager: Optional[
    EncryptionManager
] = None

_encryption_manager_lock = (
    threading.Lock()
)


def get_encryption_manager() -> EncryptionManager:

    global _encryption_manager

    with _encryption_manager_lock:

        if _encryption_manager is None:

            _encryption_manager = (
                EncryptionManager(
                    key_path=(
                        _default_key_path()
                    )
                )
            )

        return _encryption_manager


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def encrypt_text(
    text: str,
) -> str:

    return (
        get_encryption_manager()
        .encrypt_text(text)
    )


def decrypt_text(
    encrypted_text: str,
) -> str:

    return (
        get_encryption_manager()
        .decrypt_text(
            encrypted_text
        )
    )


def encrypt_json(
    data: Any,
) -> str:

    return (
        get_encryption_manager()
        .encrypt_json(data)
    )


def decrypt_json(
    encrypted_data: str,
) -> Any:

    return (
        get_encryption_manager()
        .decrypt_json(
            encrypted_data
        )
    )


def hash_text(
    text: str,
) -> str:

    return EncryptionManager.hash_text(
        text
    )


def hash_file(
    file_path: str | Path,
) -> str:

    return EncryptionManager.hash_file(
        file_path
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
        "JARVIS OS - ENCRYPTION TEST"
    )
    print("=" * 60)

    test_key_path = (
        Path(__file__).resolve().parent
        / "encryption.test.key"
    )

    manager = EncryptionManager(
        key_path=test_key_path
    )

    print("\nStatus:")

    print(
        json.dumps(
            manager.get_status(),
            indent=2,
        )
    )

    if manager.is_available():

        original = (
            "JarvisOS secret test"
        )

        encrypted = (
            manager.encrypt_text(
                original
            )
        )

        decrypted = (
            manager.decrypt_text(
                encrypted
            )
        )

        print(
            "\nEncryption test:"
        )

        print(
            "Original:",
            original,
        )

        print(
            "Encrypted:",
            encrypted[:30]
            + "...",
        )

        print(
            "Decrypted:",
            decrypted,
        )

        print(
            "Success:",
            original == decrypted,
        )

        sample = {
            "app": "JarvisOS",
            "enabled": True,
            "number": 123,
        }

        encrypted_json = (
            manager.encrypt_json(
                sample
            )
        )

        decrypted_json = (
            manager.decrypt_json(
                encrypted_json
            )
        )

        print(
            "\nJSON encryption:",
            sample == decrypted_json,
        )

    else:

        print(
            "\nEncryption unavailable."
        )

    manager.close()

    try:

        if test_key_path.exists():

            test_key_path.unlink()

    except Exception:
        pass

    print(
        "\nEncryption test completed."
      )
