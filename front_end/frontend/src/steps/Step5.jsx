import { useEffect, useState } from 'react'

export default function Step5({ messages, onRestart }) {
  const [suggestions, setSuggestions] = useState({})
  const [overallSuggestion, setOverallSuggestion] = useState('')

  useEffect(() => {
    messages.forEach((message, index) => {
      if (message.role !== 'user') {
        return
      }

      fetch('/analyze_single_response', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: message.text }),
      })
        .then((response) => response.json())
        .then((data) => {
          if (data.suggestion) {
            setSuggestions((prev) => ({ ...prev, [index]: data.suggestion }))
          }
        })
        .catch(() => {})
    })

    const conversationText = messages
      .filter((message) => message.role === 'user' || message.role === 'assistant')
      .map((message) => `${message.role === 'user' ? 'User' : 'Assistant'}: ${message.text}`)
      .join('\n')

    fetch('/analyze_whole_conversation', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conversation: conversationText }),
    })
      .then((response) => response.json())
      .then((data) => setOverallSuggestion(data.feedback || ''))
      .catch(() => {})
  }, [messages])

  return (
    <div className="step">
      <h2>Step 5: Evaluate</h2>

      <div className="messages">
        {messages.map((message, index) => {
          const suggestion = suggestions[index]
          const hasIssue = message.role === 'user' && suggestion

          return (
            <div
              key={index}
              className={`message ${message.role}${hasIssue ? ' has-issue' : ''}`}
              onClick={hasIssue ? () => alert(suggestion) : undefined}
            >
              {message.text}
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
