import './MarketTicker.css';

export default function MarketTicker({ tickers = [] }) {
  return (
    <div className="market-ticker">
      <div className="ticker-strip">
        {tickers.map((t) => (
          <div
            key={t.symbol}
            className={`ticker-item ${t.direction}`}
          >
            <span className="ticker-symbol">{t.symbol}</span>
            <div className="ticker-prices">
              <div className="ticker-bid-ask">
                <span className="ticker-bid">{t.bid.toFixed(t.symbol.includes('JPY') ? 3 : 5)}</span>
                <span style={{ color: 'var(--text-muted)', fontSize: 'var(--font-xs)' }}>/</span>
                <span className="ticker-ask">{t.ask.toFixed(t.symbol.includes('JPY') ? 3 : 5)}</span>
              </div>
              <span className="ticker-spread">Spread: {t.spread.toFixed(1)}</span>
            </div>
            <span className={`ticker-direction ${t.direction}`}>
              {t.direction === 'up' ? '▲' : '▼'}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
