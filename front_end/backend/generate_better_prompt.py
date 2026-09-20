import os
from typing import Dict

from use_chatgpt import UseChatGPT, load_env

SYSTEM_PROMPT = (
    "You help someone prepare for a practice conversation with an AI. "
    "You will be given: who they are in this context, who they are talking to, "
    "what they intend to talk about, the personality they want the other party to have, "
    "and an example of that personality. Write the middle portion of a system "
    "instruction that could be given directly to an AI so it BECOMES the other "
    "party with that personality. Be concrete and specific.\n\n"
    "Format requirements:\n"
    "- Start with exactly \"You role is \" followed by a concrete description of "
    "who the AI is being (their role/position) and their personality, based on "
    "the information given.\n"
    "- Never use the words \"role-play\" or \"roleplay\" anywhere in the text you "
    "write — the AI reading these instructions should believe it truly IS "
    "that person, not that it is performing a role-play.\n"
    "- Do not write any closing remarks, disclaimers, or meta-instructions; "
    "another fixed section will be appended after your text.\n"
    "Respond with only the instruction text, no preamble or explanation."
)

INSTRUCTION_SUFFIX = (
    "\nRemember your role as described above, it's not a roleplay, as you ARE "
    "that person and you HAVE these personalities\n"
    "After every response, you will also see the student's emotion in a "
    "[emotion: ...] tag appended at the end of what they said. "
    "Neutral: describing a fact; Negative: Angry, sad, etc; Positive: Confident, "
    "happy, etc.\n"
    "If you ouput a json: `{\"reason\":\"My student started to ... It ended the "
    "whole conversation, so I will just end the conversation\", \"confirm_end\":"
    "true}`, then the conversation will be ended. You can use it when you feel "
    "it's very uncomfortable or think this conversation is over. However, you "
    "will at least try to communicate with the person."
)

REQUIRED_FIELDS = [
    "who_context",
    "who_talking_to",
    "what_to_talk_about",
    "personality",
    "example",
]


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

    chatgpt = UseChatGPT(
        token=token,
        model="gpt-5.6-luna",
        system_prompt=SYSTEM_PROMPT,
    )

    return chatgpt.ask_chatgpt(user_input) + INSTRUCTION_SUFFIX
