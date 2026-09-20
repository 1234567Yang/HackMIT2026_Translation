import { useEffect, useRef, useState } from 'react'

function wsUrl(path) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}${path}`
}

const MAX_PHOTOS_PER_TURN = 3
const CAPTURE_INTERVAL_MS = 8000

export default function Step4({ systemPrompt, voiceId, onEvaluate }) {
  const [interimText, setInterimText] = useState('')
  const [messages, setMessages] = useState([])
  const [status, setStatus] = useState('connecting')
  const [showConversation, setShowConversation] = useState(false)
  const [isWaitingForAssistant, setIsWaitingForAssistant] = useState(false)

  const socketRef = useRef(null)
  const endedRef = useRef(false)
  const unmountedRef = useRef(false)
  const historyRef = useRef(null)
  const mediaStreamRef = useRef(null)
  const audioContextRef = useRef(null)
  const conversationIdRef = useRef(null)
  const isSpeakingRef = useRef(false)

  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const videoStreamRef = useRef(null)
  const captureLoopRef = useRef(null)
  const photosRef = useRef([])

  if (conversationIdRef.current === null) {
    conversationIdRef.current = crypto.randomUUID()
  }

  const stopMicrophone = () => {
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop())
    mediaStreamRef.current = null
    audioContextRef.current?.close()
    audioContextRef.current = null
  }

  const stopCaptureLoop = () => {
    if (captureLoopRef.current) {
      clearInterval(captureLoopRef.current)
      captureLoopRef.current = null
    }
  }

  const captureFrame = () => {
    const video = videoRef.current
    const canvas = canvasRef.current
    if (!video || !canvas || video.readyState < 2) {
      return null
    }

    canvas.width = video.videoWidth || 320
    canvas.height = video.videoHeight || 240
    canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
    return canvas.toDataURL('image/jpeg', 0.7)
  }

  const captureIfRoom = () => {
    if (photosRef.current.length >= MAX_PHOTOS_PER_TURN) {
      stopCaptureLoop()
      return
    }

    const frame = captureFrame()
    if (frame) {
      photosRef.current = [...photosRef.current, frame]
    }
  }

  const startCaptureLoop = () => {
    stopCaptureLoop()
    captureIfRoom()
    captureLoopRef.current = setInterval(captureIfRoom, CAPTURE_INTERVAL_MS)
  }

  const stopCamera = () => {
    stopCaptureLoop()
    videoStreamRef.current?.getTracks().forEach((track) => track.stop())
    videoStreamRef.current = null
  }

  const playAssistantVoice = async (text, messageId) => {
    isSpeakingRef.current = true
    photosRef.current = []
    startCaptureLoop()
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
      stopCaptureLoop()

      const listeningImages = photosRef.current
      photosRef.current = []
      if (listeningImages.length > 0) {
        setMessages((prev) =>
          prev.map((m) => (m.id === messageId ? { ...m, images: listeningImages } : m))
        )
      }

      socketRef.current?.send(JSON.stringify({ type: 'resume_listening' }))
      startCaptureLoop()
      setIsWaitingForAssistant(false)
    }
  }

  const connectSocket = () => {
    const socket = new WebSocket(wsUrl('/ws/conversation'))
    socketRef.current = socket

    socket.onopen = () => {
      setStatus('open')
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
        setIsWaitingForAssistant(true)
        stopCaptureLoop()
        const images = photosRef.current
        photosRef.current = []
        setMessages((prev) => [
          ...prev,
          { role: 'user', text: data.text, sentiment: data.sentiment, images },
        ])
      } else if (data.type === 'assistant') {
        const messageId = crypto.randomUUID()
        setMessages((prev) => [...prev, { id: messageId, role: 'assistant', text: data.text }])
        playAssistantVoice(data.text, messageId)
      } else if (data.type === 'ended') {
        endedRef.current = true
        setStatus('ended')
        stopMicrophone()
        stopCamera()
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
      setMessages((prev) => [
        ...prev,
        { role: 'system', text: 'Connection lost.' },
      ])
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
        const videoStream = await navigator.mediaDevices.getUserMedia({ video: true })

        if (cancelled) {
          videoStream.getTracks().forEach((track) => track.stop())
          return
        }

        videoStreamRef.current = videoStream
        if (videoRef.current) {
          videoRef.current.srcObject = videoStream
          videoRef.current.onloadedmetadata = () => startCaptureLoop()
        }
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          { role: 'system', text: `Camera error: ${err.message}` },
        ])
      }
    })()

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
      socketRef.current?.close()
      workletNode?.disconnect()
      stopMicrophone()
      stopCamera()
    }
  }, [systemPrompt])

  useEffect(() => {
    if (historyRef.current) {
      historyRef.current.scrollTop = historyRef.current.scrollHeight
    }
  }, [messages, interimText])

  const endConversation = () => {
    endedRef.current = true
    socketRef.current?.send(JSON.stringify({ type: 'end', confirm_end: true }))
    socketRef.current?.close()
    stopMicrophone()
    stopCamera()
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
    onEvaluate(messages)
  }

  return (
    <div className="step">
      <h2>Step 4: Conversation</h2>

      <label>
        Temporary input
        <div className="temp-input">
          {interimText ||
            (status === 'ended' ? '' : isWaitingForAssistant ? 'Responding...' : 'Listening...')}
        </div>
      </label>

      <video
        ref={videoRef}
        className="camera-preview"
        autoPlay
        muted
        playsInline
      />
      <canvas ref={canvasRef} style={{ display: 'none' }} />

      {showConversation && (
        <div className="messages" ref={historyRef}>
          {messages.map((message, index) => (
            <div key={index} className={`message ${message.role}`}>
              {message.text}
              {message.sentiment ? ` [${message.sentiment}]` : ''}
            </div>
          ))}
        </div>
      )}

      <label className="show-conversation-toggle">
        <input
          type="checkbox"
          checked={showConversation}
          onChange={(e) => setShowConversation(e.target.checked)}
        />
        Show conversation
      </label>

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
