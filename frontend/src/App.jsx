import React, { useState, useEffect } from 'react';
import { Activity, DollarSign, PieChart, TrendingUp, Wallet, ArrowUpRight, ArrowDownRight, ShieldAlert, Play, Pause, Settings } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { collection, query, orderBy, limit, onSnapshot, addDoc, serverTimestamp } from 'firebase/firestore';
import { db } from './firebase';

export default function App() {
  const [logs, setLogs] = useState([]);
  const [latestLog, setLatestLog] = useState(null);
  const [ticks, setTicks] = useState({});
  const [tickDirections, setTickDirections] = useState({});
  const [wsStatus, setWsStatus] = useState('Connecting...');
  
  // Simulation Mode state
  const [simMode, setSimMode] = useState(false);
  const [simBalance, setSimBalance] = useState(30.46);
  const [demoStartBalance, setDemoStartBalance] = useState(50000);
  
  // Command Center state
  const [eurusdRisk, setEurusdRisk] = useState(1.0);
  const [eurusdSMT, setEurusdSMT] = useState(true);
  const [eurusdVol, setEurusdVol] = useState(false);
  const [eurusdFvg, setEurusdFvg] = useState(8);

  const [goldRisk, setGoldRisk] = useState(1.0);
  const [goldVol, setGoldVol] = useState(false);
  const [goldFvg, setGoldFvg] = useState(8);
  
  const sendCommand = async (cmd, payload = {}) => {
    try {
      await addDoc(collection(db, 'bot_commands'), {
        command: cmd,
        ...payload,
        timestamp: serverTimestamp()
      });
      // Give a tiny bit of visual feedback (optional)
    } catch (e) {
      console.error("Error sending command:", e);
    }
  };

  useEffect(() => {
    // Connect to WebSocket Server
    const ws = new WebSocket('ws://13.60.234.217:8765');
    
    ws.onopen = () => setWsStatus('Connected');
    ws.onclose = () => setWsStatus('Disconnected');
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'tick') {
          setTicks(prev => {
            const oldTick = prev[data.symbol];
            let direction = '';
            
            if (oldTick) {
              if (data.bid > oldTick.bid) direction = 'up';
              else if (data.bid < oldTick.bid) direction = 'down';
            }
            
            if (direction) {
              setTickDirections(d => ({ ...d, [data.symbol]: direction }));
              setTimeout(() => {
                setTickDirections(d => ({ ...d, [data.symbol]: '' }));
              }, 800);
            }
            
            return { ...prev, [data.symbol]: data };
          });
        }
      } catch (err) {
        console.error('WebSocket Error:', err);
      }
    };

    return () => ws.close();
  }, []);

  // Compute Simulation Multiplier
  const simMultiplier = simMode ? (simBalance / demoStartBalance) : 1;
  const formatCurrency = (val) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format((val || 0) * simMultiplier);

  useEffect(() => {
    if (latestLog && latestLog.starting_balance && demoStartBalance === 50000) {
      setDemoStartBalance(latestLog.starting_balance);
    }
  }, [latestLog]);

  useEffect(() => {
    // Subscribe to the trading_logs collection
    const q = query(
      collection(db, 'trading_logs'),
      orderBy('timestamp', 'desc'),
      limit(50)
    );

    const unsubscribe = onSnapshot(q, (snapshot) => {
      const data = snapshot.docs.map(doc => ({
        id: doc.id,
        ...doc.data(),
        // Format timestamp for chart
        time: doc.data().timestamp ? new Date(doc.data().timestamp.toDate()).toLocaleTimeString() : ''
      })).reverse(); // Reverse for charting (oldest to newest)
      
      setLogs(data);
      if (data.length > 0) {
        setLatestLog(data[data.length - 1]);
      }
    });

    return () => unsubscribe();
  }, []);

  if (!latestLog) {
    return (
      <div className="app-container" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <div className="live-indicator">
          <div className="live-dot"></div>
          Connecting to MT5 Live Logs...
        </div>
      </div>
    );
  }

  // Chart data scaled by simulation multiplier
  const chartData = logs.map(log => ({
    ...log,
    equity: log.equity * simMultiplier
  }));

  return (
    <div className="app-container">
      <header className="header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            AI Trading Dashboard
            {simMode && <span style={{ fontSize: '0.8rem', background: 'var(--accent-primary)', color: '#fff', padding: '0.2rem 0.6rem', borderRadius: '12px' }}>SIMULATION MODE</span>}
          </h1>
          <p style={{ color: 'var(--text-secondary)' }}>Live SMC Bot Monitoring</p>
        </div>
        <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center' }}>
          {/* Sim Toggle */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(0,0,0,0.2)', padding: '0.5rem 1rem', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Simulate Real Money</span>
            <input type="checkbox" checked={simMode} onChange={(e) => setSimMode(e.target.checked)} style={{ accentColor: 'var(--accent-primary)', width: '16px', height: '16px' }} />
          </div>
          
          <div className="live-indicator">
            <div className="live-dot"></div>
            Live Connection
          </div>
        </div>
      </header>

      {/* Live Market Ticker */}
      <div className="ticker-bar" style={{ marginBottom: '2rem', borderRadius: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', color: wsStatus === 'Connected' ? 'var(--success)' : 'var(--warning)', fontWeight: 'bold', paddingRight: '1rem', borderRight: '1px solid var(--border-color)' }}>
          <Activity size={18} />
          {wsStatus === 'Connected' ? 'LIVE TICKS' : wsStatus}
        </div>
        
        {Object.keys(ticks).length === 0 && wsStatus === 'Connected' && (
          <div style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center' }}>Waiting for first tick...</div>
        )}

        {Object.values(ticks).map(tick => {
          const dir = tickDirections[tick.symbol];
          const flashClass = dir === 'up' ? 'flash-up' : dir === 'down' ? 'flash-down' : '';
          
          return (
            <div key={tick.symbol} className={`ticker-item ${flashClass}`}>
              <span className="ticker-symbol">{tick.symbol}</span>
              <span className="ticker-price">{tick.bid.toFixed(5)} / {tick.ask.toFixed(5)}</span>
              <span className="ticker-spread">{tick.spread.toFixed(1)}</span>
            </div>
          );
        })}
      </div>

      <div className="dashboard-grid">
        
        {/* Command Center */}
        <div className="card col-span-12" style={{ border: '1px solid rgba(59, 130, 246, 0.3)', background: 'linear-gradient(180deg, rgba(31, 41, 55, 0.7) 0%, rgba(17, 24, 39, 0.9) 100%)' }}>
          
          {/* Sim Mode Settings */}
          {simMode && (
            <div style={{ display: 'flex', gap: '2rem', padding: '1rem', background: 'rgba(0,0,0,0.3)', borderRadius: '8px', marginBottom: '1.5rem', border: '1px dashed var(--accent-primary)' }}>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Demo Account Start Balance</span>
                <input type="number" value={demoStartBalance} onChange={(e) => setDemoStartBalance(Number(e.target.value))} style={{ background: 'transparent', color: 'white', border: 'none', borderBottom: '1px solid var(--border-color)', outline: 'none', fontSize: '1.1rem' }} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <span style={{ fontSize: '0.8rem', color: 'var(--accent-primary)' }}>Simulated Real Target Balance</span>
                <input type="number" value={simBalance} onChange={(e) => setSimBalance(Number(e.target.value))} style={{ background: 'transparent', color: 'var(--accent-primary)', border: 'none', borderBottom: '1px solid var(--accent-primary)', outline: 'none', fontSize: '1.1rem', fontWeight: 'bold' }} />
              </div>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '1rem' }}>
            <h3 style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent-primary)' }}>
              <Settings size={20} />
              Command Center
            </h3>
            <button 
              onClick={() => sendCommand('CLOSE_ALL')}
              style={{ 
                background: 'rgba(239, 68, 68, 0.2)', color: 'var(--danger)', border: '1px solid rgba(239, 68, 68, 0.4)', 
                padding: '0.5rem 1.5rem', borderRadius: '8px', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', transition: 'all 0.2s' 
              }}
              onMouseOver={(e) => e.currentTarget.style.background = 'rgba(239, 68, 68, 0.4)'}
              onMouseOut={(e) => e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)'}
            >
              <ShieldAlert size={18} />
              CLOSE ALL POSITIONS (PANIC)
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
            {/* EURUSD Controls */}
            <div style={{ padding: '1.5rem', background: 'rgba(0,0,0,0.2)', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <strong style={{ fontSize: '1.25rem' }}>EURUSD Bot</strong>
                  {latestLog.active_bots && latestLog.active_bots.includes('eurusd_bot') ? (
                    <span style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', borderRadius: '4px', background: 'rgba(16, 185, 129, 0.2)', color: 'var(--success)', border: '1px solid rgba(16, 185, 129, 0.4)' }}>RUNNING</span>
                  ) : (
                    <span style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', borderRadius: '4px', background: 'rgba(239, 68, 68, 0.2)', color: 'var(--danger)', border: '1px solid rgba(239, 68, 68, 0.4)' }}>PAUSED</span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button onClick={() => sendCommand('BOT_ACTION', { bot_name: 'eurusd_bot', action: 'START' })} className="control-btn play">
                    <Play size={16} /> Start
                  </button>
                  <button onClick={() => sendCommand('BOT_ACTION', { bot_name: 'eurusd_bot', action: 'STOP' })} className="control-btn pause">
                    <Pause size={16} /> Pause
                  </button>
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Risk Per Trade</span>
                  <span style={{ fontWeight: 'bold' }}>{eurusdRisk}%</span>
                </div>
                <input 
                  type="range" min="0.1" max="5.0" step="0.1" value={eurusdRisk} 
                  onChange={(e) => setEurusdRisk(parseFloat(e.target.value))} 
                  onMouseUp={() => sendCommand('SET_CONFIG', { bot_name: 'eurusd_bot', key: 'RISK_PERCENT', value: eurusdRisk })}
                  style={{ width: '100%', accentColor: 'var(--accent-primary)' }}
                />
              </div>

              <div style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid rgba(255,255,255,0.05)', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Require SMT Divergence</span>
                  <input type="checkbox" checked={eurusdSMT} onChange={(e) => {
                    setEurusdSMT(e.target.checked);
                    sendCommand('SET_CONFIG', { bot_name: 'eurusd_bot', key: 'USE_SMT_DIVERGENCE', value: eurusdSMT });
                  }} style={{ accentColor: 'var(--accent-primary)', width: '18px', height: '18px' }} />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Strict Volatility Filter</span>
                  <input type="checkbox" checked={eurusdVol} onChange={(e) => {
                    setEurusdVol(e.target.checked);
                    sendCommand('SET_CONFIG', { bot_name: 'eurusd_bot', key: 'USE_VOLATILITY_FILTER', value: eurusdVol });
                  }} style={{ accentColor: 'var(--accent-primary)', width: '18px', height: '18px' }} />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>FVG Detection Window</span>
                    <span style={{ fontWeight: 'bold', fontSize: '0.9rem' }}>{eurusdFvg} candles</span>
                  </div>
                  <input 
                    type="range" min="3" max="20" step="1" value={eurusdFvg} 
                    onChange={(e) => setEurusdFvg(parseInt(e.target.value))} 
                    onMouseUp={() => sendCommand('SET_CONFIG', { bot_name: 'eurusd_bot', key: 'FVG_WINDOW', value: eurusdFvg })}
                    style={{ width: '100%', accentColor: 'var(--accent-primary)' }}
                  />
                </div>
              </div>
            </div>

            {/* GOLD Controls */}
            <div style={{ padding: '1.5rem', background: 'rgba(0,0,0,0.2)', borderRadius: '12px', border: '1px solid var(--border-color)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                  <strong style={{ fontSize: '1.25rem' }}>XAUUSD Bot</strong>
                  {latestLog.active_bots && latestLog.active_bots.includes('gold_bot') ? (
                    <span style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', borderRadius: '4px', background: 'rgba(16, 185, 129, 0.2)', color: 'var(--success)', border: '1px solid rgba(16, 185, 129, 0.4)' }}>RUNNING</span>
                  ) : (
                    <span style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', borderRadius: '4px', background: 'rgba(239, 68, 68, 0.2)', color: 'var(--danger)', border: '1px solid rgba(239, 68, 68, 0.4)' }}>PAUSED</span>
                  )}
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button onClick={() => sendCommand('BOT_ACTION', { bot_name: 'gold_bot', action: 'START' })} className="control-btn play">
                    <Play size={16} /> Start
                  </button>
                  <button onClick={() => sendCommand('BOT_ACTION', { bot_name: 'gold_bot', action: 'STOP' })} className="control-btn pause">
                    <Pause size={16} /> Pause
                  </button>
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-secondary)' }}>Risk Per Trade</span>
                  <span style={{ fontWeight: 'bold' }}>{goldRisk}%</span>
                </div>
                <input 
                  type="range" min="0.1" max="5.0" step="0.1" value={goldRisk} 
                  onChange={(e) => setGoldRisk(parseFloat(e.target.value))} 
                  onMouseUp={() => sendCommand('SET_CONFIG', { bot_name: 'gold_bot', key: 'RISK_PERCENT', value: goldRisk })}
                  style={{ width: '100%', accentColor: 'var(--warning)' }}
                />
              </div>

              <div style={{ marginTop: '1.5rem', paddingTop: '1.5rem', borderTop: '1px solid rgba(255,255,255,0.05)', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Strict Volatility Filter</span>
                  <input type="checkbox" checked={goldVol} onChange={(e) => {
                    setGoldVol(e.target.checked);
                    sendCommand('SET_CONFIG', { bot_name: 'gold_bot', key: 'USE_VOLATILITY_FILTER', value: goldVol });
                  }} style={{ accentColor: 'var(--warning)', width: '18px', height: '18px' }} />
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>FVG Detection Window</span>
                    <span style={{ fontWeight: 'bold', fontSize: '0.9rem' }}>{goldFvg} candles</span>
                  </div>
                  <input 
                    type="range" min="3" max="20" step="1" value={goldFvg} 
                    onChange={(e) => setGoldFvg(parseInt(e.target.value))} 
                    onMouseUp={() => sendCommand('SET_CONFIG', { bot_name: 'gold_bot', key: 'FVG_WINDOW', value: goldFvg })}
                    style={{ width: '100%', accentColor: 'var(--warning)' }}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Top Metrics Row */}
        <div className="card col-span-3 metric-card">
          <div className="metric-label">Account Balance</div>
          <div className="metric-value">
            <Wallet size={28} style={{ color: 'var(--accent-primary)' }} />
            {formatCurrency(latestLog.balance)}
          </div>
        </div>
        
        <div className="card col-span-3 metric-card">
          <div className="metric-label">Account Equity</div>
          <div className="metric-value">
            <PieChart size={28} style={{ color: 'var(--accent-primary)' }} />
            {formatCurrency(latestLog.equity)}
          </div>
        </div>

        <div className="card col-span-3 metric-card">
          <div className="metric-label">Floating Profit</div>
          <div className={`metric-value ${latestLog.profit >= 0 ? 'positive' : 'negative'}`}>
            <DollarSign size={28} />
            {latestLog.profit >= 0 ? '+' : ''}{formatCurrency(latestLog.profit)}
          </div>
        </div>

        <div className="card col-span-3 metric-card" style={{ background: (latestLog.balance - (latestLog.starting_balance || 50000)) >= 0 ? 'rgba(16, 185, 129, 0.05)' : 'rgba(239, 68, 68, 0.05)', border: `1px solid ${(latestLog.balance - (latestLog.starting_balance || 50000)) >= 0 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)'}` }}>
          <div className="metric-label">Total Net Profit</div>
          <div className={`metric-value ${(latestLog.balance - (latestLog.starting_balance || 50000)) >= 0 ? 'positive' : 'negative'}`}>
            <TrendingUp size={28} />
            {(latestLog.balance - (latestLog.starting_balance || 50000)) >= 0 ? '+' : ''}{formatCurrency(latestLog.balance - (latestLog.starting_balance || 50000))}
          </div>
        </div>

        {/* Chart Section */}
        <div className="card col-span-8">
          <h3 style={{ marginBottom: '1rem' }}>Equity Growth Curve</h3>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="colorEquity" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--accent-primary)" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="var(--accent-primary)" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
                <XAxis dataKey="time" stroke="var(--text-muted)" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="var(--text-muted)" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(val) => `$${val}`} domain={['auto', 'auto']} />
                <Tooltip 
                  contentStyle={{ backgroundColor: 'var(--bg-panel)', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                  itemStyle={{ color: 'var(--text-primary)' }}
                />
                <Area type="monotone" dataKey="equity" stroke="var(--accent-primary)" strokeWidth={3} fillOpacity={1} fill="url(#colorEquity)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Side Panel */}
        <div className="card col-span-4">
          <h3 style={{ marginBottom: '1rem' }}>Active Positions</h3>
          {latestLog.open_positions && latestLog.open_positions.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {latestLog.open_positions.map((pos, idx) => (
                <div key={idx} style={{ padding: '1rem', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <strong>{pos.symbol}</strong>
                    <span className={`badge ${pos.type === 'BUY' ? 'buy' : 'sell'}`}>{pos.type}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                    <span>Volume: {pos.volume}</span>
                    <span>Open: {pos.open}</span>
                  </div>
                  <div style={{ marginTop: '0.5rem', fontWeight: 'bold', color: pos.profit >= 0 ? 'var(--success)' : 'var(--danger)' }}>
                    P/L: {formatCurrency(pos.profit)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>
              No active positions
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
