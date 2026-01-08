// frontend/src/components/eu_comply/compliance_report.tsx
import { useState } from 'react';
import type { ComplianceAnalysis, GapFinding } from '../../pages/eu_comply_page';
import './compliance_report.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface ComplianceReportProps {
  analysis: ComplianceAnalysis;
  onAskChatbot: (finding: GapFinding) => void;
}

type FilterType = 'all' | 'met' | 'partial' | 'gap';

export const ComplianceReport = ({ analysis, onAskChatbot }: ComplianceReportProps) => {
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
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
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
      alert('Failed to export report. Please try again.');
    }
  };

  const filteredFindings = getFilteredFindings();

  return (
    <div className="compliance-report">
      <div className="compliance-report__header">
        <h2>Compliance Report</h2>
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
            Overall Compliance
          </div>
        </div>

        <div className="compliance-report__stats-grid">
          <div className={`compliance-report__stat-card ${getStatusColor('met')}`}>
            <span className={`mdi ${getStatusIcon('met')}`}></span>
            <div className="compliance-report__stat-value">
              {analysis.requirements_met}
            </div>
            <div className="compliance-report__stat-label">
              Requirements Met
            </div>
          </div>

          <div className={`compliance-report__stat-card ${getStatusColor('partial')}`}>
            <span className={`mdi ${getStatusIcon('partial')}`}></span>
            <div className="compliance-report__stat-value">
              {analysis.requirements_partial}
            </div>
            <div className="compliance-report__stat-label">
              Partial Compliance
            </div>
          </div>

          <div className={`compliance-report__stat-card ${getStatusColor('gap')}`}>
            <span className={`mdi ${getStatusIcon('gap')}`}></span>
            <div className="compliance-report__stat-value">
              {analysis.requirements_gap}
            </div>
            <div className="compliance-report__stat-label">
              Critical Gaps
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
          All ({analysis.total_requirements})
        </button>
        <button
          className={`compliance-report__filter-btn ${activeFilter === 'met' ? 'active' : ''}`}
          onClick={() => setActiveFilter('met')}
        >
          <span className={`mdi ${getStatusIcon('met')}`}></span>
          Met ({analysis.requirements_met})
        </button>
        <button
          className={`compliance-report__filter-btn ${activeFilter === 'partial' ? 'active' : ''}`}
          onClick={() => setActiveFilter('partial')}
        >
          <span className={`mdi ${getStatusIcon('partial')}`}></span>
          Partial ({analysis.requirements_partial})
        </button>
        <button
          className={`compliance-report__filter-btn ${activeFilter === 'gap' ? 'active' : ''}`}
          onClick={() => setActiveFilter('gap')}
        >
          <span className={`mdi ${getStatusIcon('gap')}`}></span>
          Gaps ({analysis.requirements_gap})
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
                  {finding.criticality}
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
                Deadline: {new Date(finding.deadline_date).toLocaleDateString()}
              </div>
            )}

            {expandedFindings.has(finding.id) && (
              <div className="compliance-report__finding-details">
                {finding.evidence_text && (
                  <div className="compliance-report__evidence">
                    <h4>
                      <span className="mdi mdi-file-document-outline"></span>
                      Evidence Found
                    </h4>
                    <p>{finding.evidence_text}</p>
                    {finding.evidence_source && (
                      <div className="compliance-report__evidence-source">
                        Source: {finding.evidence_source}
                      </div>
                    )}
                  </div>
                )}

                {finding.gap_description && (
                  <div className="compliance-report__gap">
                    <h4>
                      <span className="mdi mdi-alert-outline"></span>
                      Gap Analysis
                    </h4>
                    <p>{finding.gap_description}</p>
                  </div>
                )}

                {finding.recommendation && (
                  <div className="compliance-report__recommendation">
                    <h4>
                      <span className="mdi mdi-lightbulb-outline"></span>
                      Recommendation
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
                      Ask chatbot how to fix
                    </button>
                  </div>
                )}

                {finding.confidence_score && (
                  <div className="compliance-report__confidence">
                    Confidence: {Math.round(finding.confidence_score)}%
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {filteredFindings.length === 0 && (
          <div className="compliance-report__no-findings">
            <span className="mdi mdi-file-search-outline"></span>
            <p>No findings in this category.</p>
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
          Export Full Report (DOCX)
        </button>
      </div>
    </div>
  );
};
