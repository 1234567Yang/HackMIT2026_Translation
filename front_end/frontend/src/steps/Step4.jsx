import { useEffect, useRef, useState } from 'react'

const RECONNECT_INTERVAL_MS = 2000

function wsUrl(path) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}${path}`
}

export default function Step4({ systemPrompt, voiceId }) {
  const [interimText, setInterimText] = useState('')
  const [messages, setMessages] = useState([])
  const [status, setStatus] = useState('connecting')

  const socketRef = useRef(null)
  const endedRef = useRef(false)
  const unmountedRef = useRef(false)
  const historyRef = useRef(null)
  const mediaStreamRef = useRef(null)
  const audioContextRef = useRef(null)
  const reconnectTimerRef = useRef(null)
  const hasShownDisconnectNoticeRef = useRef(false)
  const conversationIdRef = useRef(null)
  const isSpeakingRef = useRef(false)

  if (conversationIdRef.current === null) {
    conversationIdRef.current = crypto.randomUUID()
  }

  const stopMicrophone = () => {
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop())
    mediaStreamRef.current = null
    audioContextRef.current?.close()
    audioContextRef.current = null
  }

  const playAssistantVoice = async (text) => {
    isSpeakingRef.current = true
    try {
      const response = await fetch('/generate_voice', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice_id: voiceId }),
      })

      if (!response.ok) {
        throw new Error('TTS request failed')
      }

      const blob = await response.blob()
      const audio = new Audio(URL.createObjectURL(blob))
      await new Promise((resolve) => {
        audio.onended = resolve
        audio.onerror = resolve
        audio.play()
      })
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'system', text: `Voice error: ${err.message}` },
      ])
    } finally {
      isSpeakingRef.current = false
      socketRef.current?.send(JSON.stringify({ type: 'resume_listening' }))
    }
  }

  const connectSocket = () => {
    const socket = new WebSocket(wsUrl('/ws/conversation'))
    socketRef.current = socket

    socket.onopen = () => {
      setStatus('open')
      hasShownDisconnectNoticeRef.current = false
      socket.send(JSON.stringify({
        type: 'start',
        system_prompt: systemPrompt,
        sample_rate: audioContextRef.current?.sampleRate,
        conversation_id: conversationIdRef.current,
      }))
    }

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.type === 'interim') {
        setInterimText(data.text)
      } else if (data.type === 'finalized_user') {
        setInterimText('')
        setMessages((prev) => [
          ...prev,
          { role: 'user', text: data.text, sentiment: data.sentiment },
        ])
      } else if (data.type === 'assistant') {
        setMessages((prev) => [...prev, { role: 'assistant', text: data.text }])
        playAssistantVoice(data.text)
      } else if (data.type === 'ended') {
        endedRef.current = true
        setStatus('ended')
        stopMicrophone()
        setMessages((prev) => [
          ...prev,
          { role: 'system', text: `Conversation ended: ${data.reason}` },
        ])
      } else if (data.type === 'error') {
        setMessages((prev) => [...prev, { role: 'system', text: `Error: ${data.message}` }])
      }
    }

    socket.onclose = () => {
      if (endedRef.current || unmountedRef.current) {
        return
      }

      setStatus('disconnected')
      if (!hasShownDisconnectNoticeRef.current) {
        hasShownDisconnectNoticeRef.current = true
        setMessages((prev) => [
          ...prev,
          { role: 'system', text: 'Connection lost, retrying...' },
        ])
      }

      reconnectTimerRef.current = setTimeout(connectSocket, RECONNECT_INTERVAL_MS)
    }
  }

  useEffect(() => {
    unmountedRef.current = false
    let cancelled = false
    let workletNode = null

    const audioContext = new AudioContext()
    audioContextRef.current = audioContext

    connectSocket()

    ;(async () => {
      try {
        await audioContext.audioWorklet.addModule('/pcm-worklet.js')
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1 },
        })

        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop())
          return
        }

        mediaStreamRef.current = stream
        const source = audioContext.createMediaStreamSource(stream)
        workletNode = new AudioWorkletNode(audioContext, 'pcm-worklet-processor')
        workletNode.port.onmessage = (event) => {
          if (!isSpeakingRef.current && socketRef.current?.readyState === WebSocket.OPEN) {
            socketRef.current.send(event.data)
          }
        }
        source.connect(workletNode)
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          { role: 'system', text: `Microphone error: ${err.message}` },
        ])
      }
    })()

    return () => {
      unmountedRef.current = true
      cancelled = true
      clearTimeout(reconnectTimerRef.current)
      socketRef.current?.close()
      workletNode?.disconnect()
      stopMicrophone()
    }
  }, [systemPrompt])

  useEffect(() => {
    if (historyRef.current) {
      historyRef.current.scrollTop = historyRef.current.scrollHeight
    }
  }, [messages, interimText])

  const endConversation = () => {
    endedRef.current = true
    clearTimeout(reconnectTimerRef.current)
    socketRef.current?.send(JSON.stringify({ type: 'end', confirm_end: true }))
    socketRef.current?.close()
    stopMicrophone()
    setStatus('ended')
  }

  const downloadData = () => {
    const blob = new Blob([JSON.stringify(messages, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'conversation.json'
    link.click()
    URL.revokeObjectURL(url)
  }

  const evaluateConversation = () => {
    // TODO: implement conversation evaluation
  }

  return (
    <div className="step">
      <h2>Step 4: Conversation</h2>

      <label>
        Temporary input
        <div className="temp-input">
          {interimText || (status === 'ended' ? '' : 'Listening...')}
        </div>
      </label>

      <div className="messages" ref={historyRef}>
        {messages.map((message, index) => (
          <div key={index} className={`message ${message.role}`}>
            {message.text}
          </div>
        ))}
      </div>

      <div className="actions">
        <span />
        {status === 'ended' ? (
          <>
            <button onClick={downloadData}>Download Data</button>
            <button onClick={evaluateConversation}>Evaluate conversation</button>
          </>
        ) : (
          <button onClick={endConversation}>End conversation</button>
        )}
      </div>
    </div>
  )
}
