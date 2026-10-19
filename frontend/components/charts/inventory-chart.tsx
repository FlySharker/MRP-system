"use client"

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts"
import type { AnalysisResponse } from "@/lib/api"

type IntervalRange = AnalysisResponse["intervalRanges"][number]

interface InventoryChartProps {
  chartSeries: AnalysisResponse["chartSeries"]
  intervalRanges: IntervalRange[]
  formatDate: (value: string) => string
}

export function InventoryChart({ chartSeries, intervalRanges, formatDate }: InventoryChartProps) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={chartSeries}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" tickFormatter={formatDate} />
        <YAxis />
        <Tooltip labelFormatter={formatDate} />
        <Legend />
        <Line type="monotone" dataKey="inventory" stroke="#6366f1" strokeWidth={2} dot={{r: 1.5}} activeDot={{ r: 6 }} name="Inventory" />
        <Line type="monotone" dataKey="safetyStock" stroke="#22c55e" strokeWidth={2} dot={{r: 1.5}} activeDot={{ r: 6 }} name="Safety Stock" />
        {/* idx-based rendering */}
        {intervalRanges.map((interval, idx) => {
          const isSinglePoint = interval.start_idx === interval.end_idx

          if (isSinglePoint) {
            return (
              <ReferenceLine
                key={`idx-line-${idx}`}
                x={interval.start_idx}
                stroke="#ef4444"
                strokeWidth={2}
                strokeDasharray="4 4"
              />
            )
          }

          return (
            <ReferenceArea
              key={`idx-area-${idx}`}
              x1={interval.start_idx}
              x2={interval.end_idx}
              strokeOpacity={0}
              fill="#ef4444"
              fillOpacity={0.18}
            />
          )
        })}

        {/* date-based rendering */}
        {intervalRanges.map((interval, idx) => {
          const isSinglePoint = interval.start_date === interval.end_date

          if (isSinglePoint) {
            return (
              <ReferenceLine
                key={`date-line-${idx}`}
                x={interval.start_date}
                stroke="#ef4444"
                strokeWidth={2}
                strokeDasharray="4 4"
              />
            )
          }

          return (
            <ReferenceArea
              key={`date-area-${idx}`}
              x1={interval.start_date}
              x2={interval.end_date}
              strokeOpacity={0}
              fill="#ef4444"
              fillOpacity={0.18}
            />
          )
        })}
      </LineChart>
    </ResponsiveContainer>
  )
}
