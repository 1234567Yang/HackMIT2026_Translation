class PCMWorkletProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this._buffer = []
    this._bufferedLength = 0
  }

  process(inputs) {
    const channelData = inputs[0] && inputs[0][0]
    if (channelData) {
      this._buffer.push(channelData.slice())
      this._bufferedLength += channelData.length

      if (this._bufferedLength >= 4096) {
        const merged = new Float32Array(this._bufferedLength)
        let offset = 0
        for (const chunk of this._buffer) {
          merged.set(chunk, offset)
          offset += chunk.length
        }

        const pcm16 = new Int16Array(merged.length)
        for (let i = 0; i < merged.length; i++) {
          const s = Math.max(-1, Math.min(1, merged[i]))
          pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
        }

        this.port.postMessage(pcm16.buffer, [pcm16.buffer])
        this._buffer = []
        this._bufferedLength = 0
      }
    }
    return true
  }
}

registerProcessor('pcm-worklet-processor', PCMWorkletProcessor)
