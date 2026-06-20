import ChatPanel from '../components/ChatPanel';
import './ChatPage.css';

export default function ChatPage({ messages, onSendMessage, isLoading }) {
  return (
    <div className="chat-page">
      <ChatPanel
        messages={messages}
        onSendMessage={onSendMessage}
        isLoading={isLoading}
      />
    </div>
  );
}
