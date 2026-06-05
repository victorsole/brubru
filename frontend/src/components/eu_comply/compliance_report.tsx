// frontend/src/components/eu_comply/compliance_report.tsx
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { ComplianceAnalysis, GapFinding } from '../../pages/eu_comply_page';
import { useAuth } from '../../hooks/use_auth';
import './compliance_report.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface ComplianceReportProps {
  analysis: ComplianceAnalysis;
  onAskChatbot: (finding: GapFinding) => void;
}

type FilterType = 'all' | 'met' | 'partial' | 'gap';

export const ComplianceReport = ({ analysis, onAskChatbot }: ComplianceReportProps) => {
  const { t } = useTranslation();
  const [activeFilter, setActiveFilter] = useState<FilterType>('all');
  const [expandedFindings, setExpandedFindings] = useState<Set<number>>(new Set());

  const getStatusIcon = (status: string): string => {
    switch (status) {
      case 'met':
        return 'mdi-check-circle';
      case 'partial':
        return 'mdi-alert-circle';
      case 'gap':
        return 'mdi-close-circle';
      default:
        return 'mdi-minus-circle';
    }
  };

  const getStatusColor = (status: string): string => {
    switch (status) {
      case 'met':
        return 'status-met';
      case 'partial':
        return 'status-partial';
      case 'gap':
        return 'status-gap';
      default:
        return 'status-na';
    }
  };

  const getCriticalityColor = (criticality: string): string => {
    switch (criticality) {
      case 'critical':
        return 'criticality-critical';
      case 'important':
        return 'criticality-important';
      case 'recommended':
        return 'criticality-recommended';
      default:
        return 'criticality-recommended';
    }
  };

  const toggleExpanded = (findingId: number) => {
    const newExpanded = new Set(expandedFindings);
    if (newExpanded.has(findingId)) {
      newExpanded.delete(findingId);
    } else {
      newExpanded.add(findingId);
    }
    setExpandedFindings(newExpanded);
  };

  const getFilteredFindings = (): GapFinding[] => {
    if (activeFilter === 'all') {
      return analysis.gap_findings;
    }
    return analysis.gap_findings.filter(f => f.status === activeFilter);
  };

  const handleExportReport = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/eu-law-comply/analysis/${analysis.id}/export`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${useAuth.getState().token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ format: 'docx' }),
      });

      if (!response.ok) {
        throw new Error('Export failed');
      }

      // Download the file
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Brubru_EU_Compliance_Report_${analysis.cluster.name.replace(/\s+/g, '_')}.docx`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Export error:', error);
      alert(t('comply.report.errorExport'));
    }
  };

  const filteredFindings = getFilteredFindings();

  return (
    <div className="compliance-report">
      <div className="compliance-report__header">
        <h2>{t('comply.report.title')}</h2>
        <div className="compliance-report__cluster-name">
          {analysis.cluster.name}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="compliance-report__summary">
        <div className="compliance-report__score-card">
          <div className="compliance-report__score-value">
            {Math.round(analysis.compliance_score)}%
          </div>
          <div className="compliance-report__score-label">
            {t('comply.report.overall')}
          </div>
        </div>

        <div className="compliance-report__stats-grid">
          <div className={`compliance-report__stat-card ${getStatusColor('met')}`}>
            <span className={`mdi ${getStatusIcon('met')}`}></span>
            <div className="compliance-report__stat-value">
              {analysis.requirements_met}
            </div>
            <div className="compliance-report__stat-label">
              {t('comply.report.requirementsMet')}
            </div>
          </div>

          <div className={`compliance-report__stat-card ${getStatusColor('partial')}`}>
            <span className={`mdi ${getStatusIcon('partial')}`}></span>
            <div className="compliance-report__stat-value">
              {analysis.requirements_partial}
            </div>
            <div className="compliance-report__stat-label">
              {t('comply.report.partialCompliance')}
            </div>
          </div>

          <div className={`compliance-report__stat-card ${getStatusColor('gap')}`}>
            <span className={`mdi ${getStatusIcon('gap')}`}></span>
            <div className="compliance-report__stat-value">
              {analysis.requirements_gap}
            </div>
            <div className="compliance-report__stat-label">
              {t('comply.report.criticalGaps')}
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="compliance-report__filters">
        <button
          className={`compliance-report__filter-btn ${activeFilter === 'all' ? 'active' : ''}`}
          onClick={() => setActiveFilter('all')}
        >
          {t('comply.report.filterAll')} ({analysis.total_requirements})
        </button>
        <button
          className={`compliance-report__filter-btn ${activeFilter === 'met' ? 'active' : ''}`}
          onClick={() => setActiveFilter('met')}
        >
          <span className={`mdi ${getStatusIcon('met')}`}></span>
          {t('comply.report.filterMet')} ({analysis.requirements_met})
        </button>
        <button
          className={`compliance-report__filter-btn ${activeFilter === 'partial' ? 'active' : ''}`}
          onClick={() => setActiveFilter('partial')}
        >
          <span className={`mdi ${getStatusIcon('partial')}`}></span>
          {t('comply.report.filterPartial')} ({analysis.requirements_partial})
        </button>
        <button
          className={`compliance-report__filter-btn ${activeFilter === 'gap' ? 'active' : ''}`}
          onClick={() => setActiveFilter('gap')}
        >
          <span className={`mdi ${getStatusIcon('gap')}`}></span>
          {t('comply.report.filterGap')} ({analysis.requirements_gap})
        </button>
      </div>

      {/* Findings List */}
      <div className="compliance-report__findings">
        {filteredFindings.map(finding => (
          <div
            key={finding.id}
            className={`compliance-report__finding ${getStatusColor(finding.status)}`}
          >
            <div className="compliance-report__finding-header">
              <div className="compliance-report__finding-status">
                <span className={`mdi ${getStatusIcon(finding.status)}`}></span>
                <span className="compliance-report__finding-article">
                  {finding.article_number}
                </span>
                <span className={`compliance-report__finding-criticality ${getCriticalityColor(finding.criticality)}`}>
                  {finding.criticality === 'critical' ? t('comply.report.criticalityCritical') : finding.criticality === 'important' ? t('comply.report.criticalityImportant') : t('comply.report.criticalityRecommended')}
                </span>
              </div>
              <button
                className="compliance-report__finding-toggle"
                onClick={() => toggleExpanded(finding.id)}
              >
                <span className={`mdi ${expandedFindings.has(finding.id) ? 'mdi-chevron-up' : 'mdi-chevron-down'}`}></span>
              </button>
            </div>

            <div className="compliance-report__finding-requirement">
              {finding.requirement_text}
            </div>

            {finding.deadline_date && (
              <div className="compliance-report__finding-deadline">
                <span className="mdi mdi-calendar-clock"></span>
                {t('comply.report.deadline')} {new Date(finding.deadline_date).toLocaleDateString()}
              </div>
            )}

            {expandedFindings.has(finding.id) && (
              <div className="compliance-report__finding-details">
                {finding.evidence_text && (
                  <div className="compliance-report__evidence">
                    <h4>
                      <span className="mdi mdi-file-document-outline"></span>
                      {t('comply.report.evidenceFound')}
                    </h4>
                    <p>{finding.evidence_text}</p>
                    {finding.evidence_source && (
                      <div className="compliance-report__evidence-source">
                        {t('comply.report.evidenceSource')} {finding.evidence_source}
                      </div>
                    )}
                  </div>
                )}

                {finding.gap_description && (
                  <div className="compliance-report__gap">
                    <h4>
                      <span className="mdi mdi-alert-outline"></span>
                      {t('comply.report.gapAnalysis')}
                    </h4>
                    <p>{finding.gap_description}</p>
                  </div>
                )}

                {finding.recommendation && (
                  <div className="compliance-report__recommendation">
                    <h4>
                      <span className="mdi mdi-lightbulb-outline"></span>
                      {t('comply.report.recommendation')}
                    </h4>
                    <p>{finding.recommendation}</p>
                  </div>
                )}

                {finding.status !== 'met' && (
                  <div className="compliance-report__actions">
                    <button
                      className="compliance-report__ask-chatbot-btn"
                      onClick={() => onAskChatbot(finding)}
                    >
                      <span className="mdi mdi-chat-question-outline"></span>
                      {t('comply.report.askChatbot')}
                    </button>
                  </div>
                )}

                {finding.confidence_score && (
                  <div className="compliance-report__confidence">
                    {t('comply.report.confidence')} {Math.round(finding.confidence_score)}%
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {filteredFindings.length === 0 && (
          <div className="compliance-report__no-findings">
            <span className="mdi mdi-file-search-outline"></span>
            <p>{t('comply.report.noFindings')}</p>
          </div>
        )}
      </div>

      {/* Export Button */}
      <div className="compliance-report__footer">
        <button
          className="compliance-report__export-btn"
          onClick={handleExportReport}
        >
          <span className="mdi mdi-download"></span>
          {t('comply.report.exportReport')}
        </button>
      </div>
    </div>
  );
};
