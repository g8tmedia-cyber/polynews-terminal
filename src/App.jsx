import { useState, useEffect, useRef, useCallback } from 'react'

const SOURCES = [
  { id: 'hn', label: 'Hacker News', color: '#ff6600' },
  { id: 'bbc', label: 'BBC News', color: '#bb1919' },
  { id: 'yahoo', label: 'Yahoo Finance', color: '#6001d2' },
  { id: 'coindesk', label: 'CoinDesk', color: '#00b269' },
  { id: 'block', label: 'The Block', color: '#00d4ff' },
  { id: 'polymarket', label: 'Polymarket', color: '#f0b90b' },
  { id: 'reddit', label: 'Reddit', color: '#ff4500' },
  { id: 'google', label: 'Google News', color: '#4285f4' },
]

function SourceBadge({ source }) {
  const s = SOURCES.find(x => x.id === source) || SOURCES[0]
  return (
    <span
      className="inline-block px-1.5 py-0.5 rounded text-xs font-bold mr-2 mb-1"
      style={{ backgroundColor: s.color + '22', color: s.color, border: `1px solid ${s.color}44` }}
    >
      {s.label}
    </span>
  )
}

function TimeAgo({ ts }) {
  const [ago, setAgo] = useState('')
  useEffect(() => {
    const update = () => {
      const diff = Math.floor((Date.now() / 1000 - ts))
      if (diff < 60) setAgo(`${diff}s ago`)
      else if (diff < 3600) setAgo(`${Math.floor(diff / 60)}m ago`)
      else setAgo(`${Math.floor(diff / 3600)}h ago`)
    }
    update()
    const id = setInterval(update, 30000)
    return () => clearInterval(id)
  }, [ts])
  return <span className="text-gray-500">{ago}</span>
}

function TickerItem({ text, color }) {
  return (
    <span className="inline-flex items-center whitespace-nowrap mx-6 text-sm">
      <span className="w-2 h-2 rounded-full mr-2" style={{ backgroundColor: color }} />
      <span className="text-terminal-text">{text}</span>
    </span>
  )
}

function NewsCard({ item }) {
  const s = SOURCES.find(x => x.id === item.source) || SOURCES[0]
  const hasUrl = item.url && item.url.length > 5

  if (hasUrl) {
    return (
      <a
        href={item.url}
        target="_blank"
        rel="noopener noreferrer"
        className="block p-4 bg-terminal-panel border border-terminal-border rounded-lg hover:border-terminal-muted transition-colors touch-target"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color }} />
              <span className="text-xs font-semibold" style={{ color: s.color }}>{s.label}</span>
              {item.time && <TimeAgo ts={item.time} />}
            </div>
            <h3 className="text-terminal-text font-medium text-sm leading-snug mb-2 line-clamp-2">
              {item.title}
            </h3>
          </div>
        </div>
      </a>
    )
  }

  // No URL — show as static card (not clickable)
  return (
    <div className="block p-4 bg-terminal-panel border border-terminal-border rounded-lg opacity-60 touch-target">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            <span className="w-2 h-2 rounded-full" style={{ backgroundColor: s.color }} />
            <span className="text-xs font-semibold" style={{ color: s.color }}>{s.label}</span>
            {item.time && <TimeAgo ts={item.time} />}
          </div>
          <h3 className="text-terminal-text font-medium text-sm leading-snug mb-2 line-clamp-2">
            {item.title}
          </h3>
        </div>
      </div>
    </div>
  )
}

function SearchBar({ value, onChange }) {
  return (
    <div className="relative">
      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-terminal-muted">🔍</span>
      <input
        type="text"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder="Filter headlines..."
        className="w-full bg-terminal-bg border border-terminal-border rounded-lg pl-10 pr-4 py-2.5 text-sm text-terminal-text placeholder-terminal-muted focus:outline-none focus:border-terminal-green transition-colors"
      />
    </div>
  )
}

function StatusBar({ connected, lastUpdate, itemCount }) {
  return (
    <div className="flex items-center justify-between text-xs text-terminal-muted px-4 py-2 border-b border-terminal-border">
      <div className="flex items-center gap-4">
        <span className={connected ? 'text-terminal-green' : 'text-terminal-red'}>
          ● {connected ? 'LIVE' : 'CONNECTING'}
        </span>
        <span>{itemCount} headlines</span>
        {lastUpdate && <span>Updated {new Date(lastUpdate * 1000).toLocaleTimeString()}</span>}
      </div>
      <div className="flex items-center gap-2">
        <span className="text-terminal-amber">✉ vin@hermini.pc</span>
        <span>·</span>
        <span>v1.0.0</span>
      </div>
    </div>
  )
}

function MobileNav({ activeTab, onTabChange }) {
  return (
    <div className="md:hidden fixed bottom-0 left-0 right-0 bg-terminal-header border-t border-terminal-border z-50">
      <div className="flex overflow-x-auto scrollbar-hide">
        {['all', 'finance', 'crypto', 'news'].map(tab => (
          <button
            key={tab}
            onClick={() => onTabChange(tab)}
            className={`flex-1 py-3 px-4 text-xs font-bold uppercase tracking-wider transition-colors whitespace-nowrap touch-target ${
              activeTab === tab
                ? 'text-terminal-green border-b-2 border-terminal-green bg-terminal-green/5'
                : 'text-terminal-muted hover:text-terminal-text'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Parse raw polynews lines into structured items ─────────────────────────────
function parseItems(rawLines) {
  // Join continuation lines (multi-line titles/descriptions that got split)
  // Lines that don't start with a marker are continuations of previous line
  const joined = []
  for (let i = 0; i < rawLines.length; i++) {
    const line = rawLines[i]
    const trimmed = line.trim()

    // Source header, empty, or control line = start new
    if (!trimmed || /^[,╭╰│├└─═▸▶📊📰💹🔗📈🪙💬🌐]+$/.test(trimmed) || /^[▸▶📊📰💹🔗📈🪙💬🌐]+ /.test(trimmed)) {
      joined.push({ type: 'raw', text: line })
      continue
    }

    // Line starting with bullet marker
    if (trimmed.startsWith('• ')) {
      joined.push({ type: 'raw', text: line })
      continue
    }

    // Score lines (HN/Reddit): "    3      0  Title" or " 18372  Title"
    if (/^\s*\d+\s+\d+\s+.+/.test(trimmed)) {
      joined.push({ type: 'raw', text: line })
      continue
    }

    // Bare domain line (URL on its own)
    if (/^[a-zA-Z0-9.-]+\.(?:com|org|net|io|co\.uk|gov|edu|info|biz|app|dev|io|tv|cc|ai)\/?$/i.test(trimmed)) {
      joined.push({ type: 'url', text: trimmed })
      continue
    }

    // Continuation — append to previous raw line
    if (joined.length > 0 && joined[joined.length - 1].type === 'raw') {
      joined[joined.length - 1].text += ' ' + trimmed
    } else {
      joined.push({ type: 'raw', text: line })
    }
  }

  const items = []
  let currentSource = ''
  const srcMap = {
    'Hacker News': 'hn', 'BBC News': 'bbc', 'Yahoo Finance': 'yahoo',
    'CoinDesk': 'coindesk', 'The Block': 'block', 'Polymarket': 'polymarket',
    'Reddit': 'reddit', 'Google News': 'google',
    'r/stocks': 'reddit', 'r/news': 'reddit', 'r/economy': 'reddit',
    'r/worldnews': 'reddit', 'r/cryptocurrency': 'reddit', 'r/wallstreetbets': 'reddit',
  }

  for (let i = 0; i < joined.length; i++) {
    const entry = joined[i]
    if (entry.type === 'url') {
      // Attach URL to previous item
      const url = entry.text.startsWith('http') ? entry.text : `https://${entry.text}`
      if (items.length > 0 && !items[items.length - 1].url) {
        items[items.length - 1].url = url
      }
      continue
    }

    const line = entry.text
    const trimmed = line.trim()
    if (!trimmed) continue

    // Source header
    const srcMatch = trimmed.match(/^[▸▶📊📰💹🔗📈🪙💬🌐]+ (.+)/)
    if (srcMatch) {
      currentSource = srcMatch[1].trim()
      continue
    }

    // BBC/Yahoo/Google: starts with bullet
    if (trimmed.startsWith('• ')) {
      // Title is everything after "• "
      const title = trimmed.slice(2).trim()
      if (title.length < 10) continue

      const id = Math.random().toString(36).substr(2, 9)
      const source = srcMap[currentSource] || 'hn'
      const now = Math.floor(Date.now() / 1000)

      // Look ahead for URL in next entries
      let url = ''
      for (let j = i + 1; j < joined.length && j <= i + 3; j++) {
        if (joined[j].type === 'url') {
          url = joined[j].text.startsWith('http') ? joined[j].text : `https://${joined[j].text}`
          break
        }
        if (joined[j].text.trim().startsWith('• ')) break // next item started
        if (/^\s*\d+\s+\d+\s+/.test(joined[j].text.trim())) break // HN item
      }

      items.push({ id, title, source, time: now - Math.floor(Math.random() * 300), url })
      continue
    }

    // HN/Reddit: score line "    N      0  Title"
    const scoreMatch = trimmed.match(/^\s*(\d+)\s+(\d+)\s+(.+)/)
    if (scoreMatch) {
      const title = scoreMatch[3].trim()
      if (title.length < 10) continue
      const id = Math.random().toString(36).substr(2, 9)
      const source = srcMap[currentSource] || 'hn'
      const now = Math.floor(Date.now() / 1000)
      items.push({ id, title, source, time: now - Math.floor(Math.random() * 300), url: '' })
      continue
    }

    // Skip short lines and bare domains
    if (trimmed.length < 15) continue
    if (/^[a-zA-Z0-9.-]+\.(?:com|org|net|io|co\.uk|gov|edu|info|biz|app|dev|io|tv|cc|ai)\/?$/i.test(trimmed)) continue

    // Generic fallback
    const id = Math.random().toString(36).substr(2, 9)
    const source = srcMap[currentSource] || 'hn'
    const now = Math.floor(Date.now() / 1000)
    items.push({ id, title: trimmed, source, time: now - Math.floor(Math.random() * 300), url: '' })
  }

  return items.filter(item => item.title.length > 10)
}

// ── Ticker builder ─────────────────────────────────────────────────────────────
function buildTicker(rawLines) {
  const seen = new Set()
  const ticker = []
  for (let i = rawLines.length - 1; i >= 0; i--) {
    const line = rawLines[i]
    if (line.length < 20 || line.length > 200) continue
    if (line.startsWith('╭') || line.startsWith('╰') || line.startsWith('─') || line.startsWith('═')) continue
    const key = line.trim()
    if (!key || seen.has(key)) continue
    if (seen.size >= 30) break
    seen.add(key)
    ticker.push({ text: key, color: '#00ff88' })
  }
  return ticker
}

export default function App() {
  const [rawLines, setRawLines] = useState([])
  const [items, setItems] = useState([])
  const [ticker, setTicker] = useState([])
  const [connected, setConnected] = useState(false)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [search, setSearch] = useState('')
  const [activeTab, setActiveTab] = useState('all')
  const pollRef = useRef(null)

  const fetchNews = useCallback(async () => {
    try {
      const res = await fetch('/api/news')
      if (res.ok) {
        const data = await res.json()
        if (data.lines && data.lines.length > 0) {
          setRawLines(data.lines)
          setItems(parseItems(data.lines))
          setTicker(buildTicker(data.lines))
          setConnected(true)
          setLastUpdate(Math.floor(Date.now() / 1000))
        }
      } else {
        setConnected(false)
      }
    } catch {
      setConnected(false)
    }
  }, [])

  useEffect(() => {
    fetchNews()
    pollRef.current = setInterval(fetchNews, 30000)
    return () => clearInterval(pollRef.current)
  }, [fetchNews])

  const filteredItems = items.filter(item => {
    const matchSearch = item.title.toLowerCase().includes(search.toLowerCase())
    const matchTab = activeTab === 'all' ||
      (activeTab === 'finance' && ['yahoo'].includes(item.source)) ||
      (activeTab === 'crypto' && ['coindesk', 'block', 'polymarket'].includes(item.source)) ||
      (activeTab === 'news' && ['hn', 'bbc', 'google', 'reddit'].includes(item.source))
    return matchSearch && matchTab
  })

  return (
    <div className="min-h-screen bg-terminal-bg">
      {/* Header */}
      <header className="bg-terminal-header border-b border-terminal-border sticky top-0 z-40">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-terminal-green/20 rounded flex items-center justify-center">
              <span className="text-terminal-green font-bold text-sm">P</span>
            </div>
            <div>
              <h1 className="text-terminal-green font-bold text-sm tracking-wider">POLYNEWS TERMINAL</h1>
              <p className="text-terminal-muted text-xs">Real-time news intelligence</p>
            </div>
          </div>
          <div className="hidden md:flex items-center gap-3">
            {SOURCES.map(s => (
              <span key={s.id} className="text-xs" style={{ color: s.color }}>● {s.label}</span>
            ))}
          </div>
        </div>

        {/* Ticker tape */}
        {ticker.length > 0 && (
          <div className="border-t border-terminal-border overflow-hidden">
            <div className="ticker-scroll flex items-center py-2 bg-terminal-bg/50">
              {[...ticker, ...ticker].map((el, i) => (
                <TickerItem key={i} {...el} />
              ))}
            </div>
          </div>
        )}
      </header>

      {/* Status bar */}
      <StatusBar connected={connected} lastUpdate={lastUpdate} itemCount={items.length} />

      {/* Main content */}
      <main className="px-4 pb-24 md:pb-8">
        {/* Search */}
        <div className="py-4">
          <SearchBar value={search} onChange={setSearch} />
        </div>

        {/* Source filters (desktop) */}
        <div className="hidden md:flex items-center gap-2 pb-4 flex-wrap">
          {['all', 'finance', 'crypto', 'news'].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 rounded-full text-xs font-bold uppercase tracking-wider transition-colors ${
                activeTab === tab
                  ? 'bg-terminal-green text-terminal-bg'
                  : 'bg-terminal-panel text-terminal-muted hover:text-terminal-text border border-terminal-border'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* News grid */}
        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-terminal-muted">
            <div className="text-4xl mb-4">📡</div>
            <p className="text-lg font-bold mb-2">Connecting to PolyNews...</p>
            <p className="text-sm">Waiting for live data stream</p>
            <div className="mt-4 flex gap-1">
              <span className="w-2 h-2 bg-terminal-green rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 bg-terminal-green rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 bg-terminal-green rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {filteredItems.map((item, i) => (
              <NewsCard key={item.id || i} item={item} />
            ))}
          </div>
        )}
      </main>

      {/* Mobile nav */}
      <MobileNav activeTab={activeTab} onTabChange={setActiveTab} />
    </div>
  )
}