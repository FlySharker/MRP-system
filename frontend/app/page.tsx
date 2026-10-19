"use client"

import { useEffect, useRef, useState } from "react"
import { useTranslation } from "react-i18next"
import { Clock3, SearchCheck, UploadCloud } from "lucide-react"
import { AppShell } from "@/components/app-shell"
import { getOverview, type OverviewResponse } from "@/lib/api"

function formatDate(value: string | undefined, locale: string) {
  if (!value) return "-"
  return new Date(value).toLocaleDateString(locale)
}

export default function HomePage() {
  const [overview, setOverview] = useState<OverviewResponse | null>(null)
  const [error, setError] = useState("")
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState("")
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { t, i18n } = useTranslation()
  const locale = i18n.language === "en" ? "en-US" : "zh-CN"

  const fetchOverview = () => {
    getOverview()
      .then((data) => {
        setOverview(data)
        setError("")
      })
      .catch((err: Error) => setError(err.message))
  }

  useEffect(() => {
    fetchOverview()
  }, [])

  async function handleAnalyzeUpload() {
    if (!file) {
      setUploadError(t("home.upload.noFile"))
      fileInputRef.current?.click()
      return
    }

    setUploading(true)
    setUploadError("")

    const formData = new FormData()
    formData.append("file", file)

    try {
      const res = await fetch("http://localhost:8000/api/upload", {
        method: "POST",
        body: formData,
      })
      const data = await res.json()
      if (!res.ok) {
        throw new Error(data.detail ?? t("home.upload.uploadFailed"))
      }

      const nextOverview = await getOverview()
      setOverview(nextOverview)
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : t("home.upload.uploadFailed"))
    } finally {
      setUploading(false)
    }
  }

  const metrics = [
    {
      label: t("home.materials"),
      value: overview?.materialsCount ?? "-",
      hint: t("home.materialsHint"),
      trend: t("home.materialsTrend"),
    },
    {
      label: t("home.records"),
      value: overview?.recordsCount ?? "-",
      hint: t("home.recordsHint"),
      trend: t("home.recordsTrend"),
    },
    {
      label: t("home.plants"),
      value: overview?.plantsCount ?? "-",
      hint: t("home.plantsHint"),
      trend: t("home.plantsTrend"),
    },
    {
      label: t("home.dateWindow"),
      value: overview ? `${formatDate(overview.dateRange.start, locale)} - ${formatDate(overview.dateRange.end, locale)}` : "-",
      hint: t("home.dateWindowHint"),
      trend: t("home.dateWindowTrend"),
    },
  ]

  const recentHistory = overview?.recentHistory ?? []
  const statusLabels: Record<string, string> = {
    normal: t("batch.normal"),
    anomaly: t("batch.anomaly"),
    error: t("analyze.error"),
  }

  const topbarActions = (
    <>
      <input
        ref={fileInputRef}
        type="file"
        accept=".xlsx,.csv"
        style={{ display: "none" }}
        onChange={(event) => {
          const nextFile = event.target.files?.[0]
          if (nextFile) {
            setFile(nextFile)
            setUploadError("")
          }
        }}
      />
      <button className="button" type="button" onClick={handleAnalyzeUpload} disabled={uploading}>
        <SearchCheck size={16} />
        {uploading ? t("home.upload.uploading") : t("topbar.analyze")}
      </button>
      <button className="button-secondary import-button" type="button" onClick={() => fileInputRef.current?.click()}>
        <UploadCloud size={16} />
        <span>{file ? file.name : t("topbar.importData")}</span>
      </button>
    </>
  )

  return (
    <AppShell topbarActions={topbarActions}>
      {error ? <section className="error-state">{error}</section> : null}
      {uploadError ? <section className="error-state">{uploadError}</section> : null}

      <section className="metric-grid">
        {metrics.map((metric) => (
          <article key={metric.label} className="panel metric-card">
            <div className="metric-label">{metric.label}</div>
            <div className="metric-value">{metric.value}</div>
            <div className="metric-trend">{metric.trend}</div>
            <div className="muted">{metric.hint}</div>
          </article>
        ))}
      </section>

      <section className="history-strip">
        <article className="panel table-card full-span">
          <div className="table-toolbar">
            <div className="section-head">
              <div>
                <h3>{t("home.recentAnalysisHistory")}</h3>
              </div>
            </div>
            <div className="table-pill">
              <Clock3 size={14} />
              {t("home.visibility")}
            </div>
          </div>

          {recentHistory.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{t("home.table.material")}</th>
                    <th>{t("home.table.status")}</th>
                    <th>{t("home.table.analyzedAt")}</th>
                    <th>{t("home.table.llmLabel")}</th>
                  </tr>
                </thead>
                <tbody>
                  {recentHistory.map((item, index) => (
                    <tr key={`${item.material}-${item.status}-${item.analyzed_at}-${index}`}>
                      <td>
                        <div className="row-title">
                          <strong>{item.material}</strong>
                          <span>{t("home.table.materialPrompt")}</span>
                        </div>
                      </td>
                      <td>
                        <span className={`status-chip ${item.status}`}>{statusLabels[item.status] ?? item.status}</span>
                      </td>
                      <td>{item.analyzed_at}</td>
                      <td>{item.llm_label ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">{t("home.noRecentHistory")}</div>
          )}
        </article>
      </section>
    </AppShell>
  )
}
