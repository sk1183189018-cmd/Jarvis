# updater/version_checker.py

"""
JARVIS OS - VERSION CHECKER
===========================

Checks the installed JarvisOS version against a remote
version manifest.

This module ONLY checks version information.

It does not:
- download files
- execute installers
- modify JarvisOS
- replace application files

Environment variables:

JARVIS_VERSION
    Current installed application version.

JARVIS_UPDATE_MANIFEST_URL
    HTTPS/HTTP URL containing the latest-version JSON.

Example manifest:

{
    "version": "1.2.0",
    "url": "https://example.com/JarvisOS-1.2.0.zip",
    "sha256": "64-character-sha256",
    "release_notes": "Bug fixes and improvements.",
    "mandatory": false
}
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    requests = None


logger = logging.getLogger(
    "JarvisOS.VersionChecker"
)


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class VersionInfo:
    """Version information returned by a remote manifest."""

    version: str

    url: str = ""

    sha256: str = ""

    release_notes: str = ""

    mandatory: bool = False

    published_at: str = ""

    size_bytes: int = 0

    channel: str = "stable"

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class VersionCheckResult:
    """Result of a version check."""

    success: bool

    update_available: bool

    current_version: str

    latest_version: str

    message: str

    mandatory: bool = False

    version_info: Optional[
        VersionInfo
    ] = None

    error: str = ""

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        data = asdict(
            self
        )

        return data


# ============================================================
# VERSION CHECKER
# ============================================================

class VersionChecker:
    """
    Remote version checker for JarvisOS.

    Example:

        checker = VersionChecker(
            current_version="1.0.0",
            manifest_url="https://example.com/version.json"
        )

        result = checker.check()

        if result.update_available:
            print(result.latest_version)
    """

    def __init__(
        self,
        current_version: Optional[
            str
        ] = None,
        manifest_url: Optional[
            str
        ] = None,
        timeout: Optional[
            int
        ] = None,
    ):

        self.current_version = (
            current_version
            or os.getenv(
                "JARVIS_VERSION",
                "1.0.0",
            )
        ).strip()

        self.manifest_url = (
            manifest_url
            or os.getenv(
                "JARVIS_UPDATE_MANIFEST_URL",
                "",
            )
        ).strip()

        self.timeout = (
            timeout
            if timeout is not None
            else int(
                os.getenv(
                    "JARVIS_UPDATE_TIMEOUT",
                    "30",
                )
            )
        )

        self._lock = threading.RLock()

        self.last_result: Optional[
            VersionCheckResult
        ] = None

        self.last_version_info: Optional[
            VersionInfo
        ] = None

        self.history: list[
            Dict[str, Any]
        ] = []

        self.max_history = 100

    # ========================================================
    # VERSION PARSING
    # ========================================================

    @staticmethod
    def parse_version(
        version: str,
    ) -> tuple:

        if not isinstance(
            version,
            str,
        ):
            return (0, 0, 0, 0)

        value = (
            version.strip()
            .lower()
            .lstrip("v")
        )

        # Remove build metadata.
        value = value.split(
            "+",
            1,
        )[0]

        # Keep stable numeric version before
        # prerelease identifier.
        value = value.split(
            "-",
            1,
        )[0]

        parts = []

        for part in value.split("."):

            digits = ""

            for char in part:

                if char.isdigit():
                    digits += char
                else:
                    break

            parts.append(
                int(digits)
                if digits
                else 0
            )

        while len(parts) < 4:
            parts.append(0)

        return tuple(
            parts[:4]
        )

    @classmethod
    def compare_versions(
        cls,
        first: str,
        second: str,
    ) -> int:

        a = cls.parse_version(
            first
        )

        b = cls.parse_version(
            second
        )

        if a < b:
            return -1

        if a > b:
            return 1

        return 0

    def is_newer(
        self,
        version: str,
    ) -> bool:

        return (
            self.compare_versions(
                version,
                self.current_version,
            )
            > 0
        )

    # ========================================================
    # URL VALIDATION
    # ========================================================

    @staticmethod
    def validate_url(
        url: str,
    ) -> bool:

        if not isinstance(
            url,
            str,
        ):
            return False

        try:

            parsed = urlparse(
                url.strip()
            )

        except Exception:

            return False

        return (
            parsed.scheme
            in {"http", "https"}
            and bool(
                parsed.netloc
            )
        )

    # ========================================================
    # SHA-256 VALIDATION
    # ========================================================

    @staticmethod
    def validate_sha256(
        value: str,
    ) -> bool:

        if not value:
            return True

        if not isinstance(
            value,
            str,
        ):
            return False

        value = value.strip().lower()

        return (
            len(value) == 64
            and all(
                char
                in "0123456789abcdef"
                for char in value
            )
        )

    # ========================================================
    # MANIFEST PARSING
    # ========================================================

    def parse_manifest(
        self,
        data: Dict[str, Any],
    ) -> VersionInfo:

        if not isinstance(
            data,
            dict,
        ):

            raise ValueError(
                "Version manifest must be a JSON object."
            )

        version = str(
            data.get(
                "version",
                "",
            )
        ).strip()

        if not version:

            raise ValueError(
                "Version manifest does not contain a version."
            )

        url = str(
            data.get(
                "url",
                "",
            )
            or ""
        ).strip()

        if url and not self.validate_url(
            url
        ):

            raise ValueError(
                "Manifest contains an invalid package URL."
            )

        sha256 = str(
            data.get(
                "sha256",
                "",
            )
            or ""
        ).strip().lower()

        if not self.validate_sha256(
            sha256
        ):

            raise ValueError(
                "Manifest contains an invalid SHA-256 checksum."
            )

        try:

            size_bytes = int(
                data.get(
                    "size_bytes",
                    0,
                )
                or 0
            )

        except (
            TypeError,
            ValueError,
        ):

            raise ValueError(
                "Manifest size_bytes must be an integer."
            )

        if size_bytes < 0:

            raise ValueError(
                "Manifest size_bytes cannot be negative."
            )

        channel = str(
            data.get(
                "channel",
                "stable",
            )
            or "stable"
        ).strip().lower()

        if channel not in {
            "stable",
            "beta",
            "dev",
            "nightly",
        }:

            raise ValueError(
                "Unsupported update channel."
            )

        metadata = data.get(
            "metadata",
            {},
        )

        if not isinstance(
            metadata,
            dict,
        ):

            metadata = {}

        return VersionInfo(
            version=version,
            url=url,
            sha256=sha256,
            release_notes=str(
                data.get(
                    "release_notes",
                    "",
                )
                or ""
            ),
            mandatory=bool(
                data.get(
                    "mandatory",
                    False,
                )
            ),
            published_at=str(
                data.get(
                    "published_at",
                    "",
                )
                or ""
            ),
            size_bytes=size_bytes,
            channel=channel,
            metadata=metadata,
        )

    # ========================================================
    # FETCH
    # ========================================================

    def fetch(
        self,
    ) -> VersionCheckResult:

        if requests is None:

            result = VersionCheckResult(
                success=False,
                update_available=False,
                current_version=(
                    self.current_version
                ),
                latest_version="",
                message=(
                    "The requests package is not installed."
                ),
                error="requests_missing",
            )

            self._store_result(
                result
            )

            return result

        if not self.manifest_url:

            result = VersionCheckResult(
                success=False,
                update_available=False,
                current_version=(
                    self.current_version
                ),
                latest_version="",
                message=(
                    "No update manifest URL is configured."
                ),
                error="manifest_url_missing",
            )

            self._store_result(
                result
            )

            return result

        if not self.validate_url(
            self.manifest_url
        ):

            result = VersionCheckResult(
                success=False,
                update_available=False,
                current_version=(
                    self.current_version
                ),
                latest_version="",
                message=(
                    "Configured update manifest URL is invalid."
                ),
                error="invalid_manifest_url",
            )

            self._store_result(
                result
            )

            return result

        try:

            response = requests.get(
                self.manifest_url,
                timeout=self.timeout,
                headers={
                    "Accept": "application/json",
                    "User-Agent": (
                        "JarvisOS-VersionChecker/1.0"
                    ),
                },
            )

            response.raise_for_status()

            data = response.json()

            info = self.parse_manifest(
                data
            )

            self.last_version_info = (
                info
            )

            comparison = (
                self.compare_versions(
                    info.version,
                    self.current_version,
                )
            )

            if comparison > 0:

                message = (
                    f"JarvisOS update "
                    f"{info.version} is available."
                )

                update_available = True

            elif comparison == 0:

                message = (
                    "JarvisOS is up to date."
                )

                update_available = False

            else:

                message = (
                    "The remote version is older "
                    "than the installed version."
                )

                update_available = False

            result = VersionCheckResult(
                success=True,
                update_available=(
                    update_available
                ),
                current_version=(
                    self.current_version
                ),
                latest_version=(
                    info.version
                ),
                message=message,
                mandatory=(
                    info.mandatory
                    and update_available
                ),
                version_info=info,
                metadata={
                    "channel": info.channel,
                    "published_at": (
                        info.published_at
                    ),
                    "size_bytes": (
                        info.size_bytes
                    ),
                },
            )

            self._store_result(
                result
            )

            return result

        except ValueError as exc:

            result = VersionCheckResult(
                success=False,
                update_available=False,
                current_version=(
                    self.current_version
                ),
                latest_version="",
                message=(
                    "The update manifest is invalid."
                ),
                error=str(exc),
            )

            self._store_result(
                result
            )

            return result

        except Exception as exc:

            logger.warning(
                "Version check failed: %s",
                exc,
            )

            result = VersionCheckResult(
                success=False,
                update_available=False,
                current_version=(
                    self.current_version
                ),
                latest_version="",
                message=(
                    "Unable to check for updates."
                ),
                error=str(exc),
            )

            self._store_result(
                result
            )

            return result

    # ========================================================
    # CHECK ALIAS
    # ========================================================

    def check(
        self,
    ) -> VersionCheckResult:

        return self.fetch()

    # ========================================================
    # LOCAL CHECK
    # ========================================================

    def check_version(
        self,
        remote_version: str,
    ) -> VersionCheckResult:

        remote_version = (
            str(
                remote_version
            ).strip()
        )

        if not remote_version:

            result = VersionCheckResult(
                success=False,
                update_available=False,
                current_version=(
                    self.current_version
                ),
                latest_version="",
                message=(
                    "Remote version is empty."
                ),
                error="empty_version",
            )

            self._store_result(
                result
            )

            return result

        comparison = (
            self.compare_versions(
                remote_version,
                self.current_version,
            )
        )

        if comparison > 0:

            message = (
                f"Version {remote_version} "
                "is newer than the installed version."
            )

            available = True

        elif comparison == 0:

            message = (
                "Versions are identical."
            )

            available = False

        else:

            message = (
                f"Version {remote_version} "
                "is older than the installed version."
            )

            available = False

        result = VersionCheckResult(
            success=True,
            update_available=available,
            current_version=(
                self.current_version
            ),
            latest_version=(
                remote_version
            ),
            message=message,
        )

        self._store_result(
            result
        )

        return result

    # ========================================================
    # UPDATE DETAILS
    # ========================================================

    def get_latest_info(
        self,
    ) -> Optional[
        VersionInfo
    ]:

        with self._lock:

            if self.last_version_info is None:
                return None

            return VersionInfo(
                **asdict(
                    self.last_version_info
                )
            )

    def get_last_result(
        self,
    ) -> Optional[
        VersionCheckResult
    ]:

        with self._lock:

            if self.last_result is None:
                return None

            return VersionCheckResult(
                **asdict(
                    self.last_result
                )
            )

    # ========================================================
    # HISTORY
    # ========================================================

    @staticmethod
    def _now() -> str:

        from datetime import (
            datetime,
            timezone,
        )

        return datetime.now(
            timezone.utc
        ).isoformat()

    def _store_result(
        self,
        result: VersionCheckResult,
    ) -> None:

        with self._lock:

            self.last_result = result

            self.history.append(
                {
                    "timestamp": self._now(),
                    "result": result.to_dict(),
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
    ) -> list[
        Dict[str, Any]
    ]:

        with self._lock:

            return json.loads(
                json.dumps(
                    self.history
                )
            )

    # ========================================================
    # STATUS
    # ========================================================

    def get_status(
        self,
    ) -> Dict[str, Any]:

        with self._lock:

            return {
                "current_version": (
                    self.current_version
                ),
                "manifest_url_configured": bool(
                    self.manifest_url
                ),
                "timeout": self.timeout,
                "last_check_success": (
                    self.last_result.success
                    if self.last_result
                    else None
                ),
                "update_available": (
                    self.last_result.update_available
                    if self.last_result
                    else None
                ),
                "latest_version": (
                    self.last_result.latest_version
                    if self.last_result
                    else ""
                ),
                "mandatory": (
                    self.last_result.mandatory
                    if self.last_result
                    else False
                ),
                "history_count": len(
                    self.history
                ),
            }

    # ========================================================
    # CONFIGURATION
    # ========================================================

    def set_manifest_url(
        self,
        url: str,
    ) -> None:

        if not self.validate_url(
            url
        ):

            raise ValueError(
                "Invalid manifest URL."
            )

        with self._lock:

            self.manifest_url = (
                url.strip()
            )

    def set_current_version(
        self,
        version: str,
    ) -> None:

        if not isinstance(
            version,
            str,
        ) or not version.strip():

            raise ValueError(
                "Version cannot be empty."
            )

        with self._lock:

            self.current_version = (
                version.strip()
            )

    # ========================================================
    # CLOSE
    # ========================================================

    def close(
        self,
    ) -> None:
        pass

    def __enter__(
        self,
    ) -> "VersionChecker":

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

_version_checker: Optional[
    VersionChecker
] = None

_version_checker_lock = (
    threading.Lock()
)


def get_version_checker() -> VersionChecker:

    global _version_checker

    with _version_checker_lock:

        if _version_checker is None:

            _version_checker = (
                VersionChecker()
            )

        return _version_checker


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def check_version(
    remote_version: str,
) -> VersionCheckResult:

    return (
        get_version_checker()
        .check_version(
            remote_version
        )
    )


def check_for_update() -> VersionCheckResult:

    return (
        get_version_checker()
        .check()
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
        "JARVIS OS - VERSION CHECKER TEST"
    )
    print("=" * 60)

    checker = VersionChecker(
        current_version="1.0.0"
    )

    print("\nVersion comparisons:")

    tests = [
        "1.0.0",
        "1.0.1",
        "1.1.0",
        "2.0.0",
        "0.9.9",
    ]

    for version in tests:

        result = (
            checker.check_version(
                version
            )
        )

        print(
            f"{checker.current_version} -> "
            f"{version}: "
            f"update={result.update_available}"
        )

    print("\nStatus:")

    print(
        json.dumps(
            checker.get_status(),
            indent=2,
        )
    )

    # No remote request is performed during the direct
    # test unless the user explicitly configures and calls
    # the network check themselves.

    checker.close()

    print(
        "\nVersion checker test completed."
    )
