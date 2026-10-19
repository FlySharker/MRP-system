"use client"

import { useEffect } from "react"

const SHUTDOWN_URL = "http://127.0.0.1:8000/api/shutdown"

/**
 * Sends a shutdown request when the page/tab is closed or the browser exits.
 * Uses navigator.sendBeacon which works reliably during page unload.
 */
export function PageCloseHandler() {
  useEffect(() => {
    const handleBeforeUnload = () => {
      navigator.sendBeacon(SHUTDOWN_URL, JSON.stringify({}))
    }

    window.addEventListener("beforeunload", handleBeforeUnload)
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload)
    }
  }, [])

  return null
}
