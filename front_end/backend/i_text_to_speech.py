from abc import ABC, abstractmethod
from typing import Any, Dict, List


class ITextToSpeech(ABC):
    """Text-to-speech interface."""

    @abstractmethod
    def speak(self, text: str) -> bytes:
        """Convert text to speech audio bytes."""
        raise NotImplementedError

    @abstractmethod
    def get_inline_tags(self) -> List[str]:
        """Return inline speech tags this engine understands."""
        raise NotImplementedError

    @abstractmethod
    def get_voices(self) -> List[Dict[str, Any]]:
        """Return available voices and their effects."""
        raise NotImplementedError
