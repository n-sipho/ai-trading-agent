import { useRef, useEffect, useState } from 'react';
import './ChatPanel.css';

/* ---------- Simple Markdown renderer ---------- */
function renderMarkdown(text) {
  if (!text) return '';
  let html = text
    // code blocks
    .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
    // inline code
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    // bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // unordered list items
    .replace(/^[-•]\s+(.+)/gm, '<li>$1</li>')
    // newlines to <br> (outside pre blocks)
    .replace(/\n/g, '<br/>');

  // wrap consecutive <li> in <ul>
  html = html.replace(/((<li>.*?<\/li>\s*(<br\/?>)?\s*)+)/g, '<ul>$1</ul>');

  return html;
}

function formatTime(ts) {
  if (!ts) return '';
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export default function ChatPanel({ messages = [], onSendMessage, isLoading = false }) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  // Auto-scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed) return;
    onSendMessage?.(trimmed);
    setInput('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-panel glass-card">
      <div className="chat-header">
        <span className="chat-header-title">
          <span className="chat-icon">💬</span> AI Trading Assistant
        </span>
      </div>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`chat-message ${msg.role}`}>
            <div
              className="message-bubble"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
            />
            <span className="message-time">{formatTime(msg.timestamp)}</span>
          </div>
        ))}

        {isLoading && (
          <div className="typing-indicator">
            <div className="typing-dots">
              <span />
              <span />
              <span />
            </div>
            <span className="typing-label">AI is thinking…</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-bar">
        <textarea
          className="chat-input"
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask your trading assistant…"
        />
        <button
          className="chat-send-btn"
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
          aria-label="Send message"
        >
          ➤
        </button>
      </div>
    </div>
  );
}
