// frontend/src/components/chat/message_list.tsx
import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { marked } from 'marked';
import Icon from '@mdi/react';
import { mdiMedalOutline, mdiEmoticonConfusedOutline, mdiAlertCircleOutline, mdiClose } from '@mdi/js';
import axios from 'axios';
import type { Message, Citation } from './chat_interface';
import './message_list.css';

interface MessageListProps {
  messages: Message[];
  chatId?: string | null;
}

export const MessageList = ({ messages, chatId }: MessageListProps) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [expandedSources, setExpandedSources] = useState<Set<string>>(new Set());
  const [feedbackGiven, setFeedbackGiven] = useState<Map<string, 'positive' | 'negative' | 'hallucination'>>(new Map());
  const [feedbackLoading, setFeedbackLoading] = useState<Set<string>>(new Set());
  const [showHallucinationInput, setShowHallucinationInput] = useState<string | null>(null);
  const [hallucinationText, setHallucinationText] = useState('');

  // API base URL
  const API_BASE_URL = import.meta.env?.VITE_API_URL || (window as any).REACT_APP_API_URL || 'http://localhost:8000';

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

  const toggleSources = (messageId: string) => {
    setExpandedSources((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(messageId)) {
        newSet.delete(messageId);
      } else {
        newSet.add(messageId);
      }
      return newSet;
    });
  };

  // Handle feedback submission
  const handleFeedback = async (messageId: string, rating: 'positive' | 'negative' | 'hallucination', messageContent: string, feedbackText?: string) => {
    // If feedback already given, don't allow changing
    if (feedbackGiven.has(messageId)) {
      return;
    }

    setFeedbackLoading((prev) => new Set(prev).add(messageId));

    try {
      await axios.post(`${API_BASE_URL}/api/feedback/chat`, {
        chat_id: chatId || 'unknown',
        message_id: messageId,
        rating: rating,
        message_content: messageContent.substring(0, 500), // Truncate to 500 chars
        feedback_text: feedbackText || undefined
      });

      // Mark feedback as given
      setFeedbackGiven((prev) => new Map(prev).set(messageId, rating));

      // Clear hallucination input state
      if (rating === 'hallucination') {
        setShowHallucinationInput(null);
        setHallucinationText('');
      }
    } catch (error) {
      console.error('Failed to submit feedback:', error);
      // Optionally show error toast/notification
    } finally {
      setFeedbackLoading((prev) => {
        const newSet = new Set(prev);
        newSet.delete(messageId);
        return newSet;
      });
    }
  };

  // Handle hallucination report button click
  const handleHallucinationClick = (messageId: string) => {
    if (feedbackGiven.has(messageId)) return;
    setShowHallucinationInput(showHallucinationInput === messageId ? null : messageId);
    setHallucinationText('');
  };

  // Submit hallucination report
  const submitHallucinationReport = (messageId: string, messageContent: string) => {
    handleFeedback(messageId, 'hallucination', messageContent, hallucinationText);
  };

  // Link CELEX numbers to EUR-Lex
  const linkCelexNumbers = (text: string): string => {
    const celexPattern = /\b([0-9]{5}[A-Z][0-9]{4,})\b/g;
    return text.replace(
      celexPattern,
      '<a href="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:$1" target="_blank" rel="noopener noreferrer" class="message-list__link message-list__link--celex">$1</a>'
    );
  };

  // Link procedure references to OEIL
  const linkProcedureReferences = (text: string): string => {
    const procedurePattern = /\b(\d{4}\/\d{4}\([A-Z]{2,5}\))\b/g;
    return text.replace(
      procedurePattern,
      '<a href="https://oeil.secure.europarl.europa.eu/oeil/popups/ficheprocedure.do?reference=$1" target="_blank" rel="noopener noreferrer" class="message-list__link message-list__link--procedure">$1</a>'
    );
  };

  // Link MEP names (simplified - would need MEP ID lookup in production)
  const linkMEPNames = (text: string): string => {
    // Pattern for "MEP Name" format - basic implementation
    // In production, would need to match against actual MEP database
    return text;
  };

  // Link committee codes (ENVI, ITRE, etc.) to EP committee pages
  const linkCommitteeCodes = (text: string): string => {
    // Match committee codes (4-letter uppercase codes)
    // Look for patterns like "ENVI committee" or "(ENVI)" but avoid matching inside words
    const committeePattern = /\b([A-Z]{4})\s+(?:committee|Committee)\b/g;
    let result = text.replace(
      committeePattern,
      '<a href="https://www.europarl.europa.eu/committees/en/$1/home" target="_blank" rel="noopener noreferrer" class="message-list__link message-list__link--committee">$1 committee</a>'
    );

    // Also match standalone committee codes in parentheses: (ENVI)
    const standalonePattern = /\(([A-Z]{4})\)/g;
    result = result.replace(
      standalonePattern,
      '(<a href="https://www.europarl.europa.eu/committees/en/$1/home" target="_blank" rel="noopener noreferrer" class="message-list__link message-list__link--committee">$1</a>)'
    );

    return result;
  };

  // Convert markdown to HTML
  const convertMarkdownToHTML = (text: string): string => {
    try {
      // Configure marked options
      marked.setOptions({
        breaks: true,
        gfm: true,
      });

      return marked.parse(text) as string;
    } catch (error) {
      console.error('Error parsing markdown:', error);
      return text;
    }
  };

  // Process text with all link transformations
  const processTextLinks = (text: string): string => {
    let processedText = text;

    // First convert markdown to HTML
    processedText = convertMarkdownToHTML(processedText);

    // Then apply link transformations
    processedText = linkCelexNumbers(processedText);
    processedText = linkProcedureReferences(processedText);
    processedText = linkCommitteeCodes(processedText);
    processedText = linkMEPNames(processedText);

    return processedText;
  };

  // Parse citation markers [1], [2], etc.
  const renderContentWithCitations = (content: string, citations?: Citation[]) => {
    if (!citations || citations.length === 0) {
      return (
        <div
          className="message-list__message-text"
          dangerouslySetInnerHTML={{ __html: processTextLinks(content) }}
        />
      );
    }

    // Replace citation markers with clickable footnotes
    let processedContent = processTextLinks(content);
    const citationPattern = /\[(\d+)\]/g;
    processedContent = processedContent.replace(
      citationPattern,
      '<sup class="message-list__citation-marker" data-citation-id="$1">[$1]</sup>'
    );

    return (
      <div
        className="message-list__message-text"
        dangerouslySetInnerHTML={{ __html: processedContent }}
      />
    );
  };

  const getCitationIcon = (type: string): string => {
    switch (type) {
      case 'legislation':
        return '📜';
      case 'procedure':
        return '⚖️';
      case 'mep':
        return '👤';
      case 'news':
        return '📰';
      default:
        return '📄';
    }
  };

  const formatCitationType = (type: string): string => {
    const typeMap: Record<string, string> = {
      legislation: 'Legislation',
      procedure: 'Legislative Procedure',
      mep: 'MEP Profile',
      news: 'News Article',
      search_result: 'Search Result',
    };
    return typeMap[type] || type;
  };

  return (
    <div className="message-list">
      <AnimatePresence initial={false}>
      {messages.map((message) => (
        <motion.div
          key={message.id}
          layout
          initial={{ opacity: 0, y: 8, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -6, scale: 0.98 }}
          transition={{ duration: 0.18, ease: 'easeOut' }}
          className={`message-list__message message-list__message--${message.role} message-enter`}
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

            {/* Message Content */}
            {renderContentWithCitations(message.content, message.citations)}

            {/* Context Indicator */}
            {message.role === 'assistant' && message.contextsUsed !== undefined && message.contextsUsed > 0 && (
              <div className="message-list__context-indicator">
                <span className="message-list__context-icon">🔍</span>
                <span>Used {message.contextsUsed} EU document{message.contextsUsed > 1 ? 's' : ''}</span>
                {message.searchTimeMs && (
                  <span className="message-list__context-time">
                    ({message.searchTimeMs}ms search)
                  </span>
                )}
                {message.citations && message.citations.length > 0 && (
                  <button
                    className="message-list__view-sources-button"
                    onClick={() => toggleSources(message.id)}
                  >
                    {expandedSources.has(message.id) ? 'Hide sources' : 'View sources'}
                  </button>
                )}
              </div>
            )}

            {/* Citations/Sources Section */}
            {message.role === 'assistant' &&
              message.citations &&
              message.citations.length > 0 &&
              expandedSources.has(message.id) && (
                <div className="message-list__citations">
                  <h4 className="message-list__citations-title">Sources</h4>
                  <div className="message-list__citations-list">
                    {message.citations.map((citation) => (
                      <div key={citation.id} className="message-list__citation">
                        <div className="message-list__citation-header">
                          <span className="message-list__citation-icon">
                            {getCitationIcon(citation.type)}
                          </span>
                          <span className="message-list__citation-number">[{citation.id}]</span>
                          <span className="message-list__citation-type">
                            {formatCitationType(citation.type)}
                          </span>
                        </div>
                        <div className="message-list__citation-content">
                          <div className="message-list__citation-title">
                            {citation.title}
                          </div>
                          {citation.metadata?.celex && (
                            <div className="message-list__citation-meta">
                              CELEX: {citation.metadata.celex}
                            </div>
                          )}
                          {citation.metadata?.reference && (
                            <div className="message-list__citation-meta">
                              Procedure: {citation.metadata.reference}
                            </div>
                          )}
                          {citation.metadata?.date && (
                            <div className="message-list__citation-meta">
                              Date: {citation.metadata.date}
                            </div>
                          )}
                          <a
                            href={citation.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="message-list__citation-link"
                          >
                            View source →
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

            {/* Token Usage (optional metadata) */}
            {message.role === 'assistant' && message.tokensUsed && (
              <div className="message-list__metadata">
                <span>🔢 {message.tokensUsed} tokens</span>
              </div>
            )}

            {/* Feedback Buttons */}
            {message.role === 'assistant' && (
              <div className="message-list__feedback">
                <span className="message-list__feedback-label">Was this helpful?</span>
                <div className="message-list__feedback-buttons">
                  <button
                    className={`message-list__feedback-button ${
                      feedbackGiven.get(message.id) === 'positive' ? 'message-list__feedback-button--active' : ''
                    }`}
                    onClick={() => handleFeedback(message.id, 'positive', message.content)}
                    disabled={feedbackLoading.has(message.id) || feedbackGiven.has(message.id)}
                    title="This was helpful"
                  >
                    <Icon path={mdiMedalOutline} size={0.8} />
                  </button>
                  <button
                    className={`message-list__feedback-button ${
                      feedbackGiven.get(message.id) === 'negative' ? 'message-list__feedback-button--active' : ''
                    }`}
                    onClick={() => handleFeedback(message.id, 'negative', message.content)}
                    disabled={feedbackLoading.has(message.id) || feedbackGiven.has(message.id)}
                    title="This was not helpful"
                  >
                    <Icon path={mdiEmoticonConfusedOutline} size={0.8} />
                  </button>
                  <button
                    className={`message-list__feedback-button message-list__feedback-button--report ${
                      feedbackGiven.get(message.id) === 'hallucination' ? 'message-list__feedback-button--active' : ''
                    } ${showHallucinationInput === message.id ? 'message-list__feedback-button--expanded' : ''}`}
                    onClick={() => handleHallucinationClick(message.id)}
                    disabled={feedbackLoading.has(message.id) || feedbackGiven.has(message.id)}
                    title="Report incorrect information"
                  >
                    <Icon path={mdiAlertCircleOutline} size={0.8} />
                  </button>
                </div>
                {feedbackGiven.has(message.id) && (
                  <span className="message-list__feedback-thank-you">
                    {feedbackGiven.get(message.id) === 'hallucination'
                      ? 'Thank you for reporting this issue!'
                      : 'Thank you for your feedback!'}
                  </span>
                )}

                {/* Hallucination Report Input */}
                {showHallucinationInput === message.id && !feedbackGiven.has(message.id) && (
                  <div className="message-list__hallucination-input">
                    <div className="message-list__hallucination-header">
                      <span>What was incorrect? (optional)</span>
                      <button
                        className="message-list__hallucination-close"
                        onClick={() => setShowHallucinationInput(null)}
                        title="Cancel"
                      >
                        <Icon path={mdiClose} size={0.6} />
                      </button>
                    </div>
                    <textarea
                      className="message-list__hallucination-textarea"
                      placeholder="e.g., The fine amount is wrong - GDPR fines are up to €20M, not €50M"
                      value={hallucinationText}
                      onChange={(e) => setHallucinationText(e.target.value)}
                      rows={2}
                      maxLength={500}
                    />
                    <button
                      className="message-list__hallucination-submit"
                      onClick={() => submitHallucinationReport(message.id, message.content)}
                      disabled={feedbackLoading.has(message.id)}
                    >
                      {feedbackLoading.has(message.id) ? 'Submitting...' : 'Submit Report'}
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        </motion.div>
      ))}
      </AnimatePresence>
      <div ref={messagesEndRef} />
    </div>
  );
};
