import './ConnectionStatus.css';

export default function ConnectionStatus({ isConnected }) {
  return (
    <div className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
      <span className="connection-dot" />
      <span className="connection-label">
        {isConnected ? 'Connected' : 'Disconnected'}
      </span>
    </div>
  );
}
