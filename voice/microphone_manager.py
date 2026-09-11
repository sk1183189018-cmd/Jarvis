"""
JarvisOS - Microphone Manager

Central microphone management for:
- Speech-to-Text
- Wake Word Detection
- Voice interaction
- Microphone privacy control

This module does not perform speech recognition itself.
It only manages microphone devices and audio input streams.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MicrophoneDevice:
    """Information about an available microphone."""

    index: int
    name: str
    sample_rate: int
    channels: int
    is_default: bool = False


class MicrophoneManager:
    """
    Central microphone manager for JarvisOS.

    Example:

        mic = MicrophoneManager()

        devices = mic.list_devices()

        mic.start()

        print(mic.is_active())

        mic.stop()
    """

    def __init__(
        self,
        device_index: Optional[int] = None,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 1024,
    ) -> None:

        self.device_index = device_index
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size

        self.audio = None
        self.stream = None

        self._active = False
        self._lock = threading.RLock()

        self.last_error: Optional[str] = None

        self._initialize_backend()

    # ================================================================
    # BACKEND
    # ================================================================

    def _initialize_backend(self) -> None:
        """Check whether PyAudio is available."""

        try:
            import pyaudio

            self.audio_module = pyaudio

            logger.info(
                "Microphone backend initialized."
            )

        except ImportError:

            self.audio_module = None

            self.last_error = (
                "PyAudio is not installed."
            )

            logger.warning(
                self.last_error
            )

    # ================================================================
    # AVAILABILITY
    # ================================================================

    def is_available(self) -> bool:
        """Return True when microphone backend is available."""

        return self.audio_module is not None

    # ================================================================
    # DEVICE LIST
    # ================================================================

    def list_devices(self) -> List[MicrophoneDevice]:
        """
        Return all available microphone/input devices.
        """

        if not self.is_available():
            return []

        audio = None
        devices: List[MicrophoneDevice] = []

        try:

            audio = self.audio_module.PyAudio()

            default_index = None

            try:
                default_info = (
                    audio.get_default_input_device_info()
                )

                default_index = int(
                    default_info["index"]
                )

            except Exception:
                pass

            for index in range(
                audio.get_device_count()
            ):

                try:

                    info = (
                        audio.get_device_info_by_index(
                            index
                        )
                    )

                    input_channels = int(
                        info.get(
                            "maxInputChannels",
                            0,
                        )
                    )

                    if input_channels <= 0:
                        continue

                    name = str(
                        info.get(
                            "name",
                            f"Microphone {index}",
                        )
                    )

                    sample_rate = int(
                        info.get(
                            "defaultSampleRate",
                            self.sample_rate,
                        )
                    )

                    devices.append(
                        MicrophoneDevice(
                            index=index,
                            name=name,
                            sample_rate=sample_rate,
                            channels=input_channels,
                            is_default=(
                                index == default_index
                            ),
                        )
                    )

                except Exception as exc:

                    logger.debug(
                        "Skipping audio device %s: %s",
                        index,
                        exc,
                    )

            return devices

        except Exception as exc:

            self.last_error = str(exc)

            logger.exception(
                "Unable to list microphones."
            )

            return []

        finally:

            if audio is not None:

                try:
                    audio.terminate()
                except Exception:
                    pass

    # ================================================================
    # SIMPLE DEVICE NAMES
    # ================================================================

    def get_device_names(self) -> List[str]:
        """Return microphone names only."""

        return [
            device.name
            for device in self.list_devices()
        ]

    # ================================================================
    # DEFAULT DEVICE
    # ================================================================

    def get_default_device(
        self,
    ) -> Optional[MicrophoneDevice]:
        """Return the Windows default input device."""

        if not self.is_available():
            return None

        audio = None

        try:

            audio = self.audio_module.PyAudio()

            info = (
                audio.get_default_input_device_info()
            )

            return MicrophoneDevice(
                index=int(info["index"]),
                name=str(info["name"]),
                sample_rate=int(
                    info.get(
                        "defaultSampleRate",
                        self.sample_rate,
                    )
                ),
                channels=int(
                    info.get(
                        "maxInputChannels",
                        1,
                    )
                ),
                is_default=True,
            )

        except Exception as exc:

            self.last_error = str(exc)

            logger.warning(
                "Unable to get default microphone: %s",
                exc,
            )

            return None

        finally:

            if audio is not None:

                try:
                    audio.terminate()
                except Exception:
                    pass

    # ================================================================
    # SET DEVICE
    # ================================================================

    def set_device(
        self,
        device_index: Optional[int],
    ) -> bool:
        """
        Select a microphone.

        The currently running stream is stopped first.
        """

        with self._lock:

            if self._active:
                self.stop()

            if device_index is not None:

                try:
                    device_index = int(
                        device_index
                    )
                except (
                    TypeError,
                    ValueError,
                ):

                    self.last_error = (
                        "Invalid microphone device index."
                    )

                    return False

            self.device_index = device_index

            logger.info(
                "Microphone device set to: %s",
                device_index,
            )

            return True

    # ================================================================
    # FIND DEVICE BY NAME
    # ================================================================

    def find_device(
        self,
        name: str,
    ) -> Optional[MicrophoneDevice]:
        """
        Find a microphone by partial name.
        """

        if not name:
            return None

        search = name.lower().strip()

        for device in self.list_devices():

            if search in device.name.lower():
                return device

        return None

    # ================================================================
    # START
    # ================================================================

    def start(self) -> bool:
        """
        Start microphone input stream.
        """

        with self._lock:

            if self._active:
                return True

            if not self.is_available():

                self.last_error = (
                    "Microphone backend is unavailable."
                )

                return False

            try:

                self.audio = (
                    self.audio_module.PyAudio()
                )

                kwargs = {
                    "format": self.audio_module.paInt16,
                    "channels": self.channels,
                    "rate": self.sample_rate,
                    "input": True,
                    "frames_per_buffer": self.chunk_size,
                }

                if self.device_index is not None:

                    kwargs[
                        "input_device_index"
                    ] = self.device_index

                self.stream = self.audio.open(
                    **kwargs
                )

                self._active = True
                self.last_error = None

                logger.info(
                    "Microphone started. Device=%s",
                    self.device_index,
                )

                return True

            except Exception as exc:

                self.last_error = str(exc)

                logger.exception(
                    "Unable to start microphone."
                )

                self._cleanup_stream()

                return False

    # ================================================================
    # READ AUDIO
    # ================================================================

    def read(
        self,
        frames: Optional[int] = None,
    ) -> Optional[bytes]:
        """
        Read raw PCM audio from microphone.

        Returns:
            bytes containing 16-bit PCM audio.
        """

        with self._lock:

            if not self._active:
                if not self.start():
                    return None

            if self.stream is None:
                return None

            amount = (
                frames
                if frames is not None
                else self.chunk_size
            )

            try:

                return self.stream.read(
                    amount,
                    exception_on_overflow=False,
                )

            except Exception as exc:

                self.last_error = str(exc)

                logger.error(
                    "Microphone read error: %s",
                    exc,
                )

                return None

    # ================================================================
    # TEST MICROPHONE
    # ================================================================

    def test(
        self,
        duration: float = 2.0,
    ) -> bool:
        """
        Test whether microphone can capture audio.

        The captured audio is not saved.
        """

        import time

        if duration <= 0:
            duration = 1.0

        if not self.start():
            return False

        started = time.monotonic()

        try:

            while (
                time.monotonic() - started
                < duration
            ):

                data = self.read()

                if data:
                    return True

            return False

        finally:

            self.stop()

    # ================================================================
    # ACTIVE STATUS
    # ================================================================

    def is_active(self) -> bool:
        """Return True when microphone stream is active."""

        with self._lock:
            return self._active

    # ================================================================
    # STOP
    # ================================================================

    def stop(self) -> None:
        """Stop microphone stream."""

        with self._lock:

            self._active = False

            self._cleanup_stream()

            logger.info(
                "Microphone stopped."
            )

    # ================================================================
    # CLEANUP
    # ================================================================

    def _cleanup_stream(self) -> None:
        """Close stream and PyAudio safely."""

        if self.stream is not None:

            try:

                if self.stream.is_active():
                    self.stream.stop_stream()

            except Exception:
                pass

            try:
                self.stream.close()
            except Exception:
                pass

            self.stream = None

        if self.audio is not None:

            try:
                self.audio.terminate()
            except Exception:
                pass

            self.audio = None

    # ================================================================
    # PRIVACY
    # ================================================================

    def mute(self) -> None:
        """
        Stop microphone capture.

        JarvisOS can use this for the microphone privacy button.
        """

        self.stop()

        logger.info(
            "Microphone muted."
        )

    def unmute(self) -> bool:
        """
        Resume microphone capture.
        """

        result = self.start()

        if result:

            logger.info(
                "Microphone unmuted."
            )

        return result

    # ================================================================
    # STATUS
    # ================================================================

    def get_status(self) -> dict:
        """
        Return microphone manager status.
        """

        default_device = (
            self.get_default_device()
        )

        return {
            "available": self.is_available(),
            "active": self.is_active(),
            "selected_device": self.device_index,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "chunk_size": self.chunk_size,
            "default_device": (
                default_device.name
                if default_device
                else None
            ),
            "last_error": self.last_error,
        }

    # ================================================================
    # CLOSE
    # ================================================================

    def close(self) -> None:
        """Release all microphone resources."""

        self.stop()

        logger.info(
            "Microphone manager closed."
        )

    # ================================================================
    # CONTEXT MANAGER
    # ================================================================

    def __enter__(
        self,
    ) -> "MicrophoneManager":

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:

        self.close()


# ======================================================================
# DIRECT TEST
# ======================================================================

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

    print()
    print("=" * 65)
    print("JARVIS OS - MICROPHONE MANAGER TEST")
    print("=" * 65)

    manager = MicrophoneManager()

    print(
        "\nBackend available:",
        manager.is_available(),
    )

    print("\nAvailable microphones:")

    devices = manager.list_devices()

    if not devices:

        print("No microphone found.")

    else:

        for device in devices:

            default_text = (
                " [DEFAULT]"
                if device.is_default
                else ""
            )

            print(
                f"  [{device.index}] "
                f"{device.name}"
                f"{default_text}"
            )

            print(
                f"      Sample rate: "
                f"{device.sample_rate}"
            )

            print(
                f"      Channels: "
                f"{device.channels}"
            )

    default = manager.get_default_device()

    if default:

        print(
            "\nDefault microphone:",
            default.name,
        )

    print(
        "\nStatus:"
    )

    for key, value in manager.get_status().items():

        print(
            f"  {key}: {value}"
        )

    manager.close()

    print(
        "\nMicrophone manager test finished."
      )
