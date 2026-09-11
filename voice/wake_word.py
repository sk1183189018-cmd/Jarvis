"""
JarvisOS - Wake Word Detection

Detects the JarvisOS wake word using Picovoice Porcupine.

Default wake word:
    "Jarvis"

Environment variable:
    PICOVOICE_ACCESS_KEY

Optional environment variables:
    JARVIS_WAKEWORD_KEYWORD
    JARVIS_WAKEWORD_SENSITIVITY
    JARVIS_WAKEWORD_ENABLED

The detector is designed to work with the existing JarvisOS
main.py interface:

    detector = WakeWordDetector()

    if detector.wait_for_wake_word():
        ...

    detector.stop()
"""

from __future__ import annotations

import logging
import os
import struct
import threading
import time
from typing import List, Optional

logger = logging.getLogger(__name__)


# ======================================================================
# WAKE WORD DETECTOR
# ======================================================================


class WakeWordDetector:
    """
    JarvisOS wake-word detector.

    Uses Picovoice Porcupine for local wake-word detection.

    The microphone audio is processed locally by Porcupine.
    """

    DEFAULT_KEYWORD = "jarvis"
    DEFAULT_SENSITIVITY = 0.55

    def __init__(
        self,
        access_key: Optional[str] = None,
        keyword: Optional[str] = None,
        sensitivity: Optional[float] = None,
        enabled: Optional[bool] = None,
        device_index: Optional[int] = None,
    ) -> None:
        """
        Initialize the wake-word detector.

        Args:
            access_key:
                Picovoice access key.

            keyword:
                Wake word keyword.

            sensitivity:
                Detection sensitivity from 0.0 to 1.0.

            enabled:
                Enable/disable wake-word detection.

            device_index:
                Optional microphone device index.
        """

        self.access_key = (
            access_key
            or os.getenv(
                "PICOVOICE_ACCESS_KEY",
                "",
            ).strip()
        )

        self.keyword = (
            keyword
            or os.getenv(
                "JARVIS_WAKEWORD_KEYWORD",
                self.DEFAULT_KEYWORD,
            )
        ).strip().lower()

        self.sensitivity = self._normalize_sensitivity(
            sensitivity
            if sensitivity is not None
            else self._read_float_env(
                "JARVIS_WAKEWORD_SENSITIVITY",
                self.DEFAULT_SENSITIVITY,
            )
        )

        self.enabled = (
            enabled
            if enabled is not None
            else self._read_bool_env(
                "JARVIS_WAKEWORD_ENABLED",
                True,
            )
        )

        self.device_index = device_index

        self.porcupine = None
        self.audio = None
        self.stream = None

        self._initialized = False
        self._running = False
        self._stop_event = threading.Event()

        self._lock = threading.RLock()

        self.last_error: Optional[str] = None
        self.last_detection_time: Optional[float] = None
        self.detection_count = 0

        self._initialize()

    # ==================================================================
    # ENVIRONMENT HELPERS
    # ==================================================================

    @staticmethod
    def _read_bool_env(
        name: str,
        default: bool,
    ) -> bool:
        """
        Read a boolean environment variable.
        """

        value = os.getenv(name)

        if value is None:
            return default

        value = value.strip().lower()

        if value in {
            "1",
            "true",
            "yes",
            "on",
            "enabled",
        }:
            return True

        if value in {
            "0",
            "false",
            "no",
            "off",
            "disabled",
        }:
            return False

        return default

    @staticmethod
    def _read_float_env(
        name: str,
        default: float,
    ) -> float:
        """
        Read a floating-point environment variable.
        """

        value = os.getenv(name)

        if value is None:
            return default

        try:
            return float(value)
        except ValueError:
            return default

    @staticmethod
    def _normalize_sensitivity(
        sensitivity: float,
    ) -> float:
        """
        Keep sensitivity inside the valid range.
        """

        try:
            value = float(sensitivity)
        except (TypeError, ValueError):
            value = WakeWordDetector.DEFAULT_SENSITIVITY

        return max(
            0.0,
            min(
                1.0,
                value,
            ),
        )

    # ==================================================================
    # INITIALIZATION
    # ==================================================================

    def _initialize(self) -> None:
        """
        Initialize Porcupine and microphone/audio stream.
        """

        if not self.enabled:
            logger.info(
                "Wake-word detection is disabled."
            )
            return

        if not self.access_key:
            self.last_error = (
                "PICOVOICE_ACCESS_KEY is not configured."
            )

            logger.warning(
                "%s",
                self.last_error,
            )

            return

        try:
            import pvporcupine

            self.porcupine = (
                pvporcupine.create(
                    access_key=self.access_key,
                    keywords=[self.keyword],
                    sensitivities=[self.sensitivity],
                )
            )

            self._initialized = True
            self.last_error = None

            logger.info(
                "Wake-word detector initialized. "
                "Keyword=%s Sensitivity=%.2f",
                self.keyword,
                self.sensitivity,
            )

        except ImportError:
            self.last_error = (
                "pvporcupine is not installed. "
                "Install it with: pip install pvporcupine"
            )

            logger.warning(
                "%s",
                self.last_error,
            )

        except Exception as exc:
            self.last_error = str(exc)

            logger.exception(
                "Failed to initialize wake-word detector: %s",
                exc,
            )

    # ==================================================================
    # AVAILABILITY
    # ==================================================================

    def is_available(self) -> bool:
        """
        Return True if wake-word detection is ready.
        """

        return bool(
            self.enabled
            and self._initialized
            and self.porcupine is not None
        )

    # ==================================================================
    # MICROPHONE INITIALIZATION
    # ==================================================================

    def _initialize_audio(self) -> bool:
        """
        Create the microphone audio stream.

        Porcupine requires:
            - sample rate matching Porcupine
            - frame length matching Porcupine
            - 16-bit PCM audio
        """

        if not self.is_available():
            return False

        if self.stream is not None:
            return True

        try:
            import pyaudio

            self.audio = pyaudio.PyAudio()

            self.stream = self.audio.open(
                rate=self.porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=(
                    self.porcupine.frame_length
                ),
                input_device_index=self.device_index,
            )

            logger.info(
                "Wake-word microphone stream initialized."
            )

            return True

        except ImportError:
            self.last_error = (
                "PyAudio is not installed. "
                "Install it with: pip install PyAudio"
            )

            logger.warning(
                "%s",
                self.last_error,
            )

            return False

        except Exception as exc:
            self.last_error = str(exc)

            logger.exception(
                "Unable to initialize wake-word microphone: %s",
                exc,
            )

            self._close_audio()

            return False

    # ==================================================================
    # DEVICE MANAGEMENT
    # ==================================================================

    def list_microphones(self) -> List[str]:
        """
        Return available audio input devices.
        """

        try:
            import pyaudio

            audio = pyaudio.PyAudio()
            devices: List[str] = []

            try:
                for index in range(
                    audio.get_device_count()
                ):
                    info = audio.get_device_info_by_index(
                        index
                    )

                    if (
                        info.get(
                            "maxInputChannels",
                            0,
                        )
                        > 0
                    ):
                        name = str(
                            info.get(
                                "name",
                                f"Device {index}",
                            )
                        )

                        devices.append(
                            f"{index}: {name}"
                        )

            finally:
                audio.terminate()

            return devices

        except Exception as exc:
            logger.exception(
                "Unable to list microphones: %s",
                exc,
            )

            return []

    def set_microphone(
        self,
        device_index: Optional[int],
    ) -> bool:
        """
        Change the microphone device.

        The stream is recreated on the next detection run.
        """

        with self._lock:
            self.device_index = device_index
            self._close_audio()

        logger.info(
            "Wake-word microphone changed to device=%s",
            device_index,
        )

        return True

    # ==================================================================
    # DETECTION
    # ==================================================================

    def detect_once(
        self,
        timeout: Optional[float] = None,
    ) -> bool:
        """
        Listen for the wake word once.

        Args:
            timeout:
                Maximum seconds to listen.
                None means continue until detected or stopped.

        Returns:
            True if the wake word was detected.
            False on timeout, stop, or failure.
        """

        if not self.enabled:
            return False

        if not self.is_available():
            return False

        if not self._initialize_audio():
            return False

        start_time = time.monotonic()

        try:
            while not self._stop_event.is_set():

                if (
                    timeout is not None
                    and (
                        time.monotonic()
                        - start_time
                    )
                    >= timeout
                ):
                    return False

                frame = self.stream.read(
                    self.porcupine.frame_length,
                    exception_on_overflow=False,
                )

                pcm = struct.unpack_from(
                    "h" * self.porcupine.frame_length,
                    frame,
                )

                keyword_index = (
                    self.porcupine.process(pcm)
                )

                if keyword_index >= 0:
                    self._register_detection()

                    logger.info(
                        "Wake word detected: %s",
                        self.keyword,
                    )

                    return True

        except Exception as exc:
            self.last_error = str(exc)

            logger.exception(
                "Wake-word detection failed: %s",
                exc,
            )

            return False

        return False

    # ==================================================================
    # WAIT FOR WAKE WORD
    # ==================================================================

    def wait_for_wake_word(
        self,
        timeout: Optional[float] = None,
    ) -> bool:
        """
        Wait until the Jarvis wake word is detected.

        This is the main method intended for main.py.
        """

        if not self.enabled:
            logger.debug(
                "Wake-word detection disabled."
            )
            return False

        self._stop_event.clear()

        with self._lock:
            self._running = True

        try:
            return self.detect_once(
                timeout=timeout
            )

        finally:
            with self._lock:
                self._running = False

    # ==================================================================
    # CONTINUOUS MODE
    # ==================================================================

    def listen_continuously(
        self,
        callback=None,
        stop_event: Optional[threading.Event] = None,
    ) -> None:
        """
        Continuously monitor for the wake word.

        Args:
            callback:
                Optional function called after detection.

                callback() is called when the wake word is detected.

            stop_event:
                Optional external threading.Event.
        """

        if not self.is_available():
            logger.warning(
                "Continuous wake-word detection unavailable."
            )
            return

        self._stop_event.clear()

        with self._lock:
            self._running = True

        try:
            if not self._initialize_audio():
                return

            while not self._stop_event.is_set():

                if (
                    stop_event is not None
                    and stop_event.is_set()
                ):
                    break

                detected = self.detect_once(
                    timeout=1.0
                )

                if detected:
                    if callback is not None:
                        try:
                            callback()

                        except Exception:
                            logger.exception(
                                "Wake-word callback failed."
                            )

        finally:
            with self._lock:
                self._running = False

    # ==================================================================
    # DETECTION STATE
    # ==================================================================

    def _register_detection(self) -> None:
        """
        Record a successful wake-word detection.
        """

        self.last_detection_time = time.time()
        self.detection_count += 1

    def get_detection_count(self) -> int:
        """
        Return total wake-word detections.
        """

        return self.detection_count

    # ==================================================================
    # STOP
    # ==================================================================

    def stop(self) -> None:
        """
        Stop wake-word detection and close audio resources.
        """

        self._stop_event.set()

        with self._lock:
            self._running = False

        self._close_audio()

        logger.info(
            "Wake-word detector stopped."
        )

    def is_running(self) -> bool:
        """
        Return True if detector is currently running.
        """

        with self._lock:
            return self._running

    # ==================================================================
    # ENABLE / DISABLE
    # ==================================================================

    def enable(self) -> bool:
        """
        Enable wake-word detection.

        Does not recreate Porcupine if it was not initialized because
        the access key was missing.
        """

        self.enabled = True

        if self.is_available():
            return True

        self._initialize()

        return self.is_available()

    def disable(self) -> None:
        """
        Disable wake-word detection.
        """

        self.enabled = False
        self.stop()

        logger.info(
            "Wake-word detection disabled."
        )

    # ==================================================================
    # SENSITIVITY
    # ==================================================================

    def set_sensitivity(
        self,
        sensitivity: float,
    ) -> bool:
        """
        Change detection sensitivity.

        Porcupine configuration is created during initialization, so
        the detector is recreated after changing sensitivity.
        """

        self.sensitivity = (
            self._normalize_sensitivity(
                sensitivity
            )
        )

        if not self.enabled:
            return True

        self.stop()

        if self.porcupine is not None:
            try:
                self.porcupine.delete()
            except Exception:
                pass

        self.porcupine = None
        self._initialized = False

        self._initialize()

        return self.is_available()

    # ==================================================================
    # AUDIO CLEANUP
    # ==================================================================

    def _close_audio(self) -> None:
        """
        Close microphone stream and PyAudio.
        """

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

    # ==================================================================
    # RESOURCE CLEANUP
    # ==================================================================

    def close(self) -> None:
        """
        Completely release Porcupine and microphone resources.
        """

        self.stop()

        if self.porcupine is not None:
            try:
                self.porcupine.delete()
            except Exception:
                pass

            self.porcupine = None

        self._initialized = False

        logger.info(
            "Wake-word detector resources released."
        )

    # ==================================================================
    # STATUS
    # ==================================================================

    def get_status(self) -> dict:
        """
        Return safe detector status.

        API keys are never returned.
        """

        return {
            "enabled": self.enabled,
            "available": self.is_available(),
            "initialized": self._initialized,
            "running": self.is_running(),
            "keyword": self.keyword,
            "sensitivity": self.sensitivity,
            "microphone_device": self.device_index,
            "detection_count": self.detection_count,
            "last_detection_time": (
                self.last_detection_time
            ),
            "last_error": self.last_error,
            "access_key_configured": bool(
                self.access_key
            ),
        }

    # ==================================================================
    # CONTEXT MANAGER
    # ==================================================================

    def __enter__(self) -> "WakeWordDetector":
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

    print("\n" + "=" * 65)
    print("JARVIS OS - WAKE WORD TEST")
    print("=" * 65)

    detector = WakeWordDetector()

    status = detector.get_status()

    print(
        f"Enabled: {status['enabled']}"
    )

    print(
        f"Available: {status['available']}"
    )

    print(
        f"Keyword: {status['keyword']}"
    )

    print(
        f"Sensitivity: {status['sensitivity']}"
    )

    print(
        f"Access key configured: "
        f"{status['access_key_configured']}"
    )

    if not detector.is_available():
        print(
            "\nWake-word detector is not available."
        )

        if detector.last_error:
            print(
                f"Error: {detector.last_error}"
            )

        print(
            "\nSet PICOVOICE_ACCESS_KEY in .env "
            "and make sure pvporcupine and PyAudio "
            "are installed."
        )

        detector.close()
        raise SystemExit(1)

    print(
        "\nSpeak the wake word..."
    )

    detected = detector.wait_for_wake_word(
        timeout=30
    )

    if detected:
        print(
            f"Wake word detected: "
            f"{detector.keyword}"
        )
    else:
        print(
            "Wake word was not detected."
        )

    detector.close()
