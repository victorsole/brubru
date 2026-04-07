// frontend/src/components/chat/message_list.tsx
import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { marked } from 'marked';
import Icon from '@mdi/react';
import { mdiMedalOutline, mdiEmoticonConfusedOutline, mdiAlertCircleOutline, mdiClose } from '@mdi/js';
import axios from 'axios';
import type { Message, Citation, DetectedEntities, ChatAction } from './chat_interface';
import { ActionButtons } from './action_buttons';
import { getEultUrl } from '../../utils/eu_links';
import './message_list.css';

interface MessageListProps {
  messages: Message[];
  chatId?: string | null;
  onFollowUpClick?: (text: string) => void;
  abVariant?: 'A' | 'B';
  detectedEntities?: DetectedEntities | null;
  preUserQueryCount?: number;
  onSmartSuggestionClick?: (text: string) => void;
  onActionClick?: (action: ChatAction) => void;
}

// Extract follow-up suggestions from the end of assistant messages.
// Looks for patterns like "Would you like me to...", "I can also...", "Shall I..."
// at the end of a message and splits them into clickable items.
const extractFollowUps = (content: string): { cleanContent: string; followUps: string[] } => {
  const lines = content.split('\n');
  const followUps: string[] = [];
  let cutIndex = lines.length;

  // Scan backwards from end for follow-up patterns
  for (let i = lines.length - 1; i >= 0; i--) {
    const trimmed = lines[i].trim();
    if (!trimmed) continue;

    // Match lines starting with follow-up patterns (with or without bullet prefix)
    const followUpMatch = trimmed.match(
      /^(?:[-*]\s*)?(?:Would you like (?:me to|to)|I can (?:also|help)|Shall I|Do you want me to|I could also)\b/i
    );
    if (followUpMatch) {
      // Strip bullet prefix and leading dash
      const cleaned = trimmed.replace(/^[-*]\s*/, '').trim();
      followUps.unshift(cleaned);
      cutIndex = i;
    } else {
      // Stop scanning once we hit a non-follow-up, non-empty line
      break;
    }
  }

  if (followUps.length === 0) {
    return { cleanContent: content, followUps: [] };
  }

  // Build clean content without the follow-up lines
  const cleanLines = lines.slice(0, cutIndex);
  // Also trim trailing empty lines
  while (cleanLines.length > 0 && !cleanLines[cleanLines.length - 1].trim()) {
    cleanLines.pop();
  }

  return { cleanContent: cleanLines.join('\n'), followUps };
};

// Generate smart suggestion buttons based on detected entities
const generateSmartSuggestions = (entities: DetectedEntities | null | undefined): string[] => {
  if (!entities) return [];
  const suggestions: string[] = [];

  if (entities.mep_names.length > 0) {
    suggestions.push('Show me which MEPs are working on this');
  }
  if (entities.procedure_references.length > 0) {
    const ref = entities.procedure_references[0];
    suggestions.push(`What is the current status of ${ref}?`);
  }
  if (entities.committee_codes.length > 0) {
    const code = entities.committee_codes[0];
    suggestions.push(`Who are the key members of the ${code} committee?`);
  }
  if (entities.policy_areas.length > 0) {
    suggestions.push('Draft a quick briefing on this topic');
  }

  // Fallback if no specific entities detected
  if (suggestions.length === 0) {
    suggestions.push('What EU legislation is most relevant to this topic?');
  }

  return suggestions.slice(0, 3);
};

export const MessageList = ({ messages, chatId, onFollowUpClick, abVariant, detectedEntities, preUserQueryCount, onSmartSuggestionClick, onActionClick }: MessageListProps) => {
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

  // Link CELEX numbers to EUR-Lex (only in text content, not inside HTML tags/attributes)
  const linkCelexNumbers = (text: string): string => {
    return text.replace(
      /(<[^>]*>)|(\b[0-9]{5}[A-Z][0-9]{4,}\b)/g,
      (_match, htmlTag, celex) => {
        if (htmlTag) return htmlTag; // Return HTML tags unchanged
        return `<a href="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:${celex}" target="_blank" rel="noopener noreferrer" class="message-list__link message-list__link--celex">${celex}</a>`;
      }
    );
  };

  // Link procedure references to OEIL + EU Law Tracker (only in text content, not inside HTML tags/attributes)
  const linkProcedureReferences = (text: string): string => {
    return text.replace(
      /(<[^>]*>)|(\b\d{4}\/\d{4}\([A-Z]{2,5}\)\b)/g,
      (_match, htmlTag, procRef) => {
        if (htmlTag) return htmlTag; // Return HTML tags unchanged
        const eultUrl = getEultUrl(procRef);
        const eultLink = eultUrl
          ? ` <a href="${eultUrl}" target="_blank" rel="noopener noreferrer" class="message-list__link message-list__link--procedure">EULT</a>`
          : '';
        return `<a href="https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=${procRef}" target="_blank" rel="noopener noreferrer" class="message-list__link message-list__link--procedure">${procRef}</a>${eultLink}`;
      }
    );
  };

  // Link MEP names (simplified - would need MEP ID lookup in production)
  const linkMEPNames = (text: string): string => {
    // Pattern for "MEP Name" format - basic implementation
    // In production, would need to match against actual MEP database
    return text;
  };

  // Link committee codes (ENVI, ITRE, etc.) to EP committee pages
  // Only links codes that match real EP committees
  const EP_COMMITTEE_CODES = new Set([
    'AFET', 'DROI', 'SEDE', 'DEVE', 'INTA', 'BUDG', 'CONT', 'ECON',
    'FISC', 'EMPL', 'ENVI', 'SANT', 'ITRE', 'IMCO', 'TRAN', 'REGI',
    'AGRI', 'PECH', 'CULT', 'JURI', 'LIBE', 'AFCO', 'FEMM', 'PETI',
    'EUDS', 'HOUS',
  ]);

  const linkCommitteeCodes = (text: string): string => {
    // Match "CODE committee" pattern (only in text content, not inside HTML tags)
    let result = text.replace(
      /(<[^>]*>)|(\b([A-Z]{4})\s+(?:committee|Committee)\b)/g,
      (match, htmlTag, _full, code) => {
        if (htmlTag) return htmlTag;
        if (!code || !EP_COMMITTEE_CODES.has(code)) return match;
        return `<a href="https://www.europarl.europa.eu/committees/en/${code}/home" target="_blank" rel="noopener noreferrer" class="message-list__link message-list__link--committee">${code} committee</a>`;
      }
    );

    // Also match standalone committee codes in parentheses: (ENVI)
    result = result.replace(
      /(<[^>]*>)|(\(([A-Z]{4})\))/g,
      (match, htmlTag, _full, code) => {
        if (htmlTag) return htmlTag;
        if (!code || !EP_COMMITTEE_CODES.has(code)) return match;
        return `(<a href="https://www.europarl.europa.eu/committees/en/${code}/home" target="_blank" rel="noopener noreferrer" class="message-list__link message-list__link--committee">${code}</a>)`;
      }
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

  const getCitationIconClass = (type: string): string => {
    switch (type) {
      case 'legislation':
        return 'mdi mdi-script-text';
      case 'procedure':
        return 'mdi mdi-scale-balance';
      case 'mep':
        return 'mdi mdi-account';
      case 'news':
        return 'mdi mdi-newspaper';
      default:
        return 'mdi mdi-file-document';
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
            {(() => {
              if (message.role === 'assistant') {
                // Always render markdown (even during streaming).
                // Backend escapes newlines as \\n in SSE, frontend decodes them,
                // so the accumulated text has proper markdown structure.
                const { cleanContent, followUps } = extractFollowUps(message.content);
                const isLastAssistant = message === [...messages].reverse().find(m => m.role === 'assistant');
                const showSmartSuggestions = abVariant === 'B' && preUserQueryCount === 1 && isLastAssistant;
                const smartSuggestions = showSmartSuggestions ? generateSmartSuggestions(detectedEntities) : [];
                return (
                  <>
                    {renderContentWithCitations(cleanContent, message.citations)}
                    {followUps.length > 0 && onFollowUpClick && (
                      <div className="message-list__follow-ups">
                        {followUps.map((text, idx) => (
                          <button
                            key={idx}
                            type="button"
                            className="message-list__follow-up-btn"
                            onClick={() => onFollowUpClick(text)}
                          >
                            {text}
                          </button>
                        ))}
                      </div>
                    )}
                    {isLastAssistant && message.actions && message.actions.length > 0 && onActionClick && (
                      <ActionButtons
                        actions={message.actions}
                        onActionClick={onActionClick}
                        isPreUser={!!abVariant}
                      />
                    )}
                    {smartSuggestions.length > 0 && onSmartSuggestionClick && (
                      <div className="message-list__smart-suggestions">
                        <span className="message-list__smart-suggestions-label">Explore further:</span>
                        {smartSuggestions.map((text, idx) => (
                          <button
                            key={idx}
                            type="button"
                            className="message-list__smart-suggestion-btn"
                            onClick={() => onSmartSuggestionClick(text)}
                          >
                            <span className="mdi mdi-lightbulb-on-outline"></span>
                            {text}
                          </button>
                        ))}
                      </div>
                    )}
                  </>
                );
              }
              return renderContentWithCitations(message.content, message.citations);
            })()}

            {/* Context Indicator */}
            {message.role === 'assistant' && message.contextsUsed !== undefined && message.contextsUsed > 0 && (
              <div className="message-list__context-indicator">
                <span className="message-list__context-icon mdi mdi-magnify"></span>
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
                          <span className={`message-list__citation-icon ${getCitationIconClass(citation.type)}`}>
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
                <span><span className="mdi mdi-counter"></span> {message.tokensUsed} tokens</span>
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
