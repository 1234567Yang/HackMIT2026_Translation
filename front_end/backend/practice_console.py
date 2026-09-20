"""语音版对话控制台。

和 use_chatgpt.py 里 __main__ 的逻辑一样，只不过不是手动 input()，
而是用 Deepgram 实时监听麦克风：只要转录文字持续在变化就继续听，
一旦连续 WAIT_USR_IPT_SECOND 秒没有新增内容，就认为这句话说完了，
把文字（连同情感）发给 ChatGPT。

listen_for_utterance / run_conversation_loop 用回调而不是直接 print，
这样同一套逻辑既能给这里的 CLI 用，也能给 Web 后端的 WebSocket handler 用。
"""

import os
import time
from typing import Callable, Optional

from deepgram_stt import DeepgramSTT
from use_chatgpt import UseChatGPT, load_env

WAIT_USR_IPT_SECOND = 3
EXTRA_USR_IPT_SECOND_THINKING = 4
EXTRA_TIME_WORDS = {"um", "umm", "uh", "and", "so", "but", "you know", "yeah"}
POLL_INTERVAL_SECOND = 0.2


def listen_for_utterance(
    stt: DeepgramSTT,
    on_interim: Callable[[str], None] = print,
    should_stop: Optional[Callable[[], bool]] = None,
) -> Optional[str]:
    """监听麦克风，直到文字连续 WAIT_USR_IPT_SECOND 秒没有新增，返回这段话的文字。

    如果最后一个词是语气词/连接词（um, uh, and, so, but 等），说明用户可能只是
    停顿思考、还没说完，这时多等 EXTRA_USR_IPT_SECOND_THINKING 秒再判断。

    每次转录文字变化都会调用一次 on_interim(text)。如果传了 should_stop 且它在
    某次轮询时返回 True（比如用户点了"结束对话"），会立刻停止监听并返回 None，
    用来和"这句话正常说完了"（返回文字）区分开。
    """
    stt.start()

    last_text = ""
    last_change_time = time.time()

    try:
        while True:
            if should_stop is not None and should_stop():
                return None

            time.sleep(POLL_INTERVAL_SECOND)
            text = stt.get_text()

            if text != last_text:
                last_text = text
                last_change_time = time.time()
                on_interim(text)
                continue

            words = text.split()
            current_last_word = words[-1].strip(".,!?").lower() if words else ""
            wait_second = WAIT_USR_IPT_SECOND
            if current_last_word in EXTRA_TIME_WORDS:
                wait_second += EXTRA_USR_IPT_SECOND_THINKING

            if text and (time.time() - last_change_time >= wait_second):
                return text
    finally:
        stt.stop()


def run_conversation_loop(
    chatgpt: UseChatGPT,
    stt_factory: Callable[[], DeepgramSTT],
    on_interim: Callable[[str], None],
    on_finalized_user: Callable[[str, Optional[str]], None],
    on_assistant: Callable[[str], None],
    on_ended: Callable[[str], None],
    should_stop: Optional[Callable[[], bool]] = None,
    wait_for_resume: Optional[Callable[[], None]] = None,
) -> None:
    """跑通"监听一句话 -> 情感分析 -> 问 ChatGPT -> 判断模型是否要结束对话"的循环，
    直到模型输出 confirm_end，或者 should_stop() 返回 True。

    如果传了 wait_for_resume，会在每次拿到 AI 回复之后（还没结束对话的话）
    调用一次，用来在把回复念出来（TTS）期间暂停，念完再继续听下一句。
    """
    while True:
        if should_stop is not None and should_stop():
            break

        stt = stt_factory()
        text = listen_for_utterance(stt, on_interim=on_interim, should_stop=should_stop)

        if text is None:
            break

        sentiment = stt.get_sentiment()
        on_finalized_user(text, sentiment)

        res = chatgpt.ask_chatgpt(f"{text}\n\n[emotion: {sentiment}]")
        on_assistant(res)

        ended, reason = chatgpt.parse_end_signal(res)
        if ended:
            on_ended(reason)
            break

        if wait_for_resume is not None:
            wait_for_resume()


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
            "After every response, you will also see the student's emotion in a [emotion: ...] tag appended at the end of what they said. Neutral: describing a fact; Negative: Angry, sad, etc; Positive: Confident, happy, etc.\n"
            "If you ouput a json: `{\"reason\":\"My student started to ... It ended the whole conversation, so I will just end the conversation\", \"confirm_end\":true}`, then the conversation will be ended. You can use it when you feel it's very uncomfortable or think this conversation is over. However, you will at least try to communicate with the person."
        ),
    )

    run_conversation_loop(
        chatgpt=chatgpt,
        stt_factory=lambda: DeepgramSTT(language="en-US"),
        on_interim=print,
        on_finalized_user=lambda text, sentiment: print(f"Finalized version: {text}"),
        on_assistant=print,
        on_ended=lambda reason: print(f"[The professor ended the conversation] {reason}"),
    )

    chatgpt.export_conversation("conversation.json")


if __name__ == "__main__":
    main()
