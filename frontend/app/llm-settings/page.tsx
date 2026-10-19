"use client"

import { useEffect, useMemo, useState } from "react"
import {
  AlertTriangle,
  BrainCircuit,
  CheckCircle2,
  Cloud,
  HardDrive,
  Loader2,
  Save,
  Server,
  TestTube2,
} from "lucide-react"
import { useTranslation } from "react-i18next"
import { AppShell } from "@/components/app-shell"
import {
  getLlmConfig,
  saveLlmConfig,
  testLlmConfig,
  type LlmConfig,
  type LlmProvider,
  type LlmTestResponse,
} from "@/lib/api"

const providerOptions = [
  { key: "modelscope", icon: Cloud },
  { key: "ollama", icon: Server },
  { key: "local", icon: HardDrive },
] as const

export default function LlmSettingsPage() {
  const { t } = useTranslation()
  const [config, setConfig] = useState<LlmConfig | null>(null)
  const [activeProvider, setActiveProvider] = useState<LlmProvider>("modelscope")
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [dirty, setDirty] = useState(false)
  const [error, setError] = useState("")
  const [testResult, setTestResult] = useState<LlmTestResponse | null>(null)

  useEffect(() => {
    getLlmConfig()
      .then((data) => {
        setConfig(data)
        setActiveProvider(data.default_provider)
      })
      .catch((err) => setError(err instanceof Error ? err.message : t("llmSettings.loadFailed")))
      .finally(() => setLoading(false))
  }, [t])

  const activeProviderLabel = useMemo(() => {
    return t(`llmSettings.providers.${activeProvider}.title`)
  }, [activeProvider, t])

  function updateConfig(next: LlmConfig) {
    setConfig(next)
    setDirty(true)
    setTestResult(null)
  }

  function updateGeneral<K extends keyof LlmConfig>(key: K, value: LlmConfig[K]) {
    if (!config) return
    updateConfig({ ...config, [key]: value })
  }

  async function handleSave() {
    if (!config) return
    try {
      setSaving(true)
      setError("")
      const saved = await saveLlmConfig(config)
      setConfig(saved)
      setActiveProvider(saved.default_provider)
      setDirty(false)
      setTestResult({
        ok: true,
        provider: saved.default_provider,
        message: t("llmSettings.saveSucceeded"),
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : t("llmSettings.saveFailed"))
    } finally {
      setSaving(false)
    }
  }

  async function handleTest() {
    if (!config) return
    try {
      setTesting(true)
      setError("")
      const result = await testLlmConfig({ provider: activeProvider, config })
      setTestResult(result)
    } catch (err) {
      setTestResult({
        ok: false,
        provider: activeProvider,
        message: err instanceof Error ? err.message : t("llmSettings.testFailed"),
      })
    } finally {
      setTesting(false)
    }
  }

  const topbarActions = (
    <>
      <button className="button-secondary" type="button" onClick={handleTest} disabled={!config || testing || saving}>
        {testing ? <Loader2 size={16} className="spin-icon" /> : <TestTube2 size={16} />}
        {testing ? t("llmSettings.testing") : t("llmSettings.testActive")}
      </button>
      <button className="button" type="button" onClick={handleSave} disabled={!config || saving || testing || !dirty}>
        {saving ? <Loader2 size={16} className="spin-icon" /> : <Save size={16} />}
        {saving ? t("llmSettings.saving") : t("llmSettings.save")}
      </button>
    </>
  )

  return (
    <AppShell topbarActions={topbarActions} busy={saving || testing} busyLabel={saving ? t("llmSettings.saving") : t("llmSettings.testing")}>
      {error ? <section className="error-state">{error}</section> : null}

      {testResult ? (
        <section className={`test-result ${testResult.ok ? "ok" : "error"}`}>
          {testResult.ok ? <CheckCircle2 size={18} /> : <AlertTriangle size={18} />}
          <span>{testResult.message}</span>
        </section>
      ) : null}

      {loading || !config ? (
        <section className="panel analysis-running">
          <div className="progress-line">
            <span />
          </div>
          <strong>{t("llmSettings.loading")}</strong>
        </section>
      ) : (
        <>
          <section className="panel llm-settings-hero">
            <div className="section-head">
              <div>
                <h3>{t("llmSettings.title")}</h3>
                <p>{t("llmSettings.subtitle")}</p>
              </div>
              <span className={`status-chip ${config.enabled ? "normal" : "error"}`}>
                {config.enabled ? t("llmSettings.enabled") : t("llmSettings.disabled")}
              </span>
            </div>
          </section>

          <div className="llm-settings-layout">
            <section className="panel">
              <div className="section-head">
                <div>
                  <h3>{t("llmSettings.general.title")}</h3>
                  <p>{t("llmSettings.general.subtitle")}</p>
                </div>
                <BrainCircuit size={20} />
              </div>

              <div className="form-grid">
                <label className="checkbox-pill llm-toggle">
                  <input
                    type="checkbox"
                    checked={config.enabled}
                    onChange={(event) => updateGeneral("enabled", event.target.checked)}
                  />
                  <span>{t("llmSettings.general.enableLlm")}</span>
                </label>

                <div className="field">
                  <label>{t("llmSettings.general.defaultProvider")}</label>
                  <select
                    value={config.default_provider}
                    onChange={(event) => updateGeneral("default_provider", event.target.value as LlmProvider)}
                  >
                    {providerOptions.map((provider) => (
                      <option key={provider.key} value={provider.key}>
                        {t(`llmSettings.providers.${provider.key}.title`)}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="field">
                  <label>{t("llmSettings.general.defaultLanguage")}</label>
                  <select
                    value={config.default_language}
                    onChange={(event) => updateGeneral("default_language", event.target.value as "zh" | "en")}
                  >
                    <option value="zh">{t("analyze.Chinese")}</option>
                    <option value="en">{t("analyze.English")}</option>
                  </select>
                </div>

                <div className="field">
                  <label>{t("llmSettings.general.temperature")}</label>
                  <div className="range-row">
                    <input
                      type="range"
                      min={0}
                      max={2}
                      step={0.1}
                      value={config.temperature}
                      onChange={(event) => updateGeneral("temperature", Number(event.target.value))}
                    />
                    <input
                      type="number"
                      min={0}
                      max={2}
                      step={0.1}
                      value={config.temperature}
                      onChange={(event) => updateGeneral("temperature", Number(event.target.value))}
                    />
                  </div>
                </div>

                <div className="field">
                  <label>{t("llmSettings.general.maxTokens")}</label>
                  <input
                    type="number"
                    min={64}
                    max={8192}
                    value={config.max_tokens}
                    onChange={(event) => updateGeneral("max_tokens", Number(event.target.value))}
                  />
                </div>

                <div className="field">
                  <label>{t("llmSettings.general.timeout")}</label>
                  <input
                    type="number"
                    min={5}
                    max={600}
                    value={config.timeout_seconds}
                    onChange={(event) => updateGeneral("timeout_seconds", Number(event.target.value))}
                  />
                </div>

                <div className="field">
                  <label>{t("llmSettings.general.retryCount")}</label>
                  <input
                    type="number"
                    min={0}
                    max={5}
                    value={config.retry_count}
                    onChange={(event) => updateGeneral("retry_count", Number(event.target.value))}
                  />
                </div>
              </div>
            </section>

            <section className="panel">
              <div className="section-head">
                <div>
                  <h3>{activeProviderLabel}</h3>
                  <p>{t(`llmSettings.providers.${activeProvider}.subtitle`)}</p>
                </div>
              </div>

              <div className="provider-tabs" role="tablist" aria-label={t("llmSettings.providerTabs")}>
                {providerOptions.map((provider) => {
                  const Icon = provider.icon
                  return (
                    <button
                      key={provider.key}
                      className={`provider-tab ${activeProvider === provider.key ? "active" : ""}`}
                      type="button"
                      onClick={() => setActiveProvider(provider.key)}
                    >
                      <Icon size={16} />
                      <span>{t(`llmSettings.providers.${provider.key}.short`)}</span>
                    </button>
                  )
                })}
              </div>

              {activeProvider === "modelscope" ? (
                <div className="form-grid">
                  <div className="field full-span">
                    <label>{t("llmSettings.modelscope.apiKey")}</label>
                    <input
                      type="password"
                      value={config.modelscope.api_key}
                      autoComplete="new-password"
                      placeholder={config.modelscope.api_key_set ? t("llmSettings.modelscope.apiKeySaved") : ""}
                      onChange={(event) =>
                        updateConfig({
                          ...config,
                          modelscope: { ...config.modelscope, api_key: event.target.value },
                        })
                      }
                    />
                    <div className="field-hint">{t("llmSettings.modelscope.apiKeyHint")}</div>
                  </div>

                  <div className="field">
                    <label>{t("llmSettings.modelscope.baseUrl")}</label>
                    <input
                      value={config.modelscope.base_url}
                      onChange={(event) =>
                        updateConfig({
                          ...config,
                          modelscope: { ...config.modelscope, base_url: event.target.value },
                        })
                      }
                    />
                  </div>

                  <div className="field">
                    <label>{t("llmSettings.modelscope.model")}</label>
                    <input
                      value={config.modelscope.model}
                      onChange={(event) =>
                        updateConfig({
                          ...config,
                          modelscope: { ...config.modelscope, model: event.target.value },
                        })
                      }
                    />
                  </div>
                </div>
              ) : null}

              {activeProvider === "ollama" ? (
                <div className="form-grid">
                  <div className="field">
                    <label>{t("llmSettings.ollama.host")}</label>
                    <input
                      value={config.ollama.host}
                      onChange={(event) =>
                        updateConfig({
                          ...config,
                          ollama: { ...config.ollama, host: event.target.value },
                        })
                      }
                    />
                  </div>

                  <div className="field">
                    <label>{t("llmSettings.ollama.model")}</label>
                    <input
                      value={config.ollama.model}
                      onChange={(event) =>
                        updateConfig({
                          ...config,
                          ollama: { ...config.ollama, model: event.target.value },
                        })
                      }
                    />
                  </div>

                  <div className="field">
                    <label>{t("llmSettings.ollama.keepAlive")}</label>
                    <input
                      value={config.ollama.keep_alive}
                      onChange={(event) =>
                        updateConfig({
                          ...config,
                          ollama: { ...config.ollama, keep_alive: event.target.value },
                        })
                      }
                    />
                  </div>
                </div>
              ) : null}

              {activeProvider === "local" ? (
                <div className="form-grid">
                  <div className="field full-span">
                    <label>{t("llmSettings.local.modelPath")}</label>
                    <input
                      value={config.local.model_path}
                      onChange={(event) =>
                        updateConfig({
                          ...config,
                          local: { ...config.local, model_path: event.target.value },
                        })
                      }
                    />
                  </div>

                  <div className="field">
                    <label>{t("llmSettings.local.deviceMap")}</label>
                    <select
                      value={config.local.device_map}
                      onChange={(event) =>
                        updateConfig({
                          ...config,
                          local: { ...config.local, device_map: event.target.value },
                        })
                      }
                    >
                      <option value="auto">auto</option>
                      <option value="cuda">cuda</option>
                      <option value="cpu">cpu</option>
                    </select>
                  </div>

                  <div className="field">
                    <label>{t("llmSettings.local.torchDtype")}</label>
                    <select
                      value={config.local.torch_dtype}
                      onChange={(event) =>
                        updateConfig({
                          ...config,
                          local: {
                            ...config.local,
                            torch_dtype: event.target.value as LlmConfig["local"]["torch_dtype"],
                          },
                        })
                      }
                    >
                      <option value="auto">auto</option>
                      <option value="float16">float16</option>
                      <option value="bfloat16">bfloat16</option>
                      <option value="float32">float32</option>
                    </select>
                  </div>
                </div>
              ) : null}
            </section>
          </div>

          <section className="panel table-card">
            <div className="table-toolbar">
              <strong>{t("llmSettings.usage.title")}</strong>
              <span className="table-pill">{t("llmSettings.usage.enterpriseReady")}</span>
            </div>
            <div className="table-wrap">
              <table className="usage-table">
                <thead>
                  <tr>
                    <th>{t("llmSettings.usage.provider")}</th>
                    <th>{t("llmSettings.usage.scenario")}</th>
                    <th>{t("llmSettings.usage.setup")}</th>
                    <th>{t("llmSettings.usage.operation")}</th>
                  </tr>
                </thead>
                <tbody>
                  {providerOptions.map((provider) => (
                    <tr key={provider.key}>
                      <td>
                        <strong>{t(`llmSettings.providers.${provider.key}.title`)}</strong>
                      </td>
                      <td>{t(`llmSettings.usage.${provider.key}.scenario`)}</td>
                      <td>{t(`llmSettings.usage.${provider.key}.setup`)}</td>
                      <td>{t(`llmSettings.usage.${provider.key}.operation`)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </AppShell>
  )
}
