/**
 * Tests for src/components/ui.jsx
 *
 * Tests the pure presentational components that make up the design system.
 * We test behaviour (what the user sees), not implementation details.
 */

import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import {
  SignalBadge,
  ScoreBar,
  MetricCard,
  ExplainBox,
  EmptyState,
  ErrorState,
  scoreColor,
} from '../../components/ui'

// react-i18next mock — returns the key as the translation
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => ({
      signal_buy:     'BUY',
      signal_sell:    'SELL',
      signal_neutral: 'NEUTRAL',
      section_warnings: 'Data warnings',
      error_not_found: 'Ticker not found',
      error_generic:   'Something went wrong',
    }[key] ?? key),
  }),
}))

// ── scoreColor ─────────────────────────────────────────────────────────────────

describe('scoreColor', () => {
  it('returns green for scores >= 60', () => {
    expect(scoreColor(60)).toBe('#00d97e')
    expect(scoreColor(80)).toBe('#00d97e')
    expect(scoreColor(100)).toBe('#00d97e')
  })

  it('returns red for scores < 40', () => {
    expect(scoreColor(39)).toBe('#ff4757')
    expect(scoreColor(0)).toBe('#ff4757')
  })

  it('returns amber for scores between 40 and 59', () => {
    expect(scoreColor(40)).toBe('#f5a623')
    expect(scoreColor(50)).toBe('#f5a623')
    expect(scoreColor(59)).toBe('#f5a623')
  })
})

// ── SignalBadge ────────────────────────────────────────────────────────────────

describe('SignalBadge', () => {
  it('renders BUY label for buy signal', () => {
    render(<SignalBadge signal="buy" score={72} />)
    expect(screen.getByText('BUY')).toBeInTheDocument()
  })

  it('renders SELL label for sell signal', () => {
    render(<SignalBadge signal="sell" score={30} />)
    expect(screen.getByText('SELL')).toBeInTheDocument()
  })

  it('renders NEUTRAL label for neutral signal', () => {
    render(<SignalBadge signal="neutral" score={50} />)
    expect(screen.getByText('NEUTRAL')).toBeInTheDocument()
  })

  it('renders the score', () => {
    render(<SignalBadge signal="buy" score={72} />)
    expect(screen.getByText(/72/)).toBeInTheDocument()
  })

  it('renders without score when score is undefined', () => {
    render(<SignalBadge signal="buy" />)
    expect(screen.getByText('BUY')).toBeInTheDocument()
  })
})

// ── ScoreBar ───────────────────────────────────────────────────────────────────

describe('ScoreBar', () => {
  it('renders the label', () => {
    render(<ScoreBar label="Fundamental" value={65} color="#3b82f6" />)
    expect(screen.getByText('Fundamental')).toBeInTheDocument()
  })

  it('renders the value', () => {
    render(<ScoreBar label="Technical" value={72} color="#8b5cf6" />)
    expect(screen.getByText('72')).toBeInTheDocument()
  })

  it('renders 0 value without crashing', () => {
    render(<ScoreBar label="Score" value={0} color="#ff4757" />)
    expect(screen.getByText('Score')).toBeInTheDocument()
  })
})

// ── MetricCard ─────────────────────────────────────────────────────────────────

describe('MetricCard', () => {
  it('renders label and value', () => {
    render(<MetricCard label="Beta (β)" value="1.24" />)
    expect(screen.getByText('Beta (β)')).toBeInTheDocument()
    expect(screen.getByText('1.24')).toBeInTheDocument()
  })

  it('renders delta when provided', () => {
    render(<MetricCard label="Price" value="182.40" delta="+1.2% today" deltaPositive />)
    expect(screen.getByText('+1.2% today')).toBeInTheDocument()
  })

  it('renders em dash when value is not provided', () => {
    render(<MetricCard label="Fair value" value={undefined} />)
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('renders help text when provided', () => {
    render(<MetricCard label="CAPM" value="9.8%" help="r = rf + β(rm − rf)" />)
    expect(screen.getByText('r = rf + β(rm − rf)')).toBeInTheDocument()
  })
})

// ── ExplainBox ─────────────────────────────────────────────────────────────────

describe('ExplainBox', () => {
  it('renders the title', () => {
    render(<ExplainBox title="RSI — Relative Strength Index">Explanation text</ExplainBox>)
    expect(screen.getByText('RSI — Relative Strength Index')).toBeInTheDocument()
  })

  it('renders children content', () => {
    render(<ExplainBox title="Test">Content goes here</ExplainBox>)
    expect(screen.getByText('Content goes here')).toBeInTheDocument()
  })

  it('renders source when provided', () => {
    render(
      <ExplainBox title="Test" source="Murphy (1999) p.225">Body</ExplainBox>
    )
    expect(screen.getByText(/Murphy \(1999\) p\.225/)).toBeInTheDocument()
  })

  it('does not render source section when not provided', () => {
    const { container } = render(<ExplainBox title="Test">Body</ExplainBox>)
    expect(container.querySelector('[class*="source"]')).not.toBeInTheDocument()
    expect(screen.queryByText(/📚/)).not.toBeInTheDocument()
  })
})

// ── EmptyState ─────────────────────────────────────────────────────────────────

describe('EmptyState', () => {
  it('renders the message', () => {
    render(<EmptyState message="Nothing to show yet." />)
    expect(screen.getByText('Nothing to show yet.')).toBeInTheDocument()
  })
})

// ── ErrorState ─────────────────────────────────────────────────────────────────

describe('ErrorState', () => {
  it('renders not-found message for 404 error', () => {
    render(<ErrorState error={{ status: 404, message: 'Not found' }} />)
    expect(screen.getByText('Ticker not found')).toBeInTheDocument()
  })

  it('renders generic message for non-404 error', () => {
    render(<ErrorState error={{ status: 503, message: 'Service unavailable' }} />)
    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
  })

  it('renders the raw error message for details', () => {
    render(<ErrorState error={{ status: 503, message: 'yfinance timeout' }} />)
    expect(screen.getByText('yfinance timeout')).toBeInTheDocument()
  })
})
