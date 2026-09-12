# updater/auto_update.py

"""
JARVIS OS - AUTO UPDATE MANAGER
================================

Responsible for safely checking, downloading and preparing
JarvisOS application updates.

Important:
- Does NOT silently replace the running application.
- Downloads updates into a temporary/staging directory.
- Verifies SHA-256 when a checksum is supplied.
- Never executes a downloaded installer automatically.
- Actual installation should be performed by a trusted
  installer/updater process after explicit user approval.

Environment variables:

JARVIS_UPDATE_URL
    Direct URL to an update package.

JARVIS_UPDATE_MANIFEST_URL
    URL returning a JSON update manifest.

JARVIS_UPDATE_DIR
    Optional local staging directory.

JARVIS_UPDATE_TIMEOUT
    Network timeout in seconds.

Example manifest:

{
    "version": "1.1.0",
    "url": "https://example.com/JarvisOS-1.1.0.zip",
    "sha256": "....",
    "release_notes": "Bug fixes and improvements.",
    "mandatory": false
}
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
import threading
import time
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

try:
    import requests
except ImportError:
    requests = None


logger = logging.getLogger(
    "JarvisOS.AutoUpdate"
)


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class UpdateInfo:
    """Information about an available update."""

    version: str
    url: str = ""
    sha256: str = ""
    release_notes: str = ""
    mandatory: bool = False
    size_bytes: int = 0
    published_at: str = ""
    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class UpdateResult:
    """Result returned by update operations."""

    success: bool
    operation: str
    message: str

    current_version: str = ""
    available_version: str = ""

    file_path: str = ""

    downloaded_bytes: int = 0

    verified: bool = False

    error: str = ""

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================
# AUTO UPDATE
# ============================================================

class AutoUpdate:
    """
    Safe update manager for JarvisOS.

    It handles:

    1. Manifest retrieval
    2. Version comparison
    3. Update download
    4. SHA-256 verification
    5. ZIP validation
    6. Staging
    7. Cleanup

    It does NOT execute downloaded files.
    """

    def __init__(
        self,
        current_version: Optional[str] = None,
        update_url: Optional[str] = None,
        manifest_url: Optional[str] = None,
        staging_dir: Optional[
            str | Path
        ] = None,
        timeout: Optional[int] = None,
    ):

        self.current_version = (
            current_version
            or os.getenv(
                "JARVIS_VERSION",
                "1.0.0",
            )
        )

        self.update_url = (
            update_url
            or os.getenv(
                "JARVIS_UPDATE_URL",
                "",
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

        if staging_dir is None:

            configured_dir = os.getenv(
                "JARVIS_UPDATE_DIR",
                "",
            ).strip()

            if configured_dir:

                self.staging_dir = (
                    Path(
                        configured_dir
                    )
                    .expanduser()
                    .resolve()
                )

            else:

                self.staging_dir = (
                    Path(__file__).resolve().parent
                    / "staging"
                )

        else:

            self.staging_dir = (
                Path(
                    staging_dir
                )
                .expanduser()
                .resolve()
            )

        self.staging_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._lock = threading.RLock()

        self.history: list[
            Dict[str, Any]
        ] = []

        self.max_history = 100

        self.last_update: Optional[
            UpdateInfo
        ] = None

        self.last_download: Optional[
            Path
        ] = None

    # ========================================================
    # TIME
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

    # ========================================================
    # VERSION PARSING
    # ========================================================

    @staticmethod
    def _parse_version(
        version: str,
    ) -> tuple:

        if not isinstance(
            version,
            str,
        ):

            return (0,)

        value = (
            version.strip()
            .lower()
            .lstrip("v")
        )

        # Ignore build metadata.
        value = value.split(
            "+",
            1,
        )[0]

        # Ignore prerelease information after '-'.
        base = value.split(
            "-",
            1,
        )[0]

        parts = []

        for item in base.split("."):

            digits = ""

            for char in item:

                if char.isdigit():
                    digits += char
                else:
                    break

            if digits:
                parts.append(
                    int(digits)
                )
            else:
                parts.append(0)

        while len(parts) < 4:
            parts.append(0)

        return tuple(parts[:4])

    @classmethod
    def compare_versions(
        cls,
        left: str,
        right: str,
    ) -> int:

        a = cls._parse_version(
            left
        )

        b = cls._parse_version(
            right
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
    def _validate_url(
        url: str,
    ) -> bool:

        if not isinstance(
            url,
            str,
        ):
            return False

        value = url.strip()

        try:

            parsed = urlparse(
                value
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
    # MANIFEST PARSING
    # ========================================================

    def _parse_manifest(
        self,
        data: Dict[str, Any],
    ) -> UpdateInfo:

        if not isinstance(
            data,
            dict,
        ):

            raise ValueError(
                "Update manifest must be a JSON object."
            )

        version = str(
            data.get(
                "version",
                "",
            )
        ).strip()

        if not version:

            raise ValueError(
                "Update manifest does not contain a version."
            )

        url = str(
            data.get(
                "url",
                self.update_url,
            )
            or ""
        ).strip()

        if url and not self._validate_url(
            url
        ):

            raise ValueError(
                "Update package URL is invalid."
            )

        sha256 = str(
            data.get(
                "sha256",
                "",
            )
            or ""
        ).strip().lower()

        if sha256:

            if (
                len(sha256)
                != 64
                or any(
                    char not in "0123456789abcdef"
                    for char in sha256
                )
            ):

                raise ValueError(
                    "Invalid SHA-256 checksum."
                )

        return UpdateInfo(
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
            size_bytes=int(
                data.get(
                    "size_bytes",
                    0,
                )
                or 0
            ),
            published_at=str(
                data.get(
                    "published_at",
                    "",
                )
                or ""
            ),
            metadata=dict(
                data.get(
                    "metadata",
                    {},
                )
                or {}
            ),
        )

    # ========================================================
    # FETCH MANIFEST
    # ========================================================

    def fetch_manifest(
        self,
    ) -> UpdateResult:

        if requests is None:

            return UpdateResult(
                success=False,
                operation="fetch_manifest",
                message=(
                    "The requests package is not installed."
                ),
                error="requests_missing",
            )

        if not self.manifest_url:

            return UpdateResult(
                success=False,
                operation="fetch_manifest",
                message=(
                    "No update manifest URL is configured."
                ),
                error="manifest_url_missing",
            )

        if not self._validate_url(
            self.manifest_url
        ):

            return UpdateResult(
                success=False,
                operation="fetch_manifest",
                message=(
                    "Configured manifest URL is invalid."
                ),
                error="invalid_manifest_url",
            )

        try:

            response = requests.get(
                self.manifest_url,
                timeout=self.timeout,
                headers={
                    "User-Agent": (
                        "JarvisOS-Updater/1.0"
                    )
                },
            )

            response.raise_for_status()

            data = response.json()

            info = self._parse_manifest(
                data
            )

            self.last_update = info

            result = UpdateResult(
                success=True,
                operation="fetch_manifest",
                message=(
                    "Update manifest retrieved successfully."
                ),
                current_version=(
                    self.current_version
                ),
                available_version=(
                    info.version
                ),
                metadata=asdict(
                    info
                ),
            )

            self._record(
                "fetch_manifest",
                result.to_dict(),
            )

            return result

        except Exception as exc:

            logger.warning(
                "Manifest request failed: %s",
                exc,
            )

            return UpdateResult(
                success=False,
                operation="fetch_manifest",
                message=(
                    "Unable to retrieve update information."
                ),
                current_version=(
                    self.current_version
                ),
                error=str(exc),
            )

    # ========================================================
    # CHECK UPDATE
    # ========================================================

    def check_for_update(
        self,
    ) -> UpdateResult:

        # If no remote manifest exists but a direct package
        # URL was configured, there is no reliable version
        # information. We refuse to guess.
        if not self.manifest_url:

            return UpdateResult(
                success=False,
                operation="check_update",
                message=(
                    "No update manifest URL is configured. "
                    "A direct package URL alone cannot "
                    "determine whether an update exists."
                ),
                current_version=(
                    self.current_version
                ),
                error="manifest_url_missing",
            )

        manifest_result = (
            self.fetch_manifest()
        )

        if not manifest_result.success:

            manifest_result.operation = (
                "check_update"
            )

            return manifest_result

        available = (
            manifest_result.available_version
        )

        if not self.is_newer(
            available
        ):

            result = UpdateResult(
                success=True,
                operation="check_update",
                message=(
                    "JarvisOS is already up to date."
                ),
                current_version=(
                    self.current_version
                ),
                available_version=available,
                metadata=(
                    manifest_result.metadata
                ),
            )

            self._record(
                "check_update",
                result.to_dict(),
            )

            return result

        result = UpdateResult(
            success=True,
            operation="check_update",
            message=(
                f"Version {available} is available."
            ),
            current_version=(
                self.current_version
            ),
            available_version=available,
            metadata=(
                manifest_result.metadata
            ),
        )

        self._record(
            "check_update",
            result.to_dict(),
        )

        return result

    # ========================================================
    # DOWNLOAD
    # ========================================================

    def download_update(
        self,
        update: Optional[
            UpdateInfo
        ] = None,
        *,
        confirm: bool = False,
    ) -> UpdateResult:

        if not confirm:

            return UpdateResult(
                success=False,
                operation="download_update",
                message=(
                    "Downloading an update requires "
                    "explicit confirmation."
                ),
                error="confirmation_required",
            )

        if requests is None:

            return UpdateResult(
                success=False,
                operation="download_update",
                message=(
                    "The requests package is not installed."
                ),
                error="requests_missing",
            )

        info = (
            update
            or self.last_update
        )

        if info is None:

            check = (
                self.check_for_update()
            )

            if not check.success:

                return UpdateResult(
                    success=False,
                    operation="download_update",
                    message=check.message,
                    current_version=(
                        self.current_version
                    ),
                    available_version=(
                        check.available_version
                    ),
                    error=check.error,
                )

            info = UpdateInfo(
                version=(
                    check.available_version
                ),
                url=str(
                    check.metadata.get(
                        "url",
                        "",
                    )
                ),
                sha256=str(
                    check.metadata.get(
                        "sha256",
                        "",
                    )
                ),
            )

        if not info.url:

            return UpdateResult(
                success=False,
                operation="download_update",
                message=(
                    "No update package URL is available."
                ),
                error="package_url_missing",
            )

        if not self._validate_url(
            info.url
        ):

            return UpdateResult(
                success=False,
                operation="download_update",
                message=(
                    "Update package URL is invalid."
                ),
                error="invalid_package_url",
            )

        # Do not download an older/equal version.
        if not self.is_newer(
            info.version
        ):

            return UpdateResult(
                success=False,
                operation="download_update",
                message=(
                    "The update version is not newer "
                    "than the installed version."
                ),
                current_version=(
                    self.current_version
                ),
                available_version=(
                    info.version
                ),
                error="not_newer",
            )

        safe_version = (
            "".join(
                char
                for char in info.version
                if char.isalnum()
                or char in "._-"
            )
        )

        if not safe_version:
            safe_version = "unknown"

        package_path = (
            self.staging_dir
            / f"JarvisOS-{safe_version}.update"
        )

        temporary_path = (
            self.staging_dir
            / f".download-{safe_version}-{int(time.time())}.tmp"
        )

        downloaded = 0

        try:

            with requests.get(
                info.url,
                stream=True,
                timeout=self.timeout,
                headers={
                    "User-Agent": (
                        "JarvisOS-Updater/1.0"
                    )
                },
            ) as response:

                response.raise_for_status()

                content_length = response.headers.get(
                    "Content-Length"
                )

                if (
                    content_length
                    and content_length.isdigit()
                    and info.size_bytes
                    and int(content_length)
                    > info.size_bytes
                ):

                    raise ValueError(
                        "Downloaded package is larger "
                        "than the manifest size."
                    )

                with open(
                    temporary_path,
                    "wb",
                ) as file:

                    for chunk in response.iter_content(
                        chunk_size=1024 * 128
                    ):

                        if not chunk:
                            continue

                        file.write(chunk)

                        downloaded += len(
                            chunk
                        )

                        # If the manifest gives a size,
                        # do not accept a larger package.
                        if (
                            info.size_bytes
                            and downloaded
                            > info.size_bytes
                        ):

                            raise ValueError(
                                "Downloaded package exceeded "
                                "the declared size."
                            )

            temporary_path.replace(
                package_path
            )

            verified = False

            if info.sha256:

                actual_hash = (
                    self.sha256_file(
                        package_path
                    )
                )

                verified = (
                    actual_hash.lower()
                    == info.sha256.lower()
                )

                if not verified:

                    package_path.unlink(
                        missing_ok=True
                    )

                    raise ValueError(
                        "SHA-256 verification failed."
                    )

            self.last_download = (
                package_path
            )

            result = UpdateResult(
                success=True,
                operation="download_update",
                message=(
                    "Update package downloaded successfully."
                ),
                current_version=(
                    self.current_version
                ),
                available_version=(
                    info.version
                ),
                file_path=str(
                    package_path
                ),
                downloaded_bytes=downloaded,
                verified=verified,
                metadata={
                    "sha256_provided": bool(
                        info.sha256
                    ),
                    "verification_performed": (
                        bool(info.sha256)
                    ),
                },
            )

            self._record(
                "download_update",
                result.to_dict(),
            )

            return result

        except Exception as exc:

            try:
                temporary_path.unlink(
                    missing_ok=True
                )
            except Exception:
                pass

            try:
                package_path.unlink(
                    missing_ok=True
                )
            except Exception:
                pass

            logger.error(
                "Update download failed: %s",
                exc,
            )

            return UpdateResult(
                success=False,
                operation="download_update",
                message=(
                    "Update package could not be downloaded."
                ),
                current_version=(
                    self.current_version
                ),
                available_version=(
                    info.version
                ),
                downloaded_bytes=downloaded,
                error=str(exc),
            )

    # ========================================================
    # SHA-256
    # ========================================================

    @staticmethod
    def sha256_file(
        path: str | Path,
        chunk_size: int = 1024 * 1024,
    ) -> str:

        file_path = (
            Path(path)
            .expanduser()
            .resolve()
        )

        if not file_path.is_file():

            raise FileNotFoundError(
                f"File not found: {file_path}"
            )

        digest = hashlib.sha256()

        with open(
            file_path,
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
    # PACKAGE VALIDATION
    # ========================================================

    @staticmethod
    def _is_safe_archive_path(
        name: str,
    ) -> bool:

        if not name:
            return False

        normalized = name.replace(
            "\\",
            "/",
        )

        if normalized.startswith(
            "/"
        ):
            return False

        if (
            len(normalized) >= 2
            and normalized[1] == ":"
        ):
            return False

        parts = Path(
            normalized
        ).parts

        if ".." in parts:
            return False

        return True

    def validate_package(
        self,
        package_path: str | Path,
    ) -> UpdateResult:

        path = (
            Path(package_path)
            .expanduser()
            .resolve()
        )

        if not path.is_file():

            return UpdateResult(
                success=False,
                operation="validate_package",
                message=(
                    "Update package does not exist."
                ),
                file_path=str(path),
                error="file_not_found",
            )

        if not zipfile.is_zipfile(
            path
        ):

            return UpdateResult(
                success=False,
                operation="validate_package",
                message=(
                    "Update package is not a valid ZIP archive."
                ),
                file_path=str(path),
                error="invalid_zip",
            )

        try:

            with zipfile.ZipFile(
                path,
                "r",
            ) as archive:

                members = archive.infolist()

                if not members:

                    raise ValueError(
                        "Update archive is empty."
                    )

                total_uncompressed = 0

                for member in members:

                    if not self._is_safe_archive_path(
                        member.filename
                    ):

                        raise ValueError(
                            "Archive contains an unsafe path."
                        )

                    total_uncompressed += (
                        member.file_size
                    )

                names = {
                    member.filename.replace(
                        "\\",
                        "/",
                    ).lower()
                    for member in members
                }

                has_manifest = any(
                    name == "update.json"
                    or name.endswith(
                        "/update.json"
                    )
                    for name in names
                )

                # The archive may be an installer package,
                # so update.json is recommended but not mandatory.
                metadata = {
                    "file_count": len(
                        members
                    ),
                    "uncompressed_bytes": (
                        total_uncompressed
                    ),
                    "has_update_manifest": (
                        has_manifest
                    ),
                }

                return UpdateResult(
                    success=True,
                    operation="validate_package",
                    message=(
                        "Update package passed archive safety checks."
                    ),
                    file_path=str(path),
                    verified=True,
                    metadata=metadata,
                )

        except Exception as exc:

            return UpdateResult(
                success=False,
                operation="validate_package",
                message=(
                    "Update package failed validation."
                ),
                file_path=str(path),
                error=str(exc),
            )

    # ========================================================
    # STAGE ZIP
    # ========================================================

    def stage_package(
        self,
        package_path: str | Path,
        *,
        confirm: bool = False,
    ) -> UpdateResult:

        if not confirm:

            return UpdateResult(
                success=False,
                operation="stage_package",
                message=(
                    "Staging an update requires confirmation."
                ),
                error="confirmation_required",
            )

        validation = (
            self.validate_package(
                package_path
            )
        )

        if not validation.success:

            validation.operation = (
                "stage_package"
            )

            return validation

        source = (
            Path(package_path)
            .expanduser()
            .resolve()
        )

        stage_root = (
            self.staging_dir
            / "prepared"
            / f"stage-{int(time.time())}"
        )

        stage_root.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:

            with zipfile.ZipFile(
                source,
                "r",
            ) as archive:

                for member in archive.infolist():

                    if not self._is_safe_archive_path(
                        member.filename
                    ):
                        raise ValueError(
                            "Unsafe archive path detected."
                        )

                    target = (
                        stage_root
                        / member.filename
                    ).resolve()

                    if (
                        stage_root
                        not in target.parents
                        and target != stage_root
                    ):
                        raise ValueError(
                            "Archive path escapes staging directory."
                        )

                    if member.is_dir():

                        target.mkdir(
                            parents=True,
                            exist_ok=True,
                        )

                        continue

                    target.parent.mkdir(
                        parents=True,
                        exist_ok=True,
                    )

                    with archive.open(
                        member,
                        "r",
                    ) as source_file:

                        with open(
                            target,
                            "wb",
                        ) as target_file:

                            shutil.copyfileobj(
                                source_file,
                                target_file,
                            )

            result = UpdateResult(
                success=True,
                operation="stage_package",
                message=(
                    "Update package has been safely staged."
                ),
                file_path=str(
                    stage_root
                ),
                verified=True,
            )

            self._record(
                "stage_package",
                result.to_dict(),
            )

            return result

        except Exception as exc:

            shutil.rmtree(
                stage_root,
                ignore_errors=True,
            )

            return UpdateResult(
                success=False,
                operation="stage_package",
                message=(
                    "Could not stage the update package."
                ),
                error=str(exc),
            )

    # ========================================================
    # INSTALLER HANDOFF
    # ========================================================

    def prepare_install(
        self,
        package_path: str | Path,
        *,
        confirm: bool = False,
    ) -> UpdateResult:

        """
        Validate and stage an update.

        This method intentionally stops before executing
        any installer or executable.
        """

        if not confirm:

            return UpdateResult(
                success=False,
                operation="prepare_install",
                message=(
                    "Preparing installation requires confirmation."
                ),
                error="confirmation_required",
            )

        validation = (
            self.validate_package(
                package_path
            )
        )

        if not validation.success:

            validation.operation = (
                "prepare_install"
            )

            return validation

        staged = (
            self.stage_package(
                package_path,
                confirm=True,
            )
        )

        if not staged.success:

            staged.operation = (
                "prepare_install"
            )

            return staged

        return UpdateResult(
            success=True,
            operation="prepare_install",
            message=(
                "Update is validated and staged. "
                "A trusted installer may now install it."
            ),
            file_path=staged.file_path,
            verified=True,
            metadata={
                "installer_executed": False,
                "requires_trusted_installer": True,
            },
        )

    # ========================================================
    # CLEANUP
    # ========================================================

    def cleanup(
        self,
    ) -> int:

        removed = 0

        with self._lock:

            if not self.staging_dir.exists():
                return 0

            for child in list(
                self.staging_dir.iterdir()
            ):

                try:

                    if child.is_dir():
                        shutil.rmtree(
                            child
                        )
                    else:
                        child.unlink()

                    removed += 1

                except Exception as exc:

                    logger.warning(
                        "Could not remove update file %s: %s",
                        child,
                        exc,
                    )

        self.last_download = None

        return removed

    # ========================================================
    # HISTORY
    # ========================================================

    def _record(
        self,
        operation: str,
        data: Dict[str, Any],
    ) -> None:

        with self._lock:

            self.history.append(
                {
                    "timestamp": self._now(),
                    "operation": operation,
                    "data": data,
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

            staged_files = []

            prepared = (
                self.staging_dir
                / "prepared"
            )

            if prepared.exists():

                for path in prepared.rglob(
                    "*"
                ):

                    if path.is_file():

                        staged_files.append(
                            str(path)
                        )

            return {
                "current_version": (
                    self.current_version
                ),
                "manifest_url_configured": bool(
                    self.manifest_url
                ),
                "direct_update_url_configured": bool(
                    self.update_url
                ),
                "staging_dir": str(
                    self.staging_dir
                ),
                "last_available_version": (
                    self.last_update.version
                    if self.last_update
                    else ""
                ),
                "last_download": (
                    str(self.last_download)
                    if self.last_download
                    else ""
                ),
                "staged_file_count": len(
                    staged_files
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
        pass

    def __enter__(
        self,
    ) -> "AutoUpdate":
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

_auto_update: Optional[
    AutoUpdate
] = None

_auto_update_lock = (
    threading.Lock()
)


def get_auto_update() -> AutoUpdate:

    global _auto_update

    with _auto_update_lock:

        if _auto_update is None:

            _auto_update = (
                AutoUpdate()
            )

        return _auto_update


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def check_for_update() -> UpdateResult:

    return (
        get_auto_update()
        .check_for_update()
    )


def download_update(
    *,
    confirm: bool = False,
) -> UpdateResult:

    return (
        get_auto_update()
        .download_update(
            confirm=confirm
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
        "JARVIS OS - AUTO UPDATE TEST"
    )
    print("=" * 60)

    updater = AutoUpdate(
        current_version="1.0.0"
    )

    print("\nVersion comparison:")

    print(
        "1.1.0 newer than 1.0.0:",
        updater.is_newer("1.1.0"),
    )

    print(
        "1.0.0 newer than 1.0.0:",
        updater.is_newer("1.0.0"),
    )

    print(
        "0.9.0 newer than 1.0.0:",
        updater.is_newer("0.9.0"),
    )

    print("\nStatus:")

    print(
        json.dumps(
            updater.get_status(),
            indent=2,
        )
    )

    # No network request, download or installation is
    # performed by the direct test.
    print(
        "\nNo update was downloaded or installed."
    )

    updater.close()

    print(
        "\nAuto-update test completed."
  )
