"""实时语音转文字（STT）模块的基础结构。

包含：
- RealTimeSTT: 抽象基类，定义获取文字和情感分析的接口。
- MicrophoneSTTBase: 通用基类，实现打开/关闭麦克风等与具体STT服务商无关的通用逻辑。
"""

from abc import ABC, abstractmethod
from typing import Optional

import sounddevice as sd


class RealTimeSTT(ABC):
    """实时语音转文字的抽象基类。"""

    @abstractmethod
    def get_text(self) -> str:
        """获取最新的转录文字。"""
        raise NotImplementedError

    @abstractmethod
    def get_sentiment(self) -> Optional[str]:
        """获取当前的情感分析结果（例如 positive / negative / neutral）。"""
        raise NotImplementedError


class MicrophoneSTTBase(RealTimeSTT):
    """通用基类：负责麦克风音频采集等通用逻辑，具体的转录和情感分析由子类实现。"""

    def __init__(
        self,
        rate: int = 16000,
        channels: int = 1,
        chunk: int = 8192,
        input_device_index: Optional[int] = None,
    ):
        self.rate = rate
        self.channels = channels
        self.chunk = chunk
        self.input_device_index = input_device_index

        self._stream: Optional[sd.RawInputStream] = None

    def open_microphone(self) -> None:
        """打开麦克风音频流。"""
        self._stream = sd.RawInputStream(
            samplerate=self.rate,
            channels=self.channels,
            dtype="int16",
            blocksize=self.chunk,
            device=self.input_device_index,
        )
        self._stream.start()

    def close_microphone(self) -> None:
        """关闭麦克风音频流并释放资源。"""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def read_chunk(self) -> bytes:
        """从麦克风读取一段音频数据。"""
        if self._stream is None:
            raise RuntimeError("麦克风尚未打开，请先调用 open_microphone()。")
        data, _overflowed = self._stream.read(self.chunk)
        return bytes(data)

    @property
    def is_open(self) -> bool:
        return self._stream is not None
