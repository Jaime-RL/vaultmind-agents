// Convierte [[destino|alias]] (y [[destino#sección]]) en un enlace Markdown con un
// esquema propio («wikilink:») para que NoteMarkdown lo pinte como nota de la bóveda.
const WIKILINK = /\[\[([^\]|#^]+)(?:[#^][^\]|]*)?(?:\|([^\]]+))?\]\]/g
export const WIKI_PREFIX = 'wikilink:'

export function wikilinksToMarkdown(markdown: string): string {
  return markdown.replace(WIKILINK, (_match, target: string, alias?: string) => {
    // Sin alias, Obsidian muestra el nombre de la nota, no su ruta: «agentes/Tool calling» → «Tool calling».
    const label = (alias ?? target.split('/').pop() ?? target).trim()
    return `[${label}](${WIKI_PREFIX}${encodeURIComponent(target.trim())})`
  })
}
