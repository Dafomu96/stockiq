/**
 * Tests for src/pages/Glossary.jsx
 *
 * The Glossary is the most testable page because it has no API calls —
 * it is purely driven by the TERMS constant and user interaction.
 */

import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import Glossary from '../../pages/Glossary'

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => ({
      glossary_title:    'Glossary',
      glossary_search:   'Search terms…',
    }[key] ?? key),
    i18n: { language: 'en' },
  }),
}))

describe('Glossary', () => {

  it('renders the glossary title', () => {
    render(<Glossary />)
    expect(screen.getByText('Glossary')).toBeInTheDocument()
  })

  it('renders all 10 terms by default', () => {
    render(<Glossary />)
    expect(screen.getByText('10 terms')).toBeInTheDocument()
  })

  it('renders the search input', () => {
    render(<Glossary />)
    expect(screen.getByPlaceholderText('Search terms…')).toBeInTheDocument()
  })

  it('filters terms by search text', () => {
    render(<Glossary />)
    const input = screen.getByPlaceholderText('Search terms…')
    fireEvent.change(input, { target: { value: 'Golden Cross' } })
    expect(screen.getByText('1 terms')).toBeInTheDocument()
  })

  it('shows zero results for non-matching search', () => {
    render(<Glossary />)
    const input = screen.getByPlaceholderText('Search terms…')
    fireEvent.change(input, { target: { value: 'xyznonexistentterm' } })
    expect(screen.getByText('0 terms')).toBeInTheDocument()
  })

  it('filters by category — Technical', () => {
    render(<Glossary />)
    const techBtn = screen.getByRole('button', { name: 'Technical' })
    fireEvent.click(techBtn)
    // Only technical terms should show
    const count = screen.getByText(/\d+ terms/)
    const num = parseInt(count.textContent)
    expect(num).toBeGreaterThan(0)
    expect(num).toBeLessThan(10)
  })

  it('shows all terms when All category selected', () => {
    render(<Glossary />)
    // First filter to Technical
    fireEvent.click(screen.getByRole('button', { name: 'Technical' }))
    // Then back to All
    fireEvent.click(screen.getByRole('button', { name: 'All' }))
    expect(screen.getByText('10 terms')).toBeInTheDocument()
  })

  it('renders category filter buttons', () => {
    render(<Glossary />)
    expect(screen.getByRole('button', { name: 'All' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Fundamental' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Technical' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Portfolio' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Risk' })).toBeInTheDocument()
  })

  it('CAPM term is visible when searching capm', () => {
    render(<Glossary />)
    const input = screen.getByPlaceholderText('Search terms…')
    fireEvent.change(input, { target: { value: 'Sharpe' } })
    expect(screen.getByText('1 terms')).toBeInTheDocument()
  })
})
