# installer/setup_builder.py

"""
JARVIS OS - SETUP BUILDER
=========================

Builds a Windows installer for JarvisOS.

This module is designed to work with:
- PyInstaller
- Inno Setup

It does not pretend to build an installer when required
tools are missing. It detects the tools and returns a clear
error.

Typical workflow:

    1. Build JarvisOS executable with PyInstaller.
    2. Generate an Inno Setup configuration.
    3. Run Inno Setup compiler.
    4. Produce JarvisOS-Setup.exe

Environment variables:

JARVIS_APP_NAME
JARVIS_VERSION
JARVIS_PYTHON
JARVIS_PYINSTALLER
JARVIS_INNO_SETUP
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


logger = logging.getLogger(
    "JarvisOS.SetupBuilder"
)


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class InstallerResult:
    """Result of an installer operation."""

    success: bool

    operation: str

    message: str

    output_path: str = ""

    executable_path: str = ""

    return_code: Optional[int] = None

    stdout: str = ""

    stderr: str = ""

    errors: List[str] = field(
        default_factory=list
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return asdict(self)


@dataclass
class InstallerConfig:
    """Configuration used to generate the installer."""

    app_name: str = "JarvisOS"

    app_version: str = "1.0.0"

    publisher: str = "JarvisOS"

    executable_name: str = "JarvisOS.exe"

    entry_script: str = "main.py"

    architecture: str = "x64"

    install_dir_name: str = "JarvisOS"

    output_dir: str = "dist"

    setup_filename: str = (
        "JarvisOS-Setup.exe"
    )

    icon_path: str = ""

    license_path: str = ""

    readme_path: str = ""

    create_desktop_shortcut: bool = True

    create_start_menu_shortcut: bool = True

    allow_user_install_dir: bool = True

    require_admin: bool = False

    compression: str = "lzma2"

    additional_files: List[str] = field(
        default_factory=list
    )

    additional_dirs: List[str] = field(
        default_factory=list
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


# ============================================================
# SETUP BUILDER
# ============================================================

class SetupBuilder:
    """
    Windows installer builder for JarvisOS.

    The class supports:

    - PyInstaller detection
    - PyInstaller executable building
    - Inno Setup detection
    - Inno Setup script generation
    - Installer compilation
    - Build status
    - Build history

    No installer is silently executed.
    """

    def __init__(
        self,
        project_dir: Optional[
            str | Path
        ] = None,
        config: Optional[
            InstallerConfig
        ] = None,
    ):

        if project_dir is None:

            self.project_dir = (
                Path.cwd()
                .resolve()
            )

        else:

            self.project_dir = (
                Path(
                    project_dir
                )
                .expanduser()
                .resolve()
            )

        self.config = (
            config
            or InstallerConfig(
                app_name=os.getenv(
                    "JARVIS_APP_NAME",
                    "JarvisOS",
                ),
                app_version=os.getenv(
                    "JARVIS_VERSION",
                    "1.0.0",
                ),
                publisher=os.getenv(
                    "JARVIS_PUBLISHER",
                    "JarvisOS",
                ),
                entry_script=os.getenv(
                    "JARVIS_ENTRY_SCRIPT",
                    "main.py",
                ),
            )
        )

        self._lock = threading.RLock()

        self.history: List[
            Dict[str, Any]
        ] = []

        self.max_history = 100

        self.last_result: Optional[
            InstallerResult
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
    # PATH HELPERS
    # ========================================================

    def resolve_path(
        self,
        path: str | Path,
    ) -> Path:

        value = Path(
            path
        ).expanduser()

        if not value.is_absolute():

            value = (
                self.project_dir
                / value
            )

        return value.resolve()

    def _relative_to_project(
        self,
        path: Path,
    ) -> str:

        try:

            return str(
                path.relative_to(
                    self.project_dir
                )
            )

        except ValueError:

            return str(path)

    # ========================================================
    # TOOL DETECTION
    # ========================================================

    def find_pyinstaller(
        self,
    ) -> Optional[str]:

        configured = os.getenv(
            "JARVIS_PYINSTALLER",
            "",
        ).strip()

        candidates = []

        if configured:
            candidates.append(
                configured
            )

        candidates.extend(
            [
                "pyinstaller",
                "pyinstaller.exe",
            ]
        )

        for candidate in candidates:

            found = shutil.which(
                candidate
            )

            if found:
                return found

            path = Path(
                candidate
            )

            if path.is_file():

                return str(
                    path.resolve()
                )

        return None

    def find_inno_setup(
        self,
    ) -> Optional[str]:

        configured = os.getenv(
            "JARVIS_INNO_SETUP",
            "",
        ).strip()

        candidates = []

        if configured:
            candidates.append(
                configured
            )

        candidates.extend(
            [
                r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
                r"C:\Program Files\Inno Setup 6\ISCC.exe",
                r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
                r"C:\Program Files\Inno Setup 5\ISCC.exe",
            ]
        )

        for candidate in candidates:

            found = shutil.which(
                candidate
            )

            if found:
                return found

            path = Path(
                candidate
            )

            if path.is_file():

                return str(
                    path.resolve()
                )

        return None

    def get_tool_status(
        self,
    ) -> Dict[str, Any]:

        return {
            "pyinstaller": (
                self.find_pyinstaller()
            ),
            "inno_setup": (
                self.find_inno_setup()
            ),
        }

    # ========================================================
    # CONFIGURATION
    # ========================================================

    def validate_config(
        self,
    ) -> InstallerResult:

        errors: List[str] = []

        if not self.config.app_name.strip():

            errors.append(
                "Application name is empty."
            )

        if not self.config.app_version.strip():

            errors.append(
                "Application version is empty."
            )

        if not self.config.entry_script.strip():

            errors.append(
                "Entry script is empty."
            )

        entry = self.resolve_path(
            self.config.entry_script
        )

        if not entry.is_file():

            errors.append(
                f"Entry script not found: {entry}"
            )

        if self.config.architecture not in {
            "x64",
            "x86",
            "arm64",
        }:

            errors.append(
                "Architecture must be x64, x86 or arm64."
            )

        if self.config.compression not in {
            "zip",
            "lzma",
            "lzma2",
        }:

            errors.append(
                "Unsupported compression method."
            )

        for item in (
            self.config.additional_files
        ):

            path = self.resolve_path(
                item
            )

            if not path.is_file():

                errors.append(
                    f"Additional file not found: {path}"
                )

        for item in (
            self.config.additional_dirs
        ):

            path = self.resolve_path(
                item
            )

            if not path.is_dir():

                errors.append(
                    f"Additional directory not found: {path}"
                )

        if self.config.icon_path:

            icon = self.resolve_path(
                self.config.icon_path
            )

            if not icon.is_file():

                errors.append(
                    f"Icon file not found: {icon}"
                )

            elif icon.suffix.lower() != ".ico":

                errors.append(
                    "Installer icon must be an .ico file."
                )

        if self.config.license_path:

            license_file = (
                self.resolve_path(
                    self.config.license_path
                )
            )

            if not license_file.is_file():

                errors.append(
                    f"License file not found: {license_file}"
                )

        if errors:

            return InstallerResult(
                success=False,
                operation="validate_config",
                message=(
                    "Installer configuration is invalid."
                ),
                errors=errors,
            )

        return InstallerResult(
            success=True,
            operation="validate_config",
            message=(
                "Installer configuration is valid."
            ),
        )

    # ========================================================
    # PYINSTALLER SPEC
    # ========================================================

    def build_pyinstaller_command(
        self,
        *,
        clean: bool = True,
        onefile: bool = True,
        windowed: bool = True,
    ) -> List[str]:

        entry = self.resolve_path(
            self.config.entry_script
        )

        command = [
            "pyinstaller",
        ]

        if clean:
            command.append(
                "--clean"
            )

        if onefile:
            command.append(
                "--onefile"
            )

        if windowed:
            command.append(
                "--windowed"
            )

        command.extend(
            [
                "--name",
                self.config.app_name,
                "--distpath",
                str(
                    self.resolve_path(
                        "build/dist"
                    )
                ),
                "--workpath",
                str(
                    self.resolve_path(
                        "build/work"
                    )
                ),
                "--specpath",
                str(
                    self.resolve_path(
                        "build/spec"
                    )
                ),
            ]
        )

        if self.config.icon_path:

            icon = self.resolve_path(
                self.config.icon_path
            )

            command.extend(
                [
                    "--icon",
                    str(icon),
                ]
            )

        command.append(
            str(entry)
        )

        return command

    # ========================================================
    # PYINSTALLER BUILD
    # ========================================================

    def build_executable(
        self,
        *,
        confirm: bool = False,
        clean: bool = True,
        onefile: bool = True,
        windowed: bool = True,
    ) -> InstallerResult:

        if not confirm:

            return InstallerResult(
                success=False,
                operation="build_executable",
                message=(
                    "Building the executable requires "
                    "explicit confirmation."
                ),
                errors=[
                    "confirmation_required"
                ],
            )

        validation = (
            self.validate_config()
        )

        if not validation.success:

            validation.operation = (
                "build_executable"
            )

            return validation

        pyinstaller = (
            self.find_pyinstaller()
        )

        if not pyinstaller:

            return InstallerResult(
                success=False,
                operation="build_executable",
                message=(
                    "PyInstaller was not found."
                ),
                errors=[
                    "pyinstaller_not_found"
                ],
            )

        command = (
            self.build_pyinstaller_command(
                clean=clean,
                onefile=onefile,
                windowed=windowed,
            )
        )

        # Replace the executable name with the detected
        # PyInstaller path.
        command[0] = pyinstaller

        try:

            process = subprocess.run(
                command,
                cwd=str(
                    self.project_dir
                ),
                capture_output=True,
                text=True,
                timeout=1800,
                shell=False,
            )

            executable = (
                self.resolve_path(
                    "build/dist"
                )
                / (
                    self.config.app_name
                    + ".exe"
                )
            )

            if process.returncode != 0:

                result = InstallerResult(
                    success=False,
                    operation="build_executable",
                    message=(
                        "PyInstaller failed."
                    ),
                    executable_path=str(
                        executable
                    ),
                    return_code=(
                        process.returncode
                    ),
                    stdout=process.stdout[
                        -20000:
                    ],
                    stderr=process.stderr[
                        -20000:
                    ],
                    errors=[
                        "pyinstaller_failed"
                    ],
                )

                self._record(
                    result
                )

                return result

            if not executable.is_file():

                result = InstallerResult(
                    success=False,
                    operation="build_executable",
                    message=(
                        "PyInstaller completed but "
                        "the expected executable was not found."
                    ),
                    return_code=(
                        process.returncode
                    ),
                    stdout=process.stdout[
                        -20000:
                    ],
                    stderr=process.stderr[
                        -20000:
                    ],
                    errors=[
                        "executable_missing"
                    ],
                )

                self._record(
                    result
                )

                return result

            result = InstallerResult(
                success=True,
                operation="build_executable",
                message=(
                    "JarvisOS executable built successfully."
                ),
                executable_path=str(
                    executable
                ),
                return_code=(
                    process.returncode
                ),
                stdout=process.stdout[
                    -20000:
                ],
                stderr=process.stderr[
                    -20000:
                ],
            )

            self._record(
                result
            )

            return result

        except subprocess.TimeoutExpired:

            return InstallerResult(
                success=False,
                operation="build_executable",
                message=(
                    "PyInstaller build timed out."
                ),
                errors=[
                    "build_timeout"
                ],
            )

        except Exception as exc:

            logger.error(
                "Executable build failed: %s",
                exc,
            )

            return InstallerResult(
                success=False,
                operation="build_executable",
                message=(
                    "Unable to build the executable."
                ),
                errors=[
                    str(exc)
                ],
            )

    # ========================================================
    # INNO SETUP SCRIPT
    # ========================================================

    @staticmethod
    def _inno_escape(
        value: str,
    ) -> str:

        return (
            str(value)
            .replace(
                '"',
                '""',
            )
        )

    def generate_inno_script(
        self,
        *,
        executable_path: Optional[
            str | Path
        ] = None,
        output_script: Optional[
            str | Path
        ] = None,
    ) -> InstallerResult:

        validation = (
            self.validate_config()
        )

        if not validation.success:

            validation.operation = (
                "generate_inno_script"
            )

            return validation

        if executable_path is None:

            executable = (
                self.resolve_path(
                    "build/dist"
                )
                / (
                    self.config.app_name
                    + ".exe"
                )
            )

        else:

            executable = self.resolve_path(
                executable_path
            )

        if not executable.is_file():

            return InstallerResult(
                success=False,
                operation="generate_inno_script",
                message=(
                    "JarvisOS executable was not found."
                ),
                executable_path=str(
                    executable
                ),
                errors=[
                    "executable_missing"
                ],
            )

        if output_script is None:

            script_path = (
                self.resolve_path(
                    "build/installer"
                )
                / "JarvisOS.iss"
            )

        else:

            script_path = self.resolve_path(
                output_script
            )

        script_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        source_dir = (
            executable.parent
        )

        setup_output_dir = (
            self.resolve_path(
                self.config.output_dir
            )
        )

        setup_output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        app_name = (
            self._inno_escape(
                self.config.app_name
            )
        )

        publisher = (
            self._inno_escape(
                self.config.publisher
            )
        )

        version = (
            self._inno_escape(
                self.config.app_version
            )
        )

        default_dir = (
            "{autopf}\\"
            + self._inno_escape(
                self.config.install_dir_name
            )
        )

        lines = [
            "; JarvisOS generated Inno Setup script",
            "; Generated automatically by setup_builder.py",
            "",
            "[Setup]",
            f'AppId={{{self._stable_app_id()}}}',
            f'AppName="{app_name}"',
            f'AppVersion="{version}"',
            f'AppPublisher="{publisher}"',
            f'DefaultDirName={default_dir}',
            (
                "DefaultGroupName="
                f"{app_name}"
            ),
            (
                "OutputBaseFilename="
                + self._inno_escape(
                    Path(
                        self.config.setup_filename
                    ).stem
                )
            ),
            (
                "OutputDir="
                + self._inno_escape(
                    str(
                        setup_output_dir
                    )
                )
            ),
            "Compression="
            + self.config.compression,
            "SolidCompression=yes",
            "WizardStyle=modern",
            "PrivilegesRequired="
            + (
                "admin"
                if self.config.require_admin
                else "lowest"
            ),
            "ArchitecturesInstallIn64BitMode="
            + (
                "x64"
                if self.config.architecture
                == "x64"
                else ""
            ),
        ]

        if self.config.icon_path:

            icon = self.resolve_path(
                self.config.icon_path
            )

            lines.extend(
                [
                    (
                        "SetupIconFile="
                        + self._inno_escape(
                            str(icon)
                        )
                    ),
                ]
            )

        if self.config.license_path:

            license_file = (
                self.resolve_path(
                    self.config.license_path
                )
            )

            lines.extend(
                [
                    (
                        "LicenseFile="
                        + self._inno_escape(
                            str(license_file)
                        )
                    ),
                ]
            )

        lines.extend(
            [
                "",
                "[Files]",
                (
                    'Source: "'
                    + self._inno_escape(
                        str(source_dir / "*")
                    )
                    + '"; DestDir: "{app}"; '
                    "Flags: ignoreversion recursesubdirs createallsubdirs"
                ),
            ]
        )

        # Additional files.
        for item in (
            self.config.additional_files
        ):

            path = self.resolve_path(
                item
            )

            lines.append(
                (
                    'Source: "'
                    + self._inno_escape(
                        str(path)
                    )
                    + '"; DestDir: "{app}"; '
                    "Flags: ignoreversion"
                )
            )

        # Additional directories.
        for item in (
            self.config.additional_dirs
        ):

            path = self.resolve_path(
                item
            )

            lines.append(
                (
                    'Source: "'
                    + self._inno_escape(
                        str(path)
                    )
                    + '\\*"; DestDir: "{app}\\'
                    + self._inno_escape(
                        path.name
                    )
                    + '"; Flags: ignoreversion recursesubdirs createallsubdirs'
                )
            )

        lines.extend(
            [
                "",
                "[Icons]",
            ]
        )

        if (
            self.config.create_start_menu_shortcut
        ):

            lines.append(
                (
                    'Name: "{group}\\'
                    + app_name
                    + '"; Filename: "{app}\\'
                    + self._inno_escape(
                        self.config.executable_name
                    )
                    + '"'
                )
            )

        if (
            self.config.create_desktop_shortcut
        ):

            lines.append(
                (
                    'Name: "{autodesktop}\\'
                    + app_name
                    + '"; Filename: "{app}\\'
                    + self._inno_escape(
                        self.config.executable_name
                    )
                    + '"; Tasks: desktopicon'
                )
            )

        lines.extend(
            [
                "",
                "[Tasks]",
                (
                    'Name: "desktopicon"; '
                    "Description: \"Create a desktop shortcut\"; "
                    "Flags: unchecked"
                ),
                "",
                "[Run]",
                (
                    'Filename: "{app}\\'
                    + self._inno_escape(
                        self.config.executable_name
                    )
                    + '"; Description: "Launch JarvisOS"; '
                    "Flags: nowait postinstall skipifsilent"
                ),
            ]
        )

        script = (
            "\n".join(
                lines
            )
            + "\n"
        )

        try:

            script_path.write_text(
                script,
                encoding="utf-8",
            )

            result = InstallerResult(
                success=True,
                operation="generate_inno_script",
                message=(
                    "Inno Setup script generated successfully."
                ),
                output_path=str(
                    script_path
                ),
                metadata={
                    "script_lines": len(
                        lines
                    )
                },
            )

            self._record(
                result
            )

            return result

        except Exception as exc:

            return InstallerResult(
                success=False,
                operation="generate_inno_script",
                message=(
                    "Could not generate Inno Setup script."
                ),
                errors=[
                    str(exc)
                ],
            )

    # ========================================================
    # STABLE APP ID
    # ========================================================

    def _stable_app_id(
        self,
    ) -> str:

        import hashlib

        seed = (
            f"jarvisos:"
            f"{self.config.publisher}:"
            f"{self.config.app_name}"
        )

        digest = hashlib.md5(
            seed.encode(
                "utf-8"
            )
        ).hexdigest()

        return (
            digest[:8]
            + "-"
            + digest[8:12]
            + "-"
            + digest[12:16]
            + "-"
            + digest[16:20]
            + "-"
            + digest[20:32]
        )

    # ========================================================
    # COMPILE INSTALLER
    # ========================================================

    def compile_installer(
        self,
        script_path: str | Path,
        *,
        confirm: bool = False,
    ) -> InstallerResult:

        if not confirm:

            return InstallerResult(
                success=False,
                operation="compile_installer",
                message=(
                    "Compiling the installer requires "
                    "explicit confirmation."
                ),
                errors=[
                    "confirmation_required"
                ],
            )

        compiler = (
            self.find_inno_setup()
        )

        if not compiler:

            return InstallerResult(
                success=False,
                operation="compile_installer",
                message=(
                    "Inno Setup compiler (ISCC.exe) "
                    "was not found."
                ),
                errors=[
                    "inno_setup_not_found"
                ],
            )

        script = self.resolve_path(
            script_path
        )

        if not script.is_file():

            return InstallerResult(
                success=False,
                operation="compile_installer",
                message=(
                    "Inno Setup script was not found."
                ),
                errors=[
                    "script_not_found"
                ],
            )

        try:

            process = subprocess.run(
                [
                    compiler,
                    str(script),
                ],
                cwd=str(
                    self.project_dir
                ),
                capture_output=True,
                text=True,
                timeout=1800,
                shell=False,
            )

            output_dir = (
                self.resolve_path(
                    self.config.output_dir
                )
            )

            setup_path = (
                output_dir
                / self.config.setup_filename
            )

            if not setup_path.exists():

                # Inno Setup uses the filename stem
                # from OutputBaseFilename.
                candidate = (
                    output_dir
                    / (
                        Path(
                            self.config.setup_filename
                        ).stem
                        + ".exe"
                    )
                )

                if candidate.exists():
                    setup_path = candidate

            if process.returncode != 0:

                result = InstallerResult(
                    success=False,
                    operation="compile_installer",
                    message=(
                        "Inno Setup compilation failed."
                    ),
                    output_path=str(
                        setup_path
                    ),
                    return_code=(
                        process.returncode
                    ),
                    stdout=process.stdout[
                        -20000:
                    ],
                    stderr=process.stderr[
                        -20000:
                    ],
                    errors=[
                        "inno_setup_failed"
                    ],
                )

                self._record(
                    result
                )

                return result

            if not setup_path.is_file():

                result = InstallerResult(
                    success=False,
                    operation="compile_installer",
                    message=(
                        "Inno Setup reported success, "
                        "but the installer executable was not found."
                    ),
                    return_code=(
                        process.returncode
                    ),
                    stdout=process.stdout[
                        -20000:
                    ],
                    stderr=process.stderr[
                        -20000:
                    ],
                    errors=[
                        "installer_missing"
                    ],
                )

                self._record(
                    result
                )

                return result

            result = InstallerResult(
                success=True,
                operation="compile_installer",
                message=(
                    "JarvisOS installer built successfully."
                ),
                output_path=str(
                    setup_path
                ),
                return_code=(
                    process.returncode
                ),
                stdout=process.stdout[
                    -20000:
                ],
                stderr=process.stderr[
                    -20000:
                ],
            )

            self._record(
                result
            )

            return result

        except subprocess.TimeoutExpired:

            return InstallerResult(
                success=False,
                operation="compile_installer",
                message=(
                    "Installer compilation timed out."
                ),
                errors=[
                    "compile_timeout"
                ],
            )

        except Exception as exc:

            logger.error(
                "Installer compilation failed: %s",
                exc,
            )

            return InstallerResult(
                success=False,
                operation="compile_installer",
                message=(
                    "Unable to compile the installer."
                ),
                errors=[
                    str(exc)
                ],
            )

    # ========================================================
    # COMPLETE BUILD
    # ========================================================

    def build_installer(
        self,
        *,
        confirm: bool = False,
        clean: bool = True,
    ) -> InstallerResult:

        if not confirm:

            return InstallerResult(
                success=False,
                operation="build_installer",
                message=(
                    "Building the installer requires "
                    "explicit confirmation."
                ),
                errors=[
                    "confirmation_required"
                ],
            )

        executable_result = (
            self.build_executable(
                confirm=True,
                clean=clean,
            )
        )

        if not executable_result.success:

            executable_result.operation = (
                "build_installer"
            )

            return executable_result

        script_result = (
            self.generate_inno_script(
                executable_path=(
                    executable_result.executable_path
                )
            )
        )

        if not script_result.success:

            script_result.operation = (
                "build_installer"
            )

            return script_result

        compile_result = (
            self.compile_installer(
                script_result.output_path,
                confirm=True,
            )
        )

        if not compile_result.success:

            compile_result.operation = (
                "build_installer"
            )

            return compile_result

        result = InstallerResult(
            success=True,
            operation="build_installer",
            message=(
                "Complete JarvisOS installer "
                "build finished successfully."
            ),
            output_path=(
                compile_result.output_path
            ),
            executable_path=(
                executable_result.executable_path
            ),
            metadata={
                "script_path": (
                    script_result.output_path
                ),
            },
        )

        self._record(
            result
        )

        return result

    # ========================================================
    # BUILD MANIFEST
    # ========================================================

    def write_build_manifest(
        self,
        output_path: Optional[
            str | Path
        ] = None,
    ) -> InstallerResult:

        if output_path is None:

            path = (
                self.resolve_path(
                    "build/installer"
                )
                / "build_manifest.json"
            )

        else:

            path = self.resolve_path(
                output_path
            )

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = {
            "application": (
                self.config.app_name
            ),
            "version": (
                self.config.app_version
            ),
            "configuration": asdict(
                self.config
            ),
            "project_dir": str(
                self.project_dir
            ),
            "created_at": self._now(),
        }

        try:

            path.write_text(
                json.dumps(
                    payload,
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            return InstallerResult(
                success=True,
                operation="write_build_manifest",
                message=(
                    "Installer build manifest written."
                ),
                output_path=str(
                    path
                ),
            )

        except Exception as exc:

            return InstallerResult(
                success=False,
                operation="write_build_manifest",
                message=(
                    "Could not write installer build manifest."
                ),
                errors=[
                    str(exc)
                ],
            )

    # ========================================================
    # CLEAN BUILD
    # ========================================================

    def clean_build(
        self,
        *,
        confirm: bool = False,
    ) -> InstallerResult:

        if not confirm:

            return InstallerResult(
                success=False,
                operation="clean_build",
                message=(
                    "Cleaning build files requires "
                    "explicit confirmation."
                ),
                errors=[
                    "confirmation_required"
                ],
            )

        build_dir = (
            self.resolve_path(
                "build"
            )
        )

        if not build_dir.exists():

            return InstallerResult(
                success=True,
                operation="clean_build",
                message=(
                    "Build directory does not exist."
                ),
            )

        # Safety check: only delete the project's own
        # build directory.
        if (
            build_dir
            == self.project_dir
            or build_dir.parent
            != self.project_dir
        ):

            return InstallerResult(
                success=False,
                operation="clean_build",
                message=(
                    "Refusing to delete an unsafe path."
                ),
                errors=[
                    "unsafe_path"
                ],
            )

        try:

            shutil.rmtree(
                build_dir
            )

            return InstallerResult(
                success=True,
                operation="clean_build",
                message=(
                    "Build directory cleaned."
                ),
            )

        except Exception as exc:

            return InstallerResult(
                success=False,
                operation="clean_build",
                message=(
                    "Could not clean build directory."
                ),
                errors=[
                    str(exc)
                ],
            )

    # ========================================================
    # HISTORY
    # ========================================================

    def _record(
        self,
        result: InstallerResult,
    ) -> None:

        with self._lock:

            self.last_result = result

            self.history.append(
                {
                    "timestamp": self._now(),
                    "operation": result.operation,
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
    ) -> List[
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
                "project_dir": str(
                    self.project_dir
                ),
                "app_name": (
                    self.config.app_name
                ),
                "app_version": (
                    self.config.app_version
                ),
                "entry_script": (
                    self.config.entry_script
                ),
                "tools": (
                    self.get_tool_status()
                ),
                "last_operation": (
                    self.last_result.operation
                    if self.last_result
                    else ""
                ),
                "last_success": (
                    self.last_result.success
                    if self.last_result
                    else None
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
    ) -> "SetupBuilder":

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

_setup_builder: Optional[
    SetupBuilder
] = None

_setup_builder_lock = (
    threading.Lock()
)


def get_setup_builder() -> SetupBuilder:

    global _setup_builder

    with _setup_builder_lock:

        if _setup_builder is None:

            _setup_builder = (
                SetupBuilder()
            )

        return _setup_builder


# ============================================================
# CONVENIENCE FUNCTIONS
# ============================================================

def build_installer(
    *,
    confirm: bool = False,
) -> InstallerResult:

    return (
        get_setup_builder()
        .build_installer(
            confirm=confirm
        )
    )


def get_installer_status(
) -> Dict[str, Any]:

    return (
        get_setup_builder()
        .get_status()
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
        "JARVIS OS - SETUP BUILDER TEST"
    )
    print("=" * 60)

    builder = SetupBuilder()

    print("\nProject:")

    print(
        builder.project_dir
    )

    print("\nTool status:")

    print(
        json.dumps(
            builder.get_tool_status(),
            indent=2,
        )
    )

    print("\nInstaller status:")

    print(
        json.dumps(
            builder.get_status(),
            indent=2,
        )
    )

    # No build is started automatically.
    # This is intentional because building an executable
    # and installer is a resource-intensive operation.

    print(
        "\nNo executable or installer was built by the test."
    )

    builder.close()

    print(
        "\nSetup builder test completed."
  )
