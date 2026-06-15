/**
 * Tests for src/hooks/useHistory.js
 */

import { renderHook, act } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { useHistory } from '../../hooks/useHistory'

function makeResult(ticker = 'AAPL', score = 65.0, signal = 'buy') {
  return {
    ticker,
    composite_score: score,
    signal,
    score_breakdown: { fundamental: 60.0, technical: 70.0 },
    confidence: 'medium',
    fundamental: {
      capm: { required_return: 0.1132 },
      gordon: { upside_pct: 10.5 },
    },
  }
}

describe('useHistory', () => {

  describe('initial state', () => {
    it('starts empty', () => {
      const { result } = renderHook(() => useHistory())
      expect(result.current.entries).toHaveLength(0)
      expect(result.current.count).toBe(0)
    })

    it('loads persisted entries from localStorage', () => {
      const entry = { id: 'x', ticker: 'AAPL', score: 65 }
      localStorage.setItem('stockiq:history', JSON.stringify([entry]))
      const { result } = renderHook(() => useHistory())
      expect(result.current.entries).toHaveLength(1)
      expect(result.current.entries[0].ticker).toBe('AAPL')
    })
  })

  describe('push', () => {
    it('adds a new entry', () => {
      const { result } = renderHook(() => useHistory())
      act(() => result.current.push(makeResult()))
      expect(result.current.entries).toHaveLength(1)
      expect(result.current.entries[0].ticker).toBe('AAPL')
    })

    it('stores the composite score', () => {
      const { result } = renderHook(() => useHistory())
      act(() => result.current.push(makeResult('AAPL', 72.5)))
      expect(result.current.entries[0].score).toBe(72.5)
    })

    it('stores the signal', () => {
      const { result } = renderHook(() => useHistory())
      act(() => result.current.push(makeResult('AAPL', 65, 'neutral')))
      expect(result.current.entries[0].signal).toBe('neutral')
    })

    it('stores sub-scores', () => {
      const { result } = renderHook(() => useHistory())
      act(() => result.current.push(makeResult()))
      expect(result.current.entries[0].fundamental).toBe(60.0)
      expect(result.current.entries[0].technical).toBe(70.0)
    })

    it('newest entry is first', () => {
      const { result } = renderHook(() => useHistory())
      act(() => {
        result.current.push(makeResult('AAPL'))
        result.current.push(makeResult('MSFT'))
      })
      expect(result.current.entries[0].ticker).toBe('MSFT')
    })

    it('replaces existing entry for same ticker', () => {
      const { result } = renderHook(() => useHistory())
      act(() => {
        result.current.push(makeResult('AAPL', 60))
        result.current.push(makeResult('AAPL', 75))
      })
      const aaplEntries = result.current.entries.filter(e => e.ticker === 'AAPL')
      expect(aaplEntries).toHaveLength(1)
      expect(aaplEntries[0].score).toBe(75)
    })

    it('does nothing for a result without ticker', () => {
      const { result } = renderHook(() => useHistory())
      act(() => result.current.push({ composite_score: 65 }))
      expect(result.current.entries).toHaveLength(0)
    })

    it('persists to localStorage', () => {
      const { result } = renderHook(() => useHistory())
      act(() => result.current.push(makeResult()))
      const stored = JSON.parse(localStorage.getItem('stockiq:history'))
      expect(stored).toHaveLength(1)
      expect(stored[0].ticker).toBe('AAPL')
    })

    it('caps at 20 entries', () => {
      const { result } = renderHook(() => useHistory())
      act(() => {
        for (let i = 0; i < 25; i++) {
          result.current.push(makeResult(`TICK${i}`))
        }
      })
      expect(result.current.entries).toHaveLength(20)
    })
  })

  describe('remove', () => {
    it('removes entry by id', () => {
      const { result } = renderHook(() => useHistory())
      act(() => result.current.push(makeResult('AAPL')))
      const id = result.current.entries[0].id
      act(() => result.current.remove(id))
      expect(result.current.entries).toHaveLength(0)
    })

    it('is a no-op for unknown id', () => {
      const { result } = renderHook(() => useHistory())
      act(() => result.current.push(makeResult()))
      act(() => result.current.remove('non-existent-id'))
      expect(result.current.entries).toHaveLength(1)
    })
  })

  describe('clear', () => {
    it('removes all entries', () => {
      const { result } = renderHook(() => useHistory())
      act(() => {
        result.current.push(makeResult('AAPL'))
        result.current.push(makeResult('MSFT'))
      })
      act(() => result.current.clear())
      expect(result.current.entries).toHaveLength(0)
    })
  })
})
