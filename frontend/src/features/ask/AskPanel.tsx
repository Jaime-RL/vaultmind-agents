import { useState, type FormEvent } from 'react'
import { ApiError, askVault } from '../../api/client'
import type { AskResponse } from '../../api/contract.gen'
import { NoteMarkdown } from '../review/NoteMarkdown'
import { describeModel } from './describeModel'
import { useTypewriter } from './useTypewriter'

interface Exchange {
  question: string
  response: AskResponse
}

interface Props {
  existing: Set<string>
  /** Al pulsar una cita: la cámara del grafo vuela a esa nota. */
  onFocusNote: (noteId: string) => void
  ask?: (question: string) => Promise<AskResponse>
}

const EXAMPLES = [
  '¿Qué es LoRA?',
  '¿Qué datos climáticos uso?',
  '¿Cómo funciona el routing de modelos?',
]

/** «Pregunta a tu bóveda»: responde con tus notas y las cita; cada cita lleva a su nodo. */
export function AskPanel({ existing, onFocusNote, ask = askVault }: Props) {
  const [question, setQuestion] = useState('')
  const [history, setHistory] = useState<Exchange[]>([])
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const submit = async (text: string) => {
    const q = text.trim()
    if (q.length < 3 || pending) return
    setPending(q)
    setError(null)
    try {
      const response = await ask(q)
      setHistory((h) => [{ question: q, response }, ...h])
      setQuestion('')
      if (response.citations[0]) onFocusNote(response.citations[0].id)
    } catch (e) {
      setError(e instanceof ApiError || e instanceof Error ? e.message : 'Error desconocido')
    } finally {
      setPending(null)
    }
  }

  const onSubmit = (event: FormEvent) => {
    event.preventDefault()
    void submit(question)
  }

  return (
    <div className="ask-panel">
      <form className="ask-panel__form" onSubmit={onSubmit}>
        <label htmlFor="ask-question" className="ask-panel__label">
          Pregunta a tu bóveda: responde con tus notas y te dice cuáles ha usado.
        </label>
        <div className="ask-panel__row">
          <input
            id="ask-question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="¿Qué sé sobre…?"
            maxLength={500}
            disabled={pending !== null}
          />
          <button
            type="submit"
            className="button button--primary"
            disabled={pending !== null || question.trim().length < 3}
          >
            Preguntar
          </button>
        </div>
        {history.length === 0 && !pending && (
          <p className="ask-panel__examples">
            Prueba:{' '}
            {EXAMPLES.map((example) => (
              <button
                key={example}
                type="button"
                className="chip"
                onClick={() => void submit(example)}
              >
                {example}
              </button>
            ))}
          </p>
        )}
      </form>

      {pending && (
        <p className="ask-panel__pending" role="status">
          Buscando en tus notas: «{pending}»…
        </p>
      )}
      {error && (
        <p className="notice notice--error" role="alert">
          No pude responder: {error}
        </p>
      )}

      <ol className="ask-panel__history">
        {history.map((exchange, index) => (
          <AnswerCard
            key={`${history.length - index}`}
            exchange={exchange}
            existing={existing}
            animate={index === 0}
            onFocusNote={onFocusNote}
          />
        ))}
      </ol>
    </div>
  )
}

interface CardProps {
  exchange: Exchange
  existing: Set<string>
  animate: boolean
  onFocusNote: (noteId: string) => void
}

function AnswerCard({ exchange, existing, animate, onFocusNote }: CardProps) {
  const { question, response } = exchange
  const typed = useTypewriter(response.answer)
  const text = animate ? typed : response.answer
  return (
    <li className="answer">
      <p className="answer__question">{question}</p>
      <NoteMarkdown markdown={text} existing={existing} />
      {response.citations.length > 0 && (
        <p className="answer__citations">
          <span>Notas usadas:</span>
          {response.citations.map((citation) => (
            <button
              key={citation.id}
              type="button"
              className="chip chip--note"
              title="Ver en el grafo"
              onClick={() => onFocusNote(citation.id)}
            >
              {citation.title}
            </button>
          ))}
        </p>
      )}
      <p className="answer__meta">{describeModel(response)}</p>
    </li>
  )
}
