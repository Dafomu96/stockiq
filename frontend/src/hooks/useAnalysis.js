/**
 * useAnalysis — central state hook for the analysis pipeline.
 *
 * Change from original: run() now returns the result data (or null on error).
 * This allows callers to push results to history or watchlist cache
 * without needing a separate useEffect on the result state.
 */
import { useState, useCallback } from 'react'
import { analyze } from '../lib/api'

export function useAnalysis() {
  const [result, setResult]   = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const [ticker, setTicker]   = useState('')

  const run = useCallback(async (symbol, period = '1y', strategy = 'weighted_average') => {
    if (!symbol.trim()) return null
    setLoading(true)
    setError(null)
    try {
      const data = await analyze(symbol.trim().toUpperCase(), period, strategy)
      setResult(data)
      setTicker(data.ticker)
      return data      // callers can use this to push to history / watchlist cache
    } catch (err) {
      setError(err)
      setResult(null)
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  const clear = useCallback(() => {
    setResult(null)
    setError(null)
    setTicker('')
  }, [])

  return { result, loading, error, ticker, run, clear }
}
