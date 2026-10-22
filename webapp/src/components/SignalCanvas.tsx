import { useEffect, useRef, type MutableRefObject } from 'react'

const css = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim()

/**
 * Scrolling EMG trace drawn on a canvas (recharts is too slow for 10 updates a second).
 * Reads the shared buffer on every animation frame, so callers just push samples into it.
 */
export function SignalCanvas({ buffer, capacity, height = 180, label }: { buffer: MutableRefObject<number[]>; capacity: number; height?: number; label: string }) {
  const ref = useRef<HTMLCanvasElement>(null)
  const capacityRef = useRef(capacity)
  capacityRef.current = capacity

  useEffect(() => {
    let frame = 0
    const draw = () => {
      frame = requestAnimationFrame(draw)
      const canvas = ref.current
      if (!canvas) return
      const dpr = window.devicePixelRatio || 1
      const w = canvas.clientWidth
      const h = canvas.clientHeight
      if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
        canvas.width = Math.round(w * dpr)
        canvas.height = Math.round(h * dpr)
      }
      const ctx = canvas.getContext('2d')
      if (!ctx) return
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx.clearRect(0, 0, w, h)
      const muted = css('--muted')
      ctx.font = '12px system-ui, sans-serif'

      const data = buffer.current
      if (!data.length) {
        ctx.fillStyle = muted
        ctx.textAlign = 'center'
        ctx.fillText('No signal yet', w / 2, h / 2)
        return
      }
      // Auto-scale to the visible window, with a minimum span so noise is not blown up.
      let lo = Infinity
      let hi = -Infinity
      for (const v of data) {
        if (v < lo) lo = v
        if (v > hi) hi = v
      }
      const span = Math.max(hi - lo, 100)
      const mid = (hi + lo) / 2
      lo = Math.max(0, mid - span * 0.55)
      hi = Math.min(4095, mid + span * 0.55)
      const pad = 6
      const y = (v: number) => pad + (1 - (v - lo) / (hi - lo || 1)) * (h - pad * 2)

      ctx.strokeStyle = css('--border')
      ctx.lineWidth = 1
      ctx.beginPath()
      for (const f of [0, 0.5, 1]) {
        const gy = Math.round(pad + f * (h - pad * 2)) + 0.5
        ctx.moveTo(0, gy)
        ctx.lineTo(w, gy)
      }
      ctx.stroke()

      const step = w / Math.max(capacityRef.current - 1, 1)
      ctx.strokeStyle = css('--accent')
      ctx.lineWidth = 1.5
      ctx.lineJoin = 'round'
      ctx.beginPath()
      data.forEach((v, i) => (i ? ctx.lineTo(i * step, y(v)) : ctx.moveTo(0, y(v))))
      ctx.stroke()

      ctx.fillStyle = muted
      ctx.textAlign = 'right'
      ctx.fillText(String(Math.round(hi)), w - 4, 16)
      ctx.fillText(String(Math.round(lo)), w - 4, h - 8)
    }
    draw()
    return () => cancelAnimationFrame(frame)
  }, [buffer])

  return <canvas ref={ref} className="signal-canvas" style={{ height }} role="img" aria-label={label} />
}
