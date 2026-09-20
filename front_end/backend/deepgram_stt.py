"""基于 Deepgram 的实时语音转文字（STT）实现。

依赖：
    pip install deepgram-sdk sounddevice python-dotenv

需要提供 Deepgram API key，优先级：
    1. 构造函数传入的 api_key 参数
    2. 环境变量 DEEPGRAM_API_KEY（会自动从 backend 目录下的 .env 文件加载）
    3. backend 目录下的 key.txt 文件

注意：Deepgram 目前不支持对实时音频流直接做情感分析（Audio Intelligence 功能
仅支持预录制/批处理请求）。因此这里的 get_sentiment() 是对累计的、已确定
（is_final）的转录文字调用 Deepgram 的 Text Intelligence（/v1/read）接口来完成的。
"""

import os
import threading
from typing import Optional

from dotenv import load_dotenv

from deepgram import DeepgramClient
from deepgram.core.events import EventType
from deepgram.listen.v1.types import ListenV1Results

from real_time_stt import MicrophoneSTTBase

_KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "key.txt")

load_dotenv()


def _load_api_key() -> str:
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if api_key:
        return api_key.strip()
    if os.path.exists(_KEY_FILE):
        with open(_KEY_FILE, "r", encoding="utf-8") as f:
            key = f.read().strip()
        if key:
            return key
    raise RuntimeError(
        "未找到 Deepgram API key，请设置环境变量 DEEPGRAM_API_KEY，"
        "或在 backend 目录下的 key.txt 中提供。"
    )


class DeepgramSTT(MicrophoneSTTBase):
    """使用 Deepgram Listen V1 做实时麦克风转录，并对已转录文字做情感分析。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "nova-3",
        language: str = "en-US",
        rate: int = 16000,
        channels: int = 1,
        chunk: int = 8192,
        input_device_index: Optional[int] = None,
    ):
        super().__init__(
            rate=rate,
            channels=channels,
            chunk=chunk,
            input_device_index=input_device_index,
        )
        self.model = model
        self.language = language

        self._client = DeepgramClient(api_key=api_key or _load_api_key())
        self._connection_ctx = None
        self._connection = None

        self._transcript_lock = threading.Lock()
        self._final_transcript = ""
        self._interim_transcript = ""

        self._stop_event = threading.Event()
        self._listener_thread: Optional[threading.Thread] = None
        self._sender_thread: Optional[threading.Thread] = None

    def _on_message(self, message: object) -> None:
        if not isinstance(message, ListenV1Results):
            return
        if message.channel is None or not message.channel.alternatives:
            return
        transcript = message.channel.alternatives[0].transcript
        if not transcript:
            return
        with self._transcript_lock:
            if message.is_final:
                self._final_transcript = (self._final_transcript + " " + transcript).strip()
                self._interim_transcript = ""
            else:
                self._interim_transcript = transcript

    def _send_audio_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                chunk = self.read_chunk()
            except Exception:
                break
            if chunk:
                try:
                    self._connection.send_media(chunk)
                except Exception:
                    break

    def start(self) -> None:
        """打开麦克风并建立与 Deepgram 的实时转录连接。"""
        self.open_microphone()

        self._connection_ctx = self._client.listen.v1.connect(
            model=self.model,
            language=self.language,
            encoding="linear16",
            sample_rate=self.rate,
            channels=self.channels,
            interim_results=True,
            smart_format=True,
        )
        self._connection = self._connection_ctx.__enter__()
        self._connection.on(EventType.MESSAGE, self._on_message)

        self._stop_event.clear()
        self._listener_thread = threading.Thread(
            target=self._connection.start_listening, daemon=True
        )
        self._listener_thread.start()

        self._sender_thread = threading.Thread(target=self._send_audio_loop, daemon=True)
        self._sender_thread.start()

    def stop(self) -> None:
        """停止发送音频、关闭连接并释放麦克风。"""
        self._stop_event.set()
        if self._sender_thread is not None:
            self._sender_thread.join(timeout=2)

        if self._connection is not None:
            try:
                self._connection.send_finalize()
                self._connection.send_close_stream()
            except Exception:
                pass
        if self._listener_thread is not None:
            self._listener_thread.join(timeout=5)
        if self._connection_ctx is not None:
            self._connection_ctx.__exit__(None, None, None)
            self._connection_ctx = None
            self._connection = None

        self.close_microphone()

    def get_text(self) -> str:
        """获取目前为止的转录文字（已确定部分 + 正在识别中的临时部分）。"""
        with self._transcript_lock:
            if self._interim_transcript:
                return (self._final_transcript + " " + self._interim_transcript).strip()
            return self._final_transcript

    def get_sentiment(self) -> Optional[str]:
        """对目前已确定（is_final）的转录文字做情感分析，返回 positive/negative/neutral。

        由于 Deepgram 不支持对实时音频流直接做情感分析，这里是对累计的
        转录文字调用 Text Intelligence 批处理接口完成的。
        """
        with self._transcript_lock:
            text = self._final_transcript
        if not text:
            return None

        response = self._client.read.v1.text.analyze(
            request={"text": text},
            language="en",
            sentiment=True,
        )
        sentiments = response.results.sentiments if response.results else None
        if sentiments is None or sentiments.average is None:
            return None
        return sentiments.average.sentiment
