import { describe, expect, it } from 'vitest'
import { wikilinksToMarkdown, wikilinkTarget } from './wikilinks'

describe('wikilinks', () => {
  it('convierte [[Nota]] en un enlace con el esquema interno', () => {
    expect(wikilinksToMarkdown('Ver [[SLM]].')).toBe('Ver [SLM](wikilink:SLM).')
  })

  it('usa el alias y conserva la ruta como destino', () => {
    expect(wikilinksToMarkdown('[[modelos/SLM|modelos pequeños]]')).toBe(
      '[modelos pequeños](wikilink:modelos%2FSLM)',
    )
  })

  it('muestra solo el nombre de la nota si no hay alias, e ignora el #encabezado', () => {
    expect(wikilinksToMarkdown('[[agentes/Tool calling#Riesgos]]')).toBe(
      '[Tool calling](wikilink:agentes%2FTool%20calling)',
    )
  })

  it('recupera el destino de un href interno y descarta los demás', () => {
    expect(wikilinkTarget('wikilink:modelos%2FSLM')).toBe('modelos/SLM')
    expect(wikilinkTarget('https://arxiv.org')).toBeNull()
  })
})
