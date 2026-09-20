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

提供两个具体类，共用 _DeepgramSTTBase 里和 Deepgram 连接/转录/情感分析相关的
逻辑，只在音频来源上不同：
- DeepgramSTT：本机麦克风（CLI/practice_console.py 用）。
- DeepgramRemoteSTT：音频由外部通过 feed_audio() 推入（Web 后端用，见
  conversation_ws.py，音频实际来自浏览器）。
"""

import os
import threading
from typing import Optional

from dotenv import load_dotenv

from deepgram import DeepgramClient
from deepgram.core.events import EventType
from deepgram.listen.v1.types import ListenV1Results

from real_time_stt import MicrophoneSTTBase, RealTimeSTT, RemoteAudioSTTBase

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


class _DeepgramSTTBase(RealTimeSTT):
    """Deepgram Listen V1 转录 + 情感分析的公共逻辑，不关心音频从哪来。

    子类通过 read_chunk() 提供音频（阻塞读取，返回 None 表示流结束），并实现
    _open()/_close() 做各自音频源的准备/清理。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "nova-3",
        language: str = "en-US",
        rate: int = 16000,
        channels: int = 1,
    ):
        self.model = model
        self.language = language
        self.rate = rate
        self.channels = channels

        self._client = DeepgramClient(api_key=api_key or _load_api_key())
        self._connection_ctx = None
        self._connection = None

        self._transcript_lock = threading.Lock()
        self._final_transcript = ""
        self._interim_transcript = ""

        self._stop_event = threading.Event()
        self._listener_thread: Optional[threading.Thread] = None
        self._sender_thread: Optional[threading.Thread] = None

    def _open(self) -> None:
        raise NotImplementedError

    def _close(self) -> None:
        raise NotImplementedError

    def read_chunk(self) -> Optional[bytes]:
        raise NotImplementedError

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
            if chunk is None:
                break
            if chunk:
                try:
                    self._connection.send_media(chunk)
                except Exception:
                    break

    def start(self) -> None:
        """准备音频源并建立与 Deepgram 的实时转录连接。"""
        self._open()

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
        """停止发送音频、关闭连接并释放音频源。"""
        self._stop_event.set()
        # 先关音频源：本机麦克风会让阻塞中的 read_chunk() 抛异常从而退出；
        # 远程队列则靠 _close() 里的 end_audio() 塞入 None 唤醒 read_chunk()。
        # 顺序很重要——如果先 join 再关，remote 场景下每一轮都要白等 join 的
        # 超时时间，因为唤醒 read_chunk() 的动作还没发生。
        self._close()

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


class DeepgramSTT(MicrophoneSTTBase, _DeepgramSTTBase):
    """使用本机麦克风做实时转录（CLI / practice_console.py 用）。"""

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
        MicrophoneSTTBase.__init__(
            self,
            rate=rate,
            channels=channels,
            chunk=chunk,
            input_device_index=input_device_index,
        )
        _DeepgramSTTBase.__init__(
            self, api_key=api_key, model=model, language=language, rate=rate, channels=channels
        )

    def _open(self) -> None:
        self.open_microphone()

    def _close(self) -> None:
        self.close_microphone()

    # read_chunk() 由 MicrophoneSTTBase 提供


class DeepgramRemoteSTT(RemoteAudioSTTBase, _DeepgramSTTBase):
    """音频由外部（比如浏览器通过 WebSocket 发来的二进制帧）推入，见
    conversation_ws.py 里的 feed_audio() 调用。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "nova-3",
        language: str = "en-US",
        rate: int = 16000,
        channels: int = 1,
    ):
        RemoteAudioSTTBase.__init__(self)
        _DeepgramSTTBase.__init__(
            self, api_key=api_key, model=model, language=language, rate=rate, channels=channels
        )

    def _open(self) -> None:
        pass  # 队列不需要预先打开

    def _close(self) -> None:
        self.end_audio()

    # read_chunk()/feed_audio()/end_audio() 由 RemoteAudioSTTBase 提供
