"""
JarvisOS - Text To Speech

Converts text into spoken audio.

Primary engine:
    pyttsx3

Features:
    - Offline Windows TTS
    - Voice selection
    - Speech rate control
    - Volume control
    - Async-friendly background speaking
    - Stop / interrupt support
    - Hindi/English voice discovery
    - Safe error handling
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


# ======================================================================
# DATA CLASS
# ======================================================================


@dataclass
class VoiceInfo:
    """
    Information about an installed system voice.
    """

    id: str
    name: str
    languages: List[str]
    gender: Optional[str] = None


# ======================================================================
# TEXT TO SPEECH
# ======================================================================


class TextToSpeech:
    """
    JarvisOS text-to-speech engine.

    Uses pyttsx3 for local/offline speech synthesis.

    The class keeps the TTS implementation isolated so a cloud or
    neural TTS provider can be added later without changing the rest
    of JarvisOS.
    """

    DEFAULT_RATE = 175
    DEFAULT_VOLUME = 1.0

    MIN_RATE = 80
    MAX_RATE = 350

    MIN_VOLUME = 0.0
    MAX_VOLUME = 1.0

    def __init__(
        self,
        rate: Optional[int] = None,
        volume: Optional[float] = None,
        voice_id: Optional[str] = None,
        auto_initialize: bool = True,
    ) -> None:
        """
        Initialize the TTS engine.

        Args:
            rate:
                Speech speed.

            volume:
                Volume from 0.0 to 1.0.

            voice_id:
                Optional installed system voice ID.

            auto_initialize:
                Initialize pyttsx3 immediately.
        """

        self.rate = self._clamp_rate(
            rate
            if rate is not None
            else int(
                os.getenv(
                    "JARVIS_TTS_RATE",
                    self.DEFAULT_RATE,
                )
            )
        )

        self.volume = self._clamp_volume(
            volume
            if volume is not None
            else float(
                os.getenv(
                    "JARVIS_TTS_VOLUME",
                    self.DEFAULT_VOLUME,
                )
            )
        )

        self.voice_id = (
            voice_id
            or os.getenv("JARVIS_TTS_VOICE")
        )

        self.engine: Any = None

        self._initialized = False
        self._speaking = False
        self._stop_requested = False

        self._lock = threading.RLock()
        self._speech_thread: Optional[
            threading.Thread
        ] = None

        self.last_text: str = ""
        self.last_error: Optional[str] = None

        if auto_initialize:
            self._initialize()

    # ==================================================================
    # INITIALIZATION
    # ==================================================================

    def _initialize(self) -> None:
        """
        Initialize pyttsx3 engine.
        """

        try:
            import pyttsx3

            self.engine = pyttsx3.init()

            self._initialized = True
            self.last_error = None

            self._apply_settings()

            logger.info(
                "Text-to-speech initialized."
            )

        except ImportError:
            self.last_error = (
                "pyttsx3 is not installed. "
                "Install it with: pip install pyttsx3"
            )

            logger.warning(
                self.last_error
            )

        except Exception as exc:
            self.last_error = str(exc)

            logger.exception(
                "Failed to initialize text-to-speech: %s",
                exc,
            )

    # ==================================================================
    # SETTINGS
    # ==================================================================

    @classmethod
    def _clamp_rate(
        cls,
        rate: int,
    ) -> int:
        """
        Keep speech rate inside safe limits.
        """

        return max(
            cls.MIN_RATE,
            min(
                cls.MAX_RATE,
                int(rate),
            ),
        )

    @classmethod
    def _clamp_volume(
        cls,
        volume: float,
    ) -> float:
        """
        Keep volume between 0.0 and 1.0.
        """

        return max(
            cls.MIN_VOLUME,
            min(
                cls.MAX_VOLUME,
                float(volume),
            ),
        )

    def _apply_settings(self) -> None:
        """
        Apply current rate, volume and voice settings.
        """

        if not self.engine:
            return

        self.engine.setProperty(
            "rate",
            self.rate,
        )

        self.engine.setProperty(
            "volume",
            self.volume,
        )

        if self.voice_id:
            try:
                self.engine.setProperty(
                    "voice",
                    self.voice_id,
                )
            except Exception as exc:
                logger.warning(
                    "Unable to set requested voice '%s': %s",
                    self.voice_id,
                    exc,
                )

    # ==================================================================
    # AVAILABILITY
    # ==================================================================

    def is_available(self) -> bool:
        """
        Return True if TTS engine is ready.
        """

        return bool(
            self._initialized
            and self.engine is not None
        )

    # ==================================================================
    # VOICES
    # ==================================================================

    def get_voices(self) -> List[VoiceInfo]:
        """
        Return all voices installed on the system.
        """

        if not self.is_available():
            return []

        try:
            voices = self.engine.getProperty(
                "voices"
            )

            result: List[VoiceInfo] = []

            for voice in voices or []:
                voice_id = str(
                    getattr(
                        voice,
                        "id",
                        "",
                    )
                )

                name = str(
                    getattr(
                        voice,
                        "name",
                        "",
                    )
                )

                languages = self._parse_languages(
                    getattr(
                        voice,
                        "languages",
                        [],
                    )
                )

                gender = getattr(
                    voice,
                    "gender",
                    None,
                )

                if gender:
                    gender = str(
                        gender
                    )

                result.append(
                    VoiceInfo(
                        id=voice_id,
                        name=name,
                        languages=languages,
                        gender=gender,
                    )
                )

            return result

        except Exception as exc:
            self.last_error = str(exc)

            logger.exception(
                "Unable to retrieve system voices: %s",
                exc,
            )

            return []

    @staticmethod
    def _parse_languages(
        languages: Any,
    ) -> List[str]:
        """
        Convert pyttsx3 language metadata into readable strings.
        """

        if languages is None:
            return []

        if isinstance(
            languages,
            (str, bytes),
        ):
            languages = [languages]

        result: List[str] = []

        for language in languages:
            try:
                if isinstance(
                    language,
                    bytes,
                ):
                    value = language.decode(
                        "utf-8",
                        errors="ignore",
                    )
                else:
                    value = str(language)

                value = value.strip()

                if value:
                    result.append(value)

            except Exception:
                continue

        return result

    def find_voice(
        self,
        search: str,
    ) -> Optional[VoiceInfo]:
        """
        Find an installed voice by name or language.
        """

        if not search or not search.strip():
            return None

        query = search.strip().lower()

        voices = self.get_voices()

        # First: exact name match.
        for voice in voices:
            if voice.name.lower() == query:
                return voice

        # Second: partial name/language match.
        for voice in voices:
            searchable = " ".join(
                [
                    voice.name,
                    voice.id,
                    *voice.languages,
                ]
            ).lower()

            if query in searchable:
                return voice

        return None

    def set_voice(
        self,
        voice_id: str,
    ) -> bool:
        """
        Change the active system voice.
        """

        if not self.is_available():
            return False

        if not voice_id or not voice_id.strip():
            return False

        try:
            self.engine.setProperty(
                "voice",
                voice_id.strip(),
            )

            self.voice_id = voice_id.strip()

            logger.info(
                "TTS voice changed to: %s",
                self.voice_id,
            )

            return True

        except Exception as exc:
            self.last_error = str(exc)

            logger.exception(
                "Unable to change TTS voice: %s",
                exc,
            )

            return False

    # ==================================================================
    # RATE
    # ==================================================================

    def set_rate(
        self,
        rate: int,
    ) -> None:
        """
        Change speech rate.
        """

        self.rate = self._clamp_rate(
            rate
        )

        if self.engine:
            self.engine.setProperty(
                "rate",
                self.rate,
            )

    def get_rate(self) -> int:
        """
        Return current speech rate.
        """

        return self.rate

    # ==================================================================
    # VOLUME
    # ==================================================================

    def set_volume(
        self,
        volume: float,
    ) -> None:
        """
        Change speech volume.
        """

        self.volume = self._clamp_volume(
            volume
        )

        if self.engine:
            self.engine.setProperty(
                "volume",
                self.volume,
            )

    def get_volume(self) -> float:
        """
        Return current volume.
        """

        return self.volume

    # ==================================================================
    # SPEAK
    # ==================================================================

    def speak(
        self,
        text: str,
        wait: bool = True,
    ) -> bool:
        """
        Speak text.

        Args:
            text:
                Text to speak.

            wait:
                If True, block until speech finishes.
                If False, speak in a background thread.

        Returns:
            True if speech was started successfully.
        """

        if not text or not str(text).strip():
            return False

        if not self.is_available():
            self.last_error = (
                self.last_error
                or "Text-to-speech is not available."
            )

            logger.warning(
                self.last_error
            )

            return False

        text = self._prepare_text(
            str(text)
        )

        if not text:
            return False

        if wait:
            return self._speak_blocking(
                text
            )

        return self.speak_async(
            text
        )

    def _speak_blocking(
        self,
        text: str,
    ) -> bool:
        """
        Speak synchronously.
        """

        with self._lock:
            self._stop_requested = False
            self._speaking = True
            self.last_text = text

        try:
            self._apply_settings()

            logger.info(
                "Speaking: %s",
                text,
            )

            self.engine.say(
                text
            )

            self.engine.runAndWait()

            self.last_error = None

            return True

        except Exception as exc:
            self.last_error = str(exc)

            logger.exception(
                "Text-to-speech failed: %s",
                exc,
            )

            return False

        finally:
            with self._lock:
                self._speaking = False

    # ==================================================================
    # ASYNC SPEECH
    # ==================================================================

    def speak_async(
        self,
        text: str,
    ) -> bool:
        """
        Speak text in a background thread.

        This prevents the main JarvisOS application from freezing
        while the assistant is speaking.
        """

        if not text or not str(text).strip():
            return False

        if not self.is_available():
            return False

        with self._lock:

            if (
                self._speech_thread is not None
                and self._speech_thread.is_alive()
            ):
                logger.debug(
                    "TTS is already speaking."
                )

                return False

            self._stop_requested = False

            self._speech_thread = (
                threading.Thread(
                    target=self._speak_worker,
                    args=(str(text),),
                    daemon=True,
                    name="JarvisTTS",
                )
            )

            self._speech_thread.start()

        return True

    def _speak_worker(
        self,
        text: str,
    ) -> None:
        """
        Background speech worker.
        """

        self._speak_blocking(
            self._prepare_text(text)
        )

    # ==================================================================
    # STOP
    # ==================================================================

    def stop(self) -> bool:
        """
        Immediately stop current speech.
        """

        if not self.engine:
            return False

        with self._lock:
            self._stop_requested = True

        try:
            self.engine.stop()

            with self._lock:
                self._speaking = False

            logger.info(
                "TTS speech stopped."
            )

            return True

        except Exception as exc:
            self.last_error = str(exc)

            logger.exception(
                "Unable to stop TTS: %s",
                exc,
            )

            return False

    # ==================================================================
    # STATE
    # ==================================================================

    def is_speaking(self) -> bool:
        """
        Return True while TTS is speaking.
        """

        with self._lock:
            return self._speaking

    def wait_until_finished(
        self,
        timeout: Optional[float] = None,
    ) -> bool:
        """
        Wait for asynchronous speech to finish.

        Returns:
            True if thread finished before timeout.
        """

        thread = self._speech_thread

        if thread is None:
            return True

        thread.join(
            timeout=timeout
        )

        return not thread.is_alive()

    # ==================================================================
    # TEXT PREPARATION
    # ==================================================================

    @staticmethod
    def _prepare_text(
        text: str,
    ) -> str:
        """
        Prepare text for natural speech.

        Removes common markdown syntax that should not be spoken
        literally.
        """

        text = str(text).strip()

        if not text:
            return ""

        # Remove code fences.
        text = text.replace(
            "```python",
            "",
        )

        text = text.replace(
            "```",
            "",
        )

        # Remove markdown heading markers.
        lines = []

        for line in text.splitlines():
            line = line.strip()

            if line.startswith("#"):
                line = line.lstrip("#").strip()

            if line:
                lines.append(line)

        text = " ".join(lines)

        # Remove repeated whitespace.
        text = " ".join(
            text.split()
        )

        return text.strip()

    # ==================================================================
    # STATUS
    # ==================================================================

    def get_status(self) -> dict:
        """
        Return safe TTS status.
        """

        return {
            "available": self.is_available(),
            "initialized": self._initialized,
            "rate": self.rate,
            "volume": self.volume,
            "voice_id": self.voice_id,
            "speaking": self.is_speaking(),
            "last_text": self.last_text,
            "last_error": self.last_error,
        }

    # ==================================================================
    # TEST
    # ==================================================================

    def test_voice(
        self,
        text: str = "Hello, I am JarvisOS.",
    ) -> bool:
        """
        Run a simple TTS test.
        """

        return self.speak(
            text,
            wait=True,
        )

    # ==================================================================
    # CLEANUP
    # ==================================================================

    def close(self) -> None:
        """
        Stop speech and release TTS engine.
        """

        self.stop()

        with self._lock:
            self._speech_thread = None

        self.engine = None
        self._initialized = False

        logger.info(
            "Text-to-speech resources released."
        )

    def __enter__(self) -> "TextToSpeech":
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
    print("JARVIS OS - TEXT TO SPEECH TEST")
    print("=" * 60)

    tts = TextToSpeech()

    status = tts.get_status()

    print(
        f"Available: {status['available']}"
    )

    print(
        f"Rate: {status['rate']}"
    )

    print(
        f"Volume: {status['volume']}"
    )

    if not tts.is_available():
        print(
            "\nText-to-speech is not available."
        )

        if tts.last_error:
            print(
                f"Error: {tts.last_error}"
            )

        raise SystemExit(1)

    # Display installed voices.
    voices = tts.get_voices()

    print(
        f"\nInstalled voices: {len(voices)}"
    )

    for index, voice in enumerate(
        voices[:10],
        start=1,
    ):
        print(
            f"{index}. "
            f"{voice.name} | "
            f"{voice.id}"
        )

    print(
        "\nSpeaking test..."
    )

    success = tts.test_voice(
        "Hello. I am JarvisOS. Voice system is working."
    )

    print(
        f"Speech success: {success}"
    )

    tts.close()
