// frontend/src/components/chat/chat_interface.tsx
import { useState, useRef, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import axios from 'axios';
import { MessageList } from './message_list';
import { useAuth } from '../../hooks/use_auth';
import './chat_interface.css';

export interface Citation {
  id: number;
  type: string;
  title: string;
  url: string;
  metadata?: Record<string, any>;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  citations?: Citation[];
  tokensUsed?: number;
  searchTimeMs?: number;
  contextsUsed?: number;
}

interface ChatInterfaceProps {
  initialQuestion?: string;
  documentIds?: string[];
}

export const ChatInterface = ({ initialQuestion, documentIds = [] }: ChatInterfaceProps = {}) => {
  const { t } = useTranslation();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [chatId, setChatId] = useState<string | null>(null);
  const [useContext] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [personalizedGreeting, setPersonalizedGreeting] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const { isAuthenticated, user } = useAuth();

  // API base URL - configure this in your environment
  const API_BASE_URL = import.meta.env?.VITE_API_URL || (window as any).REACT_APP_API_URL || 'http://localhost:8000';
  
  // Admin-managed example prompts
  interface ExamplePrompt { id: string; text: string }
  const [examplePrompts, setExamplePrompts] = useState<ExamplePrompt[] | null>(null);

  // Fetch personalized greeting on mount (available to all tiers)
  useEffect(() => {
    const fetchGreeting = async () => {
      if (!isAuthenticated || !user) return;

      try {
        // Pass previous_last_login from sessionStorage for welcome-back context
        const previousLogin = sessionStorage.getItem('brubru_previous_login');
        const params: Record<string, string> = {};
        if (previousLogin) {
          params.previous_last_login = previousLogin;
        }

        const response = await axios.get(`${API_BASE_URL}/api/personalization/greeting`, { params });
        const { message } = response.data;

        // Store greeting separately - don't add to messages
        setPersonalizedGreeting(message);

        // Clear sessionStorage so welcome-back only shows once per session
        sessionStorage.removeItem('brubru_previous_login');
      } catch (err) {
        console.error('Failed to fetch greeting:', err);
        // Silently fail - greeting is optional
      }
    };

    fetchGreeting();
  }, [isAuthenticated, user, API_BASE_URL]);

  // Load example prompts for the empty state (fallback to i18n on failure)
  useEffect(() => {
    const fetchExamples = async () => {
      try {
        const locale = (navigator.language || 'en').toLowerCase();
        const tier = (user?.subscription_tier || '').toLowerCase() || undefined;
        const resp = await axios.get(`${API_BASE_URL}/api/chat/examples`, {
          params: { locale, scope: 'main_chat', tier, limit: 4 },
        });
        const items = Array.isArray(resp.data) ? resp.data as ExamplePrompt[] : [];
        if (items.length > 0) setExamplePrompts(items);
        else setExamplePrompts([]);
      } catch (e) {
        setExamplePrompts([]);
      }
    };
    fetchExamples();
  }, [API_BASE_URL, user?.subscription_tier]);

  // Handle initial question from EU Law Comply or other sources
  useEffect(() => {
    if (initialQuestion && !inputValue) {
      setInputValue(initialQuestion);
    }
  }, [initialQuestion]);

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const currentInput = inputValue;
    setInputValue('');
    setIsLoading(true);
    setError(null);

    try {
      // Create abort controller for cancellation
      abortControllerRef.current = new AbortController();

      const response = await fetch(`${API_BASE_URL}/api/chat/message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: currentInput,
          chat_id: chatId,
          user_id: user?.id || null,
          document_ids: documentIds.length > 0 ? documentIds : null,
          use_context: useContext,
          stream: false,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      // Store chat_id for conversation continuity
      if (data.chat_id && !chatId) {
        setChatId(data.chat_id);
      }

      const aiMessage: Message = {
        id: data.chat_id + '_' + Date.now(),
        role: 'assistant',
        content: data.message,
        timestamp: new Date(data.timestamp),
        citations: data.citations || [],
        tokensUsed: data.tokens_used,
        searchTimeMs: data.search_time_ms,
        contextsUsed: data.citations?.length || 0,
      };

      setMessages((prev) => [...prev, aiMessage]);
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log('Request aborted');
        return;
      }

      console.error('Failed to send message:', err);
      setError(t('chat.failedResponse'));

      // Add error message to chat
      const errorMessage: Message = {
        id: 'error_' + Date.now(),
        role: 'assistant',
        content: t('chat.errorMessage'),
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleSendMessageStreaming = async () => {
    if (!inputValue.trim() || isLoading || isStreaming) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    const currentInput = inputValue;
    setInputValue('');
    setIsStreaming(true);
    setError(null);

    // Create placeholder for streaming message
    const streamingMessageId = 'streaming_' + Date.now();
    const streamingMessage: Message = {
      id: streamingMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      citations: [],
    };
    setMessages((prev) => [...prev, streamingMessage]);

    try {
      abortControllerRef.current = new AbortController();

      const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: currentInput,
          chat_id: chatId,
          user_id: user?.id || null,
          document_ids: documentIds.length > 0 ? documentIds : null,
          use_context: useContext,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      let accumulatedContent = '';

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const content = line.slice(6);

            if (content === '[DONE]') {
              break;
            }

            accumulatedContent += content;

            // Update streaming message
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === streamingMessageId
                  ? { ...msg, content: accumulatedContent }
                  : msg
              )
            );
          }
        }
      }
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log('Streaming aborted');
        return;
      }

      console.error('Failed to stream message:', err);
      setError('Failed to stream response. Please try again.');
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  };

  const cancelRequest = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // Example click -> set input and focus (no auto-send)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const handleExampleClick = async (example: ExamplePrompt | string) => {
    const text = typeof example === 'string' ? example : example.text;
    setInputValue(text);
    if (typeof example !== 'string' && example.id) {
      try {
        await fetch(`${API_BASE_URL}/api/chat/examples/${example.id}/track`, { method: 'POST' });
      } catch {}
    }
    requestAnimationFrame(() => textareaRef.current?.focus());
  };

  return (
    <div className="chat-interface">
      {/* Settings Bar - Commented out: EU Context is always enabled for Brubru */}
      {/* <div className="chat-interface__settings">
        <label className="chat-interface__setting">
          <input
            type="checkbox"
            checked={useContext}
            onChange={(e) => setUseContext(e.target.checked)}
          />
          <span>Use EU Context (search legislation, procedures, MEPs)</span>
        </label>
        {chatId && (
          <span className="chat-interface__chat-id">
            Chat ID: {chatId.slice(0, 8)}...
          </span>
        )}
      </div> */}

      {/* Error Banner */}
      {error && (
        <div className="chat-interface__error">
          <span>⚠️ {error}</span>
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      {/* Messages */}
      <div className="chat-interface__messages">
        {messages.length === 0 ? (
          <div className="chat-interface__empty">
            <h2>{personalizedGreeting || t('chat.welcome')}</h2>
            <p>{t('chat.tagline')}</p>
            <p className="chat-interface__empty-hint">
              {t('chat.startConversation')}
            </p>
            <div className="chat-interface__examples">
              <h3>{t('chat.tryAsking')}</h3>
              <div className="chat-interface__examples-list">
                {examplePrompts && examplePrompts.length > 0 ? (
                  examplePrompts.map((ex) => (
                    <button
                      key={ex.id}
                      type="button"
                      className="chat-interface__example-btn"
                      onClick={() => handleExampleClick(ex)}
                      aria-label={`Use example: ${ex.text}`}
                    >
                      “{ex.text}”
                    </button>
                  ))
                ) : (
                  <>
                    <button type="button" className="chat-interface__example-btn" onClick={() => handleExampleClick(t('chat.example1'))}>
                      “{t('chat.example1')}”
                    </button>
                    <button type="button" className="chat-interface__example-btn" onClick={() => handleExampleClick(t('chat.example2'))}>
                      “{t('chat.example2')}”
                    </button>
                    <button type="button" className="chat-interface__example-btn" onClick={() => handleExampleClick(t('chat.example3'))}>
                      “{t('chat.example3')}”
                    </button>
                    <button type="button" className="chat-interface__example-btn" onClick={() => handleExampleClick(t('chat.example4'))}>
                      “{t('chat.example4')}”
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        ) : (
          <MessageList messages={messages} chatId={chatId} />
        )}
        <AnimatePresence>
          {(isLoading || isStreaming) && (
            <motion.div
              key="typing"
              className="chat-interface__typing"
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.16 }}
            >
              <img
                src="/assets/brubru_icon_colours.png"
                alt="Brubru is thinking"
                className="chat-interface__typing-logo"
              />
              <span className="chat-interface__typing-text">
                {isStreaming ? (
                  <>
                    Streaming<span className="chat-interface__cursor">|</span>
                  </>
                ) : (
                  'Thinking…'
                )}
              </span>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Input Container */}
      <div className="chat-interface__input-container">
        <textarea
          className="chat-interface__input"
          placeholder={t('chat.placeholder')}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={handleKeyPress}
          rows={3}
          disabled={isLoading || isStreaming}
          ref={textareaRef}
          style={{
            color: '#111827',
            backgroundColor: '#ffffff',
            WebkitTextFillColor: '#111827',
            caretColor: '#111827'
          }}
        />
        <div className="chat-interface__input-actions">
          {(isLoading || isStreaming) ? (
            <button
              className="chat-interface__cancel-button button button-secondary"
              onClick={cancelRequest}
            >
              {t('chat.cancel')}
            </button>
          ) : (
            <>
              <button
                className="chat-interface__send-button button button-primary"
                onClick={handleSendMessage}
                disabled={!inputValue.trim()}
                title="Send message (Enter)"
              >
                {t('chat.send')}
              </button>
              <button
                className="chat-interface__stream-button button button-secondary"
                onClick={handleSendMessageStreaming}
                disabled={!inputValue.trim()}
                title="Stream response"
              >
                {t('chat.stream')}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
