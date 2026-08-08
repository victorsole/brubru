// frontend/src/components/eu_comply/compliance_report.tsx
import { useTranslation } from 'react-i18next';
import type { ComplianceAnalysis, GapFinding } from '../../pages/eu_comply_page';
import { useAuth } from '../../hooks/use_auth';
import { FindingsTable } from './findings_table';
import './compliance_report.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface ComplianceReportProps {
  analysis: ComplianceAnalysis;
  onAskChatbot: (finding: GapFinding) => void;
}

export const ComplianceReport = ({ analysis, onAskChatbot }: ComplianceReportProps) => {
  const { t } = useTranslation();

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

      {/* Tabular cited review. Replaces the per-finding accordion: each
          obligation is one row, the verdict is readable without expanding
          anything, and the evidence column says explicitly when nothing in the
          uploaded documents addressed the requirement. */}
      <FindingsTable
        findings={analysis.gap_findings || []}
        onAskChatbot={onAskChatbot}
      />

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
