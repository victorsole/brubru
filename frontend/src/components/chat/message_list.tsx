// frontend/src/components/chat/message_list.tsx
import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { marked } from 'marked';
import Icon from '@mdi/react';
import { mdiMedalOutline, mdiEmoticonConfusedOutline, mdiAlertCircleOutline, mdiClose } from '@mdi/js';
import axios from 'axios';
import { useTranslation } from 'react-i18next';
import type { Message, Citation, DetectedEntities, ChatAction } from './chat_interface';
import { ActionButtons } from './action_buttons';
import { DraftedDocumentCard } from './drafted_document_card';
import { getEultUrl } from '../../utils/eu_links';
import './message_list.css';
import { uiDateLocale } from '../../i18n/config';

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

// Deterministic follow-up offers based on entities the backend already
// detected for this turn. Always rendered under the last assistant message,
// independent of A/B variant or query count. Distinct from ActionButtons
// (deep-links) and from regex-scraped follow-ups (model prose).
// Takes the component's `t` so suggestions render in the UI language.
type TranslateFn = (key: string, defaultValue: string, options?: Record<string, unknown>) => string;

const generateSmartSuggestions = (
  entities: DetectedEntities | null | undefined,
  t: TranslateFn,
): string[] => {
  const suggestions: string[] = [];
  const walkThrough = t('chat.suggestWalkThrough', 'Walk me through what this means for my work.');
  if (!entities) {
    suggestions.push(walkThrough);
    return suggestions.slice(0, 3);
  }

  if (entities.procedure_references.length > 0) {
    const ref = entities.procedure_references[0];
    suggestions.push(t('chat.suggestStatus', 'What is the current status of {{ref}}?', { ref }));
  }
  if (entities.celex_numbers.length > 0) {
    const celex = entities.celex_numbers[0];
    suggestions.push(t('chat.suggestKeyArticles', 'Show me the key articles of {{celex}}.', { celex }));
  }
  if (entities.mep_names.length > 0) {
    suggestions.push(t('chat.suggestWhoElse', 'Who else is working on this file?'));
  }
  if (entities.committee_codes.length > 0) {
    const code = entities.committee_codes[0];
    suggestions.push(t('chat.suggestCommitteeAgenda', 'What is on the {{code}} committee agenda this month?', { code }));
  }
  if (suggestions.length < 3 && entities.policy_areas.length > 0) {
    suggestions.push(t('chat.suggestDraftBrief', 'Draft a one-page brief on this for me.'));
  }
  if (suggestions.length === 0) {
    suggestions.push(walkThrough);
  }
  return suggestions.slice(0, 3);
};

export const MessageList = ({ messages, chatId, onFollowUpClick, abVariant, detectedEntities, onSmartSuggestionClick, onActionClick }: MessageListProps) => {
  const { t, i18n } = useTranslation();
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
    return new Intl.DateTimeFormat(uiDateLocale(), {
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

  // EUR-Lex serves the 24 official EU languages. Catalan is not one of them,
  // so a Catalan reader gets the Spanish text, which is the closest official
  // version rather than an arbitrary English default. Everything else maps
  // straight through. Hardcoding EN meant a French, Spanish, Italian or Dutch
  // user's every legislative link opened in English.
  const eurlexLang = (): string => {
    const code = (i18n.language || 'en').slice(0, 2).toLowerCase();
    const map: Record<string, string> = {
      en: 'EN', fr: 'FR', nl: 'NL', es: 'ES', it: 'IT', ca: 'ES',
    };
    return map[code] || 'EN';
  };

  // Link CELEX numbers to EUR-Lex (only in text content, not inside HTML tags/attributes).
  // The type position takes ONE OR TWO letters: adopted acts are R/L/D/H/X
  // (32024R1781) but Commission proposals carry two (52026PC0429, 52020DC0098).
  // The single-letter form silently skipped every proposal, which is the same
  // defect fixed on the backend on 5 Aug -- the two layers had drifted apart.
  const linkCelexNumbers = (text: string): string => {
    const lang = eurlexLang();
    return text.replace(
      /(<a\b[^>]*>[\s\S]*?<\/a>)|(<[^>]*>)|(\b[0-9]{5}[A-Z]{1,2}[0-9]{4,}\b)/g,
      (_match, anchor, htmlTag, celex) => {
        // Skip whole anchors: linkifying text already inside one produces
        // nested <a> elements, which browsers unnest into broken markup.
        if (anchor) return anchor;
        if (htmlTag) return htmlTag;
        return `<a href="https://eur-lex.europa.eu/legal-content/${lang}/TXT/?uri=CELEX:${celex}" target="_blank" rel="noopener noreferrer" class="message-list__link message-list__link--celex">${celex}</a>`;
      }
    );
  };

  // Link procedure references to OEIL + EU Law Tracker (only in text content, not inside HTML tags/attributes)
  const linkProcedureReferences = (text: string): string => {
    return text.replace(
      /(<a\b[^>]*>[\s\S]*?<\/a>)|(<[^>]*>)|(\b\d{4}\/\d{4}\([A-Z]{2,5}\)\b)/g,
      (_match, anchor, htmlTag, procRef) => {
        if (anchor) return anchor;   // never nest inside an existing link
        if (htmlTag) return htmlTag; // Return HTML tags unchanged
        const eultUrl = getEultUrl(procRef);
        const eultLink = eultUrl
          ? ` <a href="${eultUrl}" target="_blank" rel="noopener noreferrer" class="message-list__link message-list__link--procedure">EULT</a>`
          : '';
        return `<a href="https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference=${procRef}" target="_blank" rel="noopener noreferrer" class="message-list__link message-list__link--procedure">${procRef}</a>${eultLink}`;
      }
    );
  };

  // MEP names are linked SERVER-SIDE by ai_service._linkify_mep_names, which
  // has the actual MEP ids from the context. There used to be a client-side
  // linkMEPNames() here that returned its input untouched -- a stub that read
  // as coverage while doing nothing. Since the backend's linkifier only ran on
  // the non-streaming path until 6 Aug 2026, MEP names were in practice linked
  // nowhere at all. Removed rather than left as a false promise.

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
      /(<a\b[^>]*>[\s\S]*?<\/a>)|(<[^>]*>)|(\b([A-Z]{4})\s+(?:committee|Committee)\b)/g,
      (match, anchor, htmlTag, _full, code) => {
        if (anchor) return anchor;
        if (htmlTag) return htmlTag;
        if (!code || !EP_COMMITTEE_CODES.has(code)) return match;
        return `<a href="https://www.europarl.europa.eu/committees/en/${code}/home" target="_blank" rel="noopener noreferrer" class="message-list__link message-list__link--committee">${code} committee</a>`;
      }
    );

    // Also match standalone committee codes in parentheses: (ENVI)
    result = result.replace(
      /(<a\b[^>]*>[\s\S]*?<\/a>)|(<[^>]*>)|(\(([A-Z]{4})\))/g,
      (match, anchor, htmlTag, _full, code) => {
        if (anchor) return anchor;
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
      legislation: t('chat.citationLegislation', 'Legislation'),
      procedure: t('chat.citationProcedure', 'Legislative Procedure'),
      mep: t('chat.citationMep', 'MEP Profile'),
      news: t('chat.citationNews', 'News Article'),
      search_result: t('chat.citationSearchResult', 'Search Result'),
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
                // Always offer smart suggestions on the last assistant turn.
                // Pre-users still pay the 3-query cap on click, but the offers
                // themselves are deterministic from the entities the backend
                // already detected for this answer.
                const showSmartSuggestions = !!isLastAssistant && !message.isStreaming;
                const smartSuggestions = showSmartSuggestions ? generateSmartSuggestions(detectedEntities, t) : [];
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
                    {message.draftedDocument && (
                      <DraftedDocumentCard drafted={message.draftedDocument} />
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
                        <span className="message-list__smart-suggestions-label">{t('chat.exploreFurther')}</span>
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

            {/* Context Indicator.
                Gated on the CITATIONS, not on contextsUsed. It used to require
                `contextsUsed > 0`, a field only the non-streaming handler ever
                set -- and the UI only calls the streaming one. So every
                streamed answer rendered its [1] [2] markers with no sources
                panel and no way to reach one, which is exactly the complaint
                that opened the 5 Aug audit ("Show me the references in this
                text: [1], [2], etc"). The count falls back to the number of
                citations when contextsUsed is absent. */}
            {message.role === 'assistant' && ((message.citations?.length ?? 0) > 0 || (message.contextsUsed ?? 0) > 0) && (
              <div className="message-list__context-indicator">
                <span className="message-list__context-icon mdi mdi-magnify"></span>
                {(() => {
                  const n = message.contextsUsed ?? message.citations?.length ?? 0;
                  return <span>{t('chat.usedDocuments', { count: n, defaultValue: `Used ${n} EU document${n === 1 ? '' : 's'}` })}</span>;
                })()}
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
                    {expandedSources.has(message.id) ? t('chat.hideSources', 'Hide sources') : t('chat.viewSources', 'View sources')}
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
                  <h4 className="message-list__citations-title">{t('chat.sources')}</h4>
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
                <span className="message-list__feedback-label">{t('chat.wasThisHelpful')}</span>
                <div className="message-list__feedback-buttons">
                  <button
                    className={`message-list__feedback-button ${
                      feedbackGiven.get(message.id) === 'positive' ? 'message-list__feedback-button--active' : ''
                    }`}
                    onClick={() => handleFeedback(message.id, 'positive', message.content)}
                    disabled={feedbackLoading.has(message.id) || feedbackGiven.has(message.id)}
                    title={t('messageList.thisWasHelpful')}
                  >
                    <Icon path={mdiMedalOutline} size={0.8} />
                  </button>
                  <button
                    className={`message-list__feedback-button ${
                      feedbackGiven.get(message.id) === 'negative' ? 'message-list__feedback-button--active' : ''
                    }`}
                    onClick={() => handleFeedback(message.id, 'negative', message.content)}
                    disabled={feedbackLoading.has(message.id) || feedbackGiven.has(message.id)}
                    title={t('messageList.thisWasNotHelpful')}
                  >
                    <Icon path={mdiEmoticonConfusedOutline} size={0.8} />
                  </button>
                  <button
                    className={`message-list__feedback-button message-list__feedback-button--report ${
                      feedbackGiven.get(message.id) === 'hallucination' ? 'message-list__feedback-button--active' : ''
                    } ${showHallucinationInput === message.id ? 'message-list__feedback-button--expanded' : ''}`}
                    onClick={() => handleHallucinationClick(message.id)}
                    disabled={feedbackLoading.has(message.id) || feedbackGiven.has(message.id)}
                    title={t('messageList.reportIncorrect')}
                  >
                    <Icon path={mdiAlertCircleOutline} size={0.8} />
                  </button>
                </div>
                {feedbackGiven.has(message.id) && (
                  <span className="message-list__feedback-thank-you">
                    {feedbackGiven.get(message.id) === 'hallucination'
                      ? t('chat.thankYouReport', 'Thank you for reporting this issue!')
                      : t('chat.thankYouFeedback', 'Thank you for your feedback!')}
                  </span>
                )}

                {/* Hallucination Report Input */}
                {showHallucinationInput === message.id && !feedbackGiven.has(message.id) && (
                  <div className="message-list__hallucination-input">
                    <div className="message-list__hallucination-header">
                      <span>{t('chat.whatWasIncorrect')}</span>
                      <button
                        className="message-list__hallucination-close"
                        onClick={() => setShowHallucinationInput(null)}
                        title={t('messageList.cancel')}
                      >
                        <Icon path={mdiClose} size={0.6} />
                      </button>
                    </div>
                    <textarea
                      className="message-list__hallucination-textarea"
                      placeholder={t('chat.feedbackPlaceholder')}
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
                      {feedbackLoading.has(message.id) ? t('chat.submitting', 'Submitting...') : t('chat.submitReport', 'Submit Report')}
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
