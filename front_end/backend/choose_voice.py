import json
import os
from pathlib import Path
from typing import Any, Dict, List

from i_text_to_speech import ITextToSpeech
from use_chatgpt import UseChatGPT, load_env
from xai_text_to_speech import XaiTextToSpeech

SYSTEM_PROMPT = (
    "You are choosing a text-to-speech voice. "
    "You will receive a system prompt describing the agent's speaking situation, "
    "and a JSON list of available voices with their ids, tones, and effects. "
    "Pick the single voice that best fits the prompt. "
    "Respond with only the voice_id string from that list. "
    "No punctuation, no explanation, no extra words."
)


def choose_voice(tts: ITextToSpeech, prompt: str) -> str:
    """Ask ChatGPT which TTS voice fits the prompt; fall back to the first."""

    if not prompt:
        raise ValueError("prompt cannot be empty")

    voices = tts.get_voices()

    if not voices:
        raise ValueError("tts has no voices to choose from")

    voice_ids = _voice_ids(voices)
    fallback = voice_ids[0]

    load_env()
    token = os.getenv("OPENAI_API_KEY")

    if not token:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your .env file."
        )

    chatgpt = UseChatGPT(
        token=token,
        model="gpt-5.6-luna",
        system_prompt=SYSTEM_PROMPT,
    )

    user_input = (
        f"Prompt:\n{prompt}\n\n"
        f"Available voices JSON:\n"
        f"{json.dumps(voices, ensure_ascii=False)}"
    )

    answer = chatgpt.ask_chatgpt(user_input)
    chosen = _normalize_voice_id(answer)
    lookup = {voice_id.lower(): voice_id for voice_id in voice_ids}

    return lookup.get(chosen.lower(), fallback)


def _voice_ids(voices: List[Dict[str, Any]]) -> List[str]:
    ids = []

    for voice in voices:
        voice_id = str(voice.get("voice_id", "")).strip()

        if voice_id:
            ids.append(voice_id)

    if not ids:
        raise ValueError("tts voices are missing voice_id")

    return ids


def _normalize_voice_id(raw: str) -> str:
    text = raw.strip()

    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    return text.strip().strip("\"'`")


if __name__ == "__main__":
    backend_dir = Path(__file__).resolve().parent
    load_env(backend_dir / ".env")

    test_prompt = (
        "You role is a math professor teaching calculus. You are strict about the grading policy and would never curve studets' grades. The only time you curved a student grade is he went to HackMIT and had a heart attack 3 years ago. \n"
        "A student is coming to have a conversation with you. Remeber your role, it's not a roleplay, as you ARE the professor and you HAVE these personalities\n"
        "After every response, you will also see the tone the student is speaking. Neutral: describing a fact; Negative: Angry, sad, etc; Positive: Confident, happy, etc.\n"
        "If you ouput a json: `{\"reason\":\"My student started to ... It ended the whole conversation, so I will just end the conversation\", \"confirm_end\":true}`, then the conversation will be ended. You can use it when you feel it's very uncomfortable or think this conversation is over. However, you will at least try to communicate with the person." 
    )

    tts = XaiTextToSpeech(
        token=os.getenv("XAI_API_KEY", "voice-selection-test-token"),
    )

    selected_voice = choose_voice(tts, test_prompt)
    print(selected_voice)
