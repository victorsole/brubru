// frontend/src/components/chat/chat_interface.tsx
import { useState } from 'react';
import { MessageList } from './message_list';
import './chat_interface.css';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export const ChatInterface = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    // Placeholder for AI response (will be connected to backend later)
    setTimeout(() => {
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: 'This is a placeholder response. Backend integration coming soon!',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, aiMessage]);
      setIsLoading(false);
    }, 1000);
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <div className="chat-interface">
      <div className="chat-interface__messages">
        {messages.length === 0 ? (
          <div className="chat-interface__empty">
            <h2>Welcome to Brubru</h2>
            <p>Your AI multiagent companion for navigating the EU bubble in Brussels</p>
            <p className="chat-interface__empty-hint">
              Start a conversation to analyse EU legislation, strategise advocacy campaigns, or get guidance on European Parliament procedures.
            </p>
          </div>
        ) : (
          <MessageList messages={messages} />
        )}
        {isLoading && (
          <div className="chat-interface__typing">
            <span className="chat-interface__typing-dot"></span>
            <span className="chat-interface__typing-dot"></span>
            <span className="chat-interface__typing-dot"></span>
          </div>
        )}
      </div>

      <div className="chat-interface__input-container">
        <textarea
          className="chat-interface__input"
          placeholder="Ask about EU legislation, procedures, or policy analysis..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={handleKeyPress}
          rows={3}
          disabled={isLoading}
        />
        <button
          className="chat-interface__send-button button button-primary"
          onClick={handleSendMessage}
          disabled={!inputValue.trim() || isLoading}
        >
          Send
        </button>
      </div>
    </div>
  );
};
