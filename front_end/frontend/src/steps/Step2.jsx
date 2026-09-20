export default function Step2({ answers, onChange, onBack, onNext }) {
  const canProceed = answers.personality.trim() && answers.example.trim()

  return (
    <div className="step">
      <h2>Step 2: Personality</h2>

      <label>
        Describe the personality of the person you want to talk to.
        <textarea
          rows={3}
          value={answers.personality}
          onChange={(e) => onChange({ personality: e.target.value })}
        />
      </label>

      <label>
        Give an example of that personality.
        <textarea
          rows={3}
          value={answers.example}
          onChange={(e) => onChange({ example: e.target.value })}
        />
      </label>

      <div className="actions">
        <button onClick={onBack}>Back</button>
        <button disabled={!canProceed} onClick={onNext}>
          Next
        </button>
      </div>
    </div>
  )
}
