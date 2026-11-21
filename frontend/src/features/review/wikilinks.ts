// Las notas usan [[wikilinks]] de Obsidian, que el Markdown estándar no entiende.
// Los convertimos en enlaces con un esquema propio (wikilink:) que el renderizador
// pinta como etiquetas: así se ve a qué notas de la bóveda conecta la propuesta.

const WIKILINK = /\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]/g

export const WIKILINK_SCHEME = 'wikilink:'

/** [[ruta/Nota|alias]] → [alias](wikilink:ruta/Nota) */
export function wikilinksToMarkdown(markdown: string): string {
  return markdown.replace(WIKILINK, (_match, target: string, alias?: string) => {
    const label = (alias ?? target.split('/').at(-1) ?? target).trim()
    return `[${label}](${WIKILINK_SCHEME}${encodeURIComponent(target.trim())})`
  })
}

export function wikilinkTarget(href: string): string | null {
  return href.startsWith(WIKILINK_SCHEME) ? decodeURIComponent(href.slice(WIKILINK_SCHEME.length)) : null
}
