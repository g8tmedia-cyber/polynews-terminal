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
  return (
    <span
      className="inline-block px-1.5 py-0.5 rounded text-xs font-bold mr-2 mb-1"
      style={{ backgroundColor: source.color + '22', color: source.color, border: `1px solid ${source.color}44` }}
    >
      {source.label}
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

function TickerItem({ item }) {
  return (
    <a
      href={item.url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center whitespace-nowrap mx-6 text-sm hover:opacity-80"
    >
      <SourceBadge source={SOURCES.find(s => s.id === item.source) || SOURCES[0]} />
      <span className="text-terminal-text font-medium">{item.title}</span>
    </a>
  )
}

function NewsCard({ item }) {
  const source = SOURCES.find(s => s.id === item.source) || SOURCES[0]
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
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ backgroundColor: source.color }}
            />
            <span className="text-xs font-semibold" style={{ color: source.color }}>{source.label}</span>
            {item.time && <TimeAgo ts={item.time} />}
          </div>
          <h3 className="text-terminal-text font-medium text-sm leading-snug mb-2 line-clamp-2">
            {item.title}
          </h3>
          {item.summary && (
            <p className="text-terminal-muted text-xs leading-relaxed line-clamp-2">{item.summary}</p>
          )}
        </div>
      </div>
    </a>
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

function StatusBar({ connected, lastUpdate, items }) {
  return (
    <div className="flex items-center justify-between text-xs text-terminal-muted px-4 py-2 border-b border-terminal-border">
      <div className="flex items-center gap-4">
        <span className={connected ? 'text-terminal-green' : 'text-terminal-red'}>
          ● {connected ? 'LIVE' : 'DISCONNECTED'}
        </span>
        <span>{items.length} headlines</span>
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

export default function App() {
  const [items, setItems] = useState([])
  const [connected, setConnected] = useState(false)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [search, setSearch] = useState('')
  const [activeTab, setActiveTab] = useState('all')
  const [tickerItems, setTickerItems] = useState([])
  const eventSourceRef = useRef(null)

  const connect = useCallback(() => {
    if (eventSourceRef.current) eventSourceRef.current.close()

    const es = new EventSource('https://carpenter-armoire-freckled.ngrok-free.dev/stream')
    eventSourceRef.current = es

    es.onopen = () => setConnected(true)
    es.onerror = () => {
      setConnected(false)
      setTimeout(connect, 5000)
    }

    es.onmessage = (e) => {
      const raw = e.data
      if (!raw || raw.length < 10) return

      // Parse blocks like "📊 Yahoo Finance" etc.
      const lines = raw.split('\n')
      let currentSource = ''
      let currentTime = null

      lines.forEach(line => {
        const srcMatch = line.match(/^[📊📰💹🔗📈🪙💬🌐]+ (.+)/)
        if (srcMatch) currentSource = srcMatch[1].trim()

        const timeMatch = line.match(/(\d+:\d+:\d+|\d+m ago)/)
        if (timeMatch) {
          const now = Date.now() / 1000
          if (line.includes('m ago')) {
            const m = parseInt(line.match(/(\d+)m/)?.[1] || '0')
            currentTime = now - m * 60
          } else {
            currentTime = now - 120
          }
        }

        if (line.trim() && line.length > 20 && !line.match(/^[╭╰│├└─]+/) && !line.match(/^\s*\|/)) {
          const clean = line.replace(/^\s*[\d➡✓✗●]+/, '').trim()
          if (clean && clean.length > 15 && clean.length < 200) {
            const id = Math.random().toString(36).substr(2, 9)
            const fakeUrl = `https://polynews/${id}`
            setTickerItems(prev => {
              const exists = prev.find(i => i.title === clean)
              if (exists) return prev
              const srcMap = {
                'Hacker News': 'hn', 'BBC News': 'bbc', 'Yahoo Finance': 'yahoo',
                'CoinDesk': 'coindesk', 'The Block': 'block', 'Polymarket': 'polymarket',
                'Reddit': 'reddit', 'Google News': 'google'
              }
              return [{ id, title: clean, source: srcMap[currentSource] || 'hn', time: currentTime || now - 120, url: fakeUrl, summary: '' }, ...prev].slice(0, 50)
            })
          }
        }
      })

      setLastUpdate(Math.floor(Date.now() / 1000))
    }
  }, [])

  useEffect(() => {
    connect()
    return () => { if (eventSourceRef.current) eventSourceRef.current.close() }
  }, [connect])

  const filteredItems = items.filter(item => {
    const matchSearch = item.title.toLowerCase().includes(search.toLowerCase())
    const source = item.source
    const matchTab = activeTab === 'all' ||
      (activeTab === 'finance' && ['yahoo'].includes(source)) ||
      (activeTab === 'crypto' && ['coindesk', 'block', 'polymarket'].includes(source)) ||
      (activeTab === 'news' && ['hn', 'bbc', 'google', 'reddit'].includes(source))
    return matchSearch && matchTab
  })

  const tickerEls = tickerItems.slice(0, 20).map((item, i) => (
    <TickerItem key={item.id || i} item={item} />
  ))

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
              <h1 className="text-terminal-green font-bold text-sm tracking-wider cursor-blink">POLYNEWS TERMINAL</h1>
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
        {tickerEls.length > 0 && (
          <div className="border-t border-terminal-border overflow-hidden">
            <div className="ticker-scroll flex items-center py-2 bg-terminal-bg/50">
              {[...tickerEls, ...tickerEls].map((el, i) => (
                <React.Fragment key={i}>{el}</React.Fragment>
              ))}
            </div>
          </div>
        )}
      </header>

      {/* Status bar */}
      <StatusBar connected={connected} lastUpdate={lastUpdate} items={items} />

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
        {tickerItems.length === 0 ? (
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
            {tickerItems.map((item, i) => (
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