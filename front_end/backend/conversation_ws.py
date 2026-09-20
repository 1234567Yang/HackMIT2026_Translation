"""对话页面（Step4）用的 WebSocket 端点：/ws/conversation。

复用 practice_console.py 里的 run_conversation_loop，只是把原来的 print
换成 ws.send(...)。音频来自浏览器（不是本机麦克风）：浏览器用 AudioWorklet
采集 PCM16 音频，通过这个 WebSocket 连接的二进制帧发过来，这里再用
DeepgramRemoteSTT.feed_audio() 转发给 Deepgram。

支持 WS 断线重连：客户端在整场对话期间保持同一个 conversation_id，断线后
用同一个 id 重新连接。后端用 _SESSIONS 这个进程内的注册表，把可以跨连接
复用的 UseChatGPT（存着 previous_response_id，也就是 ChatGPT 那边的对话
上下文）按 conversation_id 存起来，重连时直接接回同一个对象继续聊，而不是
从头开一个新对话。注意这只是内存字典，进程重启或多进程部署都不成立，
hackathon 规模下够用。

协议：
客户端 -> 服务端：
    {"type": "start", "system_prompt": "...", "sample_rate": 48000, "conversation_id": "..."}
        每次连接（包括重连）都先发一次；sample_rate 是浏览器 AudioContext
        的实际采样率；conversation_id 在整场对话期间保持不变，重连时要带
        同一个值，后端才能认出是同一场对话
    二进制帧：PCM16 单声道音频数据，连接建立后持续发送
    {"type": "end", "confirm_end": true}
        用户点击 "End conversation"
    {"type": "resume_listening"}
        前端把上一句 AI 回复的 TTS 播完了，通知后端可以继续听下一句了
        （后端在生成完回复之后会一直等这个消息，见 wait_for_resume）
服务端 -> 客户端：
    {"type": "interim", "text": "..."}
    {"type": "finalized_user", "text": "...", "sentiment": "positive"}
    {"type": "assistant", "text": "..."}
    {"type": "ended", "reason": "...", "confirm_end": true}
    {"type": "error", "message": "..."}
"""

import json
import os
import threading
import uuid

from flask_sock import Sock

from deepgram_stt import DeepgramRemoteSTT
from practice_console import run_conversation_loop
from use_chatgpt import UseChatGPT, load_env


class _ConversationSession:
    """跨 WS 连接复用的对话状态：主要是那个存着聊天上下文的 UseChatGPT。"""

    def __init__(self, chatgpt: UseChatGPT):
        self.chatgpt = chatgpt
        # 同一时间只允许一条连接跑这个 session 的对话循环
        self.lock = threading.Lock()
        # 新连接进来接管时置位，通知当前正跑着循环的旧连接尽快退出
        self.superseded = threading.Event()


_sessions_lock = threading.Lock()
_sessions: dict = {}


def _get_or_create_session(conversation_id: str, token: str, system_prompt: str) -> _ConversationSession:
    with _sessions_lock:
        session = _sessions.get(conversation_id)
        if session is None:
            session = _ConversationSession(
                chatgpt=UseChatGPT(token=token, model="gpt-5.6-luna", system_prompt=system_prompt)
            )
            _sessions[conversation_id] = session
        else:
            # 已经有一条连接（可能还活着）在用这个 session，通知它让位
            session.superseded.set()
        return session


def register_conversation_ws(app) -> None:
    sock = Sock(app)

    @sock.route("/ws/conversation")
    def conversation(ws):
        load_env()

        token = os.getenv("OPENAI_API_KEY")
        if not token:
            ws.send(json.dumps({
                "type": "error",
                "message": "OPENAI_API_KEY is not set. Add it to your .env file.",
            }))
            return

        start_raw = ws.receive()
        try:
            start_message = json.loads(start_raw) if start_raw else {}
        except json.JSONDecodeError:
            start_message = {}

        system_prompt = start_message.get("system_prompt")
        if start_message.get("type") != "start" or not system_prompt:
            ws.send(json.dumps({
                "type": "error",
                "message": "Expected a {\"type\": \"start\", \"system_prompt\": ...} message first.",
            }))
            return

        sample_rate = int(start_message.get("sample_rate") or 16000)
        conversation_id = start_message.get("conversation_id") or str(uuid.uuid4())

        session = _get_or_create_session(conversation_id, token, system_prompt)

        # 等前一条连接（如果还在跑）真正退出、释放 session，才轮到这条连接接管。
        acquired = session.lock.acquire(timeout=5)
        if not acquired:
            ws.send(json.dumps({
                "type": "error",
                "message": "Previous connection for this conversation did not release in time.",
            }))
            return

        # 从现在起这条连接是这个 session 的"当前连接"，把 superseded 复位，
        # 这样下一次重连才能正确地把*这条*连接标记为该让位了。
        session.superseded.clear()

        # 每一轮 stt_factory() 都会造一个新的 DeepgramRemoteSTT，这个 holder
        # 让读取线程知道当前这一轮的音频应该喂给哪个实例。
        current_stt = {"value": None}

        def stt_factory() -> DeepgramRemoteSTT:
            stt = DeepgramRemoteSTT(language="en-US", rate=sample_rate, channels=1)
            current_stt["value"] = stt
            return stt

        client_end = threading.Event()
        resume_event = threading.Event()
        ended_for_real = {"value": False}

        def read_client_messages() -> None:
            while True:
                try:
                    raw = ws.receive()
                except Exception:
                    client_end.set()
                    return

                if raw is None:
                    client_end.set()
                    return

                if isinstance(raw, bytes):
                    stt = current_stt["value"]
                    if stt is not None:
                        stt.feed_audio(raw)
                    continue

                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                if message.get("type") == "end" and message.get("confirm_end"):
                    ended_for_real["value"] = True
                    client_end.set()
                    stt = current_stt["value"]
                    if stt is not None:
                        stt.end_audio()
                    return

                if message.get("type") == "resume_listening":
                    resume_event.set()
                    continue

        reader_thread = threading.Thread(target=read_client_messages, daemon=True)
        reader_thread.start()

        def on_ended(reason: str) -> None:
            ended_for_real["value"] = True
            ws.send(json.dumps({"type": "ended", "reason": reason, "confirm_end": True}))

        def wait_for_resume() -> None:
            # 每 0.2 秒醒一次检查连接是不是已经断了/被接管了，避免 TTS 播放期间
            # 客户端掉线导致这个线程永远卡在这等一个不会再来的 resume_listening。
            while not (client_end.is_set() or session.superseded.is_set()):
                if resume_event.wait(timeout=0.2):
                    resume_event.clear()
                    return

        try:
            run_conversation_loop(
                chatgpt=session.chatgpt,
                stt_factory=stt_factory,
                on_interim=lambda text: ws.send(json.dumps({"type": "interim", "text": text})),
                on_finalized_user=lambda text, sentiment: ws.send(json.dumps({
                    "type": "finalized_user",
                    "text": text,
                    "sentiment": sentiment,
                })),
                on_assistant=lambda text: ws.send(json.dumps({"type": "assistant", "text": text})),
                on_ended=on_ended,
                should_stop=lambda: client_end.is_set() or session.superseded.is_set(),
                wait_for_resume=wait_for_resume,
            )
        except Exception as error:
            try:
                ws.send(json.dumps({"type": "error", "message": str(error)}))
            except Exception:
                pass
        finally:
            session.lock.release()
            if ended_for_real["value"]:
                with _sessions_lock:
                    _sessions.pop(conversation_id, None)
            try:
                ws.close()
            except Exception:
                pass
