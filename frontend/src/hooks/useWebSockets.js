import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Custom hook — connects to the FastAPI backend WebSocket for AI chat.
 *
 * @param {string} url  WebSocket URL (default: ws://localhost:8000/ws/chat)
 * @returns {{ messages, isLoading, isConnected, sendMessage }}
 */
export function useChatSocket(url = 'ws://localhost:8000/ws/chat') {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content:
        '**Welcome to the SMC Trading Assistant!** 👋\n\nI can help you with:\n- Analyzing **Smart Money Concepts** on any pair\n- Placing and managing trades\n- Reviewing your portfolio performance\n\nWhat would you like to do?',
      timestamp: new Date().toISOString(),
    },
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      console.log('[Chat WS] Connected');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'loading') {
          setIsLoading(data.isLoading);
        } else if (data.type === 'response') {
          setMessages((prev) => [
            ...prev,
            {
              role: 'assistant',
              content: data.content,
              timestamp: data.timestamp,
            },
          ]);
        } else if (data.type === 'error') {
          setMessages((prev) => [
            ...prev,
            {
              role: 'assistant',
              content: `⚠️ ${data.content}`,
              timestamp: data.timestamp,
            },
          ]);
        }
      } catch (err) {
        console.error('[Chat WS] Parse error:', err);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      console.log('[Chat WS] Disconnected — reconnecting in 3s');
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    ws.onerror = (err) => {
      console.error('[Chat WS] Error:', err);
      ws.close();
    };
  }, [url]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  const sendMessage = useCallback((text) => {
    // Add user message to state immediately
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: text, timestamp: new Date().toISOString() },
    ]);

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'message', content: text }));
    } else {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: '⚠️ Not connected to the server. Please wait while we reconnect...',
          timestamp: new Date().toISOString(),
        },
      ]);
    }
  }, []);

  return { messages, isLoading, isConnected, sendMessage };
}


/**
 * Custom hook — connects to the MT5 WebSocket Quote Server for live tickers.
 *
 * @param {string} url  WebSocket URL (default: ws://localhost:8765)
 * @returns {{ tickers, isConnected }}
 */
export function useQuoteSocket(url = 'ws://localhost:8765') {
  const [tickers, setTickers] = useState({});
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const prevPrices = useRef({});

  const connect = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setIsConnected(true);
      console.log('[Quote WS] Connected');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'tick') {
          const prev = prevPrices.current[data.symbol] || data.bid;
          const direction = data.bid > prev ? 'up' : data.bid < prev ? 'down' : 'neutral';
          prevPrices.current[data.symbol] = data.bid;

          setTickers((old) => ({
            ...old,
            [data.symbol]: {
              symbol: data.symbol,
              bid: data.bid,
              ask: data.ask,
              spread: data.spread_points,
              direction,
            },
          }));
        }
      } catch (err) {
        console.error('[Quote WS] Parse error:', err);
      }
    };

    ws.onclose = () => {
      setIsConnected(false);
      console.log('[Quote WS] Disconnected — reconnecting in 5s');
      reconnectTimer.current = setTimeout(connect, 5000);
    };

    ws.onerror = (err) => {
      console.error('[Quote WS] Error:', err);
      ws.close();
    };
  }, [url]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  const tickerArray = Object.values(tickers);

  return { tickers: tickerArray, isConnected };
}
