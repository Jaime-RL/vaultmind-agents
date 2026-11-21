import { useState, type FormEvent } from 'react'

// Límites de ResearchRequest en contracts/research.schema.json.
const MIN = 3
const MAX = 200

interface Props {
  busy: boolean
  onSubmit: (topic: string) => void
}

export function ResearchForm({ busy, onSubmit }: Props) {
  const [topic, setTopic] = useState('')
  const trimmed = topic.trim()
  const valid = trimmed.length >= MIN && trimmed.length <= MAX

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (valid && !busy) onSubmit(trimmed)
  }

  return (
    <form className="research-form" onSubmit={handleSubmit}>
      <label htmlFor="topic" className="visually-hidden">
        Tema a investigar
      </label>
      <input
        id="topic"
        className="research-form__input"
        type="text"
        placeholder="Tema a investigar (p. ej., SLMs con tool calling)"
        value={topic}
        maxLength={MAX}
        onChange={(event) => setTopic(event.target.value)}
        disabled={busy}
      />
      <button type="submit" className="button button--primary" disabled={!valid || busy}>
        {busy ? 'Investigando…' : 'Investigar'}
      </button>
    </form>
  )
}
