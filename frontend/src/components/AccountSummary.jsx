import './AccountSummary.css';

const formatCurrency = (val) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
  }).format(val);

const formatPercent = (val) => `${val.toFixed(2)}%`;

export default function AccountSummary({ account }) {
  if (!account) return null;

  const metrics = [
    {
      label: 'Balance',
      value: formatCurrency(account.balance),
      delta: account.balanceDelta,
      accent: 'cyan',
    },
    {
      label: 'Equity',
      value: formatCurrency(account.equity),
      delta: account.equityDelta,
      accent: 'green',
    },
    {
      label: 'Free Margin',
      value: formatCurrency(account.freeMargin),
      delta: null,
      accent: 'amber',
    },
    {
      label: 'Margin Level',
      value: formatPercent(account.marginLevel),
      delta: null,
      accent: 'purple',
    },
  ];

  return (
    <div className="account-summary">
      {metrics.map((m) => (
        <div key={m.label} className={`glass-card account-metric ${m.accent}`}>
          <div className="metric-label">{m.label}</div>
          <div className="metric-value">{m.value}</div>
          {m.delta != null && (
            <span className={`metric-delta ${m.delta >= 0 ? 'positive' : 'negative'}`}>
              {m.delta >= 0 ? '▲' : '▼'} {Math.abs(m.delta).toFixed(2)}%
            </span>
          )}
        </div>
      ))}
    </div>
  );
}
