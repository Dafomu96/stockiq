/**
 * useHistory — persists the last N analysis results in localStorage.
 *
 * Every time the user runs an analysis (via useAnalysis), the result
 * is pushed here. The history page renders the saved entries as a
 * chronological list with scores, signals, and a "re-analyse" button.
 *
 * Storage key: "stockiq:history"
 * Format: JSON array of HistoryEntry, newest first.
 *
 * HistoryEntry shape:
 *   {
 *     id:         string   — UUID, stable across re-renders
 *     ticker:     string   — uppercase symbol
 *     date:       string   — ISO date (YYYY-MM-DD)
 *     time:       string   — HH:MM UTC
 *     score:      number   — composite score 0–100
 *     signal:     string   — "buy" | "neutral" | "sell"
 *     fundamental: number  — fundamental sub-score
 *     technical:  number   — technical sub-score
 *     confidence: string   — "high" | "medium" | "low"
 *     capm:       number | null
 *     upside_pct: number | null
 *   }
 */

import { useState, useCallback, useEffect } from 'react'

const STORAGE_KEY = 'stockiq:history'
const MAX_ENTRIES = 20

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function save(entries) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries))
  } catch {}
}

function toEntry(result) {
  const now = new Date()
  return {
    id:          crypto.randomUUID(),
    ticker:      result.ticker,
    date:        now.toISOString().slice(0, 10),
    time:        now.toISOString().slice(11, 16) + ' UTC',
    score:       result.composite_score,
    signal:      result.signal,
    fundamental: result.score_breakdown?.fundamental ?? null,
    technical:   result.score_breakdown?.technical ?? null,
    confidence:  result.confidence,
    capm:        result.fundamental?.capm?.required_return ?? null,
    upside_pct:  result.fundamental?.gordon?.upside_pct ?? null,
  }
}

export function useHistory() {
  const [entries, setEntries] = useState(() => load())

  useEffect(() => { save(entries) }, [entries])

  const push = useCallback((result) => {
    if (!result?.ticker) return
    setEntries(prev => {
      const entry = toEntry(result)
      // Remove any previous entry for the same ticker so we don't accumulate
      // 20 entries of AAPL — keep the most recent one per ticker at the top.
      const filtered = prev.filter(e => e.ticker !== result.ticker)
      return [entry, ...filtered].slice(0, MAX_ENTRIES)
    })
  }, [])

  const remove = useCallback((id) => {
    setEntries(prev => prev.filter(e => e.id !== id))
  }, [])

  const clear = useCallback(() => setEntries([]), [])

  return {
    entries,   // HistoryEntry[] — newest first
    push,      // (CompositeResult) => void — call after every analysis
    remove,    // (id: string) => void
    clear,     // () => void
    count: entries.length,
  }
}
