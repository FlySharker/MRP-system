"use client"

import dynamic from "next/dynamic"
import { useEffect, useState } from "react"
import { BrainCircuit, RotateCcw, SearchCheck, Settings2, X } from "lucide-react"
import { useTranslation } from "react-i18next"
import { AppShell } from "@/components/app-shell"
import { analyzeMaterial, getLlmConfig, searchMaterials, type AnalysisResponse, type LlmProvider } from "@/lib/api"

const InventoryChart = dynamic(
  () => import("@/components/charts/inventory-chart").then((m) => m.InventoryChart),
  { ssr: false, loading: () => <div className="chart-stage chart-loading">Loading chart...</div> }
)

const FormulaBlock = dynamic(
  () => import("@/components/charts/formula-block").then((m) => m.FormulaBlock),
  { ssr: false }
)

type ConfigState = {
  time_window_size: string
  window_size: number
  window_unit: "D" | "W" | "M" | "Y"
  min_interval_len: number
}

type LlmDefaults = {
  enabled: boolean
  default_language: "zh" | "en"
  default_provider: LlmProvider
}

const defaultConfig: ConfigState = {
  time_window_size: "14D",
  window_size: 14,
  window_unit: "D",
  min_interval_len: 1,
}

const fallbackLlmDefaults: LlmDefaults = {
  enabled: true,
  default_language: "zh",
  default_provider: "modelscope",
}

function formatDate(value: string, locale: string) {
  return new Date(value).toLocaleDateString(locale)
}

export default function AnalyzePage() {
  const { t, i18n } = useTranslation()
  const locale = i18n.language === "en" ? "en-US" : "zh-CN"
  // const [material, setMaterial] = useState("")
  const [material, setMaterial] = useState(() => {
    if (typeof window !== "undefined") {
      return sessionStorage.getItem("analyze_material") || ""
    }
    return ""
  })
  // const [config, setConfig] = useState<ConfigState>(defaultConfig)
  const [config, setConfig] = useState<ConfigState>(() => {
    if (typeof window !== "undefined") {
      const saved = sessionStorage.getItem("analyze_config")
      if (saved) {
        return JSON.parse(saved)
      }
    }
    return defaultConfig
  })
  const [includeLlm, setIncludeLlm] = useState(fallbackLlmDefaults.enabled)
  const [suggestions, setSuggestions] = useState<string[]>([])
  // const [result, setResult] = useState<AnalysisResponse | null>(null)
  const [result, setResult] = useState<AnalysisResponse | null>(() => {
    if (typeof window !== "undefined") {
      const saved = sessionStorage.getItem("analyze_result")
      if (saved) {
        return JSON.parse(saved)
      }
    }
    return null
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [llmLang, setLlmLang] = useState<"zh" | "en">(fallbackLlmDefaults.default_language)
  const [llmProvider, setLlmProvider] = useState<LlmProvider>(fallbackLlmDefaults.default_provider)
  const [llmDefaults, setLlmDefaults] = useState<LlmDefaults>(fallbackLlmDefaults)
  const [configOpen, setConfigOpen] = useState(false)

  useEffect(() => {
    let cancelled = false

    getLlmConfig()
      .then((settings) => {
        if (cancelled) return
        const defaults: LlmDefaults = {
          enabled: settings.enabled,
          default_language: settings.default_language,
          default_provider: settings.default_provider,
        }
        setLlmDefaults(defaults)
        setLlmProvider(defaults.default_provider)
        setLlmLang(defaults.default_language)
        setIncludeLlm(defaults.enabled)
      })
      .catch(() => undefined)

    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (material.trim().length < 2) {
      setSuggestions([])
      return
    }

    const timer = window.setTimeout(() => {
      searchMaterials(material.trim())
        .then((data) => setSuggestions(data.items))
        .catch(() => setSuggestions([]))
    }, 250)

    return () => window.clearTimeout(timer)
  }, [material])


  useEffect(() => {
    sessionStorage.setItem("analyze_material", material)
  }, [material])

  useEffect(() => {
    sessionStorage.setItem("analyze_config", JSON.stringify(config))
  }, [config])

  useEffect(() => {
    if (result) {
      sessionStorage.setItem("analyze_result", JSON.stringify(result))
    } else {
      sessionStorage.removeItem("analyze_result")
    }
  }, [result])

  async function handleAnalyze() {
    if (!material.trim()) {
      setError(t("analyze.materialRequired"))
      setConfigOpen(true)
      return
    }

    try {
      setLoading(true)
      setError("")
      const data = await analyzeMaterial({
        material: material.trim(),
        include_llm: includeLlm,
        language: llmLang,
        llm_provider: llmProvider,
        config: {
          ...config,
          time_window_size: `${config.window_size}${config.window_unit}`,
        },
      })
      setResult(data)
      setConfigOpen(false)
    } catch (err) {
      setResult(null)
      setError(err instanceof Error ? err.message : t("analyze.analysisFailed"))
    } finally {
      setLoading(false)
    }
  }

  function handleReset() {
    setMaterial("")
    setSuggestions([])
    setResult(null)
    setError("")
    setConfig(defaultConfig)
    setIncludeLlm(llmDefaults.enabled)
    setLlmLang(llmDefaults.default_language)
    setLlmProvider(llmDefaults.default_provider)

    sessionStorage.removeItem("analyze_material")
    sessionStorage.removeItem("analyze_includeLlm")
    sessionStorage.removeItem("analyze_llmLang")
    sessionStorage.removeItem("analyze_llmProvider")
    sessionStorage.removeItem("analyze_config")
    sessionStorage.removeItem("analyze_result")
  }

  const ruleEntries = result
    ? [
      {
        key: "gradualShortage",
        label: t("analyze.rules.gradualShortage"),
        hit: result.rules.gradual_shortage,
        hint: t("hint.gradualshortage"),
      },
      {
        key: "fluctuation",
        label: t("analyze.rules.fluctuation"),
        hit: result.rules.fluctuation,
        hint: t("hint.fluctuation"),
      },
      {
        key: "demandSpike",
        label: t("analyze.rules.demandSpike"),
        hit: result.rules.demand_spike,
        hint: t("hint.demandspike"),
      },
      {
        key: "delayedSupply",
        label: t("analyze.rules.delayedSupply"),
        hit: result.rules.toolate,
        hint: t("hint.latesupply"),
      },
    ]
    : []

  const topbarActions = (
    <>
      <button className="button-secondary" type="button" onClick={() => setConfigOpen(true)}>
        <Settings2 size={16} />
        {t("topbar.configuration")}
      </button>
      <button className="button" type="button" onClick={handleAnalyze} disabled={loading}>
        <SearchCheck size={16} />
        {loading ? t("analyze.analyzing") : t("topbar.analyze")}
      </button>
      <button className="button-secondary" type="button" onClick={handleReset}>
        <RotateCcw size={16} />
        {t("topbar.reset")}
      </button>
    </>
  )

  return (
    <AppShell topbarActions={topbarActions} busy={loading} busyLabel={t("analyze.analyzing")}>
      {configOpen ? (
        <div className="modal-backdrop" role="presentation">
          <section className="modal-panel" role="dialog" aria-modal="true" aria-label="Single material configuration">
            <div className="modal-head">
              <div>
                <h3>{t("analyze.analysisConsole")}</h3>
                <p>{material ? material : t("analyze.placeholder")}</p>
              </div>
              <button className="icon-button" type="button" onClick={() => setConfigOpen(false)} aria-label="Close configuration">
                <X size={16} />
              </button>
            </div>

            <div className="form-grid modal-form-grid">
              <div className="field field--stacked">
                <label>{t("analyze.materialCode")}</label>
                <input value={material} onChange={(event) => setMaterial(event.target.value)} placeholder={t("analyze.placeholder")} />
                <label>{t("analyze.minIntervalLength")}</label>
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={config.min_interval_len}
                  onChange={(event) => setConfig((current) => ({ ...current, min_interval_len: Number(event.target.value) }))}
                />
                <div className="field-hint">{t("hint.minIntervalHint")}</div>
                <label>{t("analyze.llmLanguage")}</label>
                <select value={llmLang} onChange={(event) => setLlmLang(event.target.value as "zh" | "en")}>
                  <option value="zh">{t("analyze.Chinese")}</option>
                  <option value="en">{t("analyze.English")}</option>
                </select>
              </div>

              <div className="field">
                <label>{t("analyze.windowSize")}</label>
                <div style={{ display: "flex", gap: "8px" }}>
                  <input
                    type="number"
                    min={1}
                    max={365}
                    value={config.window_size}
                    onChange={(event) => setConfig((current) => ({ ...current, window_size: Number(event.target.value) }))}
                    style={{ flex: 1, minWidth: 0 }}
                  />
                  <select
                    value={config.window_unit}
                    onChange={(event) =>
                      setConfig((current) => ({
                        ...current,
                        window_unit: event.target.value as "D" | "W" | "M" | "Y",
                      }))
                    }
                    style={{ minWidth: 0 }}
                  >
                    <option value="D">{t("time.day")}</option>
                    <option value="W">{t("time.week")}</option>
                    <option value="M">{t("time.month")}</option>
                    <option value="Y">{t("time.year")}</option>
                  </select>
                </div>
                <div className="field-hint">{t("hint.windowSizeHint")}</div>
                <label>{t("analyze.llmProvider")}</label>
                <select value={llmProvider} onChange={(event) => setLlmProvider(event.target.value as LlmProvider)}>
                  <option value="modelscope">{t("analyze.providerModelscope")}</option>
                  <option value="ollama">{t("analyze.providerOllama")}</option>
                  <option value="local">{t("analyze.providerLocal")}</option>
                </select>
                <label className="checkbox-pill">
                  <input type="checkbox" checked={includeLlm} onChange={(event) => setIncludeLlm(event.target.checked)} />
                  <BrainCircuit size={14} />
                  {t("analyze.includeLlmDeep")}
                </label>
              </div>
            </div>

            {suggestions.length ? (
              <div className="history-list">
                {suggestions.map((item) => (
                  <button key={item} className="ghost-button" type="button" onClick={() => setMaterial(item)}>
                    {item}
                  </button>
                ))}
              </div>
            ) : null}

            <div className="modal-actions">
              <button className="button-secondary" type="button" onClick={handleReset}>
                <RotateCcw size={16} />
                {t("topbar.reset")}
              </button>
              <button className="button" type="button" onClick={handleAnalyze} disabled={loading}>
                <SearchCheck size={16} />
                {loading ? t("analyze.analyzing") : t("topbar.analyze")}
              </button>
            </div>
          </section>
        </div>
      ) : null}

      {error ? <section className="error-state">{error}</section> : null}

      {loading ? (
        <section className="panel analysis-running">
          <div className="progress-line">
            <span />
          </div>
          <strong>{t("analyze.analyzing")}</strong>
          <p>Running rule checks and preparing the diagnostic result.</p>
        </section>
      ) : result ? (
        <section className="panel chart-card">
          <div className="table-toolbar">
            <strong style={{ fontSize: "20px" }}>{t("analyze.inventoryTimeline")}</strong>
          </div>

          <div className="chart-explanation">
            <strong>{t("hint.safetyStockTitle")}</strong>
            <p style={{ marginTop: 4 }}>{t("hint.safetyStockExplanation")}</p>
            <details style={{ marginTop: 6 }}>
              <summary style={{ cursor: "pointer", fontWeight: 500 }}>{t("hint.viewFormula")}</summary>
              <div style={{ marginTop: 8 }}>
                <FormulaBlock math={"SS_t = Q_q\\left(\\{D_i \\mid t - W \\le i \\le t\\}\\right)"} />
                <p className="muted" style={{ marginTop: 4 }}>
                  {t("hint.safetyStockDetail")}
                </p>
              </div>
            </details>
          </div>

          <div className="chart-explanation" style={{ marginTop: 12 }}>
            <strong>{t("hint.riskScoreTitle")}</strong>
            <p style={{ marginTop: 4 }}>{t("hint.riskScoreExplanation")}</p>
            <details style={{ marginTop: 6 }}>
              <summary style={{ cursor: "pointer", fontWeight: 500 }}>{t("hint.viewRiskFormula")}</summary>
              <div style={{ marginTop: 8 }}>
                <FormulaBlock
                  math={String.raw`
                R =
                \frac{
                \sum\limits_{t \in \mathcal{A}}
                \left(
                \frac{SS_t-\max(I_t,0)}{SS_t}
                \right)\Delta t
                }{
                \sum\limits_{t \in \mathcal{T}}
                \Delta t
                }
                `}
                />
                <p className="muted" style={{ marginTop: 4 }}>
                  {t("hint.riskScoreDetail")}
                </p>
              </div>
            </details>
          </div>

          <div className="chart-stage">
            <InventoryChart chartSeries={result.chartSeries} intervalRanges={result.intervalRanges} formatDate={(value) => formatDate(value, locale)} />
          </div>
        </section>
      ) : !error ? (
        <section className="panel analyze-empty" style={{ color: "var(--muted)" }}>
          <SearchCheck size={40} strokeWidth={1.2} style={{ marginBottom: 16, opacity: 0.4 }} />
          <strong style={{ fontSize: 16, marginBottom: 6 }}>{t("analyze.emptyTitle")}</strong>
          <span style={{ fontSize: 13 }}>{t("analyze.emptyHint")}</span>
        </section>
      ) : null}

      {result ? (
        <article className="panel result-card">
          <div className="section-head">
            <div>
              <strong style={{ fontSize: "20px" }}>{t("analyze.diagnosticSummary")}</strong>
            </div>
            <span className={`status-chip ${result.status}`}>{result.status === "normal" ? t("batch.normal") : t("batch.anomaly")}</span>
          </div>

          <div className="stack-grid">
            <div className="mini-panel">
              <strong>{result.material}</strong>
              <div className="mini-note">
                {t("analyze.materialId")}
              </div>
            </div>

            <div className="mini-panel">
              <strong>{result.intervalRanges.length}</strong>
              <div className="mini-note">
                {t("analyze.intervalCount")}
              </div>
            </div>

            <div className="mini-panel">
              <strong>
                {typeof result.risk_score === "number"
                  ? result.risk_score.toFixed(4)
                  : "-"}
              </strong>

              <div className="mini-note">
                {t("analyze.riskScore")}
              </div>
            </div>

            <div className="mini-panel">
              <div>
                <strong
                  className={`risk-chip ${String(
                    result.risk_level
                  ).toLowerCase()}`}
                >
                  {String(result.risk_level ?? "-")}
                </strong>
              </div>

              <div className="mini-note">
                {t("analyze.riskLevel")}
              </div>
            </div>
          </div>

          <div className="rule-list">
            {ruleEntries.map((rule) => (
              <div key={rule.key} className="rule-item">
                <div className={`rule-title ${rule.hit ? "hit" : "not-hit"}`}>
                  <strong>{rule.label}</strong>: {rule.hit ? t("analyze.hit") : t("analyze.notHit")}
                </div>
                <div className="rule-hint">{rule.hint}</div>
              </div>
            ))}
          </div>

          <div style={{ marginTop: "12px", fontWeight: 600 }}>{t("analyze.llmReason")}</div>
          <pre className="llm-output">{result.llmOutput || t("analyze.noLlmOutput")}</pre>

          <div style={{ marginTop: "12px", fontWeight: 600 }}>{t("analyze.llmRecommendation")}</div>
          <pre className="llm-output">{result.llmRecommendation || t("analyze.noLlmRecommendation")}</pre>
        </article>
      ) : null}
    </AppShell>
  )
}
