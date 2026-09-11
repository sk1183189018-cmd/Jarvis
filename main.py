"""
JarvisOS - Main Application Entry Point

This file starts JarvisOS and connects the core components:
- AI routing
- Voice input/output
- Command processing
- Memory
- System actions

Python: 3.10+
Operating System: Windows 10/11
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path


# ============================================================
# PROJECT PATH
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


# ============================================================
# ENVIRONMENT
# ============================================================

def load_environment() -> None:
    """
    Load environment variables from .env if python-dotenv
    is installed.

    The application can still start without .env.
    AI providers will report missing API keys when used.
    """
    try:
        from dotenv import load_dotenv

        env_file = BASE_DIR / ".env"

        if env_file.exists():
            load_dotenv(env_file)

    except ImportError:
        # dotenv is optional at this stage.
        pass


# ============================================================
# LOGGING
# ============================================================

def setup_logging() -> logging.Logger:
    """Configure application logging."""

    logs_dir = BASE_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_file = logs_dir / "system.log"

    logger = logging.getLogger("JarvisOS")
    logger.setLevel(logging.INFO)

    # Prevent duplicate handlers if setup_logging() is called again.
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(
        log_file,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# ============================================================
# APPLICATION
# ============================================================

class JarvisOS:
    """
    Main JarvisOS application.

    Components are initialized lazily so that one unavailable
    optional component does not immediately crash the whole app.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger("JarvisOS")

        self.running = False

        self.ai_router = None
        self.command_processor = None
        self.memory_manager = None

        self.speech_to_text = None
        self.text_to_speech = None
        self.wake_word = None
        self.microphone_manager = None

    # --------------------------------------------------------
    # INITIALIZATION
    # --------------------------------------------------------

    def initialize(self) -> None:
        """Initialize JarvisOS core services."""

        self.logger.info("Initializing JarvisOS...")

        self._initialize_memory()
        self._initialize_ai()
        self._initialize_voice()
        self._initialize_brain()

        self.logger.info("JarvisOS initialization completed.")

    # --------------------------------------------------------
    # MEMORY
    # --------------------------------------------------------

    def _initialize_memory(self) -> None:
        """Initialize memory subsystem."""

        try:
            from memory.memory_manager import MemoryManager

            self.memory_manager = MemoryManager(
                base_dir=BASE_DIR
            )

            self.logger.info("Memory system initialized.")

        except Exception as exc:
            self.logger.exception(
                "Memory system could not be initialized: %s",
                exc
            )

    # --------------------------------------------------------
    # AI
    # --------------------------------------------------------

    def _initialize_ai(self) -> None:
        """Initialize AI provider router."""

        try:
            from ai.ai_router import AIRouter

            self.ai_router = AIRouter()

            self.logger.info("AI router initialized.")

        except Exception as exc:
            self.logger.exception(
                "AI router could not be initialized: %s",
                exc
            )

    # --------------------------------------------------------
    # VOICE
    # --------------------------------------------------------

    def _initialize_voice(self) -> None:
        """Initialize voice components."""

        # Speech-to-text
        try:
            from voice.speech_to_text import SpeechToText

            self.speech_to_text = SpeechToText()

            self.logger.info("Speech-to-text initialized.")

        except Exception as exc:
            self.logger.warning(
                "Speech-to-text unavailable: %s",
                exc
            )

        # Text-to-speech
        try:
            from voice.text_to_speech import TextToSpeech

            self.text_to_speech = TextToSpeech()

            self.logger.info("Text-to-speech initialized.")

        except Exception as exc:
            self.logger.warning(
                "Text-to-speech unavailable: %s",
                exc
            )

        # Wake word
        try:
            from voice.wake_word import WakeWordDetector

            self.wake_word = WakeWordDetector()

            self.logger.info("Wake-word system initialized.")

        except Exception as exc:
            self.logger.warning(
                "Wake-word system unavailable: %s",
                exc
            )

        # Microphone
        try:
            from voice.microphone_manager import MicrophoneManager

            self.microphone_manager = MicrophoneManager()

            self.logger.info("Microphone manager initialized.")

        except Exception as exc:
            self.logger.warning(
                "Microphone manager unavailable: %s",
                exc
            )

    # --------------------------------------------------------
    # BRAIN
    # --------------------------------------------------------

    def _initialize_brain(self) -> None:
        """Initialize command processing system."""

        try:
            from brain.command_processor import CommandProcessor

            self.command_processor = CommandProcessor(
                ai_router=self.ai_router,
                memory_manager=self.memory_manager
            )

            self.logger.info("Command processor initialized.")

        except Exception as exc:
            self.logger.exception(
                "Command processor could not be initialized: %s",
                exc
            )

    # --------------------------------------------------------
    # COMMAND
    # --------------------------------------------------------

    def process_text_command(self, command: str) -> str:
        """
        Process a text command.

        This provides a fallback when voice input is unavailable.
        """

        command = command.strip()

        if not command:
            return ""

        if command.lower() in {
            "exit",
            "quit",
            "shutdown jarvis",
            "jarvis shutdown",
        }:
            self.stop()
            return "JarvisOS shutting down."

        if self.command_processor is None:
            return (
                "Command processor is not available. "
                "Please check the application logs."
            )

        try:
            result = self.command_processor.process(command)

            if result is None:
                return "I could not process that command."

            return str(result)

        except Exception as exc:
            self.logger.exception(
                "Command processing failed: %s",
                exc
            )

            return "Sorry, an error occurred while processing your command."

    # --------------------------------------------------------
    # SPEAK
    # --------------------------------------------------------

    def speak(self, text: str) -> None:
        """Speak a response when TTS is available."""

        if not text:
            return

        if self.text_to_speech is None:
            print(f"Jarvis: {text}")
            return

        try:
            self.text_to_speech.speak(text)

        except Exception as exc:
            self.logger.warning(
                "Text-to-speech failed: %s",
                exc
            )

            print(f"Jarvis: {text}")

    # --------------------------------------------------------
    # RUN
    # --------------------------------------------------------

    def run(self) -> None:
        """
        Start the application.

        The current implementation provides a safe console
        fallback. The graphical dashboard and continuous
        wake-word loop will be connected through the UI/voice
        modules.
        """

        self.running = True

        self.logger.info("JarvisOS started.")

        print()
        print("=" * 60)
        print("                    JARVIS OS")
        print("=" * 60)
        print("JarvisOS is running.")
        print("Type a command or type 'exit' to close.")
        print("=" * 60)
        print()

        while self.running:

            try:
                command = input("You: ").strip()

            except (KeyboardInterrupt, EOFError):
                print()
                self.stop()
                break

            if not command:
                continue

            response = self.process_text_command(command)

            if response:
                self.speak(response)

    # --------------------------------------------------------
    # STOP
    # --------------------------------------------------------

    def stop(self) -> None:
        """Safely stop JarvisOS."""

        if not self.running:
            return

        self.logger.info("Stopping JarvisOS...")

        self.running = False

        # Stop microphone if supported.
        if self.microphone_manager is not None:

            try:
                stop_method = getattr(
                    self.microphone_manager,
                    "stop",
                    None
                )

                if callable(stop_method):
                    stop_method()

            except Exception as exc:
                self.logger.warning(
                    "Could not stop microphone manager: %s",
                    exc
                )

        # Stop wake-word detector if supported.
        if self.wake_word is not None:

            try:
                stop_method = getattr(
                    self.wake_word,
                    "stop",
                    None
                )

                if callable(stop_method):
                    stop_method()

            except Exception as exc:
                self.logger.warning(
                    "Could not stop wake-word detector: %s",
                    exc
                )

        self.logger.info("JarvisOS stopped.")

    # --------------------------------------------------------
    # CONTEXT MANAGER
    # --------------------------------------------------------

    def __enter__(self) -> "JarvisOS":
        self.initialize()
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback
    ) -> None:
        self.stop()


# ============================================================
# MAIN FUNCTION
# ============================================================

def main() -> int:
    """Application entry point."""

    load_environment()

    logger = setup_logging()

    logger.info("Starting JarvisOS application.")

    app = JarvisOS()

    try:
        app.initialize()
        app.run()

        return 0

    except KeyboardInterrupt:
        logger.info("Application interrupted by user.")
        app.stop()
        return 0

    except Exception as exc:
        logger.exception(
            "Fatal application error: %s",
            exc
        )

        app.stop()

        return 1


# ============================================================
# EXECUTION
# ============================================================

if __name__ == "__main__":
    sys.exit(main())
