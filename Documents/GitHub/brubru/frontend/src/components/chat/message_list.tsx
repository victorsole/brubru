// frontend/src/components/chat/message_list.tsx
import { useEffect, useRef } from 'react';
import type { Message } from './chat_interface';
import './message_list.css';

interface MessageListProps {
  messages: Message[];
}

export const MessageList = ({ messages }: MessageListProps) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const formatTime = (date: Date) => {
    return new Intl.DateTimeFormat('en-GB', {
      hour: '2-digit',
      minute: '2-digit',
    }).format(date);
  };

  return (
    <div className="message-list">
      {messages.map((message) => (
        <div
          key={message.id}
          className={`message-list__message message-list__message--${message.role}`}
        >
          <div className="message-list__message-content">
            <div className="message-list__message-header">
              <span className="message-list__message-role">
                {message.role === 'user' ? 'You' : 'Brubru'}
              </span>
              <span className="message-list__message-time">
                {formatTime(message.timestamp)}
              </span>
            </div>
            <div className="message-list__message-text">
              {message.content}
            </div>
          </div>
        </div>
      ))}
      <div ref={messagesEndRef} />
    </div>
  );
};
