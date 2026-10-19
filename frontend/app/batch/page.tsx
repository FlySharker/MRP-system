"use client"

import dynamic from "next/dynamic"
import { useEffect, useState } from "react"
import { RotateCcw, ScanSearch, Settings2, X } from "lucide-react"
import { useTranslation } from "react-i18next"
import { AppShell } from "@/components/app-shell"
import { analyzeBatch, type BatchResponse } from "@/lib/api"
import { useBatchStore } from "@/stores/batch-store"
import { useMemo } from "react"

const StatusPieChart = dynamic(
  () => import("@/components/charts/batch-charts").then((m) => m.StatusPieChart),
  { ssr: false, loading: () => <div className="chart-stage chart-loading">Loading chart...</div> }
)

const ReasonBarChart = dynamic(
  () => import("@/components/charts/batch-charts").then((m) => m.ReasonBarChart),
  { ssr: false, loading: () => <div className="chart-stage chart-loading">Loading chart...</div> }
)

type BatchConfigState = {
  material_prefix: string
  statuses: string[]
  max_materials: number
  config: {
    window_size: number
    window_unit: "D" | "W" | "M" | "Y"
    min_interval_len: number
  }
}

const initialState: BatchConfigState = {
  material_prefix: "",
  statuses: ["normal", "anomaly"],
  max_materials: 20,
  config: {
    window_size: 14,
    window_unit: "D",
    min_interval_len: 1,
  },
}

const reasonLabelKeys = {
  delayedSupply: "analyze.rules.delayedSupply",
  demandSpike: "analyze.rules.demandSpike",
  fluctuation: "analyze.rules.fluctuation",
  gradualShortage: "analyze.rules.gradualShortage",
} as const

export default function BatchPage() {
  const { t } = useTranslation()
  // const [filters, setFilters] = useState<BatchConfigState>(initialState)
  const [filters, setFilters] = useState<BatchConfigState>(() => {
    if (typeof window !== "undefined") {
      const saved = sessionStorage.getItem("batch_filters")
      if (saved) {
        return JSON.parse(saved)
      }
    }
    return initialState
  })
  // const [result, setResult] = useState<BatchResponse | null>(null)
  // const [result, setResult] = useState<BatchResponse | null>(() => {
  //   if (typeof window !== "undefined") {
  //     const saved = sessionStorage.getItem("batch_result")
  //     if (saved) {
  //       return JSON.parse(saved)
  //     }
  //   }
  //   return null
  // })
  const result = useBatchStore((s) => s.result)
  const setResult = useBatchStore((s) => s.setResult)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const [configOpen, setConfigOpen] = useState(false)
  // const [currentPage, setCurrentPage] = useState(1)
  const [currentPage, setCurrentPage] = useState(() => {
    if (typeof window !== "undefined") {
      return Number(sessionStorage.getItem("batch_currentPage") || 1)
    }
    return 1
  })
  const [jumpPage, setJumpPage] = useState("")
  const pageSize = 100

  useEffect(() => {
    sessionStorage.setItem("batch_filters", JSON.stringify(filters))
  }, [filters])

  // useEffect(() => {
  //   if (result) {
  //     sessionStorage.setItem("batch_result", JSON.stringify(result))
  //   } else {
  //     sessionStorage.removeItem("batch_result")
  //   }
  // }, [result])

  useEffect(() => {
    sessionStorage.setItem("batch_currentPage", String(currentPage))
  }, [currentPage])

  async function handleAnalyze() {
    try {
      setLoading(true)
      setError("")
      const data = await analyzeBatch({
        ...filters,
        config: {
          ...filters.config,
          time_window_size: `${filters.config.window_size}${filters.config.window_unit}`,
        },
      })
      setResult(data)
      setCurrentPage(1)
      setConfigOpen(false)
    } catch (err) {
      setResult(null)
      setError(err instanceof Error ? err.message : t("batch.batchAnalysisFailed"))
    } finally {
      setLoading(false)
    }
  }

  function handleReset() {
    setFilters(initialState)
    setResult(null)
    setError("")

    sessionStorage.removeItem("batch_filters")
    // sessionStorage.removeItem("batch_result")
    sessionStorage.removeItem("batch_currentPage")
  }

  function handleJumpPage() {
    let page = Number(jumpPage)

    if (!Number.isFinite(page)) return

    page = Math.floor(page)

    if (page < 1) {
      page = 1
    }

    if (page > totalPages) {
      page = totalPages
    }

    setCurrentPage(page)
    setJumpPage(String(page))
  }

  const reasonData = useMemo(() => {
    if (!result) return []

    return Object.entries(result.reasonCounts)
      .filter((entry): entry is [keyof typeof reasonLabelKeys, number] => {
        const [name, value] = entry
        return name in reasonLabelKeys && typeof value === "number"
      })
      .map(([name, value]) => ({
        name: t(reasonLabelKeys[name]),
        value,
      }))
  }, [result, t])

  const pieData = useMemo(() => {
    if (!result) return []

    return [
      { name: t("batch.normal"), value: result.metrics.normal },
      { name: t("batch.anomaly"), value: result.metrics.anomaly },
    ]
  }, [result, t])

  const pagedSummary = useMemo(() => {
    if (!result) return []

    return result.summary.slice(
      (currentPage - 1) * pageSize,
      currentPage * pageSize
    )
  }, [result, currentPage])
  
  const totalPages = result
    ? Math.ceil(result.summary.length / pageSize)
    : 0  
  
  const riskLevelData = result
    ? ["L1", "L2", "L3", "L4"].map((level) => ({
      name: level,
      value: result.summary.filter(
        (row) => row.risk_level === level
      ).length,
    }))
    : []

  const riskLevelMeta = {
    L1: {
      label: t("batch.riskLevels.L1.label"),
      hint: t("batch.riskLevels.L1.hint"),
    },
    L2: {
      label: t("batch.riskLevels.L2.label"),
      hint: t("batch.riskLevels.L2.hint"),
    },
    L3: {
      label: t("batch.riskLevels.L3.label"),
      hint: t("batch.riskLevels.L3.hint"),
    },
    L4: {
      label: t("batch.riskLevels.L4.label"),
      hint: t("batch.riskLevels.L4.hint"),
    },
  }

  const ruleMeta = {
    toolate: {
      label: t("analyze.rules.delayedSupply"),
      hint: t("hint.latesupply"),
    },
    gradual_shortage: {
      label: t("analyze.rules.gradualShortage"),
      hint: t("hint.gradualshortage"),
    },
    fluctuation: {
      label: t("analyze.rules.fluctuation"),
      hint: t("hint.fluctuation"),
    },
    demand_spike: {
      label: t("analyze.rules.demandSpike"),
      hint: t("hint.demandspike"),
    },
  }

  // Extract unique prefixes from materials for autocomplete suggestions
  const [prefixSuggestions, setPrefixSuggestions] = useState<string[]>([])
  
  useEffect(() => {
    // Fetch materials to extract common prefixes
    const fetchMaterials = async () => {
      try {
        const response = await fetch('/api/materials?limit=1000')
        const data = await response.json()
        if (data.items) {
          // Extract unique first characters/prefixes
          const prefixes = new Set<string>()
          data.items.forEach((material: string) => {
            if (material) {
              // Extract first character or first segment before '-'
              const firstChar = material.charAt(0).toUpperCase()
              prefixes.add(firstChar)
              const segment = material.split('-')[0]
              if (segment && segment !== material) {
                prefixes.add(segment)
              }
            }
          })
          setPrefixSuggestions(Array.from(prefixes).sort())
        }
      } catch (e) {
        // Silent fail - user can still type manually
      }
    }
    fetchMaterials()
  }, [])

  const statusOptions = [
    { value: "normal", label: t("batch.normal") },
    { value: "anomaly", label: t("batch.anomaly") },
  ]

  const topbarActions = (
    <>
      <button className="button-secondary" type="button" onClick={() => setConfigOpen(true)}>
        <Settings2 size={16} />
        {t("topbar.configuration")}
      </button>
      <button className="button" type="button" onClick={handleAnalyze} disabled={loading}>
        <ScanSearch size={16} />
        {loading ? t("batch.analyzing") : t("topbar.analyze")}
      </button>
      <button className="button-secondary" type="button" onClick={handleReset}>
        <RotateCcw size={16} />
        {t("topbar.reset")}
      </button>
    </>
  )

  return (
    <AppShell topbarActions={topbarActions} busy={loading} busyLabel={t("batch.analyzing")}>
      {configOpen ? (
        <div className="modal-backdrop" role="presentation">
          <section className="modal-panel" role="dialog" aria-modal="true" aria-label="Batch analysis configuration">
            <div className="modal-head">
              <div>
                <h3>{t("batch.batchFilterConsole")}</h3>
                <p>{t("batch.filterActive")}</p>
              </div>
              <button className="icon-button" type="button" onClick={() => setConfigOpen(false)} aria-label="Close configuration">
                <X size={16} />
              </button>
            </div>

            <div className="form-grid modal-form-grid">
              <div className="field">
                <label>{t("batch.materialPrefix")}</label>
                <input
                  type="text"
                  value={filters.material_prefix}
                  onChange={(event) => setFilters((current) => ({ ...current, material_prefix: event.target.value }))}
                  placeholder={t("batch.all")}
                  list="prefix-suggestions"
                />
                <datalist id="prefix-suggestions">
                  <option value="" label={t("batch.all")} />
                  {prefixSuggestions.map((prefix) => (
                    <option key={prefix} value={prefix} />
                  ))}
                </datalist>
                <div className="field-hint">{t("hint.materialPrefix")}</div>
              </div>

              <div className="field">
                <label>{t("batch.analysisLimit")}</label>
                <input
                  type="number"
                  min={1}
                  max={10000}
                  value={filters.max_materials}
                  onChange={(event) => setFilters((current) => ({ ...current, max_materials: Number(event.target.value) }))}
                />
                <div className="field-hint">{t("hint.analysislimit")}</div>
              </div>

              <div className="field">
                <label>{t("analyze.windowSize")}</label>
                <div style={{ display: "flex", gap: "8px" }}>
                  <input
                    type="number"
                    min={1}
                    max={365}
                    value={filters.config.window_size}
                    onChange={(event) =>
                      setFilters((current) => ({
                        ...current,
                        config: { ...current.config, window_size: Number(event.target.value) },
                      }))
                    }
                    style={{ flex: 1, minWidth: 0 }}
                  />
                  <select
                    value={filters.config.window_unit}
                    onChange={(event) =>
                      setFilters((current) => ({
                        ...current,
                        config: {
                          ...current.config,
                          window_unit: event.target.value as "D" | "W" | "M" | "Y",
                        },
                      }))
                    }
                  >
                    <option value="D">{t("time.day")}</option>
                    <option value="W">{t("time.week")}</option>
                    <option value="M">{t("time.month")}</option>
                    <option value="Y">{t("time.year")}</option>
                  </select>
                </div>
                <div className="field-hint">{t("hint.windowSizeHint")}</div>
              </div>
            </div>

            <div className="checkbox-row">
              {statusOptions.map((status) => (
                <label key={status.value} className="checkbox-pill">
                  <input
                    type="checkbox"
                    checked={filters.statuses.includes(status.value)}
                    onChange={(event) =>
                      setFilters((current) => ({
                        ...current,
                        statuses: event.target.checked ? [...current.statuses, status.value] : current.statuses.filter((item) => item !== status.value),
                      }))
                    }
                  />
                  {status.label}
                </label>
              ))}
            </div>

            <div className="modal-actions">
              <button className="button-secondary" type="button" onClick={handleReset}>
                <RotateCcw size={16} />
                {t("topbar.reset")}
              </button>
              <button className="button" type="button" onClick={handleAnalyze} disabled={loading}>
                <ScanSearch size={16} />
                {loading ? t("batch.analyzing") : t("topbar.analyze")}
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
          <strong>{t("batch.analyzing")}</strong>
          <p>Screening materials and building batch analysis results.</p>
        </section>
      ) : result ? (
        <>
          <section className="metric-grid">
            <article className="panel metric-card">
              <div className="metric-label">{t("batch.total")}</div>
              <div className="metric-value">{result.metrics.total}</div>
              <div className="muted">{t("batch.totalScreened")}</div>
            </article>
            <article className="panel metric-card">
              <div className="metric-label">{t("batch.normal")}</div>
              <div className="metric-value">{result.metrics.normal}</div>
              <div className="muted">{t("batch.normalCount")}</div>
            </article>
            <article className="panel metric-card">
              <div className="metric-label">{t("batch.anomaly")}</div>
              <div className="metric-value">{result.metrics.anomaly}</div>
              <div className="muted">{t("batch.anomalyCount")}</div>
            </article>
            <article className="panel metric-card">
              <div className="metric-label">{t("batch.riskRatio")}</div>
              <div className="metric-value">{result.metrics.riskRatio}%</div>
              <div className="muted">{t("batch.riskRatio")}</div>
            </article>
          </section>

          <section className="panel table-card">
            <div className="table-toolbar">
              <strong style={{ fontSize: "20px" }}>
                {t("batch.riskLevelDistribution")}
              </strong>
            </div>

            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(4, 1fr)",
                gap: "16px",
                marginTop: "16px",
              }}
            >
              {riskLevelData.map((item) => {
                const meta = riskLevelMeta[item.name as keyof typeof riskLevelMeta]

                return (
                  <div
                    key={item.name}
                    className="metric-card"
                    style={{
                      padding: "20px",
                      borderRadius: "12px",
                      border: "1px solid var(--border)",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: "8px",
                      }}
                    >
                      <div
                        style={{
                          fontSize: "14px",
                          color: "var(--muted)",
                          fontWeight: 600,
                        }}
                      >
                        {meta.label}
                      </div>

                      <span className={`risk-chip ${item.name.toLowerCase()}`}>
                        {item.name}
                      </span>
                    </div>

                    <div
                      style={{
                        fontSize: "32px",
                        fontWeight: 700,
                        marginBottom: "10px",
                      }}
                    >
                      {item.value}
                    </div>

                    <div
                      style={{
                        fontSize: "13px",
                        color: "var(--muted)",
                        lineHeight: 1.5,
                      }}
                    >
                      {meta.hint}
                    </div>
                  </div>
                )
              })}
            </div>
          </section>

          <section className="panel table-card">
            <div className="table-toolbar">
              <strong style={{ fontSize: "20px" }}>{t("batch.analysisResults")}</strong>
              <div className="table-pill">{t("batch.rowsTag", { count: result.summary.length })}</div>
            </div>
            <div
              className="table-wrap"
              style={{
                maxHeight: "520px",
                overflow: "auto",
              }}
            >
              <table>
                <thead>
                  <tr>
                    <th style={{ textAlign: "center" }}>{t("analyze.materialCode")}</th>
                    <th style={{ textAlign: "center" }}>{t("home.table.status")}</th>
                    <th style={{ textAlign: "center" }}>{t("batch.riskScore")}</th>
                    <th style={{ textAlign: "center" }}>{t("batch.riskLevel")}</th>
                    <th style={{ textAlign: "center" }}>{t("batch.shortageIntervalCount")}</th>
                    <th style={{ textAlign: "center" }}>{t("batch.firstShortageInterval")}</th>
                    <th style={{ textAlign: "center" }}>{t("analyze.rules.delayedSupply")}</th>
                    <th style={{ textAlign: "center" }}>{t("analyze.rules.gradualShortage")}</th>
                    <th style={{ textAlign: "center" }}>{t("analyze.rules.fluctuation")}</th>
                    <th style={{ textAlign: "center" }}>{t("analyze.rules.demandSpike")}</th>
                  </tr>
                </thead>
                <tbody>
                  {pagedSummary.map((row, index) => (
                    <tr key={`${row.material}-${index}`}>
                      <td style={{ textAlign: "center" }}>
                        <div className="row-title">
                          <strong>{String(row.material ?? "-")}</strong>
                          {/* <span>{t("batch.batchPromptRow")}</span> */}
                        </div>
                      </td>
                      <td style={{ textAlign: "center" }}>{row.Normal ? <span className="status-chip normal">{t("batch.normal")}</span> : <span className="status-chip anomaly">{t("batch.anomaly")}</span>}</td>

                      <td style={{ textAlign: "center" }}>
                        {typeof row.risk_score === "number"
                          ? row.risk_score.toFixed(4)
                          : "-"}
                      </td>

                      <td style={{ textAlign: "center" }}>
                        <span className={`risk-chip ${String(row.risk_level).toLowerCase()}`}>
                          {String(row.risk_level ?? "-")}
                        </span>
                      </td>

                      <td style={{ textAlign: "center" }}>{String(row.shortage_interval_count ?? "-")}</td>
                      <td style={{ textAlign: "center" }}>{String(row.first_interval ?? "-")}</td>
                      <td style={{ textAlign: "center" }}>{row.toolate ? t("common.yes") : t("common.no")}</td>
                      <td style={{ textAlign: "center" }}>{row.gradual_shortage ? t("common.yes") : t("common.no")}</td>
                      <td style={{ textAlign: "center" }}>{row.fluctuation ? t("common.yes") : t("common.no")}</td>
                      <td style={{ textAlign: "center" }}>{row.demand_spike ? t("common.yes") : t("common.no")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="pagination">
                <button
                  className="button-secondary"
                  disabled={currentPage === 1}
                  onClick={() => setCurrentPage((p) => p - 1)}
                >
                  Prev
                </button>

                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                  }}
                >
                  <input
                    type="number"
                    min={1}
                    max={totalPages}
                    value={jumpPage}
                    onChange={(e) => setJumpPage(e.target.value)}
                    placeholder={String(currentPage)}
                    style={{
                      width: "72px",
                      height: "32px",
                      textAlign: "center",
                    }}
                  />

                  <button
                    className="button-secondary"
                    type="button"
                    onClick={handleJumpPage}
                  >
                    Go
                  </button>
                </div>

                <span className="pagination-info">
                  {currentPage} / {totalPages}
                </span>

                <button
                  className="button-secondary"
                  disabled={currentPage === totalPages}
                  onClick={() => setCurrentPage((p) => p + 1)}
                >
                  Next
                </button>
              </div>
            </div>
          </section>

          <div className="two-col">
            <div className="panel chart-card">
              <div className="table-toolbar">
                <strong style={{ fontSize: "20px" }}>{t("batch.statusDistribution")}</strong>
                <div className="table-pill">{t("batch.sentimentTag", { count: 62 })}</div>
              </div>
              <div className="chart-stage">
                <StatusPieChart data={pieData} />
              </div>
            </div>

            <div className="panel chart-card">
              <div className="table-toolbar">
                <strong style={{ fontSize: "20px" }}>{t("batch.reasonRanking")}</strong>
                <div className="table-pill">{t("batch.mentionsTag", { count: reasonData.length })}</div>
              </div>
              <div className="chart-stage">
                <ReasonBarChart data={reasonData} />
              </div>
              <div className="rule-list">
                {Object.entries(ruleMeta).map(([key, meta]) => (
                  <div key={key} className="rule-item">
                    <div className="rule-title">
                      <strong>{meta.label}</strong>
                    </div>
                    <div className="rule-hint">{meta.hint}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </>
      ) : !error ? (
        <section className="panel analyze-empty" style={{ color: "var(--muted)" }}>
          <ScanSearch size={40} strokeWidth={1.2} style={{ marginBottom: 16, opacity: 0.4 }} />
          <strong style={{ fontSize: 16, marginBottom: 6 }}>{t("batch.emptyTitle")}</strong>
          <span style={{ fontSize: 13 }}>{t("batch.emptyHint")}</span>
        </section>
      ) : null}
    </AppShell>
  )
}
