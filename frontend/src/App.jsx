import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAnalysis } from './hooks/useAnalysis'
import './lib/i18n'

import Overview    from './pages/Overview'
import Technical   from './pages/Technical'
import Fundamental from './pages/Fundamental'
import Portfolio   from './pages/Portfolio'
import Simulator   from './pages/Simulator'
import Glossary    from './pages/Glossary'

const NAV = [
  { id: 'overview',    icon: '◈', labelKey: 'nav_overview' },
  { id: 'technical',   icon: '⟁', labelKey: 'nav_technical' },
  { id: 'fundamental', icon: '⊕', labelKey: 'nav_fundamental' },
  { id: 'portfolio',   icon: '⬡', labelKey: 'nav_portfolio' },
  { id: 'simulator',   icon: '◎', labelKey: 'nav_simulator' },
  { id: 'glossary',    icon: '≡', labelKey: 'nav_glossary' },
]

export default function App() {
  const { t, i18n } = useTranslation()
  const [page, setPage] = useState('overview')
  const [input, setInput] = useState('')
  const { result, loading, error, run } = useAnalysis()

  function handleAnalyse(e) {
    e.preventDefault()
    if (input.trim()) run(input.trim())
  }

  function toggleLang() {
    i18n.changeLanguage(i18n.language === 'en' ? 'es' : 'en')
  }

  return (
    <div className="flex h-screen bg-bg-primary overflow-hidden">
      <aside className="w-56 flex-shrink-0 bg-bg-secondary border-r border-bg-border flex flex-col">
        <div className="px-5 py-5 border-b border-bg-border">
          <div className="text-xl font-display font-bold text-slate-100 tracking-tight">StockIQ</div>
          <div className="text-[10px] text-slate-600 font-body mt-0.5 tracking-widest uppercase">Shiller · Murphy · Swensen</div>
        </div>
        <form onSubmit={handleAnalyse} className="px-4 py-4 border-b border-bg-border">
          <input
            value={input}
            onChange={e => setInput(e.target.value.toUpperCase())}
            placeholder={t('ticker_placeholder')}
            className="w-full bg-bg-primary border border-bg-border rounded-lg px-3 py-2 text-sm font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-accent transition-colors"
          />
          <button type="submit" disabled={loading || !input.trim()} className="btn-primary w-full mt-2 text-sm">
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-3.5 h-3.5 rounded-full border border-white border-t-transparent animate-spin" />
                {t('analyzing')}
              </span>
            ) : t('analyze_btn')}
          </button>
        </form>
        <nav className="flex-1 px-3 py-3 space-y-0.5 overflow-y-auto">
          {NAV.map(item => (
            <button key={item.id} onClick={() => setPage(item.id)} className={`nav-item w-full text-left ${page === item.id ? 'active' : ''}`}>
              <span className="font-mono text-base w-5 flex-shrink-0 text-center">{item.icon}</span>
              <span>{t(item.labelKey)}</span>
            </button>
          ))}
        </nav>
        <div className="px-4 py-4 border-t border-bg-border space-y-3">
          <button onClick={toggleLang} className="btn-ghost w-full text-xs flex items-center justify-center gap-2">
            <span>{i18n.language === 'en' ? '🇬🇧 EN' : '🇪🇸 ES'}</span>
            <span className="text-slate-600">→</span>
            <span>{i18n.language === 'en' ? 'ES' : 'EN'}</span>
          </button>
          <p className="text-[10px] text-slate-600 font-body text-center leading-relaxed">{t('disclaimer')}</p>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-6 py-6">
          {page === 'overview'    && <Overview    result={result} loading={loading} error={error} />}
          {page === 'technical'   && <Technical   result={result} loading={loading} error={error} />}
          {page === 'fundamental' && <Fundamental result={result} loading={loading} error={error} />}
          {page === 'portfolio'   && <Portfolio />}
          {page === 'simulator'   && <Simulator   analysisResult={result} />}
          {page === 'glossary'    && <Glossary />}
        </div>
      </main>
    </div>
  )
}
