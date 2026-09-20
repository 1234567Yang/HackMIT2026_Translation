"""测试脚本：打开麦克风录音10秒，输出识别到的英文文字和情感分析结果。"""

import time

from deepgram_stt import DeepgramSTT


def main() -> None:
    stt = DeepgramSTT(language="en-US")

    print("正在打开麦克风，请说话（10秒）...")
    stt.start()
    try:
        time.sleep(10)
    finally:
        print("录音结束，正在处理...")
        stt.stop()

    text = stt.get_text()
    print(f"识别到的文字: {text}")

    sentiment = stt.get_sentiment()
    print(f"情感: {sentiment}")


if __name__ == "__main__":
    main()

# positive negative neutral