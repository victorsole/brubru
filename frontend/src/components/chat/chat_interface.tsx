// frontend/src/components/chat/chat_interface.tsx
import { useState, useRef, useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { MessageList } from './message_list';
import { DailyBrief } from './daily_brief';
import { OnboardingTour } from './onboarding_tour';
import { EmailCapture } from './email_capture';
import { BrubruIcon } from '../../icons/brubru_icon';
import { useAuth } from '../../hooks/use_auth';
import { useLegislativeTrains } from '../../hooks/use_legislative_trains';
import { trackPreUserEvent, getAbVariant } from '../../services/preuser_tracker';
import './chat_interface.css';

export interface Citation {
  id: number;
  type: string;
  title: string;
  url: string;
  metadata?: Record<string, any>;
}

export interface ChatAction {
  action_type: 'track_file' | 'generate_document' | 'open_amendator' | 'view_prediction' | 'view_calendar';
  label: string;
  icon: string;
  colour: string;
  route?: string;
  params: Record<string, any>;
  requires_auth: boolean;
  pre_user_label?: string;
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
  actions?: ChatAction[];
  isStreaming?: boolean;
}

interface ChatInterfaceProps {
  initialQuestion?: string;
  documentIds?: string[];
  activeChatId?: string | null;
  onConversationUpdate?: () => void;
}

// Pre-user helpers
const PRE_USER_QUERY_LIMIT = 3;

const getPreUserId = (): string => {
  let id = localStorage.getItem('brubru_preuser_id');
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem('brubru_preuser_id', id);
  }
  return id;
};

const getPreUserQueryCount = (): number => {
  return parseInt(localStorage.getItem('brubru_preuser_queries') || '0', 10);
};

const incrementPreUserQueryCount = (): number => {
  const count = getPreUserQueryCount() + 1;
  localStorage.setItem('brubru_preuser_queries', count.toString());
  return count;
};

const getProgressiveCTA = (queryNumber: number): string | null => {
  if (queryNumber <= 1) {
    // Query 1: No CTA - pure value delivery
    return null;
  }
  if (queryNumber === 2) {
    // Query 2: Subtle feature discovery
    return '\n\n---\n\nDid you know? Brubru can also track legislation, draft amendments, and generate position papers. [Discover all features](/signup)';
  }
  // Query 3: Prominent feature cards
  return '\n\n---\n\n**Unlock the full Brubru toolkit:**\n\n'
    + '- **My EU Bubble** -- Track EU legislation, RSS feeds, predictions, and committee work in real time\n'
    + '- **Amendator** -- Draft EU legislative amendments in proper EP format\n'
    + '- **EU Law Comply** -- AI-powered compliance gap analysis against EU regulations\n'
    + '- **Document Generator** -- Position papers, MEP briefings, and talking points\n\n'
    + '[Start your 14-day free trial](/signup)';
};

export interface DetectedEntities {
  mep_names: string[];
  committee_codes: string[];
  procedure_references: string[];
  celex_numbers: string[];
  policy_areas: string[];
}

export const ChatInterface = ({ initialQuestion, documentIds = [], activeChatId, onConversationUpdate }: ChatInterfaceProps = {}) => {
  const { t } = useTranslation();
  const [messages, setMessages] = useState<Message[]>([]);
  // Read ?q= param directly from URL as well as initialQuestion prop
  const urlQuery = typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('q') : null;
  const urlAutofire = typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('autofire') : null;
  const [inputValue, setInputValue] = useState(initialQuestion || urlQuery || '');
  const autofirePendingRef = useRef<boolean>(urlAutofire === '1' && !!(initialQuestion || urlQuery));
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [thinkingStatus, setThinkingStatus] = useState<string | null>(null);
  const [chatId, setChatId] = useState<string | null>(null);
  const [useContext] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [personalizedGreeting, setPersonalizedGreeting] = useState<string | null>(null);
  const [detectedEntities, setDetectedEntities] = useState<DetectedEntities | null>(null);
  const [preUserQueryCount, setPreUserQueryCount] = useState<number>(getPreUserQueryCount());
  const abortControllerRef = useRef<AbortController | null>(null);

  const { isAuthenticated, user } = useAuth();
  const navigate = useNavigate();

  // API base URL - configure this in your environment
  const API_BASE_URL = import.meta.env?.VITE_API_URL || (window as any).REACT_APP_API_URL || 'http://localhost:8000';
  
  // Admin-managed example prompts
  interface ExamplePrompt { id: string; text: string }
  const [examplePrompts, setExamplePrompts] = useState<ExamplePrompt[] | null>(null);

  // Fetch personalized greeting on mount (available to all tiers)
  useEffect(() => {
    // Pre-user: show greeting (date-aware for special days) + track page_load
    if (!isAuthenticated) {
      const now = new Date();
      const m = now.getMonth() + 1;
      const d = now.getDate();
      let greeting = 'Welcome to Brubru! Ask me anything about EU policy.';
      if (m === 4 && d === 23) greeting = 'Happy Sant Jordi! Today is the day of books and roses. Ask me anything about EU policy.';
      else if (m === 5 && d === 9) greeting = 'Happy Europe Day! Ask me anything about EU policy.';
      else if (m === 12 && d === 25) greeting = 'Merry Christmas! If you still feel like thinking about Brussels today, I am here.';
      else if (m === 1 && d === 1) greeting = 'Happy New Year! Let\'s kick off the year with smart EU insights.';
      setPersonalizedGreeting(greeting);
      trackPreUserEvent(getPreUserId(), 'page_load');
      return;
    }

    const fetchGreeting = async () => {
      if (!user) return;

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
        const tier = (user?.subscription_tier || 'blue').toLowerCase();
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

  // Cycle generic status messages during non-streaming (isLoading) requests
  useEffect(() => {
    if (!isLoading) {
      setThinkingStatus(null);
      return;
    }
    const messages = [
      'Searching EU legislation...',
      'Consulting knowledge base...',
      'Composing response...',
    ];
    let index = 0;
    setThinkingStatus(messages[0]);
    const interval = setInterval(() => {
      index = (index + 1) % messages.length;
      setThinkingStatus(messages[index]);
    }, 1500);
    return () => clearInterval(interval);
  }, [isLoading]);

  // Handle initial question from EU Law Comply, daily brief ?q= param, or other sources
  const initialQuestionConsumed = useRef(false);
  useEffect(() => {
    if (initialQuestion && !initialQuestionConsumed.current) {
      setInputValue(initialQuestion);
      initialQuestionConsumed.current = true;
    }
  }, [initialQuestion]);

  // Auto-fire the chat when /main?q=...&autofire=1 (used by the Dashboard
  // tile + ProactiveOpener "Tell me more" CTA). We call the send function
  // directly with the explicit text so we don't depend on the state-closure
  // having flushed. The ref + sessionStorage key together dedupe across
  // React StrictMode's double-invocation in dev.
  const autofireFiredRef = useRef(false);
  useEffect(() => {
    if (!autofirePendingRef.current || autofireFiredRef.current) return;
    const text = (initialQuestion || urlQuery || '').trim();
    if (!text) return;
    if (isLoading || isStreaming) return;
    const dedupeKey = `brubru_autofire:${text}`;
    if (typeof sessionStorage !== 'undefined' && sessionStorage.getItem(dedupeKey) === '1') {
      autofireFiredRef.current = true;
      autofirePendingRef.current = false;
      return;
    }
    autofireFiredRef.current = true;
    autofirePendingRef.current = false;
    try {
      sessionStorage.setItem(dedupeKey, '1');
      // Clear after a short window so the same prompt can fire again on a
      // later visit if the user genuinely re-triggers it.
      setTimeout(() => sessionStorage.removeItem(dedupeKey), 4000);
    } catch {
      /* ignore sessionStorage failures (e.g. private mode) */
    }
    void handleSendMessageStreaming(text);
  }, [initialQuestion, urlQuery, isLoading, isStreaming]);

  // Load messages when activeChatId changes (clicking a previous conversation)
  useEffect(() => {
    if (activeChatId === undefined) return; // prop not provided

    if (activeChatId === null) {
      // New chat requested -- but preserve initialQuestion or ?q= param if present
      setMessages([]);
      setChatId(null);
      if (!initialQuestion && !urlQuery) {
        setInputValue('');
      }
      setError(null);
      return;
    }

    const loadConversation = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/chat/history/${activeChatId}`);
        if (!response.ok) throw new Error('Failed to load conversation');
        const data = await response.json();

        const loaded: Message[] = (data.messages || []).map((m: any) => ({
          id: m.id || crypto.randomUUID(),
          role: m.role,
          content: m.content,
          timestamp: new Date(m.timestamp),
          citations: m.citations || [],
        }));

        setMessages(loaded);
        setChatId(activeChatId);
        setInputValue('');
        setError(null);
      } catch (err) {
        console.error('Failed to load conversation:', err);
        setError('Failed to load conversation');
      }
    };

    loadConversation();
  }, [activeChatId, API_BASE_URL]);

  const handleSendMessage = async () => {
    if (!inputValue.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue,
      timestamp: new Date(),
    };

    // Pre-user query limit check
    if (!isAuthenticated) {
      const count = getPreUserQueryCount();
      if (count >= PRE_USER_QUERY_LIMIT) {
        const blockedMessage: Message = {
          id: 'blocked_' + Date.now(),
          role: 'assistant',
          content: 'You have used your 3 free queries. Start a free trial to continue chatting and unlock the full Brubru toolkit:\n\n'
            + '- **My EU Bubble** -- Track EU legislation, RSS feeds, predictions, and committee work\n'
            + '- **Amendator** -- Draft EU legislative amendments in proper EP format\n'
            + '- **EU Law Comply** -- AI-powered compliance gap analysis against EU regulations\n'
            + '- **Document Generator** -- Position papers, MEP briefings, and talking points\n\n'
            + '[Start your 14-day free trial](/signup)',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, userMessage, blockedMessage]);
        setInputValue('');
        return;
      }
    }

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
          pre_user_id: !isAuthenticated ? getPreUserId() : null,
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

      // For pre-users, increment count, track event, and append progressive CTA
      let messageContent = data.message;
      if (!isAuthenticated) {
        const newCount = incrementPreUserQueryCount();
        setPreUserQueryCount(newCount);
        const eventType = newCount <= 3 ? `query_${newCount}` : 'query_3';
        trackPreUserEvent(getPreUserId(), eventType);
        const cta = getProgressiveCTA(newCount);
        if (cta) {
          messageContent += cta;
        }
      }

      const aiMessage: Message = {
        id: data.chat_id + '_' + Date.now(),
        role: 'assistant',
        content: messageContent,
        timestamp: new Date(data.timestamp),
        citations: data.citations || [],
        tokensUsed: data.tokens_used,
        searchTimeMs: data.search_time_ms,
        contextsUsed: data.citations?.length || 0,
        actions: data.actions || [],
      };

      setMessages((prev) => [...prev, aiMessage]);
      onConversationUpdate?.();
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

  const handleSendMessageStreaming = async (overrideText?: string) => {
    // Allow callers (e.g. the autofire effect) to bypass the inputValue
    // closure when they already know the text. Falls back to the state
    // when called from the Send button or Enter-key handler.
    const messageText = (overrideText !== undefined ? overrideText : inputValue);
    if (!messageText.trim() || isLoading || isStreaming) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: messageText,
      timestamp: new Date(),
    };

    // Pre-user query limit check
    if (!isAuthenticated) {
      const count = getPreUserQueryCount();
      if (count >= PRE_USER_QUERY_LIMIT) {
        const blockedMessage: Message = {
          id: 'blocked_' + Date.now(),
          role: 'assistant',
          content: 'You have used your 3 free queries. Start a free trial to continue chatting and unlock the full Brubru toolkit:\n\n'
            + '- **My EU Bubble** -- Track EU legislation, RSS feeds, predictions, and committee work\n'
            + '- **Amendator** -- Draft EU legislative amendments in proper EP format\n'
            + '- **EU Law Comply** -- AI-powered compliance gap analysis against EU regulations\n'
            + '- **Document Generator** -- Position papers, MEP briefings, and talking points\n\n'
            + '[Start your 14-day free trial](/signup)',
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, userMessage, blockedMessage]);
        setInputValue('');
        return;
      }
    }

    setMessages((prev) => [...prev, userMessage]);
    const currentInput = messageText;
    setInputValue('');
    setIsStreaming(true);
    setError(null);

    // Streaming message placeholder -- added to messages only when first text arrives
    const streamingMessageId = 'streaming_' + Date.now();
    let messageAdded = false;

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
          pre_user_id: !isAuthenticated ? getPreUserId() : null,
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
      let sseBuffer = '';  // Buffer for incomplete SSE lines across reads

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        // Append new data to buffer, then split on double-newline (SSE event boundary)
        sseBuffer += decoder.decode(value, { stream: true });
        const parts = sseBuffer.split('\n');

        // Keep the last part in the buffer (it may be incomplete)
        sseBuffer = parts.pop() || '';

        for (const line of parts) {
          if (line.startsWith('data: ')) {
            const content = line.slice(6);

            if (content === '[DONE]') {
              setThinkingStatus(null);
              break;
            }

            // Parse status/entity events from backend
            if (content.startsWith('{')) {
              try {
                const parsed = JSON.parse(content);
                if (parsed.type === 'status') {
                  setThinkingStatus(parsed.message);
                  continue;
                }
                if (parsed.type === 'entities') {
                  setDetectedEntities({
                    mep_names: parsed.mep_names || [],
                    committee_codes: parsed.committee_codes || [],
                    procedure_references: parsed.procedure_references || [],
                    celex_numbers: parsed.celex_numbers || [],
                    policy_areas: parsed.policy_areas || [],
                  });
                  continue;
                }
                if (parsed.type === 'actions' && parsed.actions) {
                  setMessages((prev) =>
                    prev.map((msg) =>
                      msg.id === streamingMessageId
                        ? { ...msg, actions: parsed.actions }
                        : msg
                    )
                  );
                  continue;
                }
              } catch {
                // Not JSON -- treat as text chunk
              }
            }

            // Decode escaped newlines from SSE transport
            const decoded = content.replace(/\\n/g, '\n');
            accumulatedContent += decoded;

            // First real text chunk: add message frame and clear status
            if (!messageAdded) {
              messageAdded = true;
              setThinkingStatus(null);
              setMessages((prev) => [...prev, {
                id: streamingMessageId,
                role: 'assistant' as const,
                content: accumulatedContent,
                timestamp: new Date(),
                citations: [],
                isStreaming: true,
              }]);
            } else {
              // Update streaming message with accumulated content
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
      }
      // Mark streaming complete -- triggers full markdown render
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === streamingMessageId
            ? { ...msg, isStreaming: false }
            : msg
        )
      );

      // For pre-users, increment count, track event, and append progressive CTA after streaming
      if (!isAuthenticated) {
        const newCount = incrementPreUserQueryCount();
        setPreUserQueryCount(newCount);
        const eventType = newCount <= 3 ? `query_${newCount}` : 'query_3';
        trackPreUserEvent(getPreUserId(), eventType);
        const cta = getProgressiveCTA(newCount);
        if (cta) {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === streamingMessageId
                ? { ...msg, content: msg.content + cta }
                : msg
            )
          );
        }
      }
      onConversationUpdate?.();
    } catch (err: any) {
      if (err.name === 'AbortError') {
        console.log('Streaming aborted');
        return;
      }

      console.error('Streaming failed, falling back to non-streaming:', err);

      // Fallback: remove the streaming message (if it was added) and retry via non-streaming
      if (messageAdded) {
        setMessages((prev) => prev.filter((msg) => msg.id !== streamingMessageId));
      }
      setIsStreaming(false);
      setThinkingStatus(null);
      abortControllerRef.current = null;

      // Restore input so handleSendMessage can use it
      setInputValue(currentInput);
      // Small delay to let state settle, then call non-streaming path
      setTimeout(() => {
        handleSendMessage();
      }, 100);
      return;
    } finally {
      setIsStreaming(false);
      setThinkingStatus(null);
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
      handleSendMessageStreaming();
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

  const handleActionClick = (action: ChatAction) => {
    // Pre-user: always navigate to subscription
    if (!isAuthenticated) {
      navigate('/subscription');
      return;
    }

    switch (action.action_type) {
      case 'track_file': {
        const ref = action.params.procedure_ref;
        if (ref) {
          useLegislativeTrains.getState().trackFile(ref);
        }
        break;
      }
      case 'generate_document':
        navigate('/main', {
          state: {
            openDocGenerator: true,
            docType: action.params.document_type,
            topic: action.params.topic,
          },
        });
        break;
      case 'open_amendator':
      case 'view_prediction':
      case 'view_calendar':
        if (action.route) {
          navigate(action.route);
        }
        break;
    }
  };

  return (
    <div className="chat-interface">
      {/* Onboarding tour for pre-users */}
      <OnboardingTour isAuthenticated={isAuthenticated} />

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
            <BrubruIcon size={3} color="var(--color-primary)" className="chat-interface__empty-icon" />
            <h2>{personalizedGreeting || t('chat.welcome')}</h2>

            {/* Dashboard grid: headlines + example prompts + stats */}
            <DailyBrief
              onQueryClick={(query) => {
                setInputValue(query);
                requestAnimationFrame(() => textareaRef.current?.focus());
              }}
              examplePrompts={examplePrompts && examplePrompts.length > 0 ? examplePrompts : [
                { id: 'f1', text: t('chat.example1') },
                { id: 'f2', text: t('chat.example2') },
                { id: 'f3', text: t('chat.example3') },
                { id: 'f4', text: t('chat.example4') },
              ]}
              onExampleClick={handleExampleClick}
            />
          </div>
        ) : (
          <MessageList
            messages={messages}
            chatId={chatId}
            onFollowUpClick={(text) => {
              setInputValue(text);
              requestAnimationFrame(() => textareaRef.current?.focus());
            }}
            abVariant={!isAuthenticated ? getAbVariant(getPreUserId()) : undefined}
            detectedEntities={detectedEntities}
            preUserQueryCount={preUserQueryCount}
            onSmartSuggestionClick={(text) => {
              trackPreUserEvent(getPreUserId(), 'smart_suggestion_clicked', { suggestion: text });
              setInputValue(text);
              requestAnimationFrame(() => textareaRef.current?.focus());
            }}
            onActionClick={handleActionClick}
          />
        )}

        {/* Email capture prompt after first assistant response */}
        {!isAuthenticated && messages.filter(m => m.role === 'assistant').length === 1 && (
          <EmailCapture preUserId={getPreUserId()} />
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
                {thinkingStatus ? (
                  thinkingStatus
                ) : isStreaming ? (
                  <>
                    Streaming<span className="chat-interface__cursor">|</span>
                  </>
                ) : (
                  'Thinking...'
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
            <button
              className="chat-interface__send-button button button-primary"
              onClick={() => handleSendMessageStreaming()}
              disabled={!inputValue.trim()}
              title="Send message (Enter)"
            >
              {t('chat.send')}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
