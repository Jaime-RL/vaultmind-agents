import { useMemo } from 'react'
import Markdown, { defaultUrlTransform, type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useI18n } from '../../i18n/context'
import type { MessageKey } from '../../i18n/messages'
import { WIKILINK_SCHEME, wikilinksToMarkdown, wikilinkTarget } from './wikilinks'

// Avisos de Obsidian: «> [!warning] Texto». react-markdown los ve como una cita normal y se
// mostraba «[!warning]» tal cual; aquí los convertimos en un aviso con su título.
const CALLOUT_RE = /^\[!([a-z]+)\][+-]?\s*/i
const CALLOUT_TITLE_KEYS: Record<string, MessageKey> = {
  warning: 'callout.warning',
  caution: 'callout.warning',
  danger: 'callout.danger',
  error: 'callout.error',
  note: 'callout.note',
  info: 'callout.info',
  tip: 'callout.tip',
  success: 'callout.success',
  question: 'callout.question',
}

interface HastNode {
  type: string
  value?: string
  children?: HastNode[]
}

function plainText(node: HastNode | undefined): string {
  if (!node) return ''
  if (node.type === 'text') return node.value ?? ''
  return (node.children ?? []).map(plainText).join('')
}

interface Props {
  markdown: string
  /** ids y títulos de las notas que existen en la bóveda, para marcar los enlaces. */
  existing: Set<string>
}

/**
 * Renderiza la nota propuesta.
 *
 * Seguridad: el Markdown lo escribe un LLM, así que es entrada NO confiable.
 * react-markdown no interpreta HTML incrustado (no usamos rehype-raw) y su
 * urlTransform por defecto elimina esquemas peligrosos como javascript:. Solo
 * dejamos pasar además nuestro esquema interno wikilink:.
 */
export function NoteMarkdown({ markdown, existing }: Props) {
  const { t } = useI18n()
  const components = useMemo<Components>(
    () => ({
      blockquote: ({ node, children }) => {
        const text = plainText(node as HastNode | undefined).trim()
        const match = CALLOUT_RE.exec(text)
        if (!match) return <blockquote>{children}</blockquote>
        const kind = match[1]!.toLowerCase()
        return (
          <aside className={`callout callout--${kind}`} role="note">
            <p>
              <span className="callout__title">{CALLOUT_TITLE_KEYS[kind] ? t(CALLOUT_TITLE_KEYS[kind]) : kind}:</span>{' '}
              {text.slice(match[0].length)}
            </p>
          </aside>
        )
      },
      a: ({ href = '', children }) => {
        const target = wikilinkTarget(href)
        if (target !== null) {
          const title = target.split('/').at(-1) ?? target
          const known = existing.has(target) || existing.has(title)
          return (
            <span
              className={`wikilink ${known ? 'wikilink--known' : 'wikilink--new'}`}
              title={known ? `Enlaza con «${target}» de tu bóveda` : `«${target}» aún no existe en tu bóveda`}
            >
              {children}
            </span>
          )
        }
        return (
          <a href={href} target="_blank" rel="noopener noreferrer">
            {children}
          </a>
        )
      },
    }),
    [existing, t],
  )

  return (
    <div className="note-markdown">
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={components}
        urlTransform={(url) => (url.startsWith(WIKILINK_SCHEME) ? url : defaultUrlTransform(url))}
      >
        {wikilinksToMarkdown(markdown)}
      </Markdown>
    </div>
  )
}
