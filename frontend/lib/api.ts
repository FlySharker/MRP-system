const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  })

  if (!response.ok) {
    let message = `请求失败: ${response.status}`
    try {
      const data = await response.json()
      message = data.detail ?? message
    } catch { }
    throw new Error(message)
  }

  return response.json() as Promise<T>
}

export type OverviewResponse = {
  materialsCount: number
  recordsCount: number
  plantsCount: number
  dateRange: { start: string; end: string }
  recentHistory: Array<{
    material: string
    status: string
    analyzed_at: string
    llm_label?: number | null
  }>
}

export type AnalysisResponse = {
  material: string
  status: "normal" | "anomaly" | "error"
  error_message?: string
  intervalRanges: Array<{
    start_idx: number
    end_idx: number
    start_date: string
    end_date: string
  }>
  rules: {
    gradual_shortage: boolean
    fluctuation: boolean
    demand_spike: boolean
    toolate: boolean
    delay_steps: Array<number | null>
  }
  chartSeries: Array<{
    date: string
    event: string
    qty: number
    inventory: number
    safetyStock: number
  }>
  risk_score: number
  risk_level: string
  HtmlFigure: string
  llmOutput: string
  llmLabel: number | null
  llmRecommendation: string
  config: {
    windowSize: number
    quantile: number
    minIntervalLen: number
  }
}

export type BatchResponse = {
  metrics: {
    total: number
    normal: number
    anomaly: number
    riskRatio: number
  }
  reasonCounts: Partial<Record<"delayedSupply" | "demandSpike" | "fluctuation" | "gradualShortage", number>>
  summary: Array<Record<string, string | number | boolean | null>>
  history: Array<{
    material: string
    status: string
    analyzed_at: string
    llm_label?: number | null
  }>
}

export type KeyMaterial = {
  material: string
  records: number
  demandVolume: number
  lastDate: string | null
}

export type ForecastResponse = {
  material: string
  status: "success" | "error"
  horizonWeeks: number
  grain: "week"
  historyWeeks: number
  model: {
    inventory: string
    safetyStock: string
    confidence: "low" | "medium" | "high"
    inbound?: string
    outbound?: string
    weekFlowDefinition?: string
    notes?: string[]
  }
  summary: {
    overallRisk: "normal" | "watch" | "high"
    shortageWeeks: number
    maxShortage: number
    firstShortageDate: string | null
  }
  history: Array<{
    date: string
    inventory: number
    safetyStock: number
    inbound?: number
    outbound?: number
    netFlow?: number
  }>
  forecast: Array<{
    week: number
    date: string
    predictedInventory: number
    predictedSafetyStock: number
    shortage: number
    suggestedReplenishment: number
    riskLevel: "normal" | "watch" | "high"
    inventoryLower?: number
    inventoryUpper?: number
    safetyStockLower?: number
    safetyStockUpper?: number
    predictedInbound?: number
    predictedOutbound?: number
    predictedNetFlow?: number
  }>
}

export type LlmProvider = "modelscope" | "ollama" | "local"

export type LlmConfig = {
  enabled: boolean
  default_provider: LlmProvider
  default_language: "zh" | "en"
  temperature: number
  max_tokens: number
  timeout_seconds: number
  retry_count: number
  modelscope: {
    api_key: string
    api_key_set?: boolean
    base_url: string
    model: string
  }
  ollama: {
    host: string
    model: string
    keep_alive: string
  }
  local: {
    model_path: string
    device_map: string
    torch_dtype: "auto" | "float16" | "bfloat16" | "float32"
  }
}

export type LlmTestResponse = {
  ok: boolean
  provider: LlmProvider
  message: string
}

export function getOverview() {
  return apiFetch<OverviewResponse>("/api/overview")
}

export function searchMaterials(query: string) {
  const params = new URLSearchParams({ query, limit: "8" })
  return apiFetch<{ items: string[] }>(`/api/materials?${params.toString()}`)
}

export function analyzeMaterial(payload: {
  material: string
  include_llm: boolean
  language: string
  llm_provider: string
  config: {
    window_size: number
    time_window_size: string
    // quantile: number
    min_interval_len: number
  }
}) {
  return apiFetch<AnalysisResponse>("/api/analyze", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export function analyzeBatch(payload: {
  material_prefix: string
  statuses: string[]
  max_materials: number
  config: {
    window_size: number
    time_window_size: string
    // quantile: number
    min_interval_len: number
  }
}) {
  return apiFetch<BatchResponse>("/api/batch-analyze", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export function getKeyMaterials(limit = 20) {
  return apiFetch<{ items: KeyMaterial[] }>(`/api/forecast/key-materials?limit=${limit}`)
}

export function forecastMaterial(payload: {
  material: string
  horizon_weeks: number
  config: {
    window_size: number
    time_window_size: string
    min_interval_len: number
  }
}) {
  return apiFetch<ForecastResponse>("/api/forecast", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export function getLlmConfig() {
  return apiFetch<LlmConfig>("/api/llm-config")
}

export function saveLlmConfig(payload: LlmConfig) {
  return apiFetch<LlmConfig>("/api/llm-config", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export function testLlmConfig(payload: {
  provider: LlmProvider
  config: LlmConfig
}) {
  return apiFetch<LlmTestResponse>("/api/llm-config/test", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}
