plugins/marketplace.py

"""
JarvisOS - Plugin Marketplace

Safe plugin discovery, download, validation and installation.

Features:

- Search a configured remote marketplace
- Read plugin metadata
- Download plugin ZIP packages
- Verify SHA-256 when supplied
- Detect ZIP path-traversal attacks
- Validate plugin.json and plugin.py
- Install plugins safely
- Uninstall plugins with confirmation
- Local ZIP installation
- Never executes a plugin during installation

Environment variables:

JARVIS_PLUGIN_MARKETPLACE_URL=
JARVIS_PLUGIN_MARKETPLACE_TIMEOUT=30
JARVIS_PLUGIN_MAX_PACKAGE_MB=25

Expected marketplace API:

GET <MARKETPLACE_URL>/search?q=<query>&limit=<limit>

Possible response:

{
"plugins": [
{
"id": "example",
"name": "Example Plugin",
"version": "1.0.0",
"description": "Example",
"download_url": "https://...",
"sha256": "..."
}
]
}

The marketplace URL is intentionally empty by default.
JarvisOS will not connect to an invented/fake service.
"""

from future import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import tempfile
import time
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin, urlparse

try:
import requests
except ImportError:
requests = None

logger = logging.getLogger(
"JarvisOS.PluginMarketplace"
)

============================================================

DATA CLASSES

============================================================

@dataclass
class MarketplacePlugin:
"""Remote plugin metadata."""

plugin_id: str
name: str = ""
version: str = ""
description: str = ""
author: str = ""
download_url: str = ""
sha256: str = ""
homepage: str = ""
category: str = ""

def to_dict(self) -> dict[str, Any]:
    return asdict(self)

@dataclass
class MarketplaceResult:
"""Standard marketplace operation result."""

success: bool
message: str = ""
error: str = ""
data: Any = None

def to_dict(self) -> dict[str, Any]:
    return asdict(self)

============================================================

MARKETPLACE

============================================================

class PluginMarketplace:
"""
Plugin marketplace client.

Downloads are treated as untrusted input.

A downloaded plugin is NEVER automatically imported,
loaded or executed by this class.
"""

DEFAULT_TIMEOUT = 30

DEFAULT_MAX_PACKAGE_MB = 25

def __init__(
    self,
    marketplace_url: Optional[str] = None,
    plugins_dir: Optional[str | Path] = None,
    timeout: Optional[int] = None,
    max_package_mb: Optional[int] = None,
) -> None:

    self.marketplace_url = (
        marketplace_url
        or os.getenv(
            "JARVIS_PLUGIN_MARKETPLACE_URL",
            "",
        ).strip()
    )

    self.plugins_dir = (
        Path(plugins_dir)
        if plugins_dir
        else Path("plugins")
    )

    self.plugins_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:

        self.timeout = int(
            timeout
            if timeout is not None
            else os.getenv(
                "JARVIS_PLUGIN_MARKETPLACE_TIMEOUT",
                str(self.DEFAULT_TIMEOUT),
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        self.timeout = (
            self.DEFAULT_TIMEOUT
        )

    try:

        self.max_package_mb = int(
            max_package_mb
            if max_package_mb is not None
            else os.getenv(
                "JARVIS_PLUGIN_MAX_PACKAGE_MB",
                str(
                    self.DEFAULT_MAX_PACKAGE_MB
                ),
            )
        )

    except (
        TypeError,
        ValueError,
    ):

        self.max_package_mb = (
            self.DEFAULT_MAX_PACKAGE_MB
        )

    self.timeout = max(
        5,
        min(
            self.timeout,
            180,
        ),
    )

    self.max_package_mb = max(
        1,
        min(
            self.max_package_mb,
            500,
        ),
    )

    self.history: list[
        dict[str, Any]
    ] = []

# ========================================================
# VALIDATION
# ========================================================

@staticmethod
def validate_plugin_id(
    plugin_id: str,
) -> str:

    plugin_id = (
        str(plugin_id)
        .strip()
        .lower()
    )

    if not plugin_id:

        raise ValueError(
            "Plugin ID cannot be empty."
        )

    if len(plugin_id) > 80:

        raise ValueError(
            "Plugin ID is too long."
        )

    if not re.fullmatch(
        r"[a-z0-9][a-z0-9_.-]*",
        plugin_id,
    ):

        raise ValueError(
            "Invalid plugin ID."
        )

    return plugin_id

@staticmethod
def validate_url(
    url: str,
) -> str:

    url = str(
        url
    ).strip()

    parsed = urlparse(
        url
    )

    if parsed.scheme not in (
        "http",
        "https",
    ):

        raise ValueError(
            "Only HTTP/HTTPS URLs are allowed."
        )

    if not parsed.netloc:

        raise ValueError(
            "URL has no host."
        )

    return url

# ========================================================
# CONFIGURATION
# ========================================================

def is_configured(self) -> bool:

    return bool(
        self.marketplace_url
    )

def get_status(self) -> dict[str, Any]:

    return {
        "configured": self.is_configured(),
        "marketplace_url_configured": bool(
            self.marketplace_url
        ),
        "plugins_dir": str(
            self.plugins_dir
        ),
        "timeout": self.timeout,
        "max_package_mb": (
            self.max_package_mb
        ),
        "requests_available": (
            requests is not None
        ),
    }

# ========================================================
# SEARCH
# ========================================================

def search(
    self,
    query: str = "",
    limit: int = 20,
) -> MarketplaceResult:

    if requests is None:

        return MarketplaceResult(
            success=False,
            error=(
                "The 'requests' package "
                "is not installed."
            ),
        )

    if not self.is_configured():

        return MarketplaceResult(
            success=False,
            error=(
                "Plugin marketplace is not configured. "
                "Set JARVIS_PLUGIN_MARKETPLACE_URL."
            ),
        )

    try:

        limit = max(
            1,
            min(
                int(limit),
                100,
            ),
        )

    except (
        TypeError,
        ValueError,
    ):

        limit = 20

    query = str(
        query
    ).strip()

    try:

        base_url = self.marketplace_url.rstrip(
            "/"
        )

        search_url = urljoin(
            base_url + "/",
            "search",
        )

        self.validate_url(
            search_url
        )

        response = requests.get(
            search_url,
            params={
                "q": query,
                "limit": limit,
            },
            timeout=self.timeout,
        )

        response.raise_for_status()

        payload = response.json()

        plugins = self._parse_catalog(
            payload
        )

        self._record(
            "search",
            {
                "query": query,
                "count": len(
                    plugins
                ),
            },
        )

        return MarketplaceResult(
            success=True,
            message=(
                f"Found {len(plugins)} plugin(s)."
            ),
            data=[
                item.to_dict()
                for item in plugins
            ],
        )

    except Exception as exc:

        logger.error(
            "Marketplace search failed: %s",
            exc,
        )

        return MarketplaceResult(
            success=False,
            error=str(exc),
        )

# ========================================================
# PARSE CATALOG
# ========================================================

@staticmethod
def _parse_catalog(
    payload: Any,
) -> list[MarketplacePlugin]:

    if isinstance(
        payload,
        dict,
    ):

        raw_plugins = (
            payload.get(
                "plugins",
                payload.get(
                    "results",
                    payload.get(
                        "data",
                        [],
                    ),
                ),
            )
        )

    elif isinstance(
        payload,
        list,
    ):

        raw_plugins = payload

    else:

        raw_plugins = []

    if not isinstance(
        raw_plugins,
        list,
    ):

        return []

    result = []

    for item in raw_plugins:

        if not isinstance(
            item,
            dict,
        ):

            continue

        try:

            plugin_id = (
                item.get(
                    "plugin_id",
                    item.get(
                        "id",
                        "",
                    ),
                )
            )

            plugin_id = (
                PluginMarketplace
                .validate_plugin_id(
                    plugin_id
                )
            )

        except Exception:

            continue

        result.append(
            MarketplacePlugin(
                plugin_id=plugin_id,
                name=str(
                    item.get(
                        "name",
                        plugin_id,
                    )
                ),
                version=str(
                    item.get(
                        "version",
                        "",
                    )
                ),
                description=str(
                    item.get(
                        "description",
                        "",
                    )
                ),
                author=str(
                    item.get(
                        "author",
                        "",
                    )
                ),
                download_url=str(
                    item.get(
                        "download_url",
                        item.get(
                            "url",
                            "",
                        ),
                    )
                ),
                sha256=str(
                    item.get(
                        "sha256",
                        "",
                    )
                ),
                homepage=str(
                    item.get(
                        "homepage",
                        "",
                    )
                ),
                category=str(
                    item.get(
                        "category",
                        "",
                    )
                ),
            )
        )

    return result

# ========================================================
# FETCH METADATA
# ========================================================

def fetch_metadata(
    self,
    plugin_url: str,
) -> MarketplaceResult:

    if requests is None:

        return MarketplaceResult(
            success=False,
            error=(
                "The 'requests' package "
                "is not installed."
            ),
        )

    try:

        plugin_url = self.validate_url(
            plugin_url
        )

        response = requests.get(
            plugin_url,
            timeout=self.timeout,
        )

        response.raise_for_status()

        data = response.json()

        return MarketplaceResult(
            success=True,
            message="Plugin metadata retrieved.",
            data=data,
        )

    except Exception as exc:

        return MarketplaceResult(
            success=False,
            error=str(exc),
        )

# ========================================================
# DOWNLOAD
# ========================================================

def download(
    self,
    plugin: MarketplacePlugin | dict[str, Any],
    destination: Optional[str | Path] = None,
    confirm: bool = False,
) -> MarketplaceResult:

    """
    Download plugin package.

    Downloading external executable/plugin content is an
    external side effect, so confirmation is required.
    """

    if not confirm:

        return MarketplaceResult(
            success=False,
            error=(
                "confirm=True is required "
                "to download a plugin."
            ),
        )

    if requests is None:

        return MarketplaceResult(
            success=False,
            error=(
                "The 'requests' package "
                "is not installed."
            ),
        )

    metadata = (
        self._plugin_from_any(
            plugin
        )
    )

    if metadata is None:

        return MarketplaceResult(
            success=False,
            error=(
                "Invalid plugin metadata."
            ),
        )

    if not metadata.download_url:

        return MarketplaceResult(
            success=False,
            error=(
                "Plugin has no download URL."
            ),
        )

    try:

        download_url = self.validate_url(
            metadata.download_url
        )

        if destination:

            destination_path = Path(
                destination
            ).expanduser()

        else:

            destination_path = (
                Path(tempfile.gettempdir())
                / (
                    f"jarvis_plugin_"
                    f"{metadata.plugin_id}.zip"
                )
            )

        destination_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with requests.get(
            download_url,
            stream=True,
            timeout=self.timeout,
        ) as response:

            response.raise_for_status()

            content_length = response.headers.get(
                "Content-Length"
            )

            if content_length:

                try:

                    declared_size = int(
                        content_length
                    )

                    if declared_size > (
                        self.max_package_mb
                        * 1024
                        * 1024
                    ):

                        return MarketplaceResult(
                            success=False,
                            error=(
                                "Plugin package exceeds "
                                "the configured size limit."
                            ),
                        )

                except ValueError:
                    pass

            total = 0

            with destination_path.open(
                "wb"
            ) as file:

                for chunk in response.iter_content(
                    chunk_size=64 * 1024
                ):

                    if not chunk:
                        continue

                    total += len(
                        chunk
                    )

                    if total > (
                        self.max_package_mb
                        * 1024
                        * 1024
                    ):

                        try:
                            destination_path.unlink()
                        except Exception:
                            pass

                        return MarketplaceResult(
                            success=False,
                            error=(
                                "Plugin package exceeds "
                                "the configured size limit."
                            ),
                        )

                    file.write(
                        chunk
                    )

        actual_sha256 = (
            self.calculate_sha256(
                destination_path
            )
        )

        if metadata.sha256:

            expected = (
                metadata.sha256
                .strip()
                .lower()
            )

            if not re.fullmatch(
                r"[a-f0-9]{64}",
                expected,
            ):

                return MarketplaceResult(
                    success=False,
                    error=(
                        "Marketplace supplied an "
                        "invalid SHA-256 value."
                    ),
                )

            if actual_sha256 != expected:

                try:
                    destination_path.unlink()
                except Exception:
                    pass

                return MarketplaceResult(
                    success=False,
                    error=(
                        "Plugin SHA-256 verification failed."
                    ),
                )

        self._record(
            "download",
            {
                "plugin_id": metadata.plugin_id,
                "path": str(
                    destination_path
                ),
                "sha256": actual_sha256,
            },
        )

        return MarketplaceResult(
            success=True,
            message="Plugin package downloaded.",
            data={
                "path": str(
                    destination_path
                ),
                "sha256": actual_sha256,
                "size": total,
            },
        )

    except Exception as exc:

        logger.error(
            "Plugin download failed: %s",
            exc,
        )

        return MarketplaceResult(
            success=False,
            error=str(exc),
        )

# ========================================================
# ZIP SECURITY
# ========================================================

def validate_package(
    self,
    zip_path: str | Path,
) -> MarketplaceResult:

    path = Path(
        zip_path
    ).expanduser()

    if not path.exists():

        return MarketplaceResult(
            success=False,
            error="Plugin package does not exist.",
        )

    if not path.is_file():

        return MarketplaceResult(
            success=False,
            error="Plugin package is not a file.",
        )

    try:

        size = path.stat().st_size

        if size > (
            self.max_package_mb
            * 1024
            * 1024
        ):

            return MarketplaceResult(
                success=False,
                error=(
                    "Plugin package exceeds "
                    "the configured size limit."
                ),
            )

        with zipfile.ZipFile(
            path,
            "r",
        ) as archive:

            names = archive.namelist()

            if not names:

                return MarketplaceResult(
                    success=False,
                    error="Plugin ZIP is empty.",
                )

            for name in names:

                if not self._safe_archive_name(
                    name
                ):

                    return MarketplaceResult(
                        success=False,
                        error=(
                            "Unsafe ZIP path detected: "
                            f"{name}"
                        ),
                    )

            manifest_name = (
                self._find_archive_file(
                    names,
                    "plugin.json",
                )
            )

            entry_name = (
                self._find_archive_file(
                    names,
                    "plugin.py",
                )
            )

            if not manifest_name:

                return MarketplaceResult(
                    success=False,
                    error=(
                        "Plugin package must contain "
                        "plugin.json."
                    ),
                )

            if not entry_name:

                return MarketplaceResult(
                    success=False,
                    error=(
                        "Plugin package must contain "
                        "plugin.py."
                    ),
                )

            try:

                raw_manifest = (
                    archive.read(
                        manifest_name
                    )
                )

                manifest = json.loads(
                    raw_manifest.decode(
                        "utf-8"
                    )
                )

            except Exception as exc:

                return MarketplaceResult(
                    success=False,
                    error=(
                        "Invalid plugin.json: "
                        f"{exc}"
                    ),
                )

            if not isinstance(
                manifest,
                dict,
            ):

                return MarketplaceResult(
                    success=False,
                    error=(
                        "plugin.json must contain "
                        "a JSON object."
                    ),
                )

            plugin_id = manifest.get(
                "id",
                manifest.get(
                    "plugin_id",
                    "",
                ),
            )

            try:

                plugin_id = (
                    self.validate_plugin_id(
                        plugin_id
                    )
                )

            except ValueError as exc:

                return MarketplaceResult(
                    success=False,
                    error=str(
                        exc
                    ),
                )

            entry = str(
                manifest.get(
                    "entry",
                    "plugin.py",
                )
            ).strip()

            if not entry:

                entry = "plugin.py"

            entry_basename = Path(
                entry
            ).name

            if not any(
                Path(name).name
                == entry_basename
                for name in names
            ):

                return MarketplaceResult(
                    success=False,
                    error=(
                        "Plugin entry file is missing."
                    ),
                )

            return MarketplaceResult(
                success=True,
                message=(
                    "Plugin package passed "
                    "basic security validation."
                ),
                data={
                    "plugin_id": plugin_id,
                    "manifest": manifest,
                    "manifest_path": manifest_name,
                    "entry": entry,
                    "files": len(names),
                    "sha256": self.calculate_sha256(
                        path
                    ),
                },
            )

    except zipfile.BadZipFile:

        return MarketplaceResult(
            success=False,
            error="Invalid ZIP package.",
        )

    except Exception as exc:

        return MarketplaceResult(
            success=False,
            error=str(exc),
        )

@staticmethod
def _safe_archive_name(
    name: str,
) -> bool:

    if not name:
        return False

    # ZIP paths always use forward slashes.
    normalized = name.replace(
        "\\",
        "/",
    )

    if normalized.startswith(
        "/"
    ):

        return False

    if re.match(
        r"^[A-Za-z]:",
        normalized,
    ):

        return False

    parts = normalized.split(
        "/"
    )

    if ".." in parts:

        return False

    return True

@staticmethod
def _find_archive_file(
    names: list[str],
    filename: str,
) -> Optional[str]:

    filename = filename.lower()

    for name in names:

        if Path(name).name.lower() == filename:

            return name

    return None

# ========================================================
# INSTALL
# ========================================================

def install_zip(
    self,
    zip_path: str | Path,
    confirm: bool = False,
    overwrite: bool = False,
) -> MarketplaceResult:

    """
    Install a validated plugin ZIP.

    The plugin is extracted but NOT executed.
    """

    if not confirm:

        return MarketplaceResult(
            success=False,
            error=(
                "confirm=True is required "
                "to install a plugin."
            ),
        )

    validation = self.validate_package(
        zip_path
    )

    if not validation.success:

        return validation

    manifest = (
        validation.data["manifest"]
    )

    plugin_id = (
        validation.data["plugin_id"]
    )

    try:

        target = (
            self.plugins_dir
            / plugin_id
        )

        if target.exists():

            if not overwrite:

                return MarketplaceResult(
                    success=False,
                    error=(
                        "Plugin already exists. "
                        "Use overwrite=True."
                    ),
                )

            shutil.rmtree(
                target
            )

        staging = Path(
            tempfile.mkdtemp(
                prefix="jarvis_plugin_",
                dir=str(
                    self.plugins_dir
                ),
            )
        )

        try:

            with zipfile.ZipFile(
                Path(zip_path),
                "r",
            ) as archive:

                archive.extractall(
                    staging
                )

            actual_root = self._find_plugin_root(
                staging,
                plugin_id,
            )

            if actual_root is None:

                return MarketplaceResult(
                    success=False,
                    error=(
                        "Could not locate the "
                        "plugin root after extraction."
                    ),
                )

            # Re-check extracted files.
            for file_path in actual_root.rglob("*"):

                if file_path.is_symlink():

                    return MarketplaceResult(
                        success=False,
                        error=(
                            "Symbolic links are not "
                            "allowed in plugins."
                        ),
                    )

            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.move(
                str(actual_root),
                str(target),
            )

        finally:

            if staging.exists():

                shutil.rmtree(
                    staging,
                    ignore_errors=True,
                )

        self._record(
            "install",
            {
                "plugin_id": plugin_id,
                "path": str(
                    target
                ),
            },
        )

        return MarketplaceResult(
            success=True,
            message=(
                f"Plugin '{plugin_id}' installed. "
                "It has NOT been executed."
            ),
            data={
                "plugin_id": plugin_id,
                "path": str(
                    target
                ),
                "manifest": manifest,
            },
        )

    except Exception as exc:

        logger.error(
            "Plugin installation failed: %s",
            exc,
        )

        return MarketplaceResult(
            success=False,
            error=str(exc),
        )

# ========================================================
# FIND ROOT
# ========================================================

@staticmethod
def _find_plugin_root(
    staging: Path,
    plugin_id: str,
) -> Optional[Path]:

    direct = (
        staging
        / plugin_id
    )

    if (
        direct.exists()
        and direct.is_dir()
    ):

        return direct

    if (
        (staging / "plugin.json").exists()
        and (staging / "plugin.py").exists()
    ):

        return staging

    candidates = []

    for path in staging.iterdir():

        if (
            path.is_dir()
            and (
                path
                / "plugin.json"
            ).exists()
            and (
                path
                / "plugin.py"
            ).exists()
        ):

            candidates.append(
                path
            )

    if len(candidates) == 1:

        return candidates[0]

    return None

# ========================================================
# UNINSTALL
# ========================================================

def uninstall(
    self,
    plugin_id: str,
    confirm: bool = False,
) -> MarketplaceResult:

    if not confirm:

        return MarketplaceResult(
            success=False,
            error=(
                "confirm=True is required "
                "to uninstall a plugin."
            ),
        )

    try:

        plugin_id = (
            self.validate_plugin_id(
                plugin_id
            )
        )

    except ValueError as exc:

        return MarketplaceResult(
            success=False,
            error=str(exc),
        )

    target = (
        self.plugins_dir
        / plugin_id
    )

    if not target.exists():

        return MarketplaceResult(
            success=False,
            error=(
                "Plugin is not installed."
            ),
        )

    try:

        target_resolved = (
            target.resolve()
        )

        plugins_resolved = (
            self.plugins_dir.resolve()
        )

        try:

            target_resolved.relative_to(
                plugins_resolved
            )

        except ValueError:

            return MarketplaceResult(
                success=False,
                error=(
                    "Unsafe plugin path."
                ),
            )

        shutil.rmtree(
            target
        )

        self._record(
            "uninstall",
            {
                "plugin_id": plugin_id,
            },
        )

        return MarketplaceResult(
            success=True,
            message=(
                f"Plugin '{plugin_id}' uninstalled."
            ),
        )

    except Exception as exc:

        return MarketplaceResult(
            success=False,
            error=str(exc),
        )

# ========================================================
# PLUGIN MANAGER INTEGRATION
# ========================================================

def register_with_manager(
    self,
    plugin_manager: Any,
    plugin_id: str,
) -> MarketplaceResult:

    """
    Register an installed plugin with PluginManager.

    This method does not load or execute the plugin.
    """

    try:

        plugin_id = (
            self.validate_plugin_id(
                plugin_id
            )
        )

        target = (
            self.plugins_dir
            / plugin_id
        )

        if not target.exists():

            return MarketplaceResult(
                success=False,
                error=(
                    "Plugin is not installed."
                ),
            )

        if hasattr(
            plugin_manager,
            "register",
        ):

            result = (
                plugin_manager.register(
                    target
                )
            )

            return MarketplaceResult(
                success=True,
                message=(
                    "Plugin registered with "
                    "PluginManager."
                ),
                data=result,
            )

        return MarketplaceResult(
            success=False,
            error=(
                "PluginManager does not provide "
                "a compatible register() method."
            ),
        )

    except Exception as exc:

        return MarketplaceResult(
            success=False,
            error=str(exc),
        )

# ========================================================
# HASH
# ========================================================

@staticmethod
def calculate_sha256(
    path: str | Path,
) -> str:

    path = Path(
        path
    )

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as file:

        while True:

            chunk = file.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()

# ========================================================
# HELPERS
# ========================================================

@staticmethod
def _plugin_from_any(
    value: Any,
) -> Optional[MarketplacePlugin]:

    if isinstance(
        value,
        MarketplacePlugin,
    ):

        return value

    if isinstance(
        value,
        dict,
    ):

        try:

            plugin_id = (
                value.get(
                    "plugin_id",
                    value.get(
                        "id",
                        "",
                    ),
                )
            )

            return MarketplacePlugin(
                plugin_id=(
                    PluginMarketplace
                    .validate_plugin_id(
                        plugin_id
                    )
                ),
                name=str(
                    value.get(
                        "name",
                        "",
                    )
                ),
                version=str(
                    value.get(
                        "version",
                        "",
                    )
                ),
                description=str(
                    value.get(
                        "description",
                        "",
                    )
                ),
                author=str(
                    value.get(
                        "author",
                        "",
                    )
                ),
                download_url=str(
                    value.get(
                        "download_url",
                        value.get(
                            "url",
                            "",
                        ),
                    )
                ),
                sha256=str(
                    value.get(
                        "sha256",
                        "",
                    )
                ),
                homepage=str(
                    value.get(
                        "homepage",
                        "",
                    )
                ),
                category=str(
                    value.get(
                        "category",
                        "",
                    )
                ),
            )

        except Exception:

            return None

    return None

def _record(
    self,
    action: str,
    data: dict[str, Any],
) -> None:

    self.history.append(
        {
            "timestamp": datetime_now(),
            "action": action,
            "data": data,
        }
    )

    if len(
        self.history
    ) > 500:

        self.history = (
            self.history[-500:]
        )

def get_history(
    self,
    limit: int = 50,
) -> list[dict[str, Any]]:

    try:

        limit = max(
            1,
            min(
                int(limit),
                500,
            ),
        )

    except (
        TypeError,
        ValueError,
    ):

        limit = 50

    return list(
        reversed(
            self.history[-limit:]
        )
    )

def close(self) -> None:
    """Release resources."""

    # requests uses short-lived calls, so there is
    # no persistent session that needs closing.
    pass

def __enter__(
    self,
) -> "PluginMarketplace":

    return self

def __exit__(
    self,
    exc_type: Any,
    exc_value: Any,
    traceback_value: Any,
) -> None:

    self.close()

============================================================

TIME HELPER

============================================================

def datetime_now() -> str:
"""
Return an ISO timestamp without requiring another module.
"""

from datetime import datetime

return datetime.now().isoformat()

============================================================

SHARED INSTANCE

============================================================

_marketplace: Optional[
PluginMarketplace
] = None

def get_marketplace() -> PluginMarketplace:

global _marketplace

if _marketplace is None:

    _marketplace = (
        PluginMarketplace()
    )

return _marketplace

============================================================

CONVENIENCE FUNCTIONS

============================================================

def search_plugins(
query: str = "",
limit: int = 20,
) -> MarketplaceResult:

return get_marketplace().search(
    query=query,
    limit=limit,
)

def install_plugin(
zip_path: str | Path,
confirm: bool = False,
overwrite: bool = False,
) -> MarketplaceResult:

return get_marketplace().install_zip(
    zip_path=zip_path,
    confirm=confirm,
    overwrite=overwrite,
)

def uninstall_plugin(
plugin_id: str,
confirm: bool = False,
) -> MarketplaceResult:

return get_marketplace().uninstall(
    plugin_id=plugin_id,
    confirm=confirm,
)

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
print("JARVIS OS - PLUGIN MARKETPLACE TEST")
print("=" * 60)

marketplace = PluginMarketplace()

print(
    json.dumps(
        marketplace.get_status(),
        indent=2,
    )
)

print(
    "\nMarketplace is intentionally not contacted "
    "unless JARVIS_PLUGIN_MARKETPLACE_URL is configured."
)

print(
    "\nNo plugin was downloaded, installed or executed."
)
