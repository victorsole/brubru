// frontend/src/components/tenders/tender_detail.tsx
import { useState, useEffect } from 'react';
import type { Tender, TenderMatch } from '../../pages/tenderator_page';
import { useAuth } from '../../hooks/use_auth';
import './tender_detail.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// CPV sector mapping
const CPV_SECTORS: Record<string, string> = {
  '03': 'Agriculture & Food',
  '09': 'Petroleum & Fuel',
  '14': 'Mining & Minerals',
  '15': 'Food Products',
  '18': 'Clothing & Textiles',
  '22': 'Printed Matter',
  '24': 'Chemical Products',
  '30': 'Office Equipment',
  '31': 'Electrical Equipment',
  '32': 'Radio & TV Equipment',
  '33': 'Medical Equipment',
  '34': 'Transport Equipment',
  '35': 'Security Equipment',
  '37': 'Musical Instruments',
  '38': 'Laboratory Equipment',
  '39': 'Furniture',
  '42': 'Industrial Machinery',
  '43': 'Forestry Machinery',
  '44': 'Construction Materials',
  '45': 'Construction Works',
  '48': 'Software Products',
  '50': 'Repair Services',
  '51': 'Installation Services',
  '55': 'Hotel Services',
  '60': 'Transport Services',
  '63': 'Supporting Services',
  '64': 'Postal Services',
  '65': 'Utilities',
  '66': 'Financial Services',
  '70': 'Real Estate',
  '71': 'Architecture & Engineering',
  '72': 'IT Services',
  '73': 'R&D Services',
  '75': 'Public Admin',
  '76': 'Oil & Gas Services',
  '77': 'Agriculture Services',
  '79': 'Business Services',
  '80': 'Education Services',
  '85': 'Health Services',
  '90': 'Environmental Services',
  '92': 'Recreation Services',
  '98': 'Other Services',
};

interface TenderSummary {
  en_title?: string | null;
  one_liner: string;
  what: string;
  who: string;
  value: string;
  deadline: string;
  key_requirements: string[];
  award_focus: string;
}

interface SMEAnalysis {
  sme_friendly_score: number;
  barriers: string[];
  opportunities: string[];
  recommendation: string;
  consortium_suggestion: boolean;
  score_breakdown?: Record<string, number>;
  confidence?: number;
}

// Transform backend SME response to frontend format
interface BackendSMEResponse {
  sme_suitability_score?: number;
  risk_factors?: string[];
  recommendations?: string[];
  score_breakdown?: Record<string, number>;
  confidence?: number;
}

const transformSmeResponse = (data: BackendSMEResponse): SMEAnalysis => {
  const score = data.sme_suitability_score ?? 0;
  const risks = data.risk_factors ?? [];
  const recommendations = data.recommendations ?? [];

  // Generate a recommendation string based on score
  let recommendation = '';
  if (score >= 80) {
    recommendation = 'This tender is highly suitable for SMEs. The requirements and scale align well with typical SME capabilities.';
  } else if (score >= 60) {
    recommendation = 'This tender has moderate SME suitability. Consider the barriers carefully and prepare a strong bid.';
  } else if (score >= 40) {
    recommendation = 'This tender presents some challenges for SMEs. Consortium formation or subcontracting may help.';
  } else {
    recommendation = 'This tender may be challenging for SMEs due to scale or complexity. Careful evaluation is advised.';
  }

  // Determine if consortium is suggested (score below 50 or high value)
  const consortiumSuggestion = score < 50 || risks.some(r =>
    r.toLowerCase().includes('value') ||
    r.toLowerCase().includes('turnover') ||
    r.toLowerCase().includes('capacity')
  );

  return {
    sme_friendly_score: score,
    barriers: risks,
    opportunities: recommendations,
    recommendation,
    consortium_suggestion: consortiumSuggestion,
    score_breakdown: data.score_breakdown,
    confidence: data.confidence
  };
};

interface TenderDetailProps {
  tender: Tender;
  match?: TenderMatch | null;
  onBack: () => void;
  onSave?: () => void;
  onDismiss?: () => void;
  onViewChecklist: () => void;
  onAskChatbot: (question?: string) => void;
}

interface RegulatoryRisk {
  risk_level: string;
  technical_regulations: Array<{
    notification_number: number;
    reference?: string;
    title: string;
    country: string;
    status: string;
    source_url?: string;
  }>;
  trade_barriers: Array<{
    notification_id: string;
    title: string;
    country: string;
    product_area?: string;
    source_url?: string;
  }>;
}

export const TenderDetail = ({
  tender,
  match,
  onBack,
  onSave,
  onDismiss,
  onViewChecklist,
  onAskChatbot,
}: TenderDetailProps) => {
  const { token } = useAuth();
  const [summary, setSummary] = useState<TenderSummary | null>(null);
  const [smeAnalysis, setSmeAnalysis] = useState<SMEAnalysis | null>(null);
  const [regulatoryRisk, setRegulatoryRisk] = useState<RegulatoryRisk | null>(null);
  const [isLoadingSummary, setIsLoadingSummary] = useState(false);
  const [isLoadingSme, setIsLoadingSme] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'analysis' | 'criteria'>('overview');

  // Fetch AI summary
  useEffect(() => {
    const fetchSummary = async () => {
      setIsLoadingSummary(true);
      try {
        const response = await fetch(`${API_URL}/api/tenders/${tender.id}/summary`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });

        if (response.ok) {
          const data = await response.json();
          setSummary(data);
        }
      } catch (err) {
        console.error('Failed to fetch summary:', err);
      } finally {
        setIsLoadingSummary(false);
      }
    };

    fetchSummary();
  }, [tender.id]);

  // Fetch SME analysis
  useEffect(() => {
    const fetchSmeAnalysis = async () => {
      setIsLoadingSme(true);
      try {
        const response = await fetch(`${API_URL}/api/tenders/${tender.id}/sme-score`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });

        if (response.ok) {
          const data = await response.json();
          // Transform backend response to frontend format
          setSmeAnalysis(transformSmeResponse(data));
        }
      } catch (err) {
        console.error('Failed to fetch SME analysis:', err);
      } finally {
        setIsLoadingSme(false);
      }
    };

    fetchSmeAnalysis();
  }, [tender.id, token]);

  // Fetch regulatory risk data from DG GROW
  useEffect(() => {
    if (!tender.cpv_main) return;
    const fetchRegulatoryRisk = async () => {
      try {
        const params = new URLSearchParams();
        if (tender.buyer_country) params.set('country', tender.buyer_country);
        const response = await fetch(
          `${API_URL}/api/dg-grow/regulatory-risks/${encodeURIComponent(tender.cpv_main)}${params.toString() ? '?' + params.toString() : ''}`,
          { headers: { 'Authorization': `Bearer ${token}` } },
        );
        if (response.ok) {
          const data = await response.json();
          setRegulatoryRisk(data);
        }
      } catch (err) {
        console.error('Failed to fetch regulatory risk:', err);
      }
    };
    fetchRegulatoryRisk();
  }, [tender.cpv_main, tender.buyer_country, token]);

  const getRiskBadgeClass = (level: string): string => {
    if (level === 'high') return 'tender-detail__badge--risk-high';
    if (level === 'medium') return 'tender-detail__badge--risk-medium';
    return 'tender-detail__badge--risk-low';
  };

  const getSectorName = (cpvCode: string): string => {
    if (!cpvCode) return 'Unknown';
    const prefix = cpvCode.substring(0, 2);
    return CPV_SECTORS[prefix] || 'Other';
  };

  const formatValue = (value: number | null, currency: string): string => {
    if (!value) return 'Not specified';
    return new Intl.NumberFormat('en-EU', {
      style: 'currency',
      currency: currency || 'EUR',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);
  };

  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return 'Not specified';
    return new Date(dateStr).toLocaleDateString('en-EU', {
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    });
  };

  const getDaysUntilDeadline = (deadline: string | null): number | null => {
    if (!deadline) return null;
    const now = new Date();
    const deadlineDate = new Date(deadline);
    const diffTime = deadlineDate.getTime() - now.getTime();
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  };

  // Convert publication number to TED URL
  // Handles formats:
  // - "00869174-2025" (TED SPARQL format) -> direct use
  // - "2025/S 023-000023" (OJ format) -> convert to "000023-2025"
  const getTedUrl = (pubNumber: string | null, tedUrl: string | null): string => {
    // If we have a direct TED URL, use it
    if (tedUrl) return tedUrl;

    if (!pubNumber) return 'https://ted.europa.eu';

    // Format 1: TED SPARQL format "NNNNNNNN-YYYY" (e.g., "00869174-2025")
    const tedSparqlMatch = pubNumber.match(/^(\d{8})-(\d{4})$/);
    if (tedSparqlMatch) {
      return `https://ted.europa.eu/en/notice/-/detail/${pubNumber}`;
    }

    // Format 2: OJ format "YYYY/S NNN-NNNNNN" (e.g., "2025/S 023-000023")
    const ojMatch = pubNumber.match(/(\d{4})\/S\s*\d+-(\d+)/);
    if (ojMatch) {
      const year = ojMatch[1];
      const noticeNum = ojMatch[2].padStart(8, '0');
      return `https://ted.europa.eu/en/notice/-/detail/${noticeNum}-${year}`;
    }

    // Format 3: Simple format with any digit count "N+-YYYY"
    const simpleMatch = pubNumber.match(/^(\d+)-(\d{4})$/);
    if (simpleMatch) {
      return `https://ted.europa.eu/en/notice/-/detail/${pubNumber}`;
    }

    // Fallback to search
    return `https://ted.europa.eu/en/search/result?q=${encodeURIComponent(pubNumber)}`;
  };

  const daysLeft = getDaysUntilDeadline(tender.submission_deadline);

  const getScoreClass = (score: number): string => {
    if (score >= 70) return 'tender-detail__score--high';
    if (score >= 40) return 'tender-detail__score--medium';
    return 'tender-detail__score--low';
  };

  return (
    <div className="tender-detail">
      {/* Back Button */}
      <button className="tender-detail__back" onClick={onBack}>
        <span className="mdi mdi-arrow-left"></span>
        Back to list
      </button>

      {/* Header */}
      <div className="tender-detail__header">
        <div className="tender-detail__header-main">
          <div className="tender-detail__badges">
            <span className="tender-detail__badge tender-detail__badge--country">
              {tender.buyer_country}
            </span>
            <span className="tender-detail__badge tender-detail__badge--sector">
              {getSectorName(tender.cpv_main)}
            </span>
            <span className={`tender-detail__badge tender-detail__badge--status tender-detail__badge--${tender.status}`}>
              {tender.status}
            </span>
            {regulatoryRisk && regulatoryRisk.risk_level !== 'low' && (
              <span className={`tender-detail__badge ${getRiskBadgeClass(regulatoryRisk.risk_level)}`}>
                <span className="mdi mdi-shield-alert-outline"></span>
                {regulatoryRisk.risk_level === 'high' ? 'High' : 'Medium'} Regulatory Risk
              </span>
            )}
          </div>
          {/* Show the English-translated title when summary.en_title is
              present AND differs from the raw title (i.e. the source was
              not English). The raw title is preserved below as the
              "Original" line so users can still see the source text. */}
          {summary?.en_title && summary.en_title !== tender.title ? (
            <>
              <h1 className="tender-detail__title">{summary.en_title}</h1>
              <p className="tender-detail__title-original">
                <span className="mdi mdi-translate" aria-hidden="true"></span>
                Original title: {tender.title}
              </p>
            </>
          ) : (
            <h1 className="tender-detail__title">{tender.title}</h1>
          )}
          <p className="tender-detail__publication">
            <span className="mdi mdi-identifier"></span>
            {tender.publication_number}
          </p>
        </div>

        {/* Quick Stats */}
        <div className="tender-detail__quick-stats">
          {match && match.match_score != null && (
            <div className={`tender-detail__stat tender-detail__match-score ${getScoreClass(match.match_score)}`}>
              <span className="mdi mdi-target"></span>
              <span className="tender-detail__stat-value">{Math.round(match.match_score) || 0}%</span>
              <span className="tender-detail__stat-label">Match</span>
            </div>
          )}
          {tender.sme_suitability_score != null && !isNaN(tender.sme_suitability_score) && (
            <div className="tender-detail__stat tender-detail__sme-score">
              <span className="mdi mdi-account-check"></span>
              <span className="tender-detail__stat-value">{Math.round(tender.sme_suitability_score) || 0}</span>
              <span className="tender-detail__stat-label">SME Score</span>
            </div>
          )}
        </div>
      </div>

      {/* Key Info Grid */}
      <div className="tender-detail__key-info">
        <div className="tender-detail__info-card">
          <span className="mdi mdi-domain"></span>
          <div>
            <span className="tender-detail__info-label">Contracting Authority</span>
            <span className="tender-detail__info-value">{tender.buyer_name}</span>
          </div>
        </div>
        <div className="tender-detail__info-card">
          <span className="mdi mdi-currency-eur"></span>
          <div>
            <span className="tender-detail__info-label">Estimated Value</span>
            <span className="tender-detail__info-value">{formatValue(tender.estimated_value, tender.currency)}</span>
          </div>
        </div>
        <div className={`tender-detail__info-card ${daysLeft !== null && daysLeft <= 14 ? 'tender-detail__info-card--urgent' : ''}`}>
          <span className="mdi mdi-calendar-clock"></span>
          <div>
            <span className="tender-detail__info-label">Submission Deadline</span>
            <span className="tender-detail__info-value">
              {formatDate(tender.submission_deadline)}
              {daysLeft !== null && (
                <span className="tender-detail__days-left">
                  ({daysLeft > 0 ? `${daysLeft} days left` : daysLeft === 0 ? 'Due today!' : 'Expired'})
                </span>
              )}
            </span>
          </div>
        </div>
        <div className="tender-detail__info-card">
          <span className="mdi mdi-file-document"></span>
          <div>
            <span className="tender-detail__info-label">Procedure Type</span>
            <span className="tender-detail__info-value">{tender.procedure_type || 'Not specified'}</span>
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="tender-detail__actions">
        {onSave && (
          <button
            className={`tender-detail__action-btn ${match?.is_saved ? 'tender-detail__action-btn--saved' : ''}`}
            onClick={onSave}
          >
            <span className={`mdi ${match?.is_saved ? 'mdi-bookmark' : 'mdi-bookmark-outline'}`}></span>
            {match?.is_saved ? 'Saved' : 'Save'}
          </button>
        )}
        <button className="tender-detail__action-btn tender-detail__action-btn--primary" onClick={onViewChecklist}>
          <span className="mdi mdi-clipboard-check"></span>
          View Checklist
        </button>
        <button className="tender-detail__action-btn" onClick={() => onAskChatbot()}>
          <span className="mdi mdi-chat-question"></span>
          Ask AI
        </button>
        <a
          href={getTedUrl(tender.publication_number, tender.ted_url ?? null)}
          target="_blank"
          rel="noopener noreferrer"
          className="tender-detail__action-btn"
        >
          <span className="mdi mdi-open-in-new"></span>
          View on TED
        </a>
        {onDismiss && (
          <button className="tender-detail__action-btn tender-detail__action-btn--dismiss" onClick={onDismiss}>
            <span className="mdi mdi-eye-off"></span>
            Dismiss
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="tender-detail__tabs">
        <button
          className={`tender-detail__tab ${activeTab === 'overview' ? 'tender-detail__tab--active' : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          Overview
        </button>
        <button
          className={`tender-detail__tab ${activeTab === 'analysis' ? 'tender-detail__tab--active' : ''}`}
          onClick={() => setActiveTab('analysis')}
        >
          SME Analysis
        </button>
        <button
          className={`tender-detail__tab ${activeTab === 'criteria' ? 'tender-detail__tab--active' : ''}`}
          onClick={() => setActiveTab('criteria')}
        >
          Award Criteria
        </button>
      </div>

      {/* Tab Content */}
      <div className="tender-detail__content">
        {activeTab === 'overview' && (
          <div className="tender-detail__overview">
            {/* AI Summary */}
            <div className="tender-detail__section">
              <h3><span className="mdi mdi-robot"></span> AI Summary</h3>
              {isLoadingSummary ? (
                <div className="tender-detail__loading">
                  <span className="mdi mdi-loading mdi-spin"></span>
                  Generating summary...
                </div>
              ) : summary ? (
                <div className="tender-detail__summary">
                  <p className="tender-detail__one-liner">{summary.one_liner}</p>
                  <div className="tender-detail__summary-grid">
                    <div className="tender-detail__summary-item">
                      <span className="tender-detail__summary-label" title="A short English summary of what is being procured: the goods, services or works the buyer wants to purchase. Generated by Brubru's AI from the tender notice, translated from the source language if needed.">What</span>
                      <span className="tender-detail__summary-value">{summary.what}</span>
                    </div>
                    <div className="tender-detail__summary-item">
                      <span className="tender-detail__summary-label" title="The contracting authority: the public-sector body that will sign the contract and pay you. National ministry, municipality, EU institution, hospital, university, etc.">Who</span>
                      <span className="tender-detail__summary-value">{summary.who}</span>
                    </div>
                    <div className="tender-detail__summary-item">
                      <span className="tender-detail__summary-label" title="Estimated contract value as published by the buyer. Often a ceiling rather than a firm budget; the awarded value may be lower after evaluation.">Value</span>
                      <span className="tender-detail__summary-value">{summary.value}</span>
                    </div>
                    <div className="tender-detail__summary-item">
                      <span className="tender-detail__summary-label" title="Last moment to submit your bid. Almost always before midday Brussels time on the stated day. Late bids are excluded automatically.">Deadline</span>
                      <span className="tender-detail__summary-value">{summary.deadline}</span>
                    </div>
                  </div>
                  {(() => {
                    const reqs = (summary.key_requirements || [])
                      .map((r) => (typeof r === 'string' ? r.trim() : ''))
                      .filter((r) => r && r !== 'requirement 1' && r !== 'requirement 2' && r !== 'requirement 3');
                    return reqs.length > 0 ? (
                      <div className="tender-detail__requirements">
                        <span className="tender-detail__summary-label" title="The mandatory selection criteria you must meet to be eligible: minimum turnover, references for similar contracts, professional qualifications, technical capacity. If you cannot demonstrate these, the bid is rejected before evaluation.">Key Requirements</span>
                        <ul>
                          {reqs.map((req, idx) => (
                            <li key={idx}>{req}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null;
                  })()}
                  {summary.award_focus && (
                    <div className="tender-detail__award-focus">
                      <span className="mdi mdi-lightbulb"></span>
                      {summary.award_focus}
                    </div>
                  )}
                </div>
              ) : (
                <p className="tender-detail__no-data">Summary not available</p>
              )}
            </div>

            {/* Description */}
            {tender.description && (
              <div className="tender-detail__section">
                <h3><span className="mdi mdi-text"></span> Description</h3>
                <p className="tender-detail__description">{tender.description}</p>
              </div>
            )}

            {/* CPV Codes — hide entirely when neither main nor secondary
                codes are present (TED parser sometimes returns notices
                without CPV; an empty section reads as broken). */}
            {(tender.cpv_main || (tender.cpv_codes && tender.cpv_codes.length > 0)) && (
              <div className="tender-detail__section">
                <h3 title="Common Procurement Vocabulary: an 8-digit EU classification code that every TED tender carries. Divisions (first 2 digits) cover 45 sectors from agriculture (03) to IT services (72) to architectural and engineering (71). Buyers use CPV to indicate what they are buying; bidders use it to find relevant calls."><span className="mdi mdi-tag-multiple"></span> CPV Codes <span className="mdi mdi-help-circle-outline" style={{opacity:0.4, fontSize:'0.85em', marginLeft:'0.3rem', verticalAlign:'middle'}} aria-hidden="true"></span></h3>
                <div className="tender-detail__cpv-list">
                  {tender.cpv_main && (
                    <div className="tender-detail__cpv-item tender-detail__cpv-item--main">
                      <span className="tender-detail__cpv-code">{tender.cpv_main}</span>
                      <span className="tender-detail__cpv-name">{getSectorName(tender.cpv_main)} (Main)</span>
                    </div>
                  )}
                  {tender.cpv_codes && tender.cpv_codes.filter(c => c !== tender.cpv_main).map((code, idx) => (
                    <div key={idx} className="tender-detail__cpv-item">
                      <span className="tender-detail__cpv-code">{code}</span>
                      <span className="tender-detail__cpv-name">{getSectorName(code)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* DG GROW Regulatory Alerts */}
            {regulatoryRisk && (regulatoryRisk.technical_regulations.length > 0 || regulatoryRisk.trade_barriers.length > 0) && (
              <div className="tender-detail__section">
                <h3>
                  <span className="mdi mdi-shield-alert"></span>
                  Regulatory Alerts
                  <span className={`tender-detail__risk-badge tender-detail__risk-badge--${regulatoryRisk.risk_level}`}>
                    {regulatoryRisk.risk_level.toUpperCase()}
                  </span>
                </h3>

                {regulatoryRisk.technical_regulations.length > 0 && (
                  <div className="tender-detail__reg-group">
                    <h4 className="tender-detail__reg-group-title">
                      <span className="mdi mdi-file-document-alert"></span>
                      TRIS Technical Regulations ({regulatoryRisk.technical_regulations.length})
                    </h4>
                    <div className="tender-detail__reg-list">
                      {regulatoryRisk.technical_regulations.map((reg, idx) => (
                        <div key={idx} className="tender-detail__reg-item">
                          <div className="tender-detail__reg-header">
                            <span className="tender-detail__reg-id">{reg.reference || `#${reg.notification_number}`}</span>
                            <span className={`tender-detail__reg-status tender-detail__reg-status--${reg.status}`}>
                              {reg.status}
                            </span>
                            <span className="tender-detail__reg-country">{reg.country}</span>
                          </div>
                          <p className="tender-detail__reg-title">{reg.title || 'Untitled regulation'}</p>
                          {reg.source_url && (
                            <a href={reg.source_url} target="_blank" rel="noopener noreferrer" className="tender-detail__reg-link">
                              View on TRIS <span className="mdi mdi-open-in-new"></span>
                            </a>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {regulatoryRisk.trade_barriers.length > 0 && (
                  <div className="tender-detail__reg-group">
                    <h4 className="tender-detail__reg-group-title">
                      <span className="mdi mdi-earth-off"></span>
                      TBT Trade Barriers ({regulatoryRisk.trade_barriers.length})
                    </h4>
                    <div className="tender-detail__reg-list">
                      {regulatoryRisk.trade_barriers.map((tbt, idx) => (
                        <div key={idx} className="tender-detail__reg-item">
                          <div className="tender-detail__reg-header">
                            <span className="tender-detail__reg-id">{tbt.notification_id}</span>
                            <span className="tender-detail__reg-country">{tbt.country}</span>
                            {tbt.product_area && (
                              <span className="tender-detail__reg-sector">{tbt.product_area}</span>
                            )}
                          </div>
                          <p className="tender-detail__reg-title">{tbt.title || 'Trade barrier notification'}</p>
                          {tbt.source_url && (
                            <a href={tbt.source_url} target="_blank" rel="noopener noreferrer" className="tender-detail__reg-link">
                              View details <span className="mdi mdi-open-in-new"></span>
                            </a>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <button
                  className="tender-detail__ask-btn"
                  onClick={() => onAskChatbot(`Analyse the regulatory risks for this tender. There are ${regulatoryRisk.technical_regulations.length} TRIS technical regulations and ${regulatoryRisk.trade_barriers.length} TBT trade barriers in this sector. What should I be aware of?`)}
                >
                  <span className="mdi mdi-chat-question"></span>
                  Ask AI about regulatory risks
                </button>
              </div>
            )}
          </div>
        )}

        {activeTab === 'analysis' && (
          <div className="tender-detail__analysis">
            {isLoadingSme ? (
              <div className="tender-detail__loading">
                <span className="mdi mdi-loading mdi-spin"></span>
                Analyzing SME suitability...
              </div>
            ) : smeAnalysis ? (
              <>
                {/* SME Score Card */}
                <div className="tender-detail__sme-card">
                  <div className={`tender-detail__sme-score-circle ${getScoreClass(smeAnalysis.sme_friendly_score ?? 0)}`}>
                    <span className="tender-detail__sme-score-value">{Math.round(smeAnalysis.sme_friendly_score ?? 0) || 0}</span>
                    <span className="tender-detail__sme-score-label">SME Score</span>
                  </div>
                  <p className="tender-detail__sme-recommendation">{smeAnalysis.recommendation}</p>
                  {smeAnalysis.consortium_suggestion && (
                    <div className="tender-detail__consortium-tip">
                      <span className="mdi mdi-account-group"></span>
                      Consider forming a consortium for this tender
                    </div>
                  )}
                </div>

                {/* Score Breakdown */}
                {smeAnalysis.score_breakdown && Object.keys(smeAnalysis.score_breakdown).length > 0 && (
                  <div className="tender-detail__section">
                    <h3><span className="mdi mdi-chart-bar"></span> Score Breakdown</h3>
                    <div className="tender-detail__score-breakdown">
                      {Object.entries(smeAnalysis.score_breakdown).map(([category, score]) => (
                        <div key={category} className="tender-detail__breakdown-item">
                          <div className="tender-detail__breakdown-header">
                            <span className="tender-detail__breakdown-category">{category}</span>
                            <span className="tender-detail__breakdown-score">{score}/100</span>
                          </div>
                          <div className="tender-detail__breakdown-bar">
                            <div
                              className={`tender-detail__breakdown-fill ${score >= 70 ? 'high' : score >= 40 ? 'medium' : 'low'}`}
                              style={{ width: `${score}%` }}
                            ></div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Barriers */}
                {smeAnalysis.barriers && smeAnalysis.barriers.length > 0 && (
                  <div className="tender-detail__section">
                    <h3><span className="mdi mdi-alert-circle-outline"></span> Potential Barriers</h3>
                    <ul className="tender-detail__barrier-list">
                      {smeAnalysis.barriers.map((barrier, idx) => (
                        <li key={idx}>{barrier}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Opportunities */}
                {smeAnalysis.opportunities && smeAnalysis.opportunities.length > 0 && (
                  <div className="tender-detail__section">
                    <h3><span className="mdi mdi-check-circle-outline"></span> Opportunities</h3>
                    <ul className="tender-detail__opportunity-list">
                      {smeAnalysis.opportunities.map((opp, idx) => (
                        <li key={idx}>{opp}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <button
                  className="tender-detail__ask-btn"
                  onClick={() => onAskChatbot('Analyze the SME suitability of this tender in more detail. What are the specific challenges and how can I overcome them?')}
                >
                  <span className="mdi mdi-chat-question"></span>
                  Ask AI for more details
                </button>
              </>
            ) : (
              <p className="tender-detail__no-data">SME analysis not available</p>
            )}
          </div>
        )}

        {activeTab === 'criteria' && (
          <div className="tender-detail__criteria">
            {(() => {
              // Handle both array format (new) and object format (legacy)
              const criteriaArray = Array.isArray(tender.award_criteria)
                ? tender.award_criteria
                : tender.award_criteria && typeof tender.award_criteria === 'object' && Object.keys(tender.award_criteria).length > 0
                  ? Object.entries(tender.award_criteria).map(([type, weight]) => ({ type, weight: weight as number }))
                  : null;

              if (!criteriaArray || criteriaArray.length === 0) {
                return <p className="tender-detail__no-data">Award criteria not available</p>;
              }

              // Calculate aggregate weights by type
              const typeWeights: Record<string, number> = {};
              criteriaArray.forEach((c: { type?: string; weight?: number }) => {
                const type = (c.type || 'other').toLowerCase();
                typeWeights[type] = (typeWeights[type] || 0) + (c.weight || 0);
              });
              const qualityWeight = typeWeights['quality'] || 0;
              const priceWeight = typeWeights['price'] || 0;

              return (
                <>
                  <div className="tender-detail__criteria-chart">
                    {criteriaArray.map((criterion: { type?: string; name?: string; description?: string; weight?: number }, idx: number) => {
                      const weight = criterion.weight || 0;
                      const label = criterion.name || criterion.description || criterion.type || `Criterion ${idx + 1}`;
                      const displayLabel = label.length > 80 ? `${label.substring(0, 80)}...` : label;

                      return (
                        <div key={idx} className="tender-detail__criterion">
                          <div className="tender-detail__criterion-header">
                            <span className="tender-detail__criterion-type">{criterion.type || 'other'}</span>
                            <span className="tender-detail__criterion-name" title={label}>{displayLabel}</span>
                            {weight > 0 && <span className="tender-detail__criterion-weight">{weight}%</span>}
                          </div>
                          {weight > 0 && (
                            <div className="tender-detail__criterion-bar">
                              <div
                                className="tender-detail__criterion-fill"
                                style={{ width: `${Math.min(weight, 100)}%` }}
                              ></div>
                            </div>
                          )}
                          {criterion.description && criterion.description !== criterion.name && (
                            <p className="tender-detail__criterion-description">{criterion.description.substring(0, 200)}{criterion.description.length > 200 ? '...' : ''}</p>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  <div className="tender-detail__criteria-advice">
                    <h4><span className="mdi mdi-lightbulb-on"></span> Bidding Strategy</h4>
                    {qualityWeight > 0 && priceWeight > 0 ? (
                      qualityWeight > priceWeight ? (
                        <p>
                          This tender prioritizes <strong>quality</strong> ({qualityWeight}%)
                          over price ({priceWeight}%). Focus your bid on technical
                          excellence, methodology, and team expertise.
                        </p>
                      ) : (
                        <p>
                          This tender prioritizes <strong>price</strong> ({priceWeight}%)
                          over quality ({qualityWeight}%). Ensure competitive pricing
                          while meeting minimum quality thresholds.
                        </p>
                      )
                    ) : (
                      <p>
                        Review the award criteria above to determine your bidding strategy.
                        {tender.award_criteria_type && (
                          <> Primary criterion type: <strong>{tender.award_criteria_type}</strong>.</>
                        )}
                      </p>
                    )}
                  </div>

                  <button
                    className="tender-detail__ask-btn"
                    onClick={() => onAskChatbot(`Explain the award criteria for this tender and provide detailed advice on how to structure a competitive bid. The criteria are: ${criteriaArray.map((c: { type?: string; name?: string; weight?: number }) => `${c.type || 'other'}: ${c.name || 'unnamed'} (${c.weight || 0}%)`).join(', ')}.`)}
                  >
                    <span className="mdi mdi-chat-question"></span>
                    Get detailed bidding advice
                  </button>
                </>
              );
            })()}
          </div>
        )}
      </div>

      {/* Match Reasons */}
      {match?.match_reasons && match.match_reasons.length > 0 && (
        <div className="tender-detail__match-reasons">
          <h3><span className="mdi mdi-target"></span> Why This Matched Your Profile</h3>
          <div className="tender-detail__reason-list">
            {match.match_reasons.map((reason, idx) => (
              <div key={idx} className="tender-detail__reason-item">
                <span className="mdi mdi-check-circle"></span>
                {reason}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
