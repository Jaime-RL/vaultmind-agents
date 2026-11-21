// Convierte [[destino|alias]] (y [[destino#sección]]) en un enlace Markdown con un
// esquema propio («wikilink:») para que NoteMarkdown lo pinte como nota de la bóveda.
const WIKILINK = /\[\[([^\]|#^]+)(?:[#^][^\]|]*)?(?:\|([^\]]+))?\]\]/g
export const WIKI_PREFIX = 'wikilink:'

export function wikilinksToMarkdown(markdown: string): string {
  return markdown.replace(WIKILINK, (_match, target: string, alias?: string) => {
    const label = (alias ?? target).trim()
    return `[${label}](${WIKI_PREFIX}${encodeURIComponent(target.trim())})`
  })
}
