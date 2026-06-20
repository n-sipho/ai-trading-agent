import { useState } from 'react';
import { useChatSocket, useQuoteSocket } from './hooks/useWebSockets';
import ConnectionStatus from './components/ConnectionStatus';
import DashboardPage from './pages/DashboardPage';
import ChatPage from './pages/ChatPage';
import './App.css';

/* ============================================
   Fallback Mock Data (used when servers are offline)
   ============================================ */
const FALLBACK_TICKERS = [
  { symbol: 'EURUSD', bid: 1.08542, ask: 1.08556, spread: 1.4, direction: 'up' },
  { symbol: 'GBPUSD', bid: 1.27123, ask: 1.27141, spread: 1.8, direction: 'down' },
  { symbol: 'USDJPY', bid: 157.432, ask: 157.448, spread: 1.6, direction: 'up' },
  { symbol: 'XAUUSD', bid: 2338.45, ask: 2338.95, spread: 50, direction: 'up' },
];

const MOCK_ACCOUNT = {
  balance: 25430.82,
  equity: 25892.15,
  freeMargin: 22145.33,
  marginLevel: 685.42,
  balanceDelta: 2.34,
  equityDelta: 1.81,
};

const MOCK_POSITIONS = [
  {
    ticket: 10001,
    symbol: 'EURUSD',
    type: 'BUY',
    volume: 0.5,
    entryPrice: 1.0832,
    currentPrice: 1.08542,
    pl: 111.0,
  },
  {
    ticket: 10002,
    symbol: 'GBPUSD',
    type: 'SELL',
    volume: 0.3,
    entryPrice: 1.2745,
    currentPrice: 1.27123,
    pl: 98.1,
  },
  {
    ticket: 10003,
    symbol: 'USDJPY',
    type: 'BUY',
    volume: 1.0,
    entryPrice: 158.1,
    currentPrice: 157.432,
    pl: -421.5,
  },
  {
    ticket: 10004,
    symbol: 'XAUUSD',
    type: 'BUY',
    volume: 0.1,
    entryPrice: 2315.2,
    currentPrice: 2338.45,
    pl: 232.5,
  },
];

/* ============================================
   Nav Configuration
   ============================================ */
const NAV_ITEMS = [
  { key: 'dashboard', label: 'Dashboard', icon: '📊' },
  { key: 'chat', label: 'Chat', icon: '💬' },
  { key: 'positions', label: 'Positions', icon: '📈' },
  { key: 'analytics', label: 'Analytics', icon: '📉' },
];

/* ============================================
   App Component
   ============================================ */
export default function App() {
  const [activePage, setActivePage] = useState('dashboard');
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Real WebSocket hooks
  const {
    messages,
    isLoading: chatLoading,
    isConnected: chatConnected,
    sendMessage,
  } = useChatSocket();

  const {
    tickers: liveTickers,
    isConnected: quoteConnected,
  } = useQuoteSocket();

  // Use live tickers if available, otherwise fallback
  const tickers = liveTickers.length > 0 ? liveTickers : FALLBACK_TICKERS;
  const isConnected = chatConnected;

  // Positions state (will be populated by agent responses in the future)
  const [positions, setPositions] = useState(MOCK_POSITIONS);

  const handleClosePosition = (ticket) => {
    setPositions((prev) => prev.filter((p) => p.ticket !== ticket));
  };

  const handleNavClick = (key) => {
    setActivePage(key);
    setSidebarOpen(false);
  };

  const renderPage = () => {
    switch (activePage) {
      case 'chat':
        return (
          <ChatPage
            messages={messages}
            onSendMessage={sendMessage}
            isLoading={chatLoading}
          />
        );
      case 'dashboard':
      default:
        return (
          <DashboardPage
            tickers={tickers}
            account={MOCK_ACCOUNT}
            messages={messages}
            onSendMessage={sendMessage}
            isLoading={chatLoading}
            positions={positions}
            onClosePosition={handleClosePosition}
          />
        );
    }
  };

  return (
    <div className="app-layout">
      {/* Overlay for mobile sidebar */}
      <div
        className={`sidebar-overlay ${sidebarOpen ? 'visible' : ''}`}
        onClick={() => setSidebarOpen(false)}
      />

      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-brand">
          <div className="sidebar-brand-icon">S</div>
          <div className="sidebar-brand-text">
            SMC Trading
            <span>AI Assistant</span>
          </div>
        </div>

        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.key}
              className={`sidebar-nav-item ${activePage === item.key ? 'active' : ''}`}
              onClick={() => handleNavClick(item.key)}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-connection">
            <span className={`sidebar-dot ${chatConnected ? 'online' : 'offline'}`} />
            Agent: {chatConnected ? 'Online' : 'Offline'}
          </div>
          <div className="sidebar-connection">
            <span className={`sidebar-dot ${quoteConnected ? 'online' : 'offline'}`} />
            Quotes: {quoteConnected ? 'Streaming' : 'Offline'}
          </div>
          <div style={{ marginTop: '0.5rem', opacity: 0.5, fontSize: '0.75rem' }}>
            v1.0.0 — SMC Engine
          </div>
        </div>
      </aside>

      {/* Main area */}
      <div className="main-wrapper">
        <header className="header">
          <div className="header-left">
            <button
              className="hamburger"
              onClick={() => setSidebarOpen((o) => !o)}
              aria-label="Toggle sidebar"
            >
              ☰
            </button>
            <span className="header-title">SMC Trading Assistant</span>
          </div>
          <div className="header-right">
            <ConnectionStatus isConnected={isConnected} />
          </div>
        </header>

        <main className="main-content">{renderPage()}</main>
      </div>
    </div>
  );
}
