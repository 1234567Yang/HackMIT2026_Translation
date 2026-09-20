"""用 LLM 分析整场对话：找出用户在这次对话里哪里表现不好、论点哪里薄弱、
哪里说得让对方觉得生硬/不舒服。
"""

import os

from use_chatgpt import UseChatGPT, load_env

SYSTEM_PROMPT = (
    "You are a communication coach. You will be given the full transcript of "
    "a practice conversation between a user and an AI role-playing a specific "
    "person. Analyze ONLY the user's turns and give direct, concrete feedback "
    "on:\n"
    "1. Where the user did poorly overall in this conversation.\n"
    "2. Where the user's arguments/reasoning were weak or unconvincing.\n"
    "3. Where the user's phrasing came across as stiff, awkward, or "
    "uncomfortable/off-putting to the other party.\n"
    "Be specific — quote or reference the exact moment in the conversation "
    "you're talking about. Do not comment on the AI's turns. Do not praise "
    "unless it's directly relevant context for the criticism.\n\n"
    "Don't force an answer. If there's no real problem (or only a very "
    "minor/borderline one not worth mentioning), respond with exactly "
    "\"no_problem\" and nothing else.\n\n"
    "Otherwise, respond with plain text feedback, no preamble. Be very "
    "concise and easy to read — short sentences or a short bullet list, no "
    "filler, straight to the point."
)


def analyze_whole_conversation_llm(conversation_text: str) -> str:
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

    return chatgpt.ask_chatgpt(conversation_text)
