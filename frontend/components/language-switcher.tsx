"use client"

import { useState } from "react"
import { useTranslation } from "react-i18next"
import { Languages } from "lucide-react"

export function LanguageSwitcher() {
  const { i18n, t } = useTranslation()
  const [isOpen, setIsOpen] = useState(false)

  const languages = [
    { code: "zh", label: t("chinese"), nativeLabel: "中文" },
    { code: "en", label: t("english"), nativeLabel: "English" },
  ]

  const currentLang = languages.find((lang) => lang.code === i18n.language) ?? languages[0]

  function handleLanguageChange(code: string) {
    i18n.changeLanguage(code)
    setIsOpen(false)
  }

  return (
    <div className="language-switcher">
      <button
        className="language-trigger"
        onClick={() => setIsOpen(!isOpen)}
        aria-label={t("language")}
        aria-expanded={isOpen}
      >
        <Languages size={16} />
        <span className="language-label">{currentLang.nativeLabel}</span>
        <span className="language-code">{currentLang.code.toUpperCase()}</span>
      </button>

      {isOpen && (
        <div className="language-dropdown">
          {languages.map((lang) => (
            <button
              key={lang.code}
              className={`language-option ${lang.code === i18n.language ? "active" : ""}`}
              onClick={() => handleLanguageChange(lang.code)}
            >
              <span className="lang-native">{lang.nativeLabel}</span>
              <span className="lang-label">{lang.label}</span>
            </button>
          ))}
        </div>
      )}

      {isOpen && <div className="language-backdrop" onClick={() => setIsOpen(false)} />}
    </div>
  )
}
