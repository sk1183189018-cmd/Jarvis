"""
JarvisOS - File Control

Safe Windows file and folder management.

Features:
    - Search files and folders
    - Create files and folders
    - Rename files and folders
    - Copy files and folders
    - Move files and folders
    - Read text files
    - Write text files
    - Get file information
    - Safe delete with confirmation requirement
    - Trash/recycle-bin style delete when available
    - Protected-path checks

Important:
    Delete operations are never silently treated as safe.
    The caller should explicitly pass confirmed=True before deletion.
"""

from __future__ import annotations

import fnmatch
import logging
import os
import shutil
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union


logger = logging.getLogger(__name__)


# ======================================================================
# DATA MODELS
# ======================================================================


@dataclass
class FileResult:
    """Result of a file operation."""

    success: bool
    action: str
    message: str
    path: Optional[str] = None
    destination: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""

        return asdict(self)


@dataclass
class FileInfo:
    """Information about a file or folder."""

    path: str
    name: str
    is_file: bool
    is_directory: bool
    size: int
    size_mb: float
    extension: str
    created_at: Optional[float]
    modified_at: Optional[float]
    accessed_at: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        """Convert file information to dictionary."""

        return asdict(self)


@dataclass
class SearchResult:
    """One filesystem search result."""

    path: str
    name: str
    is_file: bool
    is_directory: bool
    size: int
    extension: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert search result to dictionary."""

        return asdict(self)


# ======================================================================
# FILE CONTROLLER
# ======================================================================


class FileControl:
    """
    JarvisOS file-management controller.

    This class performs filesystem operations but does not decide
    whether the user should be allowed to perform a dangerous action.

    Higher-level security/decision modules should handle user
    confirmation before calling destructive methods with confirmed=True.
    """

    DEFAULT_MAX_SEARCH_RESULTS = 200

    # Windows/system locations that should never be deleted by
    # JarvisOS through this controller.
    PROTECTED_NAMES = {
        "windows",
        "program files",
        "program files (x86)",
        "programdata",
        "system volume information",
        "$recycle.bin",
        "recovery",
        "boot",
    }

    PROTECTED_FILES = {
        "bootmgr",
        "bootmgfw.efi",
        "ntldr",
    }

    TEXT_EXTENSIONS = {
        ".txt",
        ".md",
        ".markdown",
        ".json",
        ".yaml",
        ".yml",
        ".xml",
        ".csv",
        ".log",
        ".ini",
        ".cfg",
        ".conf",
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".html",
        ".htm",
        ".css",
        ".scss",
        ".java",
        ".c",
        ".h",
        ".cpp",
        ".hpp",
        ".cs",
        ".php",
        ".sql",
        ".sh",
        ".bat",
        ".cmd",
        ".ps1",
    }

    def __init__(
        self,
        max_search_results: int = DEFAULT_MAX_SEARCH_RESULTS,
    ) -> None:

        self.max_search_results = max(
            1,
            min(
                5000,
                int(max_search_results),
            ),
        )

        self.system_drive = self._get_system_drive()

        logger.info(
            "FileControl initialized. system_drive=%s",
            self.system_drive,
        )

    # ==================================================================
    # SEARCH
    # ==================================================================

    def search(
        self,
        query: str,
        root: Optional[
            Union[str, Path]
        ] = None,
        recursive: bool = True,
        files_only: bool = False,
        folders_only: bool = False,
        extension: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> List[SearchResult]:
        """
        Search for files/folders.

        Examples:

            search("report")
            search("photo", root="C:/Users")
            search("invoice", extension=".pdf")
            search("project", files_only=True)
        """

        if not query:

            return []

        query = str(
            query
        ).strip().lower()

        if not query:

            return []

        search_root = (
            Path(root).expanduser()
            if root
            else Path.home()
        )

        if not search_root.exists():

            logger.warning(
                "Search root does not exist: %s",
                search_root,
            )

            return []

        if not search_root.is_dir():

            return []

        limit = (
            self.max_search_results
            if max_results is None
            else max(
                1,
                min(
                    self.max_search_results,
                    int(max_results),
                ),
            )
        )

        normalized_extension = (
            self._normalize_extension(
                extension
            )
            if extension
            else None
        )

        results: List[
            SearchResult
        ] = []

        try:

            iterator = (
                search_root.rglob("*")
                if recursive
                else search_root.glob("*")
            )

            for item in iterator:

                if len(results) >= limit:
                    break

                try:

                    is_file = item.is_file()
                    is_directory = item.is_dir()

                    if files_only and not is_file:
                        continue

                    if folders_only and not is_directory:
                        continue

                    if (
                        normalized_extension
                        and is_file
                        and item.suffix.lower()
                        != normalized_extension
                    ):
                        continue

                    name_lower = (
                        item.name.lower()
                    )

                    # Match against filename/folder name.
                    if query not in name_lower:
                        continue

                    try:

                        size = (
                            item.stat().st_size
                            if is_file
                            else 0
                        )

                    except OSError:

                        size = 0

                    results.append(
                        SearchResult(
                            path=str(
                                item.resolve()
                            ),
                            name=item.name,
                            is_file=is_file,
                            is_directory=is_directory,
                            size=size,
                            extension=(
                                item.suffix.lower()
                                if is_file
                                else ""
                            ),
                        )
                    )

                except (
                    PermissionError,
                    OSError,
                ):

                    continue

        except (
            PermissionError,
            OSError,
        ) as exc:

            logger.warning(
                "Search stopped at %s: %s",
                search_root,
                exc,
            )

        logger.info(
            "File search '%s' returned %d result(s).",
            query,
            len(results),
        )

        return results

    # ==================================================================
    # FIND EXACT NAME
    # ==================================================================

    def find(
        self,
        name: str,
        root: Optional[
            Union[str, Path]
        ] = None,
        recursive: bool = True,
        max_results: Optional[int] = None,
    ) -> List[SearchResult]:
        """Find files/folders by exact or wildcard name."""

        if not name:
            return []

        target = str(
            name
        ).strip()

        search_root = (
            Path(root).expanduser()
            if root
            else Path.home()
        )

        limit = (
            self.max_search_results
            if max_results is None
            else max(
                1,
                min(
                    self.max_search_results,
                    int(max_results),
                ),
            )
        )

        results = []

        try:

            iterator = (
                search_root.rglob("*")
                if recursive
                else search_root.glob("*")
            )

            for item in iterator:

                if len(results) >= limit:
                    break

                try:

                    if fnmatch.fnmatch(
                        item.name.lower(),
                        target.lower(),
                    ):

                        results.append(
                            self._make_search_result(
                                item
                            )
                        )

                except (
                    PermissionError,
                    OSError,
                ):

                    continue

        except (
            PermissionError,
            OSError,
        ):

            pass

        return results

    # ==================================================================
    # CREATE FOLDER
    # ==================================================================

    def create_folder(
        self,
        path: Union[str, Path],
        exist_ok: bool = False,
    ) -> FileResult:
        """Create a directory."""

        target = self._normalize_path(
            path
        )

        if not target:

            return FileResult(
                success=False,
                action="create_folder",
                message="Folder path is required.",
                error="empty_path",
            )

        try:

            if target.exists():

                if target.is_dir() and exist_ok:

                    return FileResult(
                        success=True,
                        action="create_folder",
                        message=(
                            f"Folder already exists: "
                            f"{target}"
                        ),
                        path=str(target),
                    )

                return FileResult(
                    success=False,
                    action="create_folder",
                    message=(
                        f"Path already exists: "
                        f"{target}"
                    ),
                    path=str(target),
                    error="already_exists",
                )

            target.mkdir(
                parents=True,
                exist_ok=False,
            )

            logger.info(
                "Folder created: %s",
                target,
            )

            return FileResult(
                success=True,
                action="create_folder",
                message=(
                    f"Folder created: "
                    f"{target}"
                ),
                path=str(target),
            )

        except PermissionError as exc:

            return FileResult(
                success=False,
                action="create_folder",
                message=(
                    "Permission denied while "
                    "creating folder."
                ),
                path=str(target),
                error=str(exc),
            )

        except Exception as exc:

            logger.exception(
                "Failed creating folder: %s",
                target,
            )

            return FileResult(
                success=False,
                action="create_folder",
                message=(
                    f"Could not create folder: "
                    f"{target}"
                ),
                path=str(target),
                error=str(exc),
            )

    # ==================================================================
    # CREATE FILE
    # ==================================================================

    def create_file(
        self,
        path: Union[str, Path],
        content: str = "",
        overwrite: bool = False,
        encoding: str = "utf-8",
    ) -> FileResult:
        """Create a text file."""

        target = self._normalize_path(
            path
        )

        if not target:

            return FileResult(
                success=False,
                action="create_file",
                message="File path is required.",
                error="empty_path",
            )

        try:

            if target.exists():

                if not overwrite:

                    return FileResult(
                        success=False,
                        action="create_file",
                        message=(
                            f"File already exists: "
                            f"{target}"
                        ),
                        path=str(target),
                        error="already_exists",
                    )

                if target.is_dir():

                    return FileResult(
                        success=False,
                        action="create_file",
                        message=(
                            "A folder already exists "
                            "at this path."
                        ),
                        path=str(target),
                        error="path_is_directory",
                    )

            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            target.write_text(
                str(content),
                encoding=encoding,
            )

            logger.info(
                "File created: %s",
                target,
            )

            return FileResult(
                success=True,
                action="create_file",
                message=(
                    f"File created: "
                    f"{target}"
                ),
                path=str(target),
                metadata={
                    "bytes": target.stat().st_size,
                },
            )

        except PermissionError as exc:

            return FileResult(
                success=False,
                action="create_file",
                message=(
                    "Permission denied while "
                    "creating file."
                ),
                path=str(target),
                error=str(exc),
            )

        except Exception as exc:

            logger.exception(
                "Failed creating file: %s",
                target,
            )

            return FileResult(
                success=False,
                action="create_file",
                message=(
                    f"Could not create file: "
                    f"{target}"
                ),
                path=str(target),
                error=str(exc),
            )

    # ==================================================================
    # READ FILE
    # ==================================================================

    def read_file(
        self,
        path: Union[str, Path],
        encoding: str = "utf-8",
        max_characters: Optional[int] = None,
    ) -> FileResult:
        """Read a text file."""

        target = self._normalize_path(
            path
        )

        if not target:

            return FileResult(
                success=False,
                action="read_file",
                message="File path is required.",
                error="empty_path",
            )

        if not target.exists():

            return FileResult(
                success=False,
                action="read_file",
                message=(
                    f"File not found: "
                    f"{target}"
                ),
                path=str(target),
                error="not_found",
            )

        if not target.is_file():

            return FileResult(
                success=False,
                action="read_file",
                message=(
                    "The specified path is not a file."
                ),
                path=str(target),
                error="not_a_file",
            )

        try:

            content = target.read_text(
                encoding=encoding
            )

            if (
                max_characters is not None
                and max_characters >= 0
            ):

                content = content[
                    : int(
                        max_characters
                    )
                ]

            return FileResult(
                success=True,
                action="read_file",
                message=(
                    f"Read file: "
                    f"{target}"
                ),
                path=str(target),
                metadata={
                    "content": content,
                    "encoding": encoding,
                },
            )

        except UnicodeDecodeError as exc:

            return FileResult(
                success=False,
                action="read_file",
                message=(
                    "The file is not valid "
                    f"{encoding} text."
                ),
                path=str(target),
                error=str(exc),
            )

        except Exception as exc:

            logger.exception(
                "Failed reading file: %s",
                target,
            )

            return FileResult(
                success=False,
                action="read_file",
                message=(
                    f"Could not read "
                    f"{target.name}."
                ),
                path=str(target),
                error=str(exc),
            )

    # ==================================================================
    # WRITE FILE
    # ==================================================================

    def write_file(
        self,
        path: Union[str, Path],
        content: str,
        overwrite: bool = True,
        encoding: str = "utf-8",
    ) -> FileResult:
        """
        Write text to a file.

        If overwrite=False and the file exists, the operation
        is rejected.
        """

        target = self._normalize_path(
            path
        )

        if not target:

            return FileResult(
                success=False,
                action="write_file",
                message="File path is required.",
                error="empty_path",
            )

        if target.exists() and not overwrite:

            return FileResult(
                success=False,
                action="write_file",
                message=(
                    f"File already exists: "
                    f"{target}"
                ),
                path=str(target),
                error="overwrite_disabled",
            )

        try:

            if target.exists() and target.is_dir():

                return FileResult(
                    success=False,
                    action="write_file",
                    message=(
                        "Cannot write to a directory."
                    ),
                    path=str(target),
                    error="path_is_directory",
                )

            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            target.write_text(
                str(content),
                encoding=encoding,
            )

            return FileResult(
                success=True,
                action="write_file",
                message=(
                    f"File written: "
                    f"{target}"
                ),
                path=str(target),
                metadata={
                    "bytes": target.stat().st_size,
                },
            )

        except Exception as exc:

            logger.exception(
                "Failed writing file: %s",
                target,
            )

            return FileResult(
                success=False,
                action="write_file",
                message=(
                    f"Could not write "
                    f"{target.name}."
                ),
                path=str(target),
                error=str(exc),
            )

    # ==================================================================
    # RENAME
    # ==================================================================

    def rename(
        self,
        source: Union[str, Path],
        new_name: str,
        overwrite: bool = False,
    ) -> FileResult:
        """Rename a file or folder."""

        source_path = self._normalize_path(
            source
        )

        if not source_path:

            return FileResult(
                success=False,
                action="rename",
                message="Source path is required.",
                error="empty_source",
            )

        if not source_path.exists():

            return FileResult(
                success=False,
                action="rename",
                message=(
                    f"Source does not exist: "
                    f"{source_path}"
                ),
                path=str(source_path),
                error="not_found",
            )

        new_name = str(
            new_name
        ).strip()

        if not new_name:

            return FileResult(
                success=False,
                action="rename",
                message="New name is required.",
                path=str(source_path),
                error="empty_name",
            )

        if (
            new_name in {
                ".",
                "..",
            }
            or "/" in new_name
            or "\\" in new_name
        ):

            return FileResult(
                success=False,
                action="rename",
                message=(
                    "New name must contain only "
                    "the file or folder name."
                ),
                path=str(source_path),
                error="invalid_name",
            )

        destination = (
            source_path.parent
            / new_name
        )

        if destination.exists():

            if not overwrite:

                return FileResult(
                    success=False,
                    action="rename",
                    message=(
                        f"Destination already exists: "
                        f"{destination}"
                    ),
                    path=str(source_path),
                    destination=str(destination),
                    error="destination_exists",
                )

            # Do not silently overwrite directories.
            if destination.is_dir():

                return FileResult(
                    success=False,
                    action="rename",
                    message=(
                        "Cannot overwrite an existing "
                        "directory during rename."
                    ),
                    path=str(source_path),
                    destination=str(destination),
                    error="destination_directory_exists",
                )

        try:

            source_path.rename(
                destination
            )

            logger.info(
                "Renamed %s -> %s",
                source_path,
                destination,
            )

            return FileResult(
                success=True,
                action="rename",
                message=(
                    f"Renamed "
                    f"{source_path.name} "
                    f"to {destination.name}."
                ),
                path=str(source_path),
                destination=str(destination),
            )

        except Exception as exc:

            logger.exception(
                "Rename failed: %s",
                source_path,
            )

            return FileResult(
                success=False,
                action="rename",
                message=(
                    f"Could not rename "
                    f"{source_path.name}."
                ),
                path=str(source_path),
                destination=str(destination),
                error=str(exc),
            )

    # ==================================================================
    # COPY
    # ==================================================================

    def copy(
        self,
        source: Union[str, Path],
        destination: Union[str, Path],
        overwrite: bool = False,
    ) -> FileResult:
        """Copy a file or directory."""

        source_path = self._normalize_path(
            source
        )

        destination_path = self._normalize_path(
            destination
        )

        if not source_path or not destination_path:

            return FileResult(
                success=False,
                action="copy",
                message=(
                    "Source and destination "
                    "are required."
                ),
                error="missing_path",
            )

        if not source_path.exists():

            return FileResult(
                success=False,
                action="copy",
                message=(
                    f"Source does not exist: "
                    f"{source_path}"
                ),
                path=str(source_path),
                destination=str(destination_path),
                error="source_not_found",
            )

        try:

            # If destination points to an existing directory,
            # copy the source inside it.
            if (
                destination_path.exists()
                and destination_path.is_dir()
            ):

                final_destination = (
                    destination_path
                    / source_path.name
                )

            else:

                final_destination = (
                    destination_path
                )

            if (
                final_destination.exists()
                and not overwrite
            ):

                return FileResult(
                    success=False,
                    action="copy",
                    message=(
                        f"Destination already exists: "
                        f"{final_destination}"
                    ),
                    path=str(source_path),
                    destination=str(
                        final_destination
                    ),
                    error="destination_exists",
                )

            if source_path.is_dir():

                if final_destination.exists():

                    if overwrite:

                        shutil.copytree(
                            source_path,
                            final_destination,
                            dirs_exist_ok=True,
                        )

                    else:

                        raise FileExistsError(
                            str(
                                final_destination
                            )
                        )

                else:

                    shutil.copytree(
                        source_path,
                        final_destination,
                    )

            else:

                final_destination.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                shutil.copy2(
                    source_path,
                    final_destination,
                )

            logger.info(
                "Copied %s -> %s",
                source_path,
                final_destination,
            )

            return FileResult(
                success=True,
                action="copy",
                message=(
                    f"Copied "
                    f"{source_path.name}."
                ),
                path=str(source_path),
                destination=str(
                    final_destination
                ),
            )

        except Exception as exc:

            logger.exception(
                "Copy failed: %s",
                source_path,
            )

            return FileResult(
                success=False,
                action="copy",
                message=(
                    f"Could not copy "
                    f"{source_path.name}."
                ),
                path=str(source_path),
                destination=str(destination_path),
                error=str(exc),
            )

    # ==================================================================
    # MOVE
    # ==================================================================

    def move(
        self,
        source: Union[str, Path],
        destination: Union[str, Path],
        overwrite: bool = False,
    ) -> FileResult:
        """Move a file or directory."""

        source_path = self._normalize_path(
            source
        )

        destination_path = self._normalize_path(
            destination
        )

        if not source_path or not destination_path:

            return FileResult(
                success=False,
                action="move",
                message=(
                    "Source and destination "
                    "are required."
                ),
                error="missing_path",
            )

        if not source_path.exists():

            return FileResult(
                success=False,
                action="move",
                message=(
                    f"Source does not exist: "
                    f"{source_path}"
                ),
                path=str(source_path),
                destination=str(destination_path),
                error="source_not_found",
            )

        try:

            if (
                destination_path.exists()
                and destination_path.is_dir()
            ):

                final_destination = (
                    destination_path
                    / source_path.name
                )

            else:

                final_destination = (
                    destination_path
                )

            if (
                final_destination.exists()
                and not overwrite
            ):

                return FileResult(
                    success=False,
                    action="move",
                    message=(
                        f"Destination already exists: "
                        f"{final_destination}"
                    ),
                    path=str(source_path),
                    destination=str(
                        final_destination
                    ),
                    error="destination_exists",
                )

            final_destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            # shutil.move does not provide a universal
            # overwrite=False switch, so remove only when
            # explicitly allowed.
            if (
                final_destination.exists()
                and overwrite
            ):

                if final_destination.is_dir():

                    shutil.rmtree(
                        final_destination
                    )

                else:

                    final_destination.unlink()

            shutil.move(
                str(source_path),
                str(final_destination),
            )

            logger.info(
                "Moved %s -> %s",
                source_path,
                final_destination,
            )

            return FileResult(
                success=True,
                action="move",
                message=(
                    f"Moved "
                    f"{source_path.name}."
                ),
                path=str(source_path),
                destination=str(
                    final_destination
                ),
            )

        except Exception as exc:

            logger.exception(
                "Move failed: %s",
                source_path,
            )

            return FileResult(
                success=False,
                action="move",
                message=(
                    f"Could not move "
                    f"{source_path.name}."
                ),
                path=str(source_path),
                destination=str(destination_path),
                error=str(exc),
            )

    # ==================================================================
    # DELETE
    # ==================================================================

    def delete(
        self,
        path: Union[str, Path],
        confirmed: bool = False,
        permanent: bool = False,
    ) -> FileResult:
        """
        Delete a file or folder.

        IMPORTANT:
            confirmed must be True.

        This prevents an accidental AI command from directly
        deleting user data.

        permanent=False attempts to use the Windows recycle bin
        when available.
        """

        target = self._normalize_path(
            path
        )

        if not target:

            return FileResult(
                success=False,
                action="delete",
                message="Path is required.",
                error="empty_path",
            )

        if not confirmed:

            return FileResult(
                success=False,
                action="delete",
                message=(
                    f"Deletion of '{target}' "
                    "requires explicit confirmation."
                ),
                path=str(target),
                error="confirmation_required",
                metadata={
                    "requires_confirmation": True,
                    "permanent": permanent,
                },
            )

        if not target.exists():

            return FileResult(
                success=False,
                action="delete",
                message=(
                    f"Path does not exist: "
                    f"{target}"
                ),
                path=str(target),
                error="not_found",
            )

        protected, reason = (
            self.is_protected_path(
                target
            )
        )

        if protected:

            return FileResult(
                success=False,
                action="delete",
                message=(
                    "This path is protected and "
                    "cannot be deleted by JarvisOS."
                ),
                path=str(target),
                error=reason,
            )

        try:

            # ----------------------------------------------------------
            # Permanent deletion
            # ----------------------------------------------------------

            if permanent:

                if target.is_dir():

                    shutil.rmtree(
                        target
                    )

                else:

                    target.unlink()

            # ----------------------------------------------------------
            # Recycle Bin on Windows
            # ----------------------------------------------------------

            else:

                if not self._send_to_recycle_bin(
                    target
                ):

                    # Fallback is still destructive, so it happens
                    # only after confirmed=True.
                    if target.is_dir():

                        shutil.rmtree(
                            target
                        )

                    else:

                        target.unlink()

            logger.warning(
                "Deleted path: %s permanent=%s",
                target,
                permanent,
            )

            return FileResult(
                success=True,
                action="delete",
                message=(
                    f"Deleted "
                    f"{target.name}."
                ),
                path=str(target),
                metadata={
                    "permanent": permanent,
                },
            )

        except PermissionError as exc:

            return FileResult(
                success=False,
                action="delete",
                message=(
                    "Permission denied while "
                    "deleting the path."
                ),
                path=str(target),
                error=str(exc),
            )

        except Exception as exc:

            logger.exception(
                "Delete failed: %s",
                target,
            )

            return FileResult(
                success=False,
                action="delete",
                message=(
                    f"Could not delete "
                    f"{target.name}."
                ),
                path=str(target),
                error=str(exc),
            )

    # ==================================================================
    # FILE INFORMATION
    # ==================================================================

    def get_info(
        self,
        path: Union[str, Path],
    ) -> Optional[FileInfo]:
        """Return file/folder metadata."""

        target = self._normalize_path(
            path
        )

        if not target or not target.exists():
            return None

        try:

            stat = target.stat()

            is_file = target.is_file()
            is_directory = target.is_dir()

            size = (
                stat.st_size
                if is_file
                else self._directory_size(
                    target
                )
            )

            return FileInfo(
                path=str(
                    target.resolve()
                ),
                name=target.name,
                is_file=is_file,
                is_directory=is_directory,
                size=size,
                size_mb=round(
                    size / (
                        1024 * 1024
                    ),
                    3,
                ),
                extension=(
                    target.suffix.lower()
                    if is_file
                    else ""
                ),
                created_at=getattr(
                    stat,
                    "st_ctime",
                    None,
                ),
                modified_at=getattr(
                    stat,
                    "st_mtime",
                    None,
                ),
                accessed_at=getattr(
                    stat,
                    "st_atime",
                    None,
                ),
            )

        except (
            PermissionError,
            OSError,
        ) as exc:

            logger.warning(
                "Could not inspect %s: %s",
                target,
                exc,
            )

            return None

    # ==================================================================
    # CHECK PATH
    # ==================================================================

    def exists(
        self,
        path: Union[str, Path],
    ) -> bool:
        """Check whether a path exists."""

        target = self._normalize_path(
            path
        )

        return bool(
            target
            and target.exists()
        )

    def is_file(
        self,
        path: Union[str, Path],
    ) -> bool:
        """Check whether a path is a file."""

        target = self._normalize_path(
            path
        )

        return bool(
            target
            and target.is_file()
        )

    def is_folder(
        self,
        path: Union[str, Path],
    ) -> bool:
        """Check whether a path is a folder."""

        target = self._normalize_path(
            path
        )

        return bool(
            target
            and target.is_dir()
        )

    # ==================================================================
    # PROTECTED PATHS
    # ==================================================================

    def is_protected_path(
        self,
        path: Union[str, Path],
    ) -> tuple[bool, str]:
        """
        Determine whether a path should be protected.

        Protection covers:
            - Windows root/system directories
            - Program Files
            - ProgramData
            - System Volume Information
            - Recycle Bin
            - boot-related files
        """

        target = self._normalize_path(
            path
        )

        if not target:

            return True, "invalid_path"

        try:

            resolved = target.resolve()

        except OSError:

            resolved = target

        name_lower = (
            resolved.name.lower()
        )

        if name_lower in self.PROTECTED_NAMES:

            return True, (
                "protected_system_directory"
            )

        if name_lower in self.PROTECTED_FILES:

            return True, (
                "protected_system_file"
            )

        # --------------------------------------------------------------
        # Protect the Windows directory itself and anything directly
        # inside it from destructive operations.
        # --------------------------------------------------------------

        windows_dir = (
            Path(
                os.environ.get(
                    "WINDIR",
                    str(
                        Path.home().anchor
                        + "Windows"
                    ),
                )
            )
            .resolve()
        )

        try:

            resolved.relative_to(
                windows_dir
            )

            return True, (
                "inside_windows_directory"
            )

        except ValueError:

            pass

        # --------------------------------------------------------------
        # Protect Program Files locations.
        # --------------------------------------------------------------

        protected_roots = []

        program_files = os.environ.get(
            "ProgramFiles"
        )

        program_files_x86 = os.environ.get(
            "ProgramFiles(x86)"
        )

        program_data = os.environ.get(
            "ProgramData"
        )

        for value in (
            program_files,
            program_files_x86,
            program_data,
        ):

            if value:
                protected_roots.append(
                    Path(value).resolve()
                )

        for root in protected_roots:

            try:

                resolved.relative_to(
                    root
                )

                return True, (
                    "inside_protected_system_directory"
                )

            except ValueError:

                continue

        # --------------------------------------------------------------
        # Protect filesystem root.
        # --------------------------------------------------------------

        if (
            resolved.parent == resolved
        ):

            return True, (
                "filesystem_root"
            )

        return False, ""

    # ==================================================================
    # DIRECTORY SIZE
    # ==================================================================

    def directory_size(
        self,
        path: Union[str, Path],
    ) -> int:
        """Calculate total size of a directory."""

        target = self._normalize_path(
            path
        )

        if not target or not target.is_dir():
            return 0

        return self._directory_size(
            target
        )

    def _directory_size(
        self,
        path: Path,
    ) -> int:

        total = 0

        try:

            for item in path.rglob("*"):

                try:

                    if item.is_file():

                        total += item.stat().st_size

                except (
                    PermissionError,
                    OSError,
                ):

                    continue

        except (
            PermissionError,
            OSError,
        ):

            pass

        return total

    # ==================================================================
    # TEXT FILE CHECK
    # ==================================================================

    def is_text_file(
        self,
        path: Union[str, Path],
    ) -> bool:
        """Check whether a file has a common text extension."""

        target = self._normalize_path(
            path
        )

        if not target or not target.is_file():
            return False

        return (
            target.suffix.lower()
            in self.TEXT_EXTENSIONS
        )

    # ==================================================================
    # DIRECTORY LIST
    # ==================================================================

    def list_directory(
        self,
        path: Optional[
            Union[str, Path]
        ] = None,
        include_hidden: bool = True,
    ) -> List[FileInfo]:
        """List direct children of a directory."""

        target = (
            self._normalize_path(
                path
            )
            if path
            else Path.home()
        )

        if not target or not target.is_dir():
            return []

        results = []

        try:

            for item in target.iterdir():

                if (
                    not include_hidden
                    and item.name.startswith(".")
                ):
                    continue

                info = self.get_info(
                    item
                )

                if info:

                    results.append(
                        info
                    )

        except (
            PermissionError,
            OSError,
        ) as exc:

            logger.warning(
                "Could not list directory %s: %s",
                target,
                exc,
            )

        results.sort(
            key=lambda item: (
                not item.is_directory,
                item.name.lower(),
            )
        )

        return results

    # ==================================================================
    # SAFE COPY / MOVE VALIDATION
    # ==================================================================

    def validate_destination(
        self,
        source: Union[str, Path],
        destination: Union[str, Path],
    ) -> Dict[str, Any]:
        """Validate a copy/move destination."""

        source_path = self._normalize_path(
            source
        )

        destination_path = self._normalize_path(
            destination
        )

        if not source_path:

            return {
                "valid": False,
                "reason": "invalid_source",
            }

        if not destination_path:

            return {
                "valid": False,
                "reason": "invalid_destination",
            }

        if (
            source_path == destination_path
        ):

            return {
                "valid": False,
                "reason": "source_equals_destination",
            }

        # Prevent moving/copying a directory into itself.
        if source_path.is_dir():

            try:

                destination_path.resolve().relative_to(
                    source_path.resolve()
                )

                return {
                    "valid": False,
                    "reason": (
                        "destination_inside_source"
                    ),
                }

            except ValueError:

                pass

        return {
            "valid": True,
            "source": str(
                source_path
            ),
            "destination": str(
                destination_path
            ),
        }

    # ==================================================================
    # RECYCLE BIN
    # ==================================================================

    def _send_to_recycle_bin(
        self,
        path: Path,
    ) -> bool:
        """
        Try sending a path to the Windows Recycle Bin.

        Uses the Windows Shell API through pywin32 when available.
        """

        if os.name != "nt":
            return False

        try:

            import win32com.shell.shell as shell
            import win32com.shell.shellcon as shellcon

            # SHFileOperation with FOF_ALLOWUNDO moves the item
            # to the Recycle Bin instead of immediately destroying it.
            operation = (
                shellcon.FO_DELETE
            )

            flags = (
                shellcon.FOF_ALLOWUNDO
                | shellcon.FOF_NOCONFIRMATION
                | shellcon.FOF_NOERRORUI
                | shellcon.FOF_SILENT
            )

            result = shell.SHFileOperation(
                (
                    0,
                    operation,
                    str(path),
                    None,
                    flags,
                    False,
                    None,
                    None,
                )
            )

            # SHFileOperation returns a tuple on common pywin32
            # installations; first value is the error code.
            if isinstance(
                result,
                tuple,
            ):

                error_code = result[0]

            else:

                error_code = result

            if error_code == 0:

                return True

        except Exception as exc:

            logger.debug(
                "Recycle Bin operation unavailable: %s",
                exc,
            )

        return False

    # ==================================================================
    # HELPERS
    # ==================================================================

    @staticmethod
    def _normalize_path(
        path: Union[str, Path, None],
    ) -> Optional[Path]:

        if path is None:
            return None

        value = str(
            path
        ).strip()

        if not value:
            return None

        # Remove matching surrounding quotes.
        if (
            len(value) >= 2
            and value[0] == '"'
            and value[-1] == '"'
        ):

            value = value[1:-1]

        try:

            return Path(
                value
            ).expanduser()

        except Exception:

            return None

    @staticmethod
    def _normalize_extension(
        extension: str,
    ) -> str:

        extension = str(
            extension
        ).strip().lower()

        if not extension.startswith(
            "."
        ):

            extension = (
                "."
                + extension
            )

        return extension

    @staticmethod
    def _make_search_result(
        path: Path,
    ) -> SearchResult:

        try:

            is_file = path.is_file()
            is_directory = path.is_dir()

            size = (
                path.stat().st_size
                if is_file
                else 0
            )

        except (
            PermissionError,
            OSError,
        ):

            is_file = False
            is_directory = False
            size = 0

        return SearchResult(
            path=str(
                path.resolve()
            ),
            name=path.name,
            is_file=is_file,
            is_directory=is_directory,
            size=size,
            extension=(
                path.suffix.lower()
                if is_file
                else ""
            ),
        )

    @staticmethod
    def _get_system_drive() -> str:

        if os.name != "nt":

            return "/"

        drive = os.environ.get(
            "SystemDrive",
            "C:",
        )

        if not drive.endswith(
            "\\"
        ):

            drive += "\\"

        return drive

    # ==================================================================
    # STATUS
    # ==================================================================

    def get_status(self) -> Dict[str, Any]:
        """Return controller status."""

        return {
            "available": True,
            "platform": os.name,
            "system_drive": self.system_drive,
            "home_directory": str(
                Path.home()
            ),
            "max_search_results": (
                self.max_search_results
            ),
            "recycle_bin_support": (
                os.name == "nt"
            ),
        }

    def close(self) -> None:
        """Close controller resources."""

        logger.info(
            "FileControl closed."
        )


# ======================================================================
# SHARED CONTROLLER
# ======================================================================


_default_controller: Optional[
    FileControl
] = None


def get_file_controller() -> FileControl:
    """Return the shared FileControl instance."""

    global _default_controller

    if _default_controller is None:

        _default_controller = FileControl()

    return _default_controller


# ======================================================================
# CONVENIENCE FUNCTIONS
# ======================================================================


def search_files(
    query: str,
    root: Optional[
        Union[str, Path]
    ] = None,
    **kwargs,
) -> List[SearchResult]:
    """Convenience file-search function."""

    return get_file_controller().search(
        query=query,
        root=root,
        **kwargs,
    )


def create_file(
    path: Union[str, Path],
    content: str = "",
    overwrite: bool = False,
) -> FileResult:
    """Convenience file-creation function."""

    return get_file_controller().create_file(
        path=path,
        content=content,
        overwrite=overwrite,
    )


def create_folder(
    path: Union[str, Path],
    exist_ok: bool = False,
) -> FileResult:
    """Convenience folder-creation function."""

    return get_file_controller().create_folder(
        path=path,
        exist_ok=exist_ok,
    )


def delete_file(
    path: Union[str, Path],
    confirmed: bool = False,
    permanent: bool = False,
) -> FileResult:
    """Convenience delete function."""

    return get_file_controller().delete(
        path=path,
        confirmed=confirmed,
        permanent=permanent,
    )


# ======================================================================
# DIRECT TEST
# ======================================================================


if __name__ == "__main__":

    import tempfile

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
    print("JARVIS OS - FILE CONTROL TEST")
    print("=" * 70)

    controller = FileControl()

    with tempfile.TemporaryDirectory(
        prefix="jarvisos_test_"
    ) as temp_directory:

        root = Path(
            temp_directory
        )

        print()
        print("1. Test directory:")
        print(root)

        # --------------------------------------------------------------
        # Create folder
        # --------------------------------------------------------------

        test_folder = (
            root
            / "Documents"
        )

        result = controller.create_folder(
            test_folder
        )

        print()
        print("2. Create folder:")
        print(result.to_dict())

        # --------------------------------------------------------------
        # Create file
        # --------------------------------------------------------------

        test_file = (
            test_folder
            / "hello.txt"
        )

        result = controller.create_file(
            test_file,
            content=(
                "Hello from JarvisOS!\n"
                "This is a real FileControl test."
            ),
        )

        print()
        print("3. Create file:")
        print(result.to_dict())

        # --------------------------------------------------------------
        # Read file
        # --------------------------------------------------------------

        result = controller.read_file(
            test_file
        )

        print()
        print("4. Read file:")
        print(
            result.metadata
        )

        # --------------------------------------------------------------
        # File information
        # --------------------------------------------------------------

        info = controller.get_info(
            test_file
        )

        print()
        print("5. File information:")

        if info:
            print(
                info.to_dict()
            )

        # --------------------------------------------------------------
        # Search
        # --------------------------------------------------------------

        results = controller.search(
            "hello",
            root=root,
        )

        print()
        print("6. Search results:")

        for item in results:

            print(
                item.to_dict()
            )

        # --------------------------------------------------------------
        # Rename
        # --------------------------------------------------------------

        renamed_file = (
            test_folder
            / "renamed.txt"
        )

        result = controller.rename(
            test_file,
            renamed_file.name,
        )

        print()
        print("7. Rename:")
        print(result.to_dict())

        # --------------------------------------------------------------
        # Copy
        # --------------------------------------------------------------

        copied_file = (
            root
            / "copied.txt"
        )

        result = controller.copy(
            renamed_file,
            copied_file,
        )

        print()
        print("8. Copy:")
        print(result.to_dict())

        # --------------------------------------------------------------
        # Move
        # --------------------------------------------------------------

        moved_file = (
            root
            / "moved.txt"
        )

        result = controller.move(
            copied_file,
            moved_file,
        )

        print()
        print("9. Move:")
        print(result.to_dict())

        # --------------------------------------------------------------
        # Delete without confirmation
        # --------------------------------------------------------------

        result = controller.delete(
            moved_file,
            confirmed=False,
        )

        print()
        print(
            "10. Delete WITHOUT confirmation:"
        )
        print(result.to_dict())

        # --------------------------------------------------------------
        # Delete with confirmation
        # --------------------------------------------------------------

        result = controller.delete(
            moved_file,
            confirmed=True,
            permanent=False,
        )

        print()
        print(
            "11. Delete WITH confirmation:"
        )
        print(result.to_dict())

        # --------------------------------------------------------------
        # Protected path
        # --------------------------------------------------------------

        protected_path = (
            Path(
                os.environ.get(
                    "WINDIR",
                    "C:/Windows",
                )
            )
        )

        protected, reason = (
            controller.is_protected_path(
                protected_path
            )
        )

        print()
        print(
            "12. Protected path test:"
        )
        print(
            {
                "path": str(
                    protected_path
                ),
                "protected": protected,
                "reason": reason,
            }
        )

        # --------------------------------------------------------------
        # Status
        # --------------------------------------------------------------

        print()
        print(
            "13. Controller status:"
        )
        print(
            controller.get_status()
        )

    controller.close()

    print()
    print("=" * 70)
    print("FILE CONTROL TEST COMPLETE")
    print("=" * 70)
