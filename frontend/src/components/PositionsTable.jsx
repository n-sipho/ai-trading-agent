import './PositionsTable.css';

const fmt = (v, d = 5) => Number(v).toFixed(d);
const fmtPL = (v) => {
  const n = Number(v);
  const prefix = n >= 0 ? '+' : '';
  return `${prefix}$${Math.abs(n).toFixed(2)}`;
};

export default function PositionsTable({ positions = [], onClosePosition }) {
  return (
    <div className="positions-table-wrapper glass-card">
      <div className="positions-header">
        <h3>
          📊 Open Positions
          <span className="positions-count">({positions.length})</span>
        </h3>
      </div>

      {positions.length === 0 ? (
        <div className="positions-empty">No open positions</div>
      ) : (
        <>
          {/* Desktop table */}
          <div className="positions-table-desktop">
            <table className="positions-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Type</th>
                  <th>Volume</th>
                  <th>Entry</th>
                  <th>Current</th>
                  <th>P/L</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p) => {
                  const digits = p.symbol.includes('JPY') ? 3 : 5;
                  return (
                    <tr key={p.ticket} className={p.type === 'BUY' ? 'buy-row' : 'sell-row'}>
                      <td style={{ fontWeight: 600 }}>{p.symbol}</td>
                      <td>
                        <span className={`type-badge ${p.type.toLowerCase()}`}>{p.type}</span>
                      </td>
                      <td>{p.volume.toFixed(2)}</td>
                      <td>{fmt(p.entryPrice, digits)}</td>
                      <td>{fmt(p.currentPrice, digits)}</td>
                      <td>
                        <span className={p.pl >= 0 ? 'pl-positive' : 'pl-negative'}>
                          {fmtPL(p.pl)}
                        </span>
                      </td>
                      <td>
                        <button
                          className="close-position-btn"
                          onClick={() => onClosePosition?.(p.ticket)}
                        >
                          Close
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <div className="positions-cards">
            {positions.map((p) => {
              const digits = p.symbol.includes('JPY') ? 3 : 5;
              return (
                <div key={p.ticket} className="position-card">
                  <div className="position-card-top">
                    <span className="position-card-symbol">{p.symbol}</span>
                    <span className={`type-badge ${p.type.toLowerCase()}`}>{p.type}</span>
                  </div>
                  <div className="position-card-grid">
                    <div className="position-card-field">
                      <span className="field-label">Volume</span>
                      <span className="field-value">{p.volume.toFixed(2)}</span>
                    </div>
                    <div className="position-card-field">
                      <span className="field-label">P/L</span>
                      <span className={`field-value ${p.pl >= 0 ? 'pl-positive' : 'pl-negative'}`}>
                        {fmtPL(p.pl)}
                      </span>
                    </div>
                    <div className="position-card-field">
                      <span className="field-label">Entry</span>
                      <span className="field-value">{fmt(p.entryPrice, digits)}</span>
                    </div>
                    <div className="position-card-field">
                      <span className="field-label">Current</span>
                      <span className="field-value">{fmt(p.currentPrice, digits)}</span>
                    </div>
                  </div>
                  <div className="position-card-actions">
                    <button
                      className="close-position-btn"
                      onClick={() => onClosePosition?.(p.ticket)}
                    >
                      Close Position
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
