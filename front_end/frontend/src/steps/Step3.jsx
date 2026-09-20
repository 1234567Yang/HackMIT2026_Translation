import { useState } from 'react'

export default function Step3({ answers, onBack, onRestart, onStartConversation }) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState('')
  const [error, setError] = useState('')
  const [hasGenerated, setHasGenerated] = useState(false)
  const [voiceId, setVoiceId] = useState('')

  const runReview = async () => {
    setHasGenerated(true)
    setLoading(true)
    setError('')
    setResult('')
    setVoiceId('')

    try {
      const response = await fetch('/api/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(answers),
      })

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data.error || 'Review failed')
      }

      setResult(data.improved_prompt)

      try {
        const voiceResponse = await fetch('/getbestvoice', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt: data.improved_prompt }),
        })
        const voiceData = await voiceResponse.json()
        if (voiceData.voice_id) {
          setVoiceId(voiceData.voice_id)
        }
      } catch {
        // best-effort; /generate_voice falls back to a default voice
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="step">
      <h2>Step 3: Review</h2>

      <div className="summary">
        <p>
          <strong>Who you are:</strong> {answers.who_context}
        </p>
        <p>
          <strong>Who you're talking to:</strong> {answers.who_talking_to}
        </p>
        <p>
          <strong>Topic:</strong> {answers.what_to_talk_about}
        </p>
        <p>
          <strong>Personality:</strong> {answers.personality}
        </p>
        <p>
          <strong>Example:</strong> {answers.example}
        </p>
      </div>

      <div className="actions">
        <button onClick={onBack} disabled={loading}>
          Back
        </button>
        <button onClick={runReview} disabled={loading || hasGenerated}>
          {loading ? 'Generating...' : 'Generate Better Instruction'}
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {result && (
        <div className="result">
          <h3>Improved instruction</h3>
          <textarea
            rows={8}
            value={result}
            onChange={(e) => setResult(e.target.value)}
          />
          {voiceId && <span className="voice-tag">Voice: {voiceId}</span>}
          <button onClick={() => onStartConversation(result, voiceId)}>
            Start Conversation
          </button>
          <button onClick={onRestart}>Start Over</button>
        </div>
      )}
    </div>
  )
}
