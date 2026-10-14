import type { ReactNode } from 'react'
import { ResponsiveContainer } from 'recharts'
import { useTheme } from '../theme'

/** Shared axis/grid/tooltip props so every chart reads as one system in both themes. */
export function useChartStyle() {
  const { palette } = useTheme()
  return {
    palette,
    color: (i: number) => palette.series[i % palette.series.length],
    axis: { stroke: palette.axis, tick: { fill: palette.axis, fontSize: 12 }, tickLine: false, axisLine: { stroke: palette.grid } },
    grid: { stroke: palette.grid, strokeDasharray: '3 3', vertical: false },
    tooltip: {
      contentStyle: { background: palette.tooltipBg, border: `1px solid ${palette.tooltipBorder}`, borderRadius: 8, color: palette.text, fontSize: 13 },
      labelStyle: { color: palette.text, fontWeight: 600 },
      itemStyle: { color: palette.text },
      cursor: { fill: palette.grid, opacity: 0.4 },
    },
    legend: { wrapperStyle: { fontSize: 12, color: palette.axis } },
  }
}

export function ChartBox({ height = 280, children }: { height?: number; children: ReactNode }) {
  return (
    <div className="chart-box" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        {children as React.ReactElement}
      </ResponsiveContainer>
    </div>
  )
}
