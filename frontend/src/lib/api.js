/**
 * StockIQ API client
 *
 * Thin wrapper around fetch that:
 * - Points at the FastAPI backend (http://localhost:8000 in dev)
 * - Normalises errors into a consistent shape
 * - Adds request logging in development
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`
  const start = performance.now()

  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })

  const ms = (performance.now() - start).toFixed(0)
  if (import.meta.env.DEV) {
    console.debug(`[API] ${options.method ?? 'GET'} ${path} → ${res.status} (${ms}ms)`)
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw {
      status: res.status,
      message: body.detail ?? body.message ?? `HTTP ${res.status}`,
    }
  }

  return res.json()
}

export function analyze(ticker, period = '1y', strategy = 'weighted_average') {
  return request('/v1/analyze', {
    method: 'POST',
    body: JSON.stringify({ ticker, period, strategy }),
  })
}

export function analyzePortfolio(currentAllocation, totalValue, horizonYears = 10) {
  return request('/v1/portfolio', {
    method: 'POST',
    body: JSON.stringify({
      current_allocation: currentAllocation,
      total_value: totalValue,
      horizon_years: horizonYears,
    }),
  })
}

export function simulate(params) {
  return request('/v1/simulate', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

export function health() {
  return request('/health')
}
