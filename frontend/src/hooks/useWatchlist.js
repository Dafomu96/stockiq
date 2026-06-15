/**
 * useWatchlist — persistent ticker watchlist via localStorage.
 *
 * Design decisions:
 * - localStorage only: no backend required. The watchlist is personal
 *   to the user's browser — no auth, no database, no API call.
 * - Lazy initialisation: reads localStorage once on mount, never on
 *   every render. Writes are synchronous (localStorage is fast).
 * - Deduplication: adding the same ticker twice is a no-op.
 * - Order preserved: tickers appear in the order they were added.
 * - Max 20 tickers: prevents the sidebar from becoming unusable.
 *
 * Storage key: "stockiq:watchlist"
 * Format: JSON array of uppercase ticker strings, e.g. ["AAPL","ASML.AS"]
 */

import { useState, useCallback, useEffect } from 'react'

const STORAGE_KEY = 'stockiq:watchlist'
const MAX_TICKERS = 20

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(t => typeof t === 'string' && t.length > 0)
  } catch {
    return []
  }
}

function saveToStorage(tickers) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(tickers))
  } catch {
    // localStorage can throw in private browsing with storage quota exceeded
    // Fail silently — the watchlist just won't persist this session
  }
}

export function useWatchlist() {
  const [tickers, setTickers] = useState(() => loadFromStorage())

  // Persist to localStorage whenever tickers change
  useEffect(() => {
    saveToStorage(tickers)
  }, [tickers])

  const add = useCallback((ticker) => {
    const upper = ticker.trim().toUpperCase()
    if (!upper) return
    setTickers(prev => {
      if (prev.includes(upper)) return prev          // already in list
      if (prev.length >= MAX_TICKERS) return prev    // cap reached
      return [...prev, upper]
    })
  }, [])

  const remove = useCallback((ticker) => {
    const upper = ticker.trim().toUpperCase()
    setTickers(prev => prev.filter(t => t !== upper))
  }, [])

  const toggle = useCallback((ticker) => {
    const upper = ticker.trim().toUpperCase()
    setTickers(prev =>
      prev.includes(upper)
        ? prev.filter(t => t !== upper)
        : prev.length >= MAX_TICKERS ? prev : [...prev, upper]
    )
  }, [])

  const clear = useCallback(() => setTickers([]), [])

  const isWatched = useCallback(
    (ticker) => tickers.includes(ticker.trim().toUpperCase()),
    [tickers]
  )

  return {
    tickers,       // string[] — ordered list of uppercase ticker symbols
    add,           // (ticker: string) => void
    remove,        // (ticker: string) => void
    toggle,        // (ticker: string) => void — add if absent, remove if present
    clear,         // () => void
    isWatched,     // (ticker: string) => boolean
    count: tickers.length,
    isFull: tickers.length >= MAX_TICKERS,
  }
}
