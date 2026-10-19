"use client"

import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import type { ForecastResponse } from "@/lib/api"

interface ForecastChartProps {
  data: ForecastResponse
  formatDate: (value: string) => string
}

export function ForecastChart({ data, formatDate }: ForecastChartProps) {
  const chartData = [
    ...data.history.map((row) => ({
      date: row.date,
      inventory: row.inventory,
      safetyStock: row.safetyStock,
      predictedInventory: null,
      predictedSafetyStock: null,
      inventoryCI: null as [number, number] | null,
      safetyStockCI: null as [number, number] | null,
      shortage: 0,
    })),
    ...data.forecast.map((row) => ({
      date: row.date,
      inventory: null,
      safetyStock: null,
      predictedInventory: row.predictedInventory,
      predictedSafetyStock: row.predictedSafetyStock,
      inventoryCI: row.inventoryLower != null && row.inventoryUpper != null
        ? [row.inventoryLower, row.inventoryUpper] as [number, number]
        : null,
      safetyStockCI: row.safetyStockLower != null && row.safetyStockUpper != null
        ? [row.safetyStockLower, row.safetyStockUpper] as [number, number]
        : null,
      shortage: row.shortage,
    })),
  ]

  const shortageRanges = data.forecast
    .filter((row) => row.shortage > 0)
    .map((row) => row.date)
  const forecastStartDate = data.forecast[0]?.date

  const axisValues = chartData
    .flatMap((row) => [
      row.inventory,
      row.safetyStock,
      row.predictedInventory,
      row.predictedSafetyStock,
    ])
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value))

  const yDomain: [number, number] = axisValues.length
    ? (() => {
      const minValue = Math.min(...axisValues)
      const maxValue = Math.max(...axisValues)
      const padding = Math.max((maxValue - minValue) * 0.15, 1)
      return [minValue - padding, maxValue + padding]
    })()
    : [0, 1]

  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" tickFormatter={formatDate} minTickGap={24} />
        {/* <YAxis domain={yDomain} /> */}
        <YAxis />
        <Tooltip labelFormatter={formatDate} />
        <Legend />
        <Line type="monotone" dataKey="inventory" stroke="#52525b" strokeWidth={2} dot={false} name="Inventory History" connectNulls={false} />
        <Line type="monotone" dataKey="safetyStock" stroke="#16a34a" strokeWidth={2} dot={false} name="Safety Stock History" connectNulls={false} />
        <Line type="monotone" dataKey="predictedInventory" stroke="#2563eb" strokeWidth={2} strokeDasharray="5 5" dot={{ r: 2 }} name="Inventory Forecast" connectNulls={false} />
        <Line type="monotone" dataKey="predictedSafetyStock" stroke="#f97316" strokeWidth={2} strokeDasharray="5 5" dot={{ r: 2 }} name="Safety Stock Forecast" connectNulls={false} />
        {forecastStartDate ? (
          <ReferenceLine
            x={forecastStartDate}
            stroke="#94a3b8"
            strokeDasharray="4 4"
            label={{ value: "Forecast Start", position: "insideTopRight", fill: "#64748b", fontSize: 12 }}
          />
        ) : null}
        {shortageRanges.map((date) => (
          <ReferenceArea key={date} x1={date} x2={date} strokeOpacity={0} fill="#ef4444" fillOpacity={0.16} />
        ))}
      </ComposedChart>
    </ResponsiveContainer>
  )
}
