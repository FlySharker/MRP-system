"use client"

import type { ReactNode } from "react"
import { useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { useTranslation } from "react-i18next"
import {
  Activity,
  BarChart3,
  Bell,
  BrainCircuit,
  ChevronDown,
  Database,
  Home,
  PanelLeftClose,
  PanelLeftOpen,
  SearchCheck,
  Settings,
  Share2,
  TableProperties,
  UploadCloud,
} from "lucide-react"
import { LanguageSwitcher } from "./language-switcher"

const mainNav = [
  { href: "/", label: "nav.overview", icon: Home },
  { href: "/analyze", label: "nav.singleAnalyze", icon: SearchCheck },
  { href: "/batch", label: "nav.batchAnalyze", icon: TableProperties },
  { href: "/forecast", label: "nav.forecast", icon: BarChart3 },
  { href: "/llm-settings", label: "nav.llmSettings", icon: BrainCircuit },
]

const pageMeta: Record<string, { title: string; subtitle: string }> = {
  "/": {
    title: "pageMeta.overview.title",
    subtitle: "pageMeta.overview.subtitle",
  },
  "/analyze": {
    title: "pageMeta.analyze.title",
    subtitle: "pageMeta.analyze.subtitle",
  },
  "/batch": {
    title: "pageMeta.batch.title",
    subtitle: "pageMeta.batch.subtitle",
  },
  "/forecast": {
    title: "pageMeta.forecast.title",
    subtitle: "pageMeta.forecast.subtitle",
  },
  "/llm-settings": {
    title: "pageMeta.llmSettings.title",
    subtitle: "pageMeta.llmSettings.subtitle",
  },
}

export function AppShell({
  children,
  topbarActions,
  busy,
  busyLabel,
}: {
  children: ReactNode
  topbarActions?: ReactNode
  busy?: boolean
  busyLabel?: string
}) {
  const { t } = useTranslation()
  const pathname = usePathname()
  const normalizedPathname = pathname === "/" ? pathname : pathname.replace(/\/+$/, "")
  const meta = pageMeta[normalizedPathname] ?? pageMeta["/"]
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  return (
    <div className={`workspace-shell${sidebarCollapsed ? " sidebar-collapsed" : ""}`}>
      <aside className="workspace-sidebar">
        <div className="sidebar-brand">
          <div className="brand-mark">
            <Database size={20} />
          </div>
          <div>
            <strong>{t("app.MRPInsight")}</strong>
            <span>{t("app.operationConsole")}</span>
          </div>
          <ChevronDown className="brand-caret" size={16} />
        </div>

        <div className="sidebar-group">
          <div className="sidebar-label">PROJECT</div>
          <nav className="sidebar-nav" aria-label="Main navigation">
            {mainNav.map((item) => {
              const Icon = item.icon
              const active = normalizedPathname === item.href
              return (
                <Link key={item.href} href={item.href} className={`sidebar-link${active ? " active" : ""}`}>
                  <Icon size={16} />
                  <span>{t(item.label)}</span>
                </Link>
              )
            })}
          </nav>
        </div>

        {/* <div className="sidebar-group">
          <div className="sidebar-label">ANALYSIS</div>
          <div className="sidebar-chip">
            <span>production</span>
            <ChevronDown size={14} />
          </div>
          <div className="sidebar-stack">
            <div className="sidebar-link muted-link">
              <Activity size={16} />
              <span>Monitoring</span>
            </div>
            <div className="sidebar-link muted-link">
              <BarChart3 size={16} />
              <span>Rule Metrics</span>
            </div>
            <div className="sidebar-link muted-link">
              <Settings size={16} />
              <span>Settings</span>
            </div>
          </div>
        </div> */}

        <div className="sidebar-footer">
          <button
            className="sidebar-link sidebar-collapse-button"
            type="button"
            onClick={() => setSidebarCollapsed((current) => !current)}
          >
            {sidebarCollapsed ? (
              <PanelLeftOpen size={16} />
            ) : (
              <PanelLeftClose size={16} />
            )}

            <span>
              {sidebarCollapsed
                ? t("sidebar.expandMenu")
                : t("sidebar.collapseMenu")}
            </span>
          </button>
        </div>

      </aside>

      <main className="workspace-main">
        {/* <div className="workspace-accountbar">
          <div className="account-cluster">
            <div className="brand-glyph">M</div>
            <span className="account-name">mrp.analysis.local</span>
            <span className="plan-chip">Local</span>
            <ChevronDown size={14} />
            <span className="account-separator" />
            <strong>MRP Workspace</strong>
            <ChevronDown size={14} />
          </div>
          <div className="account-actions">
            <span className="health-pill">
              <span className="health-dot" />
              All OK
            </span>
            <button className="icon-button" type="button" aria-label="Notifications">
              <Bell size={16} />
            </button>
            <div className="avatar-badge">A</div>
          </div>
        </div> */}

        <header className="workspace-topbar">
          {busy ? (
            <div className="topbar-progress" role="status" aria-live="polite">
              <span />
            </div>
          ) : null}
          <div className="topbar-title">
            <h1>{t(meta.title)}</h1>
            <p>{busy ? busyLabel ?? t("topbar.processingAnalysis") : t(meta.subtitle)}</p>
          </div>

          <div className="topbar-tools">
            {topbarActions ?? (
              <>
                <button className="button" type="button">
                  <Share2 size={16} />
                  {t("topbar.connect")}
                </button>
                <button className="button-secondary" type="button">
                  <UploadCloud size={16} />
                  {t("topbar.importData")}
                </button>
              </>
            )}
            <LanguageSwitcher />
          </div>
        </header>

        <div className="workspace-content">{children}</div>
      </main>
    </div>
  )
}
