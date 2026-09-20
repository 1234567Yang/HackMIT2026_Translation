import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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


class UseChatGPT:
    """Simple stateful client for OpenAI Responses API."""

    def __init__(
        self,
        token: str,
        model: str = "gpt-5.6-luna",
        system_prompt: Optional[str] = None,
    ):
        if not token:
            raise ValueError("token cannot be empty")

        self.token = token
        self.model = model
        self.system_prompt = system_prompt
        self.api_url = "https://api.openai.com/v1/responses"

        self.previous_response_id: Optional[str] = None
        self.conversation: List[Dict[str, Any]] = []

    def ask_chatgpt(self, prompt: str) -> str:
        """Send a prompt and continue this object's conversation."""

        if not prompt:
            raise ValueError("prompt cannot be empty")

        payload = {
            "model": self.model,
            "input": prompt,
        }

        if self.system_prompt:
            payload["instructions"] = self.system_prompt

        if self.previous_response_id:
            payload["previous_response_id"] = self.previous_response_id

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
                data = json.loads(
                    response.read().decode("utf-8")
                )

        except HTTPError as error:
            details = error.read().decode(
                "utf-8",
                errors="replace",
            )
            raise RuntimeError(
                f"OpenAI API request failed: "
                f"{error.code} {details}"
            ) from error

        except URLError as error:
            raise RuntimeError(
                f"Could not connect to OpenAI API: "
                f"{error.reason}"
            ) from error

        self.previous_response_id = data.get("id")

        answer = self._extract_text(data)

        self.conversation.append({
            "role": "user",
            "content": prompt,
        })

        self.conversation.append({
            "role": "assistant",
            "content": answer,
        })

        return answer

    def export_conversation(
        self,
        file_path: str = "conversation.json",
    ) -> None:
        """Export this conversation to a JSON file."""

        data = {
            "exported_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "model": self.model,
            "system_prompt": self.system_prompt,
            "messages": self.conversation,
        }

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        path.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _extract_text(
        self,
        data: Dict[str, Any],
    ) -> str:
        if data.get("output_text"):
            return data["output_text"]

        parts = []

        for item in data.get("output", []):
            for content in item.get("content", []):
                if (
                    content.get("type") == "output_text"
                    and content.get("text")
                ):
                    parts.append(content["text"])

        if parts:
            return "".join(parts)

        raise RuntimeError(
            "OpenAI API response did not include text output"
        )
    def parse_end_signal(self, response: str) -> tuple[bool, str]:
        """Return (should_end, reason) if the model emitted the end-of-chat JSON."""
        text = response.strip()

        if text.startswith("```"):
            lines = text.splitlines()[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        if not text.startswith("{"):
            return False, ""

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return False, ""

        if isinstance(data, dict) and data.get("confirm_end") is True:
            return True, str(data.get("reason", ""))

        return False, ""

if __name__ == "__main__":
    load_env()

    token = os.getenv("OPENAI_API_KEY")

    if not token:
        raise RuntimeError(
            "Please set OPENAI_API_KEY in your .env file "
            "or environment"
        )

    chatgpt = UseChatGPT(
        token=token,
        model="gpt-5.6-luna",
        system_prompt=(
            "You role is a math professor teaching calculus. You are strict about the grading policy and would never curve studets' grades. The only time you curved a student grade is he went to HackMIT and had a heart attack 3 years ago. \n"
            "A student is coming to have a conversation with you. Remeber your role, it's not a roleplay, as you ARE the professor and you HAVE these personalities\n"
            "After every response, you will also see the tone the student is speaking. Neutral: describing a fact; Negative: Angry, sad, etc; Positive: Confident, happy, etc.\n"
            "If you ouput a json: `{\"reason\":\"My student started to ... It ended the whole conversation, so I will just end the conversation\", \"confirm_end\":true}`, then the conversation will be ended. You can use it when you feel it's very uncomfortable or think this conversation is over. However, you will at least try to communicate with the person." 
        ),
    )

    # print(chatgpt.ask_chatgpt("Hi professor, how are you doing? I am here to see if I could just bump my grade a little bit, you know I have a eighty nine point eight. I really want to bump my grade a little bit."))
    # print(chatgpt.ask_chatgpt("你还记得我叫什么名字吗？"))

    print(chatgpt.ask_chatgpt("Hi professor, how are you doing? I am here to see if I could just bump my grade a little bit, you know I have a eighty nine point eight. I really want to bump my grade a little bit."))

    while True:
        try:
            ipt = input("Input your next message: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not ipt:
            continue

        if ipt.lower() in {"quit", "exit", "q"}:
            break

        try:
            res = chatgpt.ask_chatgpt(ipt)
        except RuntimeError as error:
            print(f"[error] {error}")
            break

        ended, reason = chatgpt.parse_end_signal(res)

        if ended:
            print(f"[The professor ended the conversation] {reason}")
            break

        print(res)

    chatgpt.export_conversation("conversation.json")
    print("Saved to conversation.json")