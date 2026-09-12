"""
JarvisOS - Browser Control

Windows browser control for JarvisOS.

Features:
    - Detect installed browsers
    - Detect default browser
    - Open URLs
    - Perform web searches
    - Open a URL in a selected browser
    - Open a new browser window
    - Open a new browser tab
    - Close browser processes
    - Check browser status

This module focuses on launching and basic process-level control.
Advanced DOM/page automation belongs in the web/automation layer.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import webbrowser
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote_plus


try:
    import psutil
except ImportError:
    psutil = None


logger = logging.getLogger(__name__)


# ======================================================================
# DATA MODELS
# ======================================================================


@dataclass
class BrowserInfo:
    """Information about a browser."""

    name: str
    executable: str
    path: Optional[str]
    installed: bool
    running: bool = False

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class BrowserResult:
    """Result of a browser operation."""

    success: bool
    action: str
    message: str
    browser: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict] = None

    def to_dict(self) -> Dict:
        return asdict(self)


# ======================================================================
# BROWSER CONTROLLER
# ======================================================================


class BrowserControl:
    """
    Browser controller for JarvisOS.

    Supported browsers include common Windows installations of:

        - Google Chrome
        - Microsoft Edge
        - Mozilla Firefox
        - Brave
        - Opera
        - Vivaldi

    Browser executable discovery uses:
        - Windows registry
        - common installation paths
        - PATH
    """

    BROWSERS = {
        "chrome": {
            "display_name": "Google Chrome",
            "executable": "chrome.exe",
            "registry_names": [
                "Chrome",
            ],
        },
        "google chrome": {
            "display_name": "Google Chrome",
            "executable": "chrome.exe",
            "registry_names": [
                "Chrome",
            ],
        },
        "edge": {
            "display_name": "Microsoft Edge",
            "executable": "msedge.exe",
            "registry_names": [
                "Microsoft Edge",
            ],
        },
        "microsoft edge": {
            "display_name": "Microsoft Edge",
            "executable": "msedge.exe",
            "registry_names": [
                "Microsoft Edge",
            ],
        },
        "firefox": {
            "display_name": "Mozilla Firefox",
            "executable": "firefox.exe",
            "registry_names": [
                "Firefox",
            ],
        },
        "brave": {
            "display_name": "Brave",
            "executable": "brave.exe",
            "registry_names": [
                "Brave",
            ],
        },
        "opera": {
            "display_name": "Opera",
            "executable": "opera.exe",
            "registry_names": [
                "Opera",
            ],
        },
        "vivaldi": {
            "display_name": "Vivaldi",
            "executable": "vivaldi.exe",
            "registry_names": [
                "Vivaldi",
            ],
        },
    }

    PROCESS_ALIASES = {
        "chrome": "chrome.exe",
        "google chrome": "chrome.exe",
        "edge": "msedge.exe",
        "microsoft edge": "msedge.exe",
        "firefox": "firefox.exe",
        "brave": "brave.exe",
        "opera": "opera.exe",
        "vivaldi": "vivaldi.exe",
    }

    def __init__(
        self,
        default_browser: Optional[str] = None,
    ) -> None:

        self.default_browser = (
            self._normalize_browser_name(
                default_browser
            )
            if default_browser
            else None
        )

        logger.info(
            "BrowserControl initialized."
        )

    # ==================================================================
    # DETECT BROWSERS
    # ==================================================================

    def detect_browsers(
        self,
    ) -> List[BrowserInfo]:
        """Detect commonly installed browsers."""

        results: List[
            BrowserInfo
        ] = []

        seen = set()

        for key, data in self.BROWSERS.items():

            executable = data[
                "executable"
            ]

            if executable in seen:
                continue

            seen.add(
                executable
            )

            path = self.find_browser_path(
                executable
            )

            results.append(
                BrowserInfo(
                    name=data[
                        "display_name"
                    ],
                    executable=executable,
                    path=path,
                    installed=(
                        path is not None
                    ),
                    running=self.is_running(
                        executable
                    ),
                )
            )

        return results

    # ==================================================================
    # FIND BROWSER PATH
    # ==================================================================

    def find_browser_path(
        self,
        executable: str,
    ) -> Optional[str]:
        """Find an installed browser executable."""

        executable = str(
            executable
        ).strip()

        # --------------------------------------------------------------
        # PATH
        # --------------------------------------------------------------

        path_result = shutil.which(
            executable
        )

        if path_result:

            return path_result

        # --------------------------------------------------------------
        # Windows common paths
        # --------------------------------------------------------------

        if os.name != "nt":

            return None

        candidates = []

        program_files = os.environ.get(
            "ProgramFiles"
        )

        program_files_x86 = os.environ.get(
            "ProgramFiles(x86)"
        )

        local_app_data = os.environ.get(
            "LOCALAPPDATA"
        )

        app_data = os.environ.get(
            "APPDATA"
        )

        if executable.lower() == "chrome.exe":

            if program_files:

                candidates.append(
                    Path(program_files)
                    / "Google"
                    / "Chrome"
                    / "Application"
                    / executable
                )

            if program_files_x86:

                candidates.append(
                    Path(program_files_x86)
                    / "Google"
                    / "Chrome"
                    / "Application"
                    / executable
                )

            if local_app_data:

                candidates.append(
                    Path(local_app_data)
                    / "Google"
                    / "Chrome"
                    / "Application"
                    / executable
                )

        elif executable.lower() == "msedge.exe":

            if program_files:

                candidates.append(
                    Path(program_files)
                    / "Microsoft"
                    / "Edge"
                    / "Application"
                    / executable
                )

            if program_files_x86:

                candidates.append(
                    Path(program_files_x86)
                    / "Microsoft"
                    / "Edge"
                    / "Application"
                    / executable
                )

        elif executable.lower() == "firefox.exe":

            if program_files:

                candidates.append(
                    Path(program_files)
                    / "Mozilla Firefox"
                    / executable
                )

            if program_files_x86:

                candidates.append(
                    Path(program_files_x86)
                    / "Mozilla Firefox"
                    / executable
                )

        elif executable.lower() == "brave.exe":

            if program_files:

                candidates.append(
                    Path(program_files)
                    / "BraveSoftware"
                    / "Brave-Browser"
                    / "Application"
                    / executable
                )

            if local_app_data:

                candidates.append(
                    Path(local_app_data)
                    / "BraveSoftware"
                    / "Brave-Browser"
                    / "Application"
                    / executable
                )

        elif executable.lower() == "opera.exe":

            if local_app_data:

                candidates.append(
                    Path(local_app_data)
                    / "Programs"
                    / "Opera"
                    / executable
                )

            if program_files:

                candidates.append(
                    Path(program_files)
                    / "Opera"
                    / executable
                )

        elif executable.lower() == "vivaldi.exe":

            if program_files:

                candidates.append(
                    Path(program_files)
                    / "Vivaldi"
                    / "Application"
                    / executable
                )

            if local_app_data:

                candidates.append(
                    Path(local_app_data)
                    / "Vivaldi"
                    / "Application"
                    / executable
                )

        for candidate in candidates:

            try:

                if candidate.is_file():

                    return str(
                        candidate
                    )

            except OSError:

                continue

        return None

    # ==================================================================
    # NORMALIZE BROWSER
    # ==================================================================

    def _normalize_browser_name(
        self,
        browser: Optional[str],
    ) -> Optional[str]:

        if not browser:
            return None

        value = (
            str(browser)
            .strip()
            .lower()
        )

        if value in self.BROWSERS:

            data = self.BROWSERS[
                value
            ]

            return data[
                "executable"
            ]

        if value.endswith(
            ".exe"
        ):

            return value

        if value in self.PROCESS_ALIASES:

            return self.PROCESS_ALIASES[
                value
            ]

        return value

    # ==================================================================
    # DEFAULT BROWSER
    # ==================================================================

    def get_default_browser(
        self,
    ) -> Optional[BrowserInfo]:
        """Detect the Windows default browser."""

        if self.default_browser:

            executable = (
                self.default_browser
            )

            path = (
                self.find_browser_path(
                    executable
                )
            )

            return BrowserInfo(
                name=self._display_name_for_executable(
                    executable
                ),
                executable=executable,
                path=path,
                installed=path is not None,
                running=self.is_running(
                    executable
                ),
            )

        # --------------------------------------------------------------
        # Windows registry
        # --------------------------------------------------------------

        if os.name == "nt":

            try:

                import winreg

                key_path = (
                    r"Software\Microsoft"
                    r"\Windows\Shell"
                    r"\Associations\UrlAssociations\http"
                    r"\UserChoice"
                )

                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    key_path,
                ) as key:

                    prog_id, _ = (
                        winreg.QueryValueEx(
                            key,
                            "ProgId",
                        )
                    )

                prog_id = str(
                    prog_id
                ).lower()

                if "chrome" in prog_id:

                    executable = "chrome.exe"

                elif "edge" in prog_id:

                    executable = "msedge.exe"

                elif "firefox" in prog_id:

                    executable = "firefox.exe"

                elif "brave" in prog_id:

                    executable = "brave.exe"

                elif "opera" in prog_id:

                    executable = "opera.exe"

                elif "vivaldi" in prog_id:

                    executable = "vivaldi.exe"

                else:

                    executable = None

                if executable:

                    path = (
                        self.find_browser_path(
                            executable
                        )
                    )

                    return BrowserInfo(
                        name=(
                            self._display_name_for_executable(
                                executable
                            )
                        ),
                        executable=executable,
                        path=path,
                        installed=(
                            path is not None
                        ),
                        running=self.is_running(
                            executable
                        ),
                    )

            except Exception as exc:

                logger.debug(
                    "Default browser registry lookup failed: %s",
                    exc,
                )

        # --------------------------------------------------------------
        # Fallback to Python's webbrowser module
        # --------------------------------------------------------------

        try:

            controller = (
                webbrowser.get()
            )

            command = str(
                getattr(
                    controller,
                    "name",
                    "",
                )
            ).lower()

            if "chrome" in command:

                executable = "chrome.exe"

            elif "firefox" in command:

                executable = "firefox.exe"

            elif "edge" in command:

                executable = "msedge.exe"

            else:

                executable = None

            if executable:

                path = (
                    self.find_browser_path(
                        executable
                    )
                )

                return BrowserInfo(
                    name=(
                        self._display_name_for_executable(
                            executable
                        )
                    ),
                    executable=executable,
                    path=path,
                    installed=(
                        path is not None
                    ),
                    running=self.is_running(
                        executable
                    ),
                )

        except Exception:

            pass

        return None

    # ==================================================================
    # OPEN URL
    # ==================================================================

    def open_url(
        self,
        url: str,
        browser: Optional[str] = None,
        new_window: bool = False,
        new_tab: bool = True,
    ) -> BrowserResult:
        """
        Open a URL.

        If browser is omitted, Windows' default browser is used.
        """

        if not url:

            return BrowserResult(
                success=False,
                action="open_url",
                message="URL is required.",
                error="empty_url",
            )

        url = str(
            url
        ).strip()

        if not self._is_valid_url(
            url
        ):

            if self._looks_like_domain(
                url
            ):

                url = (
                    "https://"
                    + url
                )

            else:

                return BrowserResult(
                    success=False,
                    action="open_url",
                    message="Invalid URL.",
                    url=url,
                    error="invalid_url",
                )

        executable = (
            self._normalize_browser_name(
                browser
            )
            if browser
            else None
        )

        # --------------------------------------------------------------
        # Default browser
        # --------------------------------------------------------------

        if not executable:

            try:

                if new_window:

                    webbrowser.open_new(
                        url
                    )

                elif new_tab:

                    webbrowser.open_new_tab(
                        url
                    )

                else:

                    webbrowser.open(
                        url
                    )

                return BrowserResult(
                    success=True,
                    action="open_url",
                    message=(
                        f"Opened {url} "
                        "in the default browser."
                    ),
                    url=url,
                )

            except Exception as exc:

                logger.exception(
                    "Default browser open failed."
                )

                return BrowserResult(
                    success=False,
                    action="open_url",
                    message=(
                        "Could not open the "
                        "default browser."
                    ),
                    url=url,
                    error=str(exc),
                )

        # --------------------------------------------------------------
        # Specific browser
        # --------------------------------------------------------------

        path = self.find_browser_path(
            executable
        )

        if not path:

            return BrowserResult(
                success=False,
                action="open_url",
                message=(
                    f"Browser '{browser}' "
                    "was not found."
                ),
                browser=browser,
                url=url,
                error="browser_not_found",
            )

        command = [
            path
        ]

        if new_window:

            command.append(
                "--new-window"
            )

        elif new_tab:

            command.append(
                "--new-tab"
            )

        command.append(
            url
        )

        try:

            subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )

            logger.info(
                "Opened URL with %s: %s",
                executable,
                url,
            )

            return BrowserResult(
                success=True,
                action="open_url",
                message=(
                    f"Opened {url} "
                    f"with {browser or executable}."
                ),
                browser=(
                    browser
                    or executable
                ),
                url=url,
            )

        except Exception as exc:

            logger.exception(
                "Failed opening URL with %s",
                executable,
            )

            return BrowserResult(
                success=False,
                action="open_url",
                message=(
                    f"Could not open {url}."
                ),
                browser=(
                    browser
                    or executable
                ),
                url=url,
                error=str(exc),
            )

    # ==================================================================
    # SEARCH
    # ==================================================================

    def search_web(
        self,
        query: str,
        browser: Optional[str] = None,
        engine: str = "google",
    ) -> BrowserResult:
        """Search the web using a selected search engine."""

        if not query:

            return BrowserResult(
                success=False,
                action="search",
                message="Search query is required.",
                error="empty_query",
            )

        query = str(
            query
        ).strip()

        engines = {
            "google": (
                "https://www.google.com/search?q="
            ),
            "bing": (
                "https://www.bing.com/search?q="
            ),
            "duckduckgo": (
                "https://duckduckgo.com/?q="
            ),
        }

        engine_key = (
            str(engine)
            .strip()
            .lower()
        )

        base_url = engines.get(
            engine_key
        )

        if not base_url:

            return BrowserResult(
                success=False,
                action="search",
                message=(
                    f"Unsupported search engine: "
                    f"{engine}"
                ),
                error="unsupported_search_engine",
            )

        url = (
            base_url
            + quote_plus(query)
        )

        return self.open_url(
            url=url,
            browser=browser,
            new_tab=True,
        )

    # ==================================================================
    # OPEN NEW TAB
    # ==================================================================

    def new_tab(
        self,
        url: Optional[str] = None,
        browser: Optional[str] = None,
    ) -> BrowserResult:
        """Open a new browser tab."""

        target_url = (
            url
            if url
            else "about:blank"
        )

        return self.open_url(
            url=target_url,
            browser=browser,
            new_tab=True,
        )

    # ==================================================================
    # OPEN NEW WINDOW
    # ==================================================================

    def new_window(
        self,
        url: Optional[str] = None,
        browser: Optional[str] = None,
    ) -> BrowserResult:
        """Open a new browser window."""

        target_url = (
            url
            if url
            else "about:blank"
        )

        return self.open_url(
            url=target_url,
            browser=browser,
            new_window=True,
        )

    # ==================================================================
    # PROCESS STATUS
    # ==================================================================

    def is_running(
        self,
        browser: str,
    ) -> bool:
        """Check whether a browser process is running."""

        if psutil is None:

            return False

        executable = (
            self._normalize_browser_name(
                browser
            )
        )

        if not executable:

            return False

        executable = executable.lower()

        for process in psutil.process_iter(
            ["name"]
        ):

            try:

                name = (
                    process.info.get(
                        "name"
                    )
                    or ""
                ).lower()

                if name == executable:

                    return True

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):

                continue

        return False

    # ==================================================================
    # CLOSE BROWSER
    # ==================================================================

    def close_browser(
        self,
        browser: str,
        force: bool = False,
    ) -> BrowserResult:
        """
        Close a browser.

        force=False:
            graceful process termination.

        force=True:
            terminate/kill remaining browser processes.

        The higher-level JarvisOS security layer should handle
        confirmation for force operations.
        """

        executable = (
            self._normalize_browser_name(
                browser
            )
        )

        if not executable:

            return BrowserResult(
                success=False,
                action="close_browser",
                message="Browser is required.",
                error="empty_browser",
            )

        if psutil is None:

            return BrowserResult(
                success=False,
                action="close_browser",
                message=(
                    "psutil is required for "
                    "browser process control."
                ),
                browser=browser,
                error="psutil_not_installed",
            )

        processes = []

        for process in psutil.process_iter(
            ["name"]
        ):

            try:

                name = (
                    process.info.get(
                        "name"
                    )
                    or ""
                ).lower()

                if (
                    name
                    == executable.lower()
                ):

                    processes.append(
                        process
                    )

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):

                continue

        if not processes:

            return BrowserResult(
                success=False,
                action="close_browser",
                message=(
                    f"{browser} is not running."
                ),
                browser=browser,
                error="not_running",
            )

        closed = 0

        for process in processes:

            try:

                process.terminate()

                closed += 1

            except (
                psutil.NoSuchProcess,
                psutil.ZombieProcess,
            ):

                closed += 1

            except psutil.AccessDenied:

                continue

        try:

            _, remaining = (
                psutil.wait_procs(
                    processes,
                    timeout=3,
                )
            )

        except Exception:

            remaining = []

        if force:

            for process in remaining:

                try:

                    process.kill()

                except Exception:

                    continue

        logger.info(
            "Browser close requested: %s",
            browser,
        )

        return BrowserResult(
            success=True,
            action="close_browser",
            message=(
                f"Close request sent to "
                f"{browser}."
            ),
            browser=browser,
            metadata={
                "processes_found": len(
                    processes
                ),
                "force": force,
            },
        )

    # ==================================================================
    # BROWSER STATUS
    # ==================================================================

    def get_browser_status(
        self,
        browser: Optional[str] = None,
    ) -> Dict:
        """Get status for one browser or all browsers."""

        if browser:

            executable = (
                self._normalize_browser_name(
                    browser
                )
            )

            path = (
                self.find_browser_path(
                    executable
                )
                if executable
                else None
            )

            return {
                "browser": browser,
                "executable": executable,
                "installed": (
                    path is not None
                ),
                "path": path,
                "running": (
                    self.is_running(
                        executable
                    )
                    if executable
                    else False
                ),
            }

        browsers = (
            self.detect_browsers()
        )

        return {
            "browsers": [
                item.to_dict()
                for item in browsers
            ],
            "default_browser": (
                self._safe_default_browser_dict()
            ),
        }

    # ==================================================================
    # SAFE HELPERS
    # ==================================================================

    @staticmethod
    def _is_valid_url(
        url: str,
    ) -> bool:

        lower = url.lower()

        return (
            lower.startswith(
                "http://"
            )
            or lower.startswith(
                "https://"
            )
        )

    @staticmethod
    def _looks_like_domain(
        value: str,
    ) -> bool:

        value = value.strip()

        if " " in value:
            return False

        return (
            "." in value
            and len(value) > 3
        )

    def _display_name_for_executable(
        self,
        executable: str,
    ) -> str:

        executable = (
            executable.lower()
        )

        names = {
            "chrome.exe": "Google Chrome",
            "msedge.exe": "Microsoft Edge",
            "firefox.exe": "Mozilla Firefox",
            "brave.exe": "Brave",
            "opera.exe": "Opera",
            "vivaldi.exe": "Vivaldi",
        }

        return names.get(
            executable,
            executable,
        )

    def _safe_default_browser_dict(
        self,
    ) -> Optional[Dict]:

        try:

            browser = (
                self.get_default_browser()
            )

            if browser:

                return browser.to_dict()

        except Exception as exc:

            logger.debug(
                "Default browser status failed: %s",
                exc,
            )

        return None

    # ==================================================================
    # STATUS
    # ==================================================================

    def get_status(
        self,
    ) -> Dict:
        """Return controller status."""

        detected = (
            self.detect_browsers()
        )

        return {
            "available": True,
            "platform": os.name,
            "installed_browsers": [
                browser.name
                for browser in detected
                if browser.installed
            ],
            "running_browsers": [
                browser.name
                for browser in detected
                if browser.running
            ],
            "default_browser": (
                self._safe_default_browser_dict()
            ),
        }

    def close(self) -> None:
        """Release resources."""

        logger.info(
            "BrowserControl closed."
        )


# ======================================================================
# SHARED CONTROLLER
# ======================================================================


_default_controller: Optional[
    BrowserControl
] = None


def get_browser_controller() -> BrowserControl:
    """Return shared BrowserControl instance."""

    global _default_controller

    if _default_controller is None:

        _default_controller = BrowserControl()

    return _default_controller


# ======================================================================
# CONVENIENCE FUNCTIONS
# ======================================================================


def open_url(
    url: str,
    browser: Optional[str] = None,
) -> BrowserResult:
    """Open URL."""

    return get_browser_controller().open_url(
        url=url,
        browser=browser,
    )


def search_web(
    query: str,
    browser: Optional[str] = None,
    engine: str = "google",
) -> BrowserResult:
    """Search the web."""

    return get_browser_controller().search_web(
        query=query,
        browser=browser,
        engine=engine,
    )


def open_new_tab(
    url: Optional[str] = None,
    browser: Optional[str] = None,
) -> BrowserResult:
    """Open new browser tab."""

    return get_browser_controller().new_tab(
        url=url,
        browser=browser,
    )


# ======================================================================
# DIRECT TEST
# ======================================================================


if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(message)s"
        ),
    )

    print()
    print("=" * 70)
    print("JARVIS OS - BROWSER CONTROL TEST")
    print("=" * 70)

    browser = BrowserControl()

    # --------------------------------------------------------------
    # Detect browsers
    # --------------------------------------------------------------

    print()
    print("1. Installed browsers:")

    for item in browser.detect_browsers():

        print(
            item.to_dict()
        )

    # --------------------------------------------------------------
    # Default browser
    # --------------------------------------------------------------

    print()
    print("2. Default browser:")

    default = (
        browser.get_default_browser()
    )

    if default:

        print(
            default.to_dict()
        )

    else:

        print(
            "Could not detect default browser."
        )

    # --------------------------------------------------------------
    # Browser status
    # --------------------------------------------------------------

    print()
    print("3. Browser status:")

    print(
        browser.get_status()
    )

    # --------------------------------------------------------------
    # Running status
    # --------------------------------------------------------------

    print()
    print("4. Chrome running:")

    print(
        browser.is_running(
            "chrome"
        )
    )

    print()
    print("5. Edge running:")

    print(
        browser.is_running(
            "edge"
        )
    )

    # --------------------------------------------------------------
    # URL validation only
    # --------------------------------------------------------------

    print()
    print("6. URL validation:")

    for value in (
        "https://www.google.com",
        "https://example.com",
        "not a url",
    ):

        print(
            value,
            "->",
            browser._is_valid_url(
                value
            ),
        )

    # --------------------------------------------------------------
    # Search URL generation
    # --------------------------------------------------------------

    print()
    print(
        "7. Google search URL:"
    )

    query = (
        "JarvisOS AI assistant"
    )

    print(
        "https://www.google.com/search?q="
        + quote_plus(query)
    )

    print()
    print("=" * 70)
    print("BROWSER CONTROL TEST COMPLETE")
    print("=" * 70)
