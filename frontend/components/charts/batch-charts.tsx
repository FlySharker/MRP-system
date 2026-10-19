"use client"

import { Bar, BarChart, Legend, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts"

const pieColors = ["#4c8b54", "#c98345"]

interface PieDataItem {
  name: string
  value: number
}

interface BarDataItem {
  name: string
  value: number
}

export function StatusPieChart({ data }: { data: PieDataItem[] }) {
  return (
    <ResponsiveContainer>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={74} outerRadius={110}>
          {data.map((entry, index) => (
            <Cell key={entry.name} fill={pieColors[index % pieColors.length]} />
          ))}
        </Pie>
        <Tooltip />
      </PieChart>
    </ResponsiveContainer>
  )
}

export function ReasonBarChart({ data }: { data: BarDataItem[] }) {
  return (
    <ResponsiveContainer>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24 }}>
        <XAxis type="number" stroke="#8d8377" />
        <YAxis dataKey="name" type="category" width={120} stroke="#8d8377" />
        <Tooltip />
        <Bar dataKey="value" fill="#c98345" radius={[0, 8, 8, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
