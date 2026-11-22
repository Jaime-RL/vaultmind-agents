import { useEffect, useState } from 'react'

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  typeof window.matchMedia === 'function' &&
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

/**
 * Muestra `text` poco a poco, como si se estuviera escribiendo. La respuesta llega entera
 * (SmartRoute la valida antes de decidir si escala), así que el efecto es solo visual.
 * Con «reducir movimiento» activado, el texto aparece de golpe.
 */
export function useTypewriter(text: string, charsPerTick = 4, tickMs = 16): string {
  const [progress, setProgress] = useState({ text, shown: 0 })
  // Texto nuevo: se reinicia durante el render (patrón recomendado por React en lugar de
  // un setState dentro de un efecto).
  if (progress.text !== text) setProgress({ text, shown: 0 })

  const done = progress.shown >= text.length
  useEffect(() => {
    if (done || prefersReducedMotion()) return
    const timer = setInterval(
      () => setProgress((p) => ({ ...p, shown: Math.min(p.shown + charsPerTick, p.text.length) })),
      tickMs,
    )
    return () => clearInterval(timer)
  }, [done, charsPerTick, tickMs])

  return prefersReducedMotion() ? text : text.slice(0, progress.shown)
}
