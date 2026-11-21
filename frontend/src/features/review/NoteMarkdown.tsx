import { useMemo } from 'react'
import Markdown, { defaultUrlTransform, type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { WIKILINK_SCHEME, wikilinksToMarkdown, wikilinkTarget } from './wikilinks'

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
  const components = useMemo<Components>(
    () => ({
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
    [existing],
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
