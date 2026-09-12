"""
JarvisOS - Windows Application Control

Provides safe Windows application management:

    - Launch applications
    - Open files with their default application
    - Open URLs with the default browser
    - Find running processes
    - Check whether an application is running
    - Close applications gracefully
    - Force-stop applications when explicitly requested
    - Get application/process information

Safety:
    - Normal launching is allowed.
    - Graceful closing is supported.
    - Force termination is separated from normal close.
    - System-critical processes are protected.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union
from urllib.parse import urlparse

try:
    import psutil
except ImportError:
    psutil = None


logger = logging.getLogger(__name__)


# ======================================================================
# DATA MODELS
# ======================================================================


@dataclass
class ApplicationResult:
    """Result returned by an application-control operation."""

    success: bool
    action: str
    message: str
    application: Optional[str] = None
    pid: Optional[int] = None
    error: Optional[str] = None
    metadata: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """Convert result to a dictionary."""

        return asdict(self)


@dataclass
class ProcessInfo:
    """Basic information about a Windows process."""

    pid: int
    name: str
    executable: Optional[str] = None
    username: Optional[str] = None
    status: Optional[str] = None
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None

    def to_dict(self) -> Dict:
        """Convert process information to a dictionary."""

        return asdict(self)


# ======================================================================
# APPLICATION CONTROLLER
# ======================================================================


class AppControl:
    """
    Windows application and process controller.

    Example:

        apps = AppControl()

        result = apps.open_app("notepad")
        print(result.message)

        print(apps.is_running("notepad"))

        result = apps.close_app("notepad")
    """

    # Common aliases used by natural-language commands.
    APPLICATION_ALIASES = {
        "notepad": "notepad.exe",
        "notepad.exe": "notepad.exe",

        "calculator": "calc.exe",
        "calc": "calc.exe",
        "calc.exe": "calc.exe",

        "paint": "mspaint.exe",
        "mspaint": "mspaint.exe",
        "mspaint.exe": "mspaint.exe",

        "command prompt": "cmd.exe",
        "cmd": "cmd.exe",
        "cmd.exe": "cmd.exe",

        "powershell": "powershell.exe",
        "powershell.exe": "powershell.exe",

        "explorer": "explorer.exe",
        "file explorer": "explorer.exe",
        "windows explorer": "explorer.exe",
        "explorer.exe": "explorer.exe",

        "task manager": "taskmgr.exe",
        "taskmgr": "taskmgr.exe",
        "taskmgr.exe": "taskmgr.exe",

        "control panel": "control.exe",
        "control": "control.exe",

        "registry editor": "regedit.exe",
        "regedit": "regedit.exe",
        "regedit.exe": "regedit.exe",

        "chrome": "chrome.exe",
        "google chrome": "chrome.exe",
        "chrome.exe": "chrome.exe",

        "edge": "msedge.exe",
        "microsoft edge": "msedge.exe",
        "msedge": "msedge.exe",
        "msedge.exe": "msedge.exe",

        "firefox": "firefox.exe",
        "firefox.exe": "firefox.exe",

        "discord": "Discord.exe",
        "spotify": "Spotify.exe",
        "telegram": "Telegram.exe",

        "code": "Code.exe",
        "visual studio code": "Code.exe",
        "vs code": "Code.exe",

        "word": "WINWORD.EXE",
        "excel": "EXCEL.EXE",
        "powerpoint": "POWERPNT.EXE",

        "winword": "WINWORD.EXE",
        "excel.exe": "EXCEL.EXE",
        "powerpoint.exe": "POWERPNT.EXE",
    }

    # Processes that JarvisOS must not terminate through this class.
    PROTECTED_PROCESSES = {
        "system",
        "system idle process",
        "smss.exe",
        "csrss.exe",
        "wininit.exe",
        "winlogon.exe",
        "services.exe",
        "lsass.exe",
        "svchost.exe",
        "dwm.exe",
        "explorer.exe",
        "fontdrvhost.exe",
        "securityhealthservice.exe",
        "registry",
        "memory compression",
    }

    def __init__(
        self,
        startup_timeout: float = 5.0,
        terminate_timeout: float = 3.0,
    ) -> None:

        self.startup_timeout = max(
            0.5,
            float(startup_timeout),
        )

        self.terminate_timeout = max(
            0.5,
            float(terminate_timeout),
        )

        self.is_windows = (
            os.name == "nt"
        )

        logger.info(
            "AppControl initialized. Windows=%s",
            self.is_windows,
        )

    # ==================================================================
    # OPEN APPLICATION
    # ==================================================================

    def open_app(
        self,
        application: str,
        arguments: Optional[
            Sequence[str]
        ] = None,
        wait: bool = False,
    ) -> ApplicationResult:
        """
        Launch a Windows application.

        `application` may be:

            - application alias
            - executable name
            - full executable path
            - shortcut (.lnk)
            - document/file
        """

        if not application:
            return ApplicationResult(
                success=False,
                action="open",
                message="Application name is required.",
                error="empty_application",
            )

        target = application.strip()
        resolved = self.resolve_application(
            target
        )

        command = [resolved]

        if arguments:
            command.extend(
                str(arg)
                for arg in arguments
            )

        try:

            if self._is_url(target):

                return self.open_url(
                    target
                )

            # ----------------------------------------------------------
            # Existing file / shortcut
            # ----------------------------------------------------------

            if (
                os.path.exists(resolved)
                and not self._is_executable_path(
                    resolved
                )
            ):

                process = self._open_with_windows(
                    resolved
                )

            else:

                process = subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    creationflags=(
                        getattr(
                            subprocess,
                            "CREATE_NEW_PROCESS_GROUP",
                            0,
                        )
                    ),
                )

            pid = getattr(
                process,
                "pid",
                None,
            )

            if wait and process is not None:

                try:
                    process.wait(
                        timeout=self.startup_timeout
                    )
                except subprocess.TimeoutExpired:
                    pass

            logger.info(
                "Application opened: %s (pid=%s)",
                target,
                pid,
            )

            return ApplicationResult(
                success=True,
                action="open",
                message=(
                    f"Opened {target}."
                ),
                application=target,
                pid=pid,
            )

        except FileNotFoundError:

            logger.warning(
                "Application not found: %s",
                target,
            )

            return ApplicationResult(
                success=False,
                action="open",
                message=(
                    f"Application '{target}' "
                    "was not found."
                ),
                application=target,
                error="application_not_found",
            )

        except PermissionError as exc:

            logger.error(
                "Permission denied opening %s: %s",
                target,
                exc,
            )

            return ApplicationResult(
                success=False,
                action="open",
                message=(
                    f"Permission denied while "
                    f"opening {target}."
                ),
                application=target,
                error="permission_denied",
            )

        except Exception as exc:

            logger.exception(
                "Failed to open application: %s",
                target,
            )

            return ApplicationResult(
                success=False,
                action="open",
                message=(
                    f"Could not open {target}."
                ),
                application=target,
                error=str(exc),
            )

    # ==================================================================
    # URL
    # ==================================================================

    def open_url(
        self,
        url: str,
    ) -> ApplicationResult:
        """Open a URL using the Windows default browser."""

        if not url:
            return ApplicationResult(
                success=False,
                action="open_url",
                message="URL is required.",
                error="empty_url",
            )

        url = url.strip()

        if not self._is_url(url):

            if re.match(
                r"^[\w.-]+\.[a-zA-Z]{2,}",
                url,
            ):
                url = (
                    "https://"
                    + url
                )

            else:
                return ApplicationResult(
                    success=False,
                    action="open_url",
                    message="Invalid URL.",
                    error="invalid_url",
                )

        try:

            if self.is_windows:

                os.startfile(url)

            else:

                if shutil.which("xdg-open"):

                    subprocess.Popen(
                        [
                            "xdg-open",
                            url,
                        ],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )

                else:

                    raise RuntimeError(
                        "No supported URL opener found."
                    )

            logger.info(
                "URL opened: %s",
                url,
            )

            return ApplicationResult(
                success=True,
                action="open_url",
                message=f"Opened {url}.",
                application=url,
            )

        except Exception as exc:

            logger.exception(
                "Failed to open URL: %s",
                url,
            )

            return ApplicationResult(
                success=False,
                action="open_url",
                message=(
                    f"Could not open {url}."
                ),
                application=url,
                error=str(exc),
            )

    # ==================================================================
    # CLOSE APPLICATION
    # ==================================================================

    def close_app(
        self,
        application: str,
        force: bool = False,
    ) -> ApplicationResult:
        """
        Close an application.

        By default this attempts graceful termination first.

        `force=True` performs process termination after checking
        the protected-process list.
        """

        if not application:
            return ApplicationResult(
                success=False,
                action="close",
                message="Application name is required.",
                error="empty_application",
            )

        target = self._normalize_process_name(
            application
        )

        if self._is_protected(
            target
        ):

            return ApplicationResult(
                success=False,
                action="close",
                message=(
                    f"{application} is a protected "
                    "system process and cannot be closed "
                    "by JarvisOS."
                ),
                application=application,
                error="protected_process",
            )

        if psutil is None:

            return self._close_without_psutil(
                target
            )

        matches = self._find_processes(
            target
        )

        if not matches:

            return ApplicationResult(
                success=False,
                action="close",
                message=(
                    f"{application} is not running."
                ),
                application=application,
                error="not_running",
            )

        closed = 0
        errors = []

        for process in matches:

            try:

                if force:

                    process.terminate()

                else:

                    # terminate() is preferable to kill()
                    # because it gives the process a chance
                    # to shut down cleanly.
                    process.terminate()

                closed += 1

            except (
                psutil.NoSuchProcess,
                psutil.ZombieProcess,
            ):

                closed += 1

            except psutil.AccessDenied as exc:

                errors.append(
                    f"PID {process.pid}: access denied"
                )

                logger.warning(
                    "Access denied closing PID %s: %s",
                    process.pid,
                    exc,
                )

            except Exception as exc:

                errors.append(
                    f"PID {process.pid}: {exc}"
                )

        # --------------------------------------------------------------
        # Wait for graceful termination
        # --------------------------------------------------------------

        if closed:

            try:

                _, still_running = (
                    psutil.wait_procs(
                        matches,
                        timeout=self.terminate_timeout,
                    )
                )

            except Exception:

                still_running = []

            # Force mode can kill processes that refuse to terminate.
            if force and still_running:

                for process in still_running:

                    try:

                        if not self._is_protected(
                            process.name()
                        ):
                            process.kill()

                    except Exception as exc:

                        errors.append(
                            f"PID {process.pid}: {exc}"
                        )

        if errors:

            return ApplicationResult(
                success=closed > 0,
                action="close",
                message=(
                    f"Closed {closed} process(es) "
                    f"for {application}, with some errors."
                ),
                application=application,
                error="; ".join(errors),
            )

        return ApplicationResult(
            success=closed > 0,
            action="close",
            message=(
                f"Closed {application}."
            ),
            application=application,
        )

    # ==================================================================
    # FORCE CLOSE
    # ==================================================================

    def force_close_app(
        self,
        application: str,
    ) -> ApplicationResult:
        """
        Force-close an application.

        This should only be called after the higher-level
        JarvisOS security/confirmation layer approves the action.
        """

        return self.close_app(
            application=application,
            force=True,
        )

    # ==================================================================
    # PROCESS CHECK
    # ==================================================================

    def is_running(
        self,
        application: str,
    ) -> bool:
        """Return True if an application/process is running."""

        target = self._normalize_process_name(
            application
        )

        if not target:
            return False

        if psutil is None:

            return False

        return bool(
            self._find_processes(
                target
            )
        )

    # ==================================================================
    # FIND PROCESSES
    # ==================================================================

    def find_processes(
        self,
        name: Optional[str] = None,
    ) -> List[ProcessInfo]:
        """
        Find running processes.

        If `name` is None, returns a snapshot of accessible
        processes.
        """

        if psutil is None:

            logger.warning(
                "psutil is not installed."
            )

            return []

        results = []

        for process in psutil.process_iter(
            [
                "pid",
                "name",
                "exe",
                "username",
                "status",
                "memory_percent",
            ]
        ):

            try:

                process_name = (
                    process.info.get(
                        "name"
                    )
                    or ""
                )

                if name:

                    target = (
                        self._normalize_process_name(
                            name
                        )
                    )

                    current = (
                        self._normalize_process_name(
                            process_name
                        )
                    )

                    if (
                        target != current
                        and target not in current
                        and current not in target
                    ):
                        continue

                try:

                    cpu = process.cpu_percent(
                        interval=0.0
                    )

                except Exception:

                    cpu = None

                results.append(
                    ProcessInfo(
                        pid=int(
                            process.info[
                                "pid"
                            ]
                        ),
                        name=process_name,
                        executable=process.info.get(
                            "exe"
                        ),
                        username=process.info.get(
                            "username"
                        ),
                        status=process.info.get(
                            "status"
                        ),
                        cpu_percent=cpu,
                        memory_percent=process.info.get(
                            "memory_percent"
                        ),
                    )
                )

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):

                continue

            except Exception as exc:

                logger.debug(
                    "Could not inspect process: %s",
                    exc,
                )

        return results

    # ==================================================================
    # PROCESS BY PID
    # ==================================================================

    def get_process(
        self,
        pid: int,
    ) -> Optional[ProcessInfo]:
        """Get information about a specific PID."""

        if psutil is None:
            return None

        try:

            process = psutil.Process(
                int(pid)
            )

            try:
                cpu = process.cpu_percent(
                    interval=0.0
                )
            except Exception:
                cpu = None

            try:
                memory = (
                    process.memory_percent()
                )
            except Exception:
                memory = None

            return ProcessInfo(
                pid=process.pid,
                name=process.name(),
                executable=self._safe_process_exe(
                    process
                ),
                username=self._safe_process_username(
                    process
                ),
                status=self._safe_process_status(
                    process
                ),
                cpu_percent=cpu,
                memory_percent=memory,
            )

        except (
            psutil.NoSuchProcess,
            psutil.AccessDenied,
            psutil.ZombieProcess,
        ):

            return None

    # ==================================================================
    # LIST APPLICATIONS
    # ==================================================================

    def list_running_apps(
        self,
    ) -> List[ProcessInfo]:
        """
        Return a simplified list of running applications.

        On Windows this filters common background/system processes
        as much as possible using executable paths and process names.
        """

        processes = self.find_processes()

        results = []

        for process in processes:

            name = (
                process.name
                or ""
            ).lower()

            if not name:
                continue

            # Skip obvious system/background processes.
            if name in self.PROTECTED_PROCESSES:
                continue

            if name.endswith(
                ".exe"
            ):

                results.append(
                    process
                )

        results.sort(
            key=lambda item: (
                item.name.lower()
                if item.name
                else ""
            )
        )

        return results

    # ==================================================================
    # RESOLVE APPLICATION
    # ==================================================================

    def resolve_application(
        self,
        application: str,
    ) -> str:
        """
        Resolve an application alias/name into an executable/path.
        """

        target = application.strip()

        if not target:
            return target

        normalized = (
            target.lower()
            .strip()
        )

        # Remove surrounding quotes.
        if (
            len(target) >= 2
            and target[0] == '"'
            and target[-1] == '"'
        ):

            target = target[1:-1]

        normalized = (
            target.lower()
            .strip()
        )

        # Known alias.
        alias = self.APPLICATION_ALIASES.get(
            normalized
        )

        if alias:
            return alias

        # Existing absolute/relative path.
        if os.path.exists(target):
            return target

        # PATH lookup.
        executable = shutil.which(
            target
        )

        if executable:
            return executable

        # Try adding .exe on Windows.
        if self.is_windows:

            if not normalized.endswith(
                ".exe"
            ):

                executable = shutil.which(
                    target + ".exe"
                )

                if executable:
                    return executable

        return target

    # ==================================================================
    # OPEN FILE WITH DEFAULT APP
    # ==================================================================

    def open_file(
        self,
        file_path: Union[
            str,
            Path,
        ],
    ) -> ApplicationResult:
        """Open a file using the operating system default application."""

        path = Path(
            file_path
        ).expanduser()

        if not path.exists():

            return ApplicationResult(
                success=False,
                action="open_file",
                message=(
                    f"File not found: {path}"
                ),
                application=str(path),
                error="file_not_found",
            )

        try:

            if self.is_windows:

                os.startfile(
                    str(path)
                )

            elif shutil.which(
                "xdg-open"
            ):

                subprocess.Popen(
                    [
                        "xdg-open",
                        str(path),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            else:

                raise RuntimeError(
                    "No supported file opener found."
                )

            logger.info(
                "File opened: %s",
                path,
            )

            return ApplicationResult(
                success=True,
                action="open_file",
                message=(
                    f"Opened {path.name}."
                ),
                application=str(path),
            )

        except Exception as exc:

            logger.exception(
                "Could not open file: %s",
                path,
            )

            return ApplicationResult(
                success=False,
                action="open_file",
                message=(
                    f"Could not open {path.name}."
                ),
                application=str(path),
                error=str(exc),
            )

    # ==================================================================
    # APP STATUS
    # ==================================================================

    def get_app_status(
        self,
        application: str,
    ) -> Dict:
        """Return useful status information for an application."""

        target = self._normalize_process_name(
            application
        )

        processes = self.find_processes(
            target
        )

        return {
            "application": application,
            "normalized_name": target,
            "running": bool(processes),
            "process_count": len(
                processes
            ),
            "processes": [
                item.to_dict()
                for item in processes
            ],
        }

    # ==================================================================
    # HELPERS
    # ==================================================================

    def _find_processes(
        self,
        target: str,
    ):

        if psutil is None:
            return []

        target = (
            self._normalize_process_name(
                target
            )
        )

        matches = []

        for process in psutil.process_iter(
            ["pid", "name", "exe"]
        ):

            try:

                name = (
                    process.info.get(
                        "name"
                    )
                    or ""
                )

                normalized_name = (
                    self._normalize_process_name(
                        name
                    )
                )

                executable = (
                    process.info.get(
                        "exe"
                    )
                    or ""
                )

                normalized_exe = (
                    self._normalize_process_name(
                        executable
                    )
                )

                if (
                    target == normalized_name
                    or target == normalized_exe
                ):

                    matches.append(
                        process
                    )

            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
                psutil.ZombieProcess,
            ):

                continue

        return matches

    @staticmethod
    def _normalize_process_name(
        name: Optional[str],
    ) -> str:

        if not name:
            return ""

        value = str(
            name
        ).strip().lower()

        if "\\" in value:
            value = value.rsplit(
                "\\",
                1,
            )[-1]

        if "/" in value:
            value = value.rsplit(
                "/",
                1,
            )[-1]

        return value

    def _is_protected(
        self,
        name: str,
    ) -> bool:

        normalized = (
            self._normalize_process_name(
                name
            )
        )

        if normalized in self.PROTECTED_PROCESSES:
            return True

        # explorer.exe is deliberately protected.
        if normalized == "explorer.exe":
            return True

        return False

    @staticmethod
    def _is_url(
        value: str,
    ) -> bool:

        try:

            parsed = urlparse(
                value
            )

            return parsed.scheme in {
                "http",
                "https",
                "ftp",
            }

        except Exception:

            return False

    @staticmethod
    def _is_executable_path(
        path: str,
    ) -> bool:

        return str(
            path
        ).lower().endswith(
            (
                ".exe",
                ".com",
                ".bat",
                ".cmd",
                ".ps1",
            )
        )

    def _open_with_windows(
        self,
        path: str,
    ):

        if not self.is_windows:

            return subprocess.Popen(
                [
                    path
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        # os.startfile() uses the user's registered
        # Windows application association.
        os.startfile(
            path
        )

        # os.startfile does not return a process object.
        return None

    def _close_without_psutil(
        self,
        target: str,
    ) -> ApplicationResult:

        if not self.is_windows:

            return ApplicationResult(
                success=False,
                action="close",
                message=(
                    "Process control requires psutil."
                ),
                application=target,
                error="psutil_not_installed",
            )

        try:

            # taskkill /IM is a Windows-native fallback.
            completed = subprocess.run(
                [
                    "taskkill",
                    "/IM",
                    target,
                    "/T",
                ],
                capture_output=True,
                text=True,
                timeout=self.terminate_timeout,
            )

            if completed.returncode == 0:

                return ApplicationResult(
                    success=True,
                    action="close",
                    message=(
                        f"Closed {target}."
                    ),
                    application=target,
                )

            return ApplicationResult(
                success=False,
                action="close",
                message=(
                    f"{target} could not be closed."
                ),
                application=target,
                error=(
                    completed.stderr.strip()
                    or "taskkill_failed"
                ),
            )

        except Exception as exc:

            return ApplicationResult(
                success=False,
                action="close",
                message=(
                    f"Could not close {target}."
                ),
                application=target,
                error=str(exc),
            )

    @staticmethod
    def _safe_process_exe(
        process,
    ) -> Optional[str]:

        try:
            return process.exe()
        except Exception:
            return None

    @staticmethod
    def _safe_process_username(
        process,
    ) -> Optional[str]:

        try:
            return process.username()
        except Exception:
            return None

    @staticmethod
    def _safe_process_status(
        process,
    ) -> Optional[str]:

        try:
            return process.status()
        except Exception:
            return None

    # ==================================================================
    # SYSTEM INFORMATION
    # ==================================================================

    def get_summary(
        self,
    ) -> Dict:
        """Return a compact application/process summary."""

        if psutil is None:

            return {
                "available": False,
                "reason": "psutil_not_installed",
            }

        try:

            processes = list(
                psutil.process_iter(
                    ["pid", "name"]
                )
            )

            return {
                "available": True,
                "platform": os.name,
                "process_count": len(
                    processes
                ),
                "windows": self.is_windows,
            }

        except Exception as exc:

            return {
                "available": False,
                "reason": str(exc),
            }

    # ==================================================================
    # CLEANUP
    # ==================================================================

    def close(self) -> None:
        """Release controller resources.

        AppControl currently does not maintain persistent handles,
        so this method exists for a consistent JarvisOS interface.
        """

        logger.info(
            "AppControl closed."
        )


# ======================================================================
# CONVENIENCE FUNCTIONS
# ======================================================================


_default_controller: Optional[
    AppControl
] = None


def get_app_controller() -> AppControl:
    """Return a shared application controller."""

    global _default_controller

    if _default_controller is None:

        _default_controller = AppControl()

    return _default_controller


def open_application(
    application: str,
) -> ApplicationResult:
    """Convenience function for opening an application."""

    return get_app_controller().open_app(
        application
    )


def close_application(
    application: str,
    force: bool = False,
) -> ApplicationResult:
    """Convenience function for closing an application."""

    return get_app_controller().close_app(
        application,
        force=force,
    )


def application_is_running(
    application: str,
) -> bool:
    """Convenience function for checking an application."""

    return get_app_controller().is_running(
        application
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
    print("JARVIS OS - APPLICATION CONTROL TEST")
    print("=" * 70)

    controller = AppControl()

    # --------------------------------------------------------------
    # Basic status
    # --------------------------------------------------------------

    print()
    print("1. Controller status:")
    print(
        controller.get_summary()
    )

    # --------------------------------------------------------------
    # Resolve aliases
    # --------------------------------------------------------------

    print()
    print("2. Application resolution:")

    for app in (
        "notepad",
        "calculator",
        "chrome",
        "explorer",
    ):

        print(
            f"{app} -> "
            f"{controller.resolve_application(app)}"
        )

    # --------------------------------------------------------------
    # Check running applications
    # --------------------------------------------------------------

    print()
    print("3. Checking common applications:")

    for app in (
        "notepad",
        "chrome",
        "calculator",
    ):

        print(
            f"{app}: "
            f"{controller.is_running(app)}"
        )

    # --------------------------------------------------------------
    # Process search
    # --------------------------------------------------------------

    print()
    print("4. Searching for explorer:")

    explorer_processes = (
        controller.find_processes(
            "explorer.exe"
        )
    )

    for process in explorer_processes:

        print(
            process.to_dict()
        )

    # --------------------------------------------------------------
    # Safe launch test
    # --------------------------------------------------------------

    print()
    print(
        "5. Opening Calculator..."
    )

    result = controller.open_app(
        "calculator"
    )

    print(
        result.to_dict()
    )

    if result.success:

        time.sleep(1)

        print()
        print(
            "6. Calculator running:"
        )

        print(
            controller.is_running(
                "calculator"
            )
        )

        # ----------------------------------------------------------
        # Close calculator
        # ----------------------------------------------------------

        print()
        print(
            "7. Closing Calculator..."
        )

        close_result = (
            controller.close_app(
                "calculator"
            )
        )

        print(
            close_result.to_dict()
        )

    # --------------------------------------------------------------
    # Protected-process test
    # --------------------------------------------------------------

    print()
    print(
        "8. Protected process test:"
    )

    protected_result = (
        controller.close_app(
            "explorer.exe"
        )
    )

    print(
        protected_result.to_dict()
    )

    # --------------------------------------------------------------
    # Final status
    # --------------------------------------------------------------

    print()
    print(
        "9. Final status:"
    )

    print(
        controller.get_summary()
    )

    controller.close()

    print()
    print("=" * 70)
    print("APPLICATION CONTROL TEST COMPLETE")
    print("=" * 70)
