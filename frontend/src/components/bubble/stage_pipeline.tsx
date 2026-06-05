/**
 * Stage Pipeline Component
 *
 * Visual representation of legislative procedure stages.
 * Shows: Proposal → Committee → Plenary → Trilogue → Adopted
 */

import Icon from '@mdi/react';
import { useTranslation } from 'react-i18next';
import { mdiCheck, mdiCircle } from '@mdi/js';
import './stage_pipeline.css';

interface StagePipelineProps {
  currentStatus: string;
  compact?: boolean;
}

// Map status to pipeline stage
const getStageFromStatus = (status: string): number => {
  const statusLower = status.toLowerCase().replace(/_/g, ' ');

  // Stage 0: Proposal/Announced
  if (statusLower.includes('announced') || statusLower.includes('proposal')) {
    return 0;
  }

  // Stage 1: Committee/Tabled/Legislative Initiative
  if (
    statusLower.includes('tabled') ||
    statusLower.includes('committee') ||
    statusLower.includes('legislative initiative')
  ) {
    return 1;
  }

  // Stage 2: Plenary vote (1st reading position adopted)
  if (
    statusLower.includes('plenary') ||
    statusLower.includes('1st reading') ||
    statusLower.includes('first reading') ||
    statusLower.includes('awaiting parliament')
  ) {
    return 2;
  }

  // Stage 3: Close to adoption/Trilogue
  if (statusLower.includes('close to adoption') || statusLower.includes('trilogue')) {
    return 3;
  }

  // Stage 4: Adopted/Completed/In Force
  if (
    statusLower.includes('adopted') ||
    statusLower.includes('completed') ||
    statusLower.includes('in force')
  ) {
    return 4;
  }

  // Blocked/Withdrawn - show at current perceived stage
  if (statusLower.includes('blocked')) {
    return 1; // Usually blocked at committee stage
  }

  if (statusLower.includes('withdrawn')) {
    return -1; // Special case - withdrawn
  }

  return 0; // Default to first stage
};

const stages = [
  { id: 0, label: 'Proposal', shortLabel: 'Prop' },
  { id: 1, label: 'Committee', shortLabel: 'Comm' },
  { id: 2, label: 'Plenary', shortLabel: 'Plen' },
  { id: 3, label: 'Trilogue', shortLabel: 'Tril' },
  { id: 4, label: 'Adopted', shortLabel: 'Adpt' },
];

export const StagePipeline = ({ currentStatus, compact = false }: StagePipelineProps) => {
  const { t } = useTranslation();
  const currentStage = getStageFromStatus(currentStatus);
  const isWithdrawn = currentStatus.toLowerCase().includes('withdrawn');
  const isBlocked = currentStatus.toLowerCase().includes('blocked');

  if (isWithdrawn) {
    return (
      <div className={`stage-pipeline ${compact ? 'stage-pipeline--compact' : ''}`}>
        <div className="stage-pipeline__withdrawn">
          <span className="stage-pipeline__withdrawn-label">{t('amendmentsTab.statusWithdrawn')}</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`stage-pipeline ${compact ? 'stage-pipeline--compact' : ''}`}>
      <div className="stage-pipeline__track">
        {stages.map((stage, idx) => {
          const isCompleted = stage.id < currentStage;
          const isCurrent = stage.id === currentStage;
          const isPending = stage.id > currentStage;

          return (
            <div key={stage.id} className="stage-pipeline__stage-wrapper">
              {/* Connector line (except for first stage) */}
              {idx > 0 && (
                <div
                  className={`stage-pipeline__connector ${
                    isCompleted || isCurrent ? 'stage-pipeline__connector--active' : ''
                  }`}
                />
              )}

              {/* Stage node */}
              <div
                className={`stage-pipeline__stage ${
                  isCompleted ? 'stage-pipeline__stage--completed' : ''
                } ${isCurrent ? 'stage-pipeline__stage--current' : ''} ${
                  isPending ? 'stage-pipeline__stage--pending' : ''
                } ${isCurrent && isBlocked ? 'stage-pipeline__stage--blocked' : ''}`}
              >
                <div className="stage-pipeline__node">
                  {isCompleted ? (
                    <Icon path={mdiCheck} size={compact ? 0.5 : 0.6} />
                  ) : (
                    <Icon path={mdiCircle} size={compact ? 0.3 : 0.4} />
                  )}
                </div>
                <span className="stage-pipeline__label">
                  {compact ? stage.shortLabel : stage.label}
                </span>
                {isCurrent && isBlocked && (
                  <span className="stage-pipeline__blocked-indicator">{t('myFilesTab.blocked')}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
