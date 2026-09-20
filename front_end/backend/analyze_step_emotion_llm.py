"""用 LLM 逐句分析面部情绪，覆盖两种场景，各用各的 system prompt：

1. speaking：结合用户说这句话时的面部情绪和前面的对话上下文，判断嘴上说的和
   脸上表现的是否一致（比如嘴上说"没问题"但脸上写着紧张）。
2. listening：结合用户听对方说话时的面部情绪，判断这个反应跟对方刚说的内容
   合不合适（比如对方说了不好的事，用户却在笑）。
"""

import os
from typing import Any, Dict, List, Optional

from use_chatgpt import UseChatGPT, load_env

SYSTEM_PROMPT_SPEAKING = (
    "You are a social-confidence coach helping someone practice a conversation. "
    "You will be given, for ONE message the user just said:\n"
    "1. Up to 2 previous messages for context (could be the user or the other "
    "party).\n"
    "2. The message itself (what the user said).\n"
    "3. A facial emotion breakdown (percentages for angry/disgust/fear/happy/"
    "sad/surprise/neutral) captured from the user's webcam while they were "
    "saying it. This may be missing if no face was detected.\n\n"
    "Your job: judge whether the user's facial emotion while speaking matches "
    "what they were saying. Look specifically for signs of social anxiety "
    "masking — e.g. their words sound confident/calm but their face shows "
    "fear/sad/disgust, or they are smiling out of nervousness rather than "
    "genuine ease. Use the previous messages only as context to judge whether "
    "the emotional reaction made sense for the moment.\n\n"
    "Don't force an answer. If there's no emotion data, or there's no real "
    "problem (or only a very minor/borderline one not worth mentioning), "
    "respond with exactly \"no_problem\" and nothing else.\n\n"
    "Only if there's a genuinely notable mismatch, respond with ONE short, "
    "direct, encouraging sentence of feedback the user can act on (e.g. 'You "
    "said you were fine with the plan, but your face showed a lot of fear — "
    "try naming the discomfort out loud instead of masking it.'). No "
    "preamble, no disclaimers, plain text only."
)

SYSTEM_PROMPT_LISTENING = (
    "You are a social-confidence coach helping someone practice a conversation. "
    "You will be given, for a moment right after the OTHER PARTY finished "
    "speaking:\n"
    "1. Up to 2 previous messages for context.\n"
    "2. The message the other party just said (this is what the user was "
    "listening to, NOT something the user said).\n"
    "3. A facial emotion breakdown (percentages for angry/disgust/fear/happy/"
    "sad/surprise/neutral) captured from the user's webcam while they were "
    "listening to that message. This may be missing if no face was detected.\n\n"
    "Your job: judge whether the user's facial reaction was an appropriate "
    "response to what they just heard. Look specifically for mismatches — e.g. "
    "laughing or smiling while being told something sad/serious/upsetting, or "
    "showing fear/disgust in reaction to something neutral or positive. Use "
    "the previous messages only as context to judge whether the reaction made "
    "sense for the moment.\n\n"
    "Don't force an answer. If there's no emotion data, or there's no real "
    "problem (or only a very minor/borderline one not worth mentioning), "
    "respond with exactly \"no_problem\" and nothing else.\n\n"
    "Only if there's a genuinely notable mismatch, respond with ONE short, "
    "direct, encouraging sentence of feedback the user can act on (e.g. "
    "'They just told you something upsetting, but you were smiling — a more "
    "measured reaction would land better.'). No preamble, no disclaimers, "
    "plain text only."
)


def _format_previous_messages(previous_messages: List[Dict[str, str]]) -> str:
    if not previous_messages:
        return "(none)"

    lines = []
    for item in previous_messages:
        role = item.get("role", "unknown")
        text = item.get("text", "")
        lines.append(f"{role}: {text}")

    return "\n".join(lines)


def _format_emotion(emotion: Optional[Dict[str, float]]) -> str:
    if not emotion:
        return "(no face detected / not available)"

    return ", ".join(f"{key}: {value:.1f}%" for key, value in emotion.items())


def analyze_step_emotion_llm(data: Dict[str, Any]) -> str:
    load_env()

    token = os.getenv("OPENAI_API_KEY")

    if not token:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your .env file."
        )

    message = data.get("message") or {}
    previous_messages = data.get("previous_messages") or []
    emotion = data.get("emotion")
    context_type = data.get("context_type", "speaking")

    is_listening = context_type == "listening"
    system_prompt = SYSTEM_PROMPT_LISTENING if is_listening else SYSTEM_PROMPT_SPEAKING
    emotion_label = "while listening" if is_listening else "while speaking"

    prompt = (
        f"Previous messages:\n{_format_previous_messages(previous_messages)}\n\n"
        f"This message ({message.get('role', 'unknown')}): "
        f"\"{message.get('text', '')}\"\n\n"
        f"User's facial emotion {emotion_label}: {_format_emotion(emotion)}\n"
    )

    chatgpt = UseChatGPT(
        token=token,
        model="gpt-5.6-luna",
        system_prompt=system_prompt,
    )

    return chatgpt.ask_chatgpt(prompt)
