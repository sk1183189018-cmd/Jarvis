"""
JarvisOS - Speech To Text

Converts microphone speech into text.

Primary engine:
    SpeechRecognition

Features:
    - Microphone input
    - Hindi / English support
    - Ambient noise adjustment
    - Configurable timeout
    - Configurable phrase limit
    - Retry handling
    - Background-noise tolerance
    - Safe error handling
    - Text normalization
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ======================================================================
# RESULT
# ======================================================================


@dataclass
class SpeechResult:
    """
    Result returned by the speech recognition system.
    """

    success: bool
    text: str = ""
    language: str = ""
    error: Optional[str] = None
    duration: float = 0.0


# ======================================================================
# SPEECH TO TEXT
# ======================================================================


class SpeechToText:
    """
    JarvisOS speech-to-text engine.

    Uses the SpeechRecognition package with Google's speech
    recognition service by default.

    The class is intentionally independent from the rest of
    JarvisOS so that another STT engine can be added later.
    """

    DEFAULT_LANGUAGE = "en-IN"

    SUPPORTED_LANGUAGES = {
        "en": "en-IN",
        "english": "en-IN",
        "hi": "hi-IN",
        "hindi": "hi-IN",
        "hinglish": "hi-IN",
        "auto": "en-IN",
    }

    def __init__(
        self,
        language: Optional[str] = None,
        timeout: float = 5.0,
        phrase_time_limit: float = 15.0,
        energy_threshold: int = 300,
        dynamic_energy_threshold: bool = True,
        pause_threshold: float = 0.8,
        non_speaking_duration: float = 0.5,
    ) -> None:
        """
        Initialize speech recognition.

        Args:
            language:
                Language code or friendly name.

            timeout:
                Maximum seconds to wait for speech to start.

            phrase_time_limit:
                Maximum duration of one spoken phrase.

            energy_threshold:
                Minimum microphone energy required to detect speech.

            dynamic_energy_threshold:
                Automatically adjust microphone sensitivity.

            pause_threshold:
                Seconds of silence that indicate the phrase has ended.

            non_speaking_duration:
                Amount of non-speaking audio kept around speech.
        """

        self.language = self._normalize_language(
            language
            or os.getenv(
                "JARVIS_STT_LANGUAGE",
                self.DEFAULT_LANGUAGE,
            )
        )

        self.timeout = max(
            0.1,
            float(timeout),
        )

        self.phrase_time_limit = max(
            0.5,
            float(phrase_time_limit),
        )

        self.energy_threshold = max(
            0,
            int(energy_threshold),
        )

        self.dynamic_energy_threshold = bool(
            dynamic_energy_threshold
        )

        self.pause_threshold = max(
            0.1,
            float(pause_threshold),
        )

        self.non_speaking_duration = max(
            0.0,
            float(non_speaking_duration),
        )

        self.recognizer = None
        self.microphone = None

        self._initialized = False
        self.last_error: Optional[str] = None
        self.last_text: str = ""

        self._initialize()

    # ==================================================================
    # INITIALIZATION
    # ==================================================================

    def _initialize(self) -> None:
        """
        Initialize SpeechRecognition and microphone.
        """

        try:
            import speech_recognition as sr

            self.recognizer = sr.Recognizer()

            self.recognizer.energy_threshold = (
                self.energy_threshold
            )

            self.recognizer.dynamic_energy_threshold = (
                self.dynamic_energy_threshold
            )

            self.recognizer.pause_threshold = (
                self.pause_threshold
            )

            self.recognizer.non_speaking_duration = (
                self.non_speaking_duration
            )

            self.microphone = sr.Microphone()

            self._initialized = True
            self.last_error = None

            logger.info(
                "Speech-to-text initialized. Language=%s",
                self.language,
            )

        except ImportError:
            self.last_error = (
                "SpeechRecognition is not installed. "
                "Install it with: pip install SpeechRecognition"
            )

            logger.warning(
                self.last_error
            )

        except Exception as exc:
            self.last_error = str(exc)

            logger.exception(
                "Failed to initialize speech-to-text: %s",
                exc,
            )

    # ==================================================================
    # LANGUAGE
    # ==================================================================

    @classmethod
    def _normalize_language(
        cls,
        language: str,
    ) -> str:
        """
        Convert friendly language names into speech-recognition
        language codes.
        """

        value = (
            str(language)
            .strip()
            .lower()
        )

        if not value:
            return cls.DEFAULT_LANGUAGE

        return cls.SUPPORTED_LANGUAGES.get(
            value,
            value,
        )

    def set_language(
        self,
        language: str,
    ) -> None:
        """
        Change speech recognition language.
        """

        self.language = self._normalize_language(
            language
        )

        logger.info(
            "Speech recognition language changed to %s",
            self.language,
        )

    def get_language(self) -> str:
        """
        Return current speech language.
        """

        return self.language

    # ==================================================================
    # AVAILABILITY
    # ==================================================================

    def is_available(self) -> bool:
        """
        Return True when microphone and recognizer are ready.
        """

        return bool(
            self._initialized
            and self.recognizer is not None
            and self.microphone is not None
        )

    # ==================================================================
    # MICROPHONE
    # ==================================================================

    def list_microphones(self) -> list[str]:
        """
        Return available microphone names.

        Useful for debugging or future microphone selection UI.
        """

        if not self._initialized:
            return []

        try:
            import speech_recognition as sr

            return list(
                sr.Microphone.list_microphone_names()
            )

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
        Select a microphone by device index.

        Args:
            device_index:
                Microphone device index.
                None selects the default microphone.

        Returns:
            True when microphone was successfully selected.
        """

        if not self._initialized:
            return False

        try:
            import speech_recognition as sr

            self.microphone = sr.Microphone(
                device_index=device_index
            )

            logger.info(
                "Microphone changed. device_index=%s",
                device_index,
            )

            return True

        except Exception as exc:
            self.last_error = str(exc)

            logger.exception(
                "Failed to select microphone: %s",
                exc,
            )

            return False

    # ==================================================================
    # CALIBRATION
    # ==================================================================

    def calibrate(
        self,
        duration: float = 1.0,
    ) -> bool:
        """
        Calibrate microphone for ambient noise.

        Args:
            duration:
                Seconds used for ambient noise measurement.

        Returns:
            True on success.
        """

        if not self.is_available():
            self.last_error = (
                "Speech-to-text is not available."
            )

            return False

        duration = max(
            0.1,
            float(duration),
        )

        try:
            with self.microphone as source:
                logger.info(
                    "Calibrating microphone for %.1f seconds...",
                    duration,
                )

                self.recognizer.adjust_for_ambient_noise(
                    source,
                    duration=duration,
                )

            logger.info(
                "Microphone calibration complete. "
                "Energy threshold=%s",
                self.recognizer.energy_threshold,
            )

            self.last_error = None

            return True

        except Exception as exc:
            self.last_error = str(exc)

            logger.exception(
                "Microphone calibration failed: %s",
                exc,
            )

            return False

    # ==================================================================
    # LISTEN
    # ==================================================================

    def listen(
        self,
        timeout: Optional[float] = None,
        phrase_time_limit: Optional[float] = None,
        adjust_for_noise: bool = False,
        noise_duration: float = 0.5,
    ):
        """
        Listen to microphone and return raw audio.

        Returns:
            SpeechRecognition AudioData object.

        Raises:
            RuntimeError:
                If speech-to-text is unavailable.

            TimeoutError:
                If speech does not start within timeout.

            RuntimeError:
                If microphone/audio capture fails.
        """

        if not self.is_available():
            raise RuntimeError(
                self.last_error
                or "Speech-to-text is not available."
            )

        timeout_value = (
            self.timeout
            if timeout is None
            else max(0.1, float(timeout))
        )

        phrase_limit = (
            self.phrase_time_limit
            if phrase_time_limit is None
            else max(0.5, float(phrase_time_limit))
        )

        try:
            import speech_recognition as sr

            with self.microphone as source:

                if adjust_for_noise:
                    self.recognizer.adjust_for_ambient_noise(
                        source,
                        duration=max(
                            0.1,
                            float(noise_duration),
                        ),
                    )

                logger.debug(
                    "Listening for speech..."
                )

                try:
                    audio = self.recognizer.listen(
                        source,
                        timeout=timeout_value,
                        phrase_time_limit=phrase_limit,
                    )

                except sr.WaitTimeoutError as exc:
                    raise TimeoutError(
                        "No speech detected within "
                        f"{timeout_value:.1f} seconds."
                    ) from exc

            return audio

        except TimeoutError:
            raise

        except Exception as exc:
            self.last_error = str(exc)

            logger.exception(
                "Microphone listening failed: %s",
                exc,
            )

            raise RuntimeError(
                f"Microphone listening failed: {exc}"
            ) from exc

    # ==================================================================
    # RECOGNIZE
    # ==================================================================

    def recognize_audio(
        self,
        audio,
        language: Optional[str] = None,
    ) -> SpeechResult:
        """
        Convert recorded audio into text.
        """

        if not self.is_available():
            return SpeechResult(
                success=False,
                error=(
                    self.last_error
                    or "Speech-to-text is not available."
                ),
            )

        selected_language = (
            self._normalize_language(language)
            if language
            else self.language
        )

        start_time = time.perf_counter()

        try:
            text = self.recognizer.recognize_google(
                audio,
                language=selected_language,
            )

            text = self.normalize_text(
                text
            )

            duration = (
                time.perf_counter()
                - start_time
            )

            if not text:
                return SpeechResult(
                    success=False,
                    language=selected_language,
                    error="Speech was detected but no text was returned.",
                    duration=duration,
                )

            self.last_text = text
            self.last_error = None

            logger.info(
                "Speech recognized: %s",
                text,
            )

            return SpeechResult(
                success=True,
                text=text,
                language=selected_language,
                duration=duration,
            )

        except Exception as exc:
            duration = (
                time.perf_counter()
                - start_time
            )

            self.last_error = str(exc)

            logger.exception(
                "Speech recognition failed: %s",
                exc,
            )

            return SpeechResult(
                success=False,
                language=selected_language,
                error=str(exc),
                duration=duration,
            )

    # ==================================================================
    # SPEAK -> TEXT
    # ==================================================================

    def listen_and_transcribe(
        self,
        timeout: Optional[float] = None,
        phrase_time_limit: Optional[float] = None,
        language: Optional[str] = None,
        adjust_for_noise: bool = False,
    ) -> SpeechResult:
        """
        Listen to microphone and immediately convert speech to text.
        """

        start_time = time.perf_counter()

        try:
            audio = self.listen(
                timeout=timeout,
                phrase_time_limit=phrase_time_limit,
                adjust_for_noise=adjust_for_noise,
            )

            result = self.recognize_audio(
                audio,
                language=language,
            )

            result.duration = (
                time.perf_counter()
                - start_time
            )

            return result

        except TimeoutError as exc:
            duration = (
                time.perf_counter()
                - start_time
            )

            self.last_error = str(exc)

            return SpeechResult(
                success=False,
                language=(
                    language
                    or self.language
                ),
                error=str(exc),
                duration=duration,
            )

        except Exception as exc:
            duration = (
                time.perf_counter()
                - start_time
            )

            self.last_error = str(exc)

            return SpeechResult(
                success=False,
                language=(
                    language
                    or self.language
                ),
                error=str(exc),
                duration=duration,
            )

    # ==================================================================
    # SIMPLE TEXT API
    # ==================================================================

    def recognize(
        self,
        timeout: Optional[float] = None,
        phrase_time_limit: Optional[float] = None,
        language: Optional[str] = None,
        adjust_for_noise: bool = False,
    ) -> str:
        """
        Simple interface.

        Returns:
            Recognized text, or empty string on failure.
        """

        result = self.listen_and_transcribe(
            timeout=timeout,
            phrase_time_limit=phrase_time_limit,
            language=language,
            adjust_for_noise=adjust_for_noise,
        )

        if result.success:
            return result.text

        logger.debug(
            "Speech recognition returned no text: %s",
            result.error,
        )

        return ""

    # ==================================================================
    # TEXT NORMALIZATION
    # ==================================================================

    @staticmethod
    def normalize_text(
        text: str,
    ) -> str:
        """
        Clean recognized text without changing its meaning.
        """

        if not text:
            return ""

        text = str(text)

        # Normalize whitespace.
        text = " ".join(
            text.split()
        )

        return text.strip()

    # ==================================================================
    # TEST MICROPHONE
    # ==================================================================

    def test_microphone(
        self,
        duration: float = 1.0,
    ) -> SpeechResult:
        """
        Test microphone by listening for a short phrase.
        """

        logger.info(
            "Starting microphone test..."
        )

        return self.listen_and_transcribe(
            timeout=5.0,
            phrase_time_limit=max(
                1.0,
                duration,
            ),
            adjust_for_noise=True,
            noise_duration=0.5,
        )

    # ==================================================================
    # STATUS
    # ==================================================================

    def get_status(self) -> dict:
        """
        Return safe speech-to-text status.
        """

        return {
            "available": self.is_available(),
            "initialized": self._initialized,
            "language": self.language,
            "timeout": self.timeout,
            "phrase_time_limit": (
                self.phrase_time_limit
            ),
            "energy_threshold": (
                self.energy_threshold
            ),
            "dynamic_energy_threshold": (
                self.dynamic_energy_threshold
            ),
            "last_text": self.last_text,
            "last_error": self.last_error,
        }

    # ==================================================================
    # CLEANUP
    # ==================================================================

    def close(self) -> None:
        """
        Release speech-to-text resources.
        """

        self.microphone = None
        self.recognizer = None
        self._initialized = False

        logger.info(
            "Speech-to-text resources released."
        )

    def __enter__(self) -> "SpeechToText":
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

    print("\n" + "=" * 60)
    print("JARVIS OS - SPEECH TO TEXT TEST")
    print("=" * 60)

    stt = SpeechToText(
        language="hinglish"
    )

    status = stt.get_status()

    print(
        f"Available: {status['available']}"
    )

    print(
        f"Language: {status['language']}"
    )

    print(
        f"Timeout: {status['timeout']} sec"
    )

    if not stt.is_available():
        print(
            "\nSpeech-to-text is not available."
        )

        if stt.last_error:
            print(
                f"Error: {stt.last_error}"
            )

        raise SystemExit(1)

    print(
        "\nMicrophone calibration..."
    )

    if stt.calibrate(1.0):
        print(
            "Calibration successful."
        )
    else:
        print(
            "Calibration failed."
        )

    print(
        "\nSpeak something after the prompt..."
    )

    result = stt.test_microphone()

    print("\nResult:")
    print(
        f"Success: {result.success}"
    )
    print(
        f"Text: {result.text}"
    )
    print(
        f"Language: {result.language}"
    )
    print(
        f"Duration: {result.duration:.2f}s"
    )

    if result.error:
        print(
            f"Error: {result.error}"
        )

    stt.close()
