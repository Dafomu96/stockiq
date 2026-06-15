/**
 * Tests for src/hooks/useWatchlist.js
 *
 * Uses renderHook from @testing-library/react to test the hook
 * in isolation without rendering a full component tree.
 */

import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, beforeEach } from 'vitest'
import { useWatchlist } from '../../hooks/useWatchlist'

// localStorage is cleared before each test by setup.js

describe('useWatchlist', () => {

  describe('initial state', () => {
    it('starts with an empty list', () => {
      const { result } = renderHook(() => useWatchlist())
      expect(result.current.tickers).toEqual([])
      expect(result.current.count).toBe(0)
      expect(result.current.isFull).toBe(false)
    })

    it('loads persisted tickers from localStorage', () => {
      localStorage.setItem('stockiq:watchlist', JSON.stringify(['AAPL', 'MSFT']))
      const { result } = renderHook(() => useWatchlist())
      expect(result.current.tickers).toEqual(['AAPL', 'MSFT'])
    })

    it('ignores corrupted localStorage data', () => {
      localStorage.setItem('stockiq:watchlist', 'not-valid-json{{{')
      const { result } = renderHook(() => useWatchlist())
      expect(result.current.tickers).toEqual([])
    })
  })

  describe('add', () => {
    it('adds a ticker', () => {
      const { result } = renderHook(() => useWatchlist())
      act(() => result.current.add('AAPL'))
      expect(result.current.tickers).toContain('AAPL')
    })

    it('uppercases the ticker', () => {
      const { result } = renderHook(() => useWatchlist())
      act(() => result.current.add('aapl'))
      expect(result.current.tickers).toContain('AAPL')
    })

    it('does not add duplicates', () => {
      const { result } = renderHook(() => useWatchlist())
      act(() => { result.current.add('AAPL'); result.current.add('AAPL') })
      expect(result.current.tickers.filter(t => t === 'AAPL')).toHaveLength(1)
    })

    it('ignores empty strings', () => {
      const { result } = renderHook(() => useWatchlist())
      act(() => result.current.add(''))
      expect(result.current.tickers).toHaveLength(0)
    })

    it('persists to localStorage', () => {
      const { result } = renderHook(() => useWatchlist())
      act(() => result.current.add('TSLA'))
      const stored = JSON.parse(localStorage.getItem('stockiq:watchlist'))
      expect(stored).toContain('TSLA')
    })
  })

  describe('remove', () => {
    it('removes a specific ticker', () => {
      localStorage.setItem('stockiq:watchlist', JSON.stringify(['AAPL', 'MSFT']))
      const { result } = renderHook(() => useWatchlist())
      act(() => result.current.remove('AAPL'))
      expect(result.current.tickers).not.toContain('AAPL')
      expect(result.current.tickers).toContain('MSFT')
    })

    it('is a no-op for a ticker not in the list', () => {
      localStorage.setItem('stockiq:watchlist', JSON.stringify(['AAPL']))
      const { result } = renderHook(() => useWatchlist())
      act(() => result.current.remove('NOTHERE'))
      expect(result.current.tickers).toHaveLength(1)
    })
  })

  describe('toggle', () => {
    it('adds a ticker that is not watched', () => {
      const { result } = renderHook(() => useWatchlist())
      act(() => result.current.toggle('GOOG'))
      expect(result.current.tickers).toContain('GOOG')
    })

    it('removes a ticker that is already watched', () => {
      localStorage.setItem('stockiq:watchlist', JSON.stringify(['GOOG']))
      const { result } = renderHook(() => useWatchlist())
      act(() => result.current.toggle('GOOG'))
      expect(result.current.tickers).not.toContain('GOOG')
    })
  })

  describe('isWatched', () => {
    it('returns true for a watched ticker', () => {
      localStorage.setItem('stockiq:watchlist', JSON.stringify(['AAPL']))
      const { result } = renderHook(() => useWatchlist())
      expect(result.current.isWatched('AAPL')).toBe(true)
    })

    it('returns false for a ticker not in list', () => {
      const { result } = renderHook(() => useWatchlist())
      expect(result.current.isWatched('AAPL')).toBe(false)
    })

    it('is case-insensitive', () => {
      localStorage.setItem('stockiq:watchlist', JSON.stringify(['AAPL']))
      const { result } = renderHook(() => useWatchlist())
      expect(result.current.isWatched('aapl')).toBe(true)
    })
  })

  describe('clear', () => {
    it('removes all tickers', () => {
      localStorage.setItem('stockiq:watchlist', JSON.stringify(['AAPL', 'MSFT']))
      const { result } = renderHook(() => useWatchlist())
      act(() => result.current.clear())
      expect(result.current.tickers).toHaveLength(0)
    })

    it('clears localStorage', () => {
      localStorage.setItem('stockiq:watchlist', JSON.stringify(['AAPL']))
      const { result } = renderHook(() => useWatchlist())
      act(() => result.current.clear())
      expect(JSON.parse(localStorage.getItem('stockiq:watchlist'))).toHaveLength(0)
    })
  })

  describe('max limit', () => {
    it('does not exceed 20 tickers', () => {
      const { result } = renderHook(() => useWatchlist())
      act(() => {
        for (let i = 0; i < 25; i++) {
          result.current.add(`TICK${i}`)
        }
      })
      expect(result.current.tickers).toHaveLength(20)
      expect(result.current.isFull).toBe(true)
    })
  })
})
