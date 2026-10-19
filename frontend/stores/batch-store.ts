import { create } from "zustand"
import type { BatchResponse } from "@/lib/api"

type BatchStore = {
  result: BatchResponse | null
  setResult: (result: BatchResponse | null) => void
}

export const useBatchStore = create<BatchStore>((set) => ({
  result: null,
  setResult: (result) => set({ result }),
}))