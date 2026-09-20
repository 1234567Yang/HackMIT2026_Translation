import { useState } from 'react'
import Step1 from './steps/Step1.jsx'
import Step2 from './steps/Step2.jsx'
import Step3 from './steps/Step3.jsx'
import Step4 from './steps/Step4.jsx'
import Step5 from './steps/Step5.jsx'

const initialAnswers = {
  who_context: '',
  who_talking_to: '',
  what_to_talk_about: '',
  personality: '',
  example: '',
}

export default function App() {
  const [step, setStep] = useState(1)
  const [answers, setAnswers] = useState(initialAnswers)
  const [finalInstruction, setFinalInstruction] = useState('')
  const [voiceId, setVoiceId] = useState('')
  const [conversationMessages, setConversationMessages] = useState([])

  const update = (fields) => setAnswers((prev) => ({ ...prev, ...fields }))

  const restart = () => {
    setAnswers(initialAnswers)
    setFinalInstruction('')
    setVoiceId('')
    setStep(1)
  }

  const startConversation = (instruction, voice) => {
    setFinalInstruction(instruction)
    setVoiceId(voice)
    setStep(4)
  }

  return (
    <div className="app">
      <h1>Conversation Setup</h1>
      <div className="steps-indicator">Step {step} of 5</div>

      {step === 1 && (
        <Step1 answers={answers} onChange={update} onNext={() => setStep(2)} />
      )}

      {step === 2 && (
        <Step2
          answers={answers}
          onChange={update}
          onBack={() => setStep(1)}
          onNext={() => setStep(3)}
        />
      )}

      {step === 3 && (
        <Step3
          answers={answers}
          onBack={() => setStep(2)}
          onRestart={restart}
          onStartConversation={startConversation}
        />
      )}

      {step === 4 && (
        <Step4
          systemPrompt={finalInstruction}
          voiceId={voiceId}
          onEvaluate={(msgs) => {
            setConversationMessages(msgs)
            setStep(5)
          }}
        />
      )}

      {step === 5 && <Step5 messages={conversationMessages} onRestart={restart} />}
    </div>
  )
}
