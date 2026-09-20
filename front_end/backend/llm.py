import json
import os
from pathlib import Path
from typing import Dict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API_URL = "https://api.openai.com/v1/responses"
MODEL = "gpt-5.6-luna"

SYSTEM_PROMPT = (
    "You help someone prepare for a role-play conversation with an AI. "
    "You will be given: who they are in this context, who they are talking to, "
    "what they intend to talk about, the personality they want the other party to have, "
    "and an example of that personality. Write one improved, ready-to-use system "
    "instruction that could be given directly to an AI so it role-plays as the other "
    "party with that personality. Be concrete and specific. "
    "Respond with only the instruction text, no preamble or explanation."
)

REQUIRED_FIELDS = [
    "who_context",
    "who_talking_to",
    "what_to_talk_about",
    "personality",
    "example",
]


def load_env() -> None:
    """Load KEY=VALUE pairs from the backend's .env file."""
    env_path = Path(__file__).resolve().parent / ".env"

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


def generate_better_prompt(data: Dict[str, str]) -> str:
    load_env()

    token = os.getenv("OPENAI_API_KEY")

    if not token:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your .env file."
        )

    user_input = (
        f"Who I am in this context: {data['who_context']}\n"
        f"Who I'm talking to: {data['who_talking_to']}\n"
        f"What we'll talk about: {data['what_to_talk_about']}\n"
        f"Personality I want them to have: {data['personality']}\n"
        f"Example of that personality: {data['example']}\n"
    )

    payload = {
        "model": MODEL,
        "input": user_input,
        "instructions": SYSTEM_PROMPT,
    }

    request = Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))

    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"OpenAI API request failed: {error.code} {details}"
        ) from error

    except URLError as error:
        raise RuntimeError(
            f"Could not connect to OpenAI API: {error.reason}"
        ) from error

    return _extract_text(result)


def _extract_text(data: Dict) -> str:
    if data.get("output_text"):
        return data["output_text"]

    parts = []

    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(content["text"])

    if parts:
        return "".join(parts)

    raise RuntimeError("OpenAI API response did not include text output")
