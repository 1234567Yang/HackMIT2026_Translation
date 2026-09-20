export default function Step1({ answers, onChange, onNext }) {
  const canProceed =
    answers.who_context.trim() &&
    answers.who_talking_to.trim() &&
    answers.what_to_talk_about.trim()

  return (
    <div className="step">
      <h2>Step 1: The basics</h2>

      <label>
        Who are you in this context?
        <textarea
          rows={2}
          value={answers.who_context}
          onChange={(e) => onChange({ who_context: e.target.value })}
        />
      </label>

      <label>
        Who are you talking to?
        <textarea
          rows={2}
          value={answers.who_talking_to}
          onChange={(e) => onChange({ who_talking_to: e.target.value })}
        />
      </label>

      <label>
        What are you going to talk about?
        <textarea
          rows={3}
          value={answers.what_to_talk_about}
          onChange={(e) => onChange({ what_to_talk_about: e.target.value })}
        />
      </label>

      <div className="actions">
        <span />
        <button disabled={!canProceed} onClick={onNext}>
          Next
        </button>
      </div>
    </div>
  )
}
