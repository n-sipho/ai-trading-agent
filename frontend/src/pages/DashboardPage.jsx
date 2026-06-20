import MarketTicker from '../components/MarketTicker';
import AccountSummary from '../components/AccountSummary';
import ChatPanel from '../components/ChatPanel';
import PositionsTable from '../components/PositionsTable';
import './DashboardPage.css';

export default function DashboardPage({
  tickers,
  account,
  messages,
  onSendMessage,
  isLoading,
  positions,
  onClosePosition,
}) {
  return (
    <div className="dashboard-page">
      <section>
        <p className="dashboard-section-label">Live Market</p>
        <MarketTicker tickers={tickers} />
      </section>

      <section>
        <p className="dashboard-section-label">Account Overview</p>
        <AccountSummary account={account} />
      </section>

      <section className="dashboard-columns">
        <div className="dashboard-chat-col">
          <ChatPanel
            messages={messages}
            onSendMessage={onSendMessage}
            isLoading={isLoading}
          />
        </div>
        <div className="dashboard-positions-col">
          <PositionsTable
            positions={positions}
            onClosePosition={onClosePosition}
          />
        </div>
      </section>
    </div>
  );
}
