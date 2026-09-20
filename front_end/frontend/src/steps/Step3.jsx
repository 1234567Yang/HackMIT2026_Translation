import { useState } from 'react'

export default function Step3({ answers, onBack, onRestart }) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState('')
  const [error, setError] = useState('')

  const runReview = async () => {
    setLoading(true)
    setError('')
    setResult('')

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
        <button onClick={runReview} disabled={loading}>
          {loading ? 'Generating...' : 'Generate Better Instruction'}
        </button>
      </div>

      {error && <p className="error">{error}</p>}

      {result && (
        <div className="result">
          <h3>Improved instruction</h3>
          <p>{result}</p>
          <button onClick={onRestart}>Start Over</button>
        </div>
      )}
    </div>
  )
}
