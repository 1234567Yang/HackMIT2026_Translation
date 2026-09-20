import { useEffect, useState } from 'react'

async function getMessageEmotion(images) {
  if (!images || images.length === 0) {
    return null
  }

  const results = await Promise.all(
    images.map(async (dataUrl) => {
      try {
        const blob = await (await fetch(dataUrl)).blob()
        const formData = new FormData()
        formData.append('image', blob, 'frame.jpg')

        const response = await fetch('/analyze_emotion', {
          method: 'POST',
          body: formData,
        })
        const data = await response.json()
        return data.emotion || null
      } catch {
        return null
      }
    })
  )

  const validResults = results.filter(Boolean)
  if (validResults.length === 0) {
    return null
  }

  const averaged = {}
  Object.keys(validResults[0]).forEach((key) => {
    averaged[key] =
      validResults.reduce((sum, emotion) => sum + (emotion[key] || 0), 0) / validResults.length
  })

  return averaged
}

export default function Step5({ messages, onRestart }) {
  const [suggestions, setSuggestions] = useState({})
  const [emotionNotes, setEmotionNotes] = useState({})
  const [overallSuggestion, setOverallSuggestion] = useState('')
  const [isAnalyzing, setIsAnalyzing] = useState(true)
  const [singleProgress, setSingleProgress] = useState({ done: 0, total: 0 })
  const [emotionProgress, setEmotionProgress] = useState({ done: 0, total: 0 })
  const [overallProgress, setOverallProgress] = useState({ done: 0, total: 1 })

  useEffect(() => {
    let cancelled = false

    async function runAnalysis() {
      setIsAnalyzing(true)

      const userMessages = messages
        .map((message, index) => ({ message, index }))
        .filter(({ message }) => message.role === 'user')

      const emotionTargets = [
        ...userMessages.map(({ message, index }) => ({ message, index, contextType: 'speaking' })),
        ...messages
          .map((message, index) => ({ message, index }))
          .filter(({ message }) => message.role === 'assistant' && message.images?.length > 0)
          .map(({ message, index }) => ({ message, index, contextType: 'listening' })),
      ].sort((a, b) => a.index - b.index)

      setSingleProgress({ done: 0, total: userMessages.length })
      setEmotionProgress({ done: 0, total: emotionTargets.length })
      setOverallProgress({ done: 0, total: 1 })

      const singleResponsePromise = Promise.all(
        userMessages.map(({ message, index }) =>
          fetch('/analyze_single_response', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: message.text }),
          })
            .then((response) => response.json())
            .then((data) => {
              if (data.suggestions && data.suggestions.length > 0) {
                setSuggestions((prev) => ({ ...prev, [index]: data.suggestions }))
              }
            })
            .catch(() => {})
            .finally(() => setSingleProgress((prev) => ({ ...prev, done: prev.done + 1 })))
        )
      )

      const emotionPromise = (async () => {
        for (const { message, index, contextType } of emotionTargets) {
          if (cancelled) {
            return
          }

          const emotion = await getMessageEmotion(message.images)
          const previousMessages = messages
            .slice(Math.max(0, index - 2), index)
            .map((m) => ({ role: m.role, text: m.text }))

          await fetch('/analyze_step_emotion', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              previous_messages: previousMessages,
              emotion,
              message: { role: message.role, text: message.text },
              context_type: contextType,
            }),
          })
            .then((response) => response.json())
            .then((data) => {
              const feedback = (data.feedback || '').trim()
              if (feedback && feedback !== 'no_problem') {
                setEmotionNotes((prev) => ({ ...prev, [index]: feedback }))
              }
            })
            .catch(() => {})

          setEmotionProgress((prev) => ({ ...prev, done: prev.done + 1 }))
        }
      })()

      await Promise.all([singleResponsePromise, emotionPromise])
      if (cancelled) {
        return
      }

      const conversationText = messages
        .filter((message) => message.role === 'user' || message.role === 'assistant')
        .map((message) => `${message.role === 'user' ? 'User' : 'Assistant'}: ${message.text}`)
        .join('\n')

      await fetch('/analyze_whole_conversation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ conversation: conversationText }),
      })
        .then((response) => response.json())
        .then((data) => setOverallSuggestion(data.feedback || ''))
        .catch(() => {})
        .finally(() => setOverallProgress((prev) => ({ ...prev, done: prev.done + 1 })))

      if (!cancelled) {
        setIsAnalyzing(false)
      }
    }

    runAnalysis()

    return () => {
      cancelled = true
    }
  }, [messages])

  return (
    <div className="step">
      <h2>Step 5: Evaluate</h2>

      {isAnalyzing && (
        <div className="analyzing-label">
          Analyzing single response ({singleProgress.done}/{singleProgress.total}), Analyzing
          step-by-step emotion ({emotionProgress.done}/{emotionProgress.total}), Analyzing overall
          conversation ({overallProgress.done}/{overallProgress.total})
        </div>
      )}

      <div className="messages">
        {messages.map((message, index) => {
          const suggestionList = suggestions[index]
          const emotionNote = emotionNotes[index]
          const hasIssue = message.role === 'user' && Boolean(suggestionList?.length)
          const hasEmotionIssue = Boolean(emotionNote)

          return (
            <div key={index} className={`message-row ${message.role}`}>
              <div className="message-icons">
                {hasEmotionIssue && (
                  <span
                    className="message-icon warning-icon"
                    title="Emotion warning"
                    onClick={() => alert(emotionNote)}
                  >
                    ⚠️
                  </span>
                )}
                {hasIssue && (
                  <span
                    className="message-icon error-icon"
                    title="Speech issue"
                    onClick={() => alert(suggestionList.join('\n\n'))}
                  >
                    ❌
                  </span>
                )}
              </div>
              <div className={`message ${message.role}${hasIssue ? ' has-issue' : ''}`}>
                {message.text}
              </div>
            </div>
          )
        })}
      </div>

      {overallSuggestion && (
        <div className="overall-suggestions">
          <h3>Overall suggestions</h3>
          <p>{overallSuggestion}</p>
        </div>
      )}

      <div className="actions">
        <span />
        <button onClick={onRestart}>Start Over</button>
      </div>
    </div>
  )
}
