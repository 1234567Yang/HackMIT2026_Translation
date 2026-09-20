"""语音版对话控制台。

和 use_chatgpt.py 里 __main__ 的逻辑一样，只不过不是手动 input()，
而是用 Deepgram 实时监听麦克风：只要转录文字持续在变化就继续听，
一旦连续 WAIT_USR_IPT_SECOND 秒没有新增内容，就认为这句话说完了，
把文字（连同情感）发给 ChatGPT。
"""

import json
import os
import time

from deepgram_stt import DeepgramSTT
from use_chatgpt import UseChatGPT, load_env

WAIT_USR_IPT_SECOND = 3
EXTRA_USR_IPT_SECOND_THINKING = 4
EXTRA_TIME_WORDS = {"um", "umm", "uh", "and", "so", "but", "you know","yeah"}
POLL_INTERVAL_SECOND = 0.2


def listen_for_utterance(stt: DeepgramSTT) -> str:
    """监听麦克风，直到文字连续 WAIT_USR_IPT_SECOND 秒没有新增，返回这段话的文字。

    如果最后一个词是语气词/连接词（um, uh, and, so, but 等），说明用户可能只是
    停顿思考、还没说完，这时多等 EXTRA_USR_IPT_SECOND_THINKING 秒再判断。
    """
    stt.start()

    last_text = ""
    last_change_time = time.time()

    try:
        while True:
            time.sleep(POLL_INTERVAL_SECOND)
            text = stt.get_text()

            if text != last_text:
                last_text = text
                last_change_time = time.time()
                print(text)
                continue

            words = text.split()
            current_last_word = words[-1].strip(".,!?").lower() if words else ""
            wait_second = WAIT_USR_IPT_SECOND
            if current_last_word in EXTRA_TIME_WORDS:
                wait_second += EXTRA_USR_IPT_SECOND_THINKING

            if text and (time.time() - last_change_time >= wait_second):
                print(f"Finalized version: {text}")
                return text
    finally:
        stt.stop()


def main() -> None:
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
            "You role is a computer science professor teaching computer systems. You are strict about the grading policy and would never curve studets' grades. The only time you curved a student grade is he went to HackMIT and had a heart attack 3 years ago. \n"
            "A student is coming to have a conversation with you. Remeber your role, it's not a roleplay, as you ARE the professor and you HAVE these personalities\n"
            "After every response, you will also see the tone the student is speaking. Neutral: describing a fact; Negative: Angry, sad, etc; Positive: Confident, happy, etc.\n"
            "If you ouput a json: `{\"reason\":\"My student started to ... It ended the whole conversation, so I will just end the conversation\", \"confirm_end\":true}`, then the conversation will be ended. You can use it when you feel it's very uncomfortable or think this conversation is over. However, you will at least try to communicate with the person."
        ),
    )

    # print(chatgpt.ask_chatgpt("Hi professor, how are you doing? I am here to see if I could just bump my grade a little bit, you know I have a eighty nine point eight. I really want to bump my grade a little bit."))

    while True:
        stt = DeepgramSTT(language="en-US")
        text = listen_for_utterance(stt)
        sentiment = stt.get_sentiment()

        res = chatgpt.ask_chatgpt(f"{text}\n\n[Tone: {sentiment}]")
        print(res)

        try:
            json.loads(res)
        except json.JSONDecodeError:
            continue
        break

    chatgpt.export_conversation("conversation.json")


if __name__ == "__main__":
    main()
