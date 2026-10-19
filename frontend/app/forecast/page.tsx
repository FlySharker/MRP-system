"use client"

import dynamic from "next/dynamic"
import { useEffect, useMemo, useState } from "react"
import { RefreshCw, SearchCheck, TrendingUp } from "lucide-react"
import { useTranslation } from "react-i18next"
import { AppShell } from "@/components/app-shell"
import {
  forecastMaterial,
  getKeyMaterials,
  searchMaterials,
  type ForecastResponse,
  type KeyMaterial,
} from "@/lib/api"

const ForecastChart = dynamic(
  () => import("@/components/charts/forecast-chart").then((m) => m.ForecastChart),
  { ssr: false, loading: () => <div className="chart-stage chart-loading">Loading chart...</div> }
)

const FormulaBlock = dynamic(
  () => import("@/components/charts/formula-block").then((m) => m.FormulaBlock),
  { ssr: false }
)

const defaultConfig = {
  window_size: 14,
  window_unit: "D" as "D" | "W" | "M" | "Y",
  min_interval_len: 1,
}

type ForecastPageConfig = typeof defaultConfig

const modelFormula = String.raw`\begin{gathered}
\ell_t = \alpha \left(y_t - s_{t-m}\right) + \left(1-\alpha\right)\left(\ell_{t-1} + \phi b_{t-1}\right) \\
\hat{y}_{t+h} = \ell_t + \left(\phi + \cdots + \phi^h\right)b_t + s_{t-m+h_m}
\end{gathered}`

const replenishmentFormula = String.raw`\begin{gathered}
\mathrm{Gap}_t = \max\left(\widehat{SS}_t - \widehat{I}_t, 0\right) \\
\mathrm{Replenishment}_t = \mathrm{Gap}_t
\end{gathered}`

function formatDate(value: string, locale: string) {
  return new Date(value).toLocaleDateString(locale)
}

export default function ForecastPage() {
  const { t, i18n } = useTranslation()
  const locale = i18n.language === "en" ? "en-US" : "zh-CN"
  const [materials, setMaterials] = useState<KeyMaterial[]>([])
  const [material, setMaterial] = useState(() => {
    if (typeof window !== "undefined") {
      return sessionStorage.getItem("forecast_material") || ""
    }
    return ""
  })
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [result, setResult] = useState<ForecastResponse | null>(() => {
    if (typeof window !== "undefined") {
      const saved = sessionStorage.getItem("forecast_result")
      if (saved) {
        return JSON.parse(saved)
      }
    }
    return null
  })
  const [loading, setLoading] = useState(false)
  const [loadingMaterials, setLoadingMaterials] = useState(false)
  const [error, setError] = useState("")
  const [config, setConfig] = useState<ForecastPageConfig>(() => {
    if (typeof window !== "undefined") {
      const saved = sessionStorage.getItem("forecast_config")
      if (saved) {
        return JSON.parse(saved)
      }
    }
    return defaultConfig
  })

  useEffect(() => {
    setLoadingMaterials(true)
    getKeyMaterials(20)
      .then((data) => {
        setMaterials(data.items)
      })
      .catch((err) => setError(err instanceof Error ? err.message : t("forecast.loadFailed")))
      .finally(() => setLoadingMaterials(false))
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
    sessionStorage.setItem("forecast_material", material)
  }, [material])

  useEffect(() => {
    sessionStorage.setItem("forecast_config", JSON.stringify(config))
  }, [config])

  useEffect(() => {
    if (result) {
      sessionStorage.setItem("forecast_result", JSON.stringify(result))
    } else {
      sessionStorage.removeItem("forecast_result")
    }
  }, [result])

  async function handleForecast(selectedMaterial = material) {
    if (!selectedMaterial.trim()) {
      setError(t("forecast.materialRequired"))
      return
    }

    try {
      setLoading(true)
      setError("")
      const data = await forecastMaterial({
        material: selectedMaterial.trim(),
        horizon_weeks: 12,
        config: {
          window_size: config.window_size,
          time_window_size: `${config.window_size}${config.window_unit}`,
          min_interval_len: config.min_interval_len,
        },
      })
      setMaterial(selectedMaterial.trim())
      setResult(data)
    } catch (err) {
      setResult(null)
      setError(err instanceof Error ? err.message : t("forecast.forecastFailed"))
    } finally {
      setLoading(false)
    }
  }

  function handleReset() {
    setResult(null)
    setError("")
    setConfig(defaultConfig)
    setMaterial("")
    sessionStorage.removeItem("forecast_material")
    sessionStorage.removeItem("forecast_config")
    sessionStorage.removeItem("forecast_result")
  }

  const metrics = useMemo(() => {
    if (!result) {
      return []
    }

    const firstShortage = result.forecast.find((row) => row.shortage > 0)
    const cumulativeShortage = result.forecast.reduce((sum, row) => sum + row.shortage, 0)

    return [
      {
        label: t("forecast.firstShortageWeek"),
        value: firstShortage ? firstShortage.week : "-",
      },
      { label: t("forecast.shortageWeeks"), value: result.summary.shortageWeeks },
      { label: t("forecast.maxShortage"), value: result.summary.maxShortage },
      {
        label: t("forecast.cumulativeShortage"),
        value: cumulativeShortage.toFixed(2),
      },
      { label: t("forecast.modelReliability"), value: t(`forecast.confidenceLabel.${result.model.confidence}`) },
    ]
  }, [result, t])

  const selectedMaterial = result?.material ?? ""
  const forecastSummary = useMemo(() => {
    if (!result) {
      return ""
    }

    const firstShortage = result.forecast.find((row) => row.shortage > 0)
    if (!firstShortage) {
      return t("forecast.summary.noShortage")
    }

    const escalatedRow = result.forecast.find((row) => row.riskLevel === "high")
    if (escalatedRow) {
      return t("forecast.summary.withEscalation", {
        shortageWeek: firstShortage.week,
        riskWeek: escalatedRow.week,
      })
    }

    return t("forecast.summary.withWatch", {
      shortageWeek: firstShortage.week,
    })
  }, [result, t])

  const topbarActions = (
    <>
      <button className="button" type="button" onClick={() => handleForecast()} disabled={loading}>
        <TrendingUp size={16} />
        {loading ? t("forecast.forecasting") : t("forecast.runForecast")}
      </button>
      <button className="button-secondary" type="button" onClick={handleReset}>
        <RefreshCw size={16} />
        {t("topbar.reset")}
      </button>
    </>
  )

  return (
    <AppShell topbarActions={topbarActions} busy={loading} busyLabel={t("forecast.forecasting")}>
      {error ? <section className="error-state">{error}</section> : null}

      <section className="forecast-layout">
        <aside className="panel forecast-sidebar">
          <div className="section-head">
            <div>
              <h3>{t("forecast.keyMaterials")}</h3>
              <p>{t("forecast.keyMaterialsHint")}</p>
            </div>
          </div>

          <div className="field">
            <label>{t("analyze.materialCode")}</label>
            <input value={material} onChange={(event) => setMaterial(event.target.value)} placeholder={t("analyze.placeholder")} />
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

          <div className="form-grid">
            <div className="field">
              <label>{t("forecast.historyWindow")}</label>
              <input
                type="number"
                min={1}
                max={365}
                value={config.window_size}
                onChange={(event) => setConfig((current) => ({ ...current, window_size: Number(event.target.value) }))}
              />
            </div>
            <div className="field">
              <label>{t("forecast.windowUnit")}</label>
              <select value={config.window_unit} onChange={(event) => setConfig((current) => ({ ...current, window_unit: event.target.value as "D" | "W" | "M" | "Y" }))}>
                <option value="D">{t("time.day")}</option>
                <option value="W">{t("time.week")}</option>
                <option value="M">{t("time.month")}</option>
                <option value="Y">{t("time.year")}</option>
              </select>
            </div>
          </div>

          <button className="button" type="button" onClick={() => handleForecast()} disabled={loading}>
            <SearchCheck size={16} />
            {loading ? t("forecast.forecasting") : t("forecast.runForecast")}
          </button>

          <div className="table-wrap forecast-material-list">
            <table>
              <thead>
                <tr>
                  <th>{t("home.table.material")}</th>
                  <th>{t("forecast.demandVolume")}</th>
                </tr>
              </thead>
              <tbody>
                {materials.map((item) => (
                  <tr key={item.material} className={item.material === selectedMaterial ? "selected-row" : ""}>
                    <td>
                      <button className="table-link-button" type="button" onClick={() => handleForecast(item.material)}>
                        {item.material}
                      </button>
                    </td>
                    <td>{item.demandVolume}</td>
                  </tr>
                ))}
                {!materials.length && !loadingMaterials ? (
                  <tr>
                    <td colSpan={2}>{t("forecast.noMaterials")}</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </aside>

        <main className="forecast-main">
          {loading ? (
            <section className="panel analysis-running">
              <div className="progress-line">
                <span />
              </div>
              <strong>{t("forecast.forecasting")}</strong>
              <p>{t("forecast.runningHint")}</p>
            </section>
          ) : result ? (
            <>
              <section className="metric-grid">
                {metrics.map((metric) => (
                  <article className="metric-card" key={metric.label}>
                    <div className="metric-label">{metric.label}</div>
                    <div className="metric-value">{metric.value}</div>
                  </article>
                ))}
              </section>

              <section className="panel chart-card">
                <div className="table-toolbar">
                  <div>
                    <strong>{t("forecast.forecastTimeline")}</strong>
                    <p className="muted" style={{ marginTop: 4 }}>
                      {t("forecast.timelineLabelNote")}
                    </p>
                  </div>
                  <span className={`status-chip ${result.summary.overallRisk === "normal" ? "normal" : "anomaly"}`}>
                    {t(`forecast.risk.${result.summary.overallRisk}`)}
                  </span>
                </div>
                <div className="forecast-summary-card">
                  <strong>{t("forecast.summaryTitle")}</strong>
                  <p>{forecastSummary}</p>
                </div>
                <div className="chart-stage">
                  <ForecastChart data={result} formatDate={(value) => formatDate(value, locale)} />
                </div>
                <div className="summary-inline">
                  <span className="summary-tag">{result.historyWeeks} {t("forecast.historyWeeks")}</span>
                  <span className="summary-tag">{t(`forecast.confidenceLabel.${result.model.confidence}`)}</span>
                  <span className="summary-tag">{t(`forecast.risk.${result.summary.overallRisk}`)}</span>
                </div>
                <div className="chart-explanation">
                  <details>
                    <summary>{t("forecast.readingGuideTitle")}</summary>
                    <div className="forecast-formula-grid">
                      <div className="chart-explanation">
                        <strong>{t("forecast.weekFlowTitle")}</strong>
                        <p>{t("forecast.weekFlowExplanation")}</p>
                        {/* <p className="muted">{result.model.weekFlowDefinition}</p> */}
                        <p className="muted">{t("forecast.weekFlowDefinition")}</p>
                      </div>
                      <div className="chart-explanation">
                        <strong>{t("forecast.modelReliabilityTitle")}</strong>
                        <p>{t(`forecast.confidenceText.${result.model.confidence}`)}</p>
                        <p className="muted">{t(`forecast.confidenceRule.${result.model.confidence}`)}</p>
                      </div>
                      <div className="chart-explanation">
                        <strong>{t("forecast.riskLevelTitle")}</strong>
                        <p>{t("forecast.riskLevelExplanation")}</p>
                        <p className="muted">{t("forecast.riskLevelDifference")}</p>
                      </div>
                      <div className="chart-explanation">
                        <strong>{t("forecast.riskLevelBandsTitle")}</strong>
                        <p>{t("forecast.riskBands.normal")}</p>
                        <p>{t("forecast.riskBands.watch")}</p>
                        <p>{t("forecast.riskBands.high")}</p>
                      </div>
                      <div className="chart-explanation">
                        <strong>{t("forecast.modelFormulaTitle")}</strong>
                        <p>{t("forecast.modelFormulaExplanation")}</p>
                        <details>
                          <summary>{t("hint.viewFormula")}</summary>
                          <div className="formula-container">
                            <FormulaBlock
                              math={modelFormula}
                            />
                            <p className="muted">
                              {t("forecast.modelFormulaDetail")}
                            </p>
                          </div>
                        </details>
                      </div>
                      <div className="chart-explanation">
                        <strong>{t("forecast.replenishmentFormulaTitle")}</strong>
                        <p>{t("forecast.replenishmentFormulaExplanation")}</p>
                        <details>
                          <summary>{t("hint.viewFormula")}</summary>
                          <div className="formula-container">
                            <FormulaBlock
                              math={replenishmentFormula}
                            />
                            <p className="muted">
                              {t("forecast.replenishmentFormulaDetail")}
                            </p>
                          </div>
                        </details>
                      </div>
                    </div>
                    {/* {result.model.notes?.length ? (
                      <div className="forecast-notes-stack">
                        {result.model.notes.map((note) => (
                          <p key={note} className="muted">{note}</p>
                        ))}
                      </div>
                    ) : null} */}
                    <p className="muted">
                      {t("forecast.notes")}
                    </p>
                  </details>
                </div>
              </section>

              <section className="panel table-card">
                <div className="table-toolbar">
                  <strong>{t("forecast.replenishmentAdvice")}</strong>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>{t("forecast.week")}</th>
                        <th>{t("forecast.date")}</th>
                        <th>{t("forecast.predictedInventory")}</th>
                        <th>{t("forecast.predictedSafetyStock")}</th>
                        <th>{t("forecast.shortage")}</th>
                        <th>{t("forecast.suggestedReplenishment")}</th>
                        <th>{t("batch.riskLevel")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.forecast.map((row) => (
                        <tr key={row.week}>
                          <td>{row.week}</td>
                          <td>{formatDate(row.date, locale)}</td>
                          <td>{row.predictedInventory}</td>
                          <td>{row.predictedSafetyStock}</td>
                          <td>{row.shortage}</td>
                          <td>{row.suggestedReplenishment}</td>
                          <td>
                            <span className={`status-chip ${row.riskLevel === "normal" ? "normal" : "anomaly"}`}>
                              {t(`forecast.risk.${row.riskLevel}`)}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          ) : (
            <section className="panel analyze-empty">
              <TrendingUp size={40} strokeWidth={1.2} style={{ marginBottom: 16, opacity: 0.4 }} />
              <strong>{t("forecast.emptyTitle")}</strong>
              <span>{t("forecast.emptyHint")}</span>
            </section>
          )}
        </main>
      </section>
    </AppShell>
  )
}
