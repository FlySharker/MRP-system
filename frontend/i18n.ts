import i18n from "i18next"
import { initReactI18next } from "react-i18next"

import enCommon from "./public/locales/en/common.json"
import zhCommon from "./public/locales/zh/common.json"

const supportedLanguages = ["zh", "en"] as const

function isSupportedLanguage(language: string | null | undefined): language is (typeof supportedLanguages)[number] {
  return !!language && supportedLanguages.includes(language as (typeof supportedLanguages)[number])
}

function getInitialLanguage() {
  if (typeof window === "undefined") {
    return "en"
  }

  const storedLanguage = window.localStorage.getItem("i18nextLng")
  if (isSupportedLanguage(storedLanguage)) {
    return storedLanguage
  }

  const browserLanguage = window.navigator.language?.split("-")[0]
  return isSupportedLanguage(browserLanguage) ? browserLanguage : "en"
}

void i18n.use(initReactI18next).init({
  resources: {
    zh: {
      common: zhCommon,
    },
    en: {
      common: enCommon,
    },
  },
  lng: getInitialLanguage(),
  fallbackLng: "en",
  ns: ["common"],
  defaultNS: "common",
  interpolation: {
    escapeValue: false,
  },
})

i18n.on("languageChanged", (language) => {
  if (typeof window !== "undefined") {
    window.localStorage.setItem("i18nextLng", language)
  }
})

export default i18n
