"use client"

import { BlockMath } from "react-katex"

interface FormulaBlockProps {
  math: string
}

export function FormulaBlock({ math }: FormulaBlockProps) {
  return (
    <div className="formula-block">
      <BlockMath math={math} />
    </div>
  )
}
