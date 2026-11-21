import Markdown, { type Components } from 'react-markdown'
import { WIKI_PREFIX, wikilinksToMarkdown } from './wikilinks'

// react-markdown no interpreta HTML incrustado, así que el Markdown que escribe
// el LLM no puede inyectar código en la página.

const components: Components = {
  a({ href, children }) {
    if (href?.startsWith(WIKI_PREFIX)) {
      const target = decodeURIComponent(href.slice(WIKI_PREFIX.length))
      return (
        <span className="wikilink" title={`Nota de la bóveda: ${target}`}>
          {children}
        </span>
      )
    }
    // Enlaces externos (fuentes): siempre en otra pestaña y sin acceso a esta ventana.
    return (
      <a href={href} target="_blank" rel="noreferrer noopener">
        {children}
      </a>
    )
  },
}

// Por defecto react-markdown descarta las URL con esquemas peligrosos (javascript:...).
// Dejamos pasar también nuestro esquema «wikilink:», que solo pinta un <span>.
const urlTransform = (url: string): string =>
  url.startsWith(WIKI_PREFIX) || /^(https?:|mailto:|#)/i.test(url) ? url : ''

export default function NoteMarkdown({ markdown }: { markdown: string }) {
  return (
    <div className="note-markdown">
      <Markdown components={components} urlTransform={urlTransform}>
        {wikilinksToMarkdown(markdown)}
      </Markdown>
    </div>
  )
}
