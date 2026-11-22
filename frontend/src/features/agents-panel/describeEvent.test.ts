import { describe, expect, it } from 'vitest'
import { describeToolCall } from './describeEvent'

describe('describeToolCall', () => {
  it('traduce las búsquedas de las dos fuentes del Investigador', () => {
    expect(describeToolCall('search_arxiv', { query: 'mtp' })).toBe('Buscando en arXiv: «mtp»')
    expect(describeToolCall('search_semantic_scholar', { query: 'mtp' })).toBe(
      'Buscando en Semantic Scholar: «mtp»',
    )
    expect(describeToolCall('otra', {})).toBe('Usando la herramienta otra…')
  })
})
