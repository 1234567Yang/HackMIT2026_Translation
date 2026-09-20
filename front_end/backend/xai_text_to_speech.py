import json
import os
from pathlib import Path
from typing import Any, Dict, List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from i_text_to_speech import ITextToSpeech


def load_env(path: str = ".env") -> None:
    """Load KEY=VALUE pairs from a .env file."""
    env_path = Path(path)

    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")

        if key and key not in os.environ:
            os.environ[key] = value


class XaiTextToSpeech(ITextToSpeech):
    """Stateful client for the xAI Text to Speech API."""

    voices: List[Dict[str, str]] = [
        {
            "voice_id": "eve",
            "type": "female",
            "tone": "Energetic, upbeat",
            "effect": "Default voice. Engaging and enthusiastic.",
        },
        {
            "voice_id": "ara",
            "type": "female",
            "tone": "Warm, friendly",
            "effect": "Balanced and conversational.",
        },
        {
            "voice_id": "rex",
            "type": "male",
            "tone": "Confident, clear",
            "effect": "Professional and articulate, good for business.",
        },
        {
            "voice_id": "sal",
            "type": "neutral",
            "tone": "Smooth, balanced",
            "effect": "Versatile across many contexts.",
        },
        {
            "voice_id": "leo",
            "type": "male",
            "tone": "Authoritative, strong",
            "effect": "Decisive and commanding, good for instructional content.",
        },
    ]

    inline_tags: List[str] = [
        "[pause]",
        "[long-pause]",
        "[laugh]",
        "[chuckle]",
        "[giggle]",
        "[cry]",
        "[tsk]",
        "[tongue-click]",
        "[lip-smack]",
        "[hum-tune]",
        "[breath]",
        "[inhale]",
        "[exhale]",
        "[sigh]",
    ]

    def __init__(
        self,
        token: str,
        language: str = "en",
        voice_id: str = "eve",
        speed: float = 1.0,
        text_normalization: bool = False,
        optimize_streaming_latency: int = 0,
    ):
        if not token:
            raise ValueError("token cannot be empty")

        if not language:
            raise ValueError("language cannot be empty")

        if not (0.7 <= speed <= 1.5):
            raise ValueError("speed must be between 0.7 and 1.5")

        if optimize_streaming_latency not in {0, 1, 2}:
            raise ValueError(
                "optimize_streaming_latency must be 0, 1, or 2"
            )

        self.token = token
        self.language = language
        self.voice_id = voice_id
        self.speed = speed
        self.text_normalization = text_normalization
        self.optimize_streaming_latency = optimize_streaming_latency
        self.api_url = "https://api.x.ai/v1/tts"

    def speak(self, text: str) -> bytes:
        """Convert text to speech audio bytes (default MP3)."""

        if not text:
            raise ValueError("text cannot be empty")

        payload: Dict[str, Any] = {
            "text": text,
            "language": self.language,
            "voice_id": self.voice_id,
            "speed": self.speed,
            "text_normalization": self.text_normalization,
            "optimize_streaming_latency": (
                self.optimize_streaming_latency
            ),
        }

        request = Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=60) as response:
                return response.read()

        except HTTPError as error:
            details = error.read().decode(
                "utf-8",
                errors="replace",
            )
            raise RuntimeError(
                f"xAI TTS request failed: "
                f"{error.code} {details}"
            ) from error

        except URLError as error:
            raise RuntimeError(
                f"Could not connect to xAI TTS API: "
                f"{error.reason}"
            ) from error

    def get_inline_tags(self) -> List[str]:
        return list(self.inline_tags)

    def get_voices(self) -> List[Dict[str, Any]]:
        return [dict(voice) for voice in self.voices]


if __name__ == "__main__":
    backend_dir = Path(__file__).resolve().parent
    load_env(backend_dir / ".env")

    token = os.getenv("XAI_API_KEY")

    if not token:
        raise RuntimeError(
            "Please set XAI_API_KEY in your .env file "
            "or environment"
        )

    tts = XaiTextToSpeech(
        token=token,
        language="en",
        voice_id="eve",
        speed=1.0,
        text_normalization=False,
        optimize_streaming_latency=0,
    )

    audio = tts.speak(
        "well[long-pause]that's a good point[breath]"
    )

    out_path = backend_dir / "test.mp3"
    out_path.write_bytes(audio)
    print(f"Saved {len(audio):,} bytes to {out_path}")
