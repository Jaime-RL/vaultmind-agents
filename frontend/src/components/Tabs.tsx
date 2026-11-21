import { useId, useRef, type KeyboardEvent, type ReactNode } from 'react'

export interface Tab {
  id: string
  label: string
  /** Contador opcional junto a la etiqueta (p. ej., notas pendientes). */
  badge?: number
  content: ReactNode
}

interface Props {
  tabs: Tab[]
  active: string
  onChange: (id: string) => void
  label: string
}

/**
 * Pestañas accesibles (patrón WAI-ARIA «tabs»): roles tablist/tab/tabpanel y
 * navegación con las flechas del teclado.
 */
export function Tabs({ tabs, active, onChange, label }: Props) {
  const baseId = useId()
  const buttons = useRef<Array<HTMLButtonElement | null>>([])

  const onKeyDown = (event: KeyboardEvent, index: number) => {
    const delta = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0
    if (!delta) return
    const next = (index + delta + tabs.length) % tabs.length
    onChange(tabs[next]!.id)
    buttons.current[next]?.focus()
  }

  return (
    <div className="tabs">
      <div role="tablist" aria-label={label} className="tabs__list">
        {tabs.map((tab, index) => (
          <button
            key={tab.id}
            ref={(el) => {
              buttons.current[index] = el
            }}
            type="button"
            role="tab"
            id={`${baseId}-tab-${tab.id}`}
            aria-selected={tab.id === active}
            aria-controls={`${baseId}-panel-${tab.id}`}
            tabIndex={tab.id === active ? 0 : -1}
            className="tabs__tab"
            onClick={() => onChange(tab.id)}
            onKeyDown={(event) => onKeyDown(event, index)}
          >
            {tab.label}
            {tab.badge ? <span className="tabs__badge">{tab.badge}</span> : null}
          </button>
        ))}
      </div>
      {tabs.map((tab) => (
        <div
          key={tab.id}
          role="tabpanel"
          id={`${baseId}-panel-${tab.id}`}
          aria-labelledby={`${baseId}-tab-${tab.id}`}
          hidden={tab.id !== active}
          className="tabs__panel"
        >
          {tab.content}
        </div>
      ))}
    </div>
  )
}
