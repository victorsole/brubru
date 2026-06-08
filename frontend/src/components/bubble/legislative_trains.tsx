/**
 * Legislative Trains Component
 *
 * Displays EU Commission legislative trains and their legislative files.
 * Allows users to view file details and select files for AI analysis.
 */

import { useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import Icon from '@mdi/react';
import { mdiTrain, mdiFileDocument, mdiRobotOutline, mdiCheckCircle, mdiChevronDown, mdiChevronUp, mdiStar, mdiStarOutline } from '@mdi/js';
import { useLegislativeTrains } from '../../hooks/use_legislative_trains';
import type { LegislativeFile } from '../../hooks/use_legislative_trains';
import { LegislativeFileDetail } from './legislative_file_detail';
import { MeubHeader } from './meub_header';
import { useAuth } from '../../hooks/use_auth';
import axios from 'axios';
import './legislative_trains.css';
import { useState, useMemo } from 'react';
import { useTranslation } from 'react-i18next';

const API_BASE = `${import.meta.env.VITE_API_URL || ''}/api`;

export const LegislativeTrains = () => {
  const { t } = useTranslation();
  const {
    trains,
    isLoadingTrains,
    selectedFileIds,
    isAnalyzing,
    trackedFiles,
    isTracking,
    fetchTrains,
    fetchFileDetail,
    fetchTrackedFiles,
    toggleFileSelection,
    analyzeBatch,
    clearFileSelection,
    trackFile,
    untrackFile,
  } = useLegislativeTrains();

  const [expandedTrainIds, setExpandedTrainIds] = useState<string[]>([]);
  const [searchParams] = useSearchParams();

  // PI lens: train files carry no committee/policy metadata, so we match the
  // user's Policy-Interest topic keywords against the file title.
  const [piKeywords, setPiKeywords] = useState<string[]>([]);
  const [piOnly, setPiOnly] = useState(false);

  useEffect(() => {
    // Fetch trains and tracked files on mount
    fetchTrains();
    fetchTrackedFiles();
    (async () => {
      try {
        const token = useAuth.getState().token;
        const res = await axios.get<{ keywords: string[] }>(
          `${API_BASE}/legislative-train/my-interest-keywords`,
          token ? { headers: { Authorization: `Bearer ${token}` } } : undefined,
        );
        setPiKeywords(res.data?.keywords || []);
      } catch { /* no PI lens if unavailable */ }
    })();
  }, []);

  const matchesInterests = (file: LegislativeFile): boolean => {
    if (piKeywords.length === 0) return false;
    const hay = `${file.title || ''} ${(file.policy_areas || []).join(' ')}`.toLowerCase();
    return piKeywords.some((k) => hay.includes(k));
  };

  // Per-train count of PI-matching files (for the train header badge).
  const trainInterestCounts = useMemo(() => {
    const m: Record<string, number> = {};
    for (const tr of trains) {
      m[tr.id] = (tr.files || []).filter(matchesInterests).length;
    }
    return m;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trains, piKeywords]);

  // Deep-link: ?file=<file_id> opens that file's detail card directly.
  // Used by the EFPIA brief "tracking your files" links so a click lands on
  // the file card inside My EU Bubble, not the Chat.
  useEffect(() => {
    const fileParam = searchParams.get('file');
    if (fileParam) {
      fetchFileDetail(fileParam);
    }
  }, [searchParams]);

  // Check if a file is tracked
  const isFileTracked = (fileId: string, oeilRef?: string) => {
    return trackedFiles.some(
      (tf) => tf.file_id === fileId || (oeilRef && tf.oeil_procedure_ref === oeilRef)
    );
  };

  // Handle track/untrack - supports both procedure ref and carriage ID
  const handleTrackToggle = async (e: React.MouseEvent, file: { id: string; file_id: string; oeil_procedure_ref?: string }) => {
    e.stopPropagation();
    if (isTracking) return;

    const tracked = isFileTracked(file.file_id, file.oeil_procedure_ref);
    const useCarriageId = !file.oeil_procedure_ref;
    const identifier = file.oeil_procedure_ref || file.id || file.file_id;

    try {
      if (tracked) {
        // Untrack - use procedure ref if available, otherwise carriage ID
        const trackedFile = trackedFiles.find(
          (tf) => tf.file_id === file.file_id || tf.oeil_procedure_ref === file.oeil_procedure_ref
        );
        if (trackedFile) {
          await untrackFile(trackedFile.oeil_procedure_ref || trackedFile.file_id, !trackedFile.oeil_procedure_ref);
        }
      } else {
        await trackFile(identifier, useCarriageId);
      }
    } catch (error) {
      console.error('Failed to toggle tracking:', error);
    }
  };

  const toggleTrain = (trainId: string) => {
    setExpandedTrainIds(prev =>
      prev.includes(trainId)
        ? prev.filter(id => id !== trainId)
        : [...prev, trainId]
    );
  };

  const handleFileClick = (fileId: string) => {
    fetchFileDetail(fileId);
  };

  const handleBatchAnalyze = async () => {
    if (selectedFileIds.length === 0) return;

    try {
      await analyzeBatch(selectedFileIds);
      alert(`Successfully analyzed ${selectedFileIds.length} legislative files!`);
    } catch (error) {
      alert('Failed to analyze files. Please try again.');
    }
  };

  const getStatusColor = (status: string) => {
    const statusMap: Record<string, string> = {
      'announced': '#9e9e9e',
      'legislative_initiative': '#2196f3',
      'tabled': '#ff9800',
      'close_to_adoption': '#4caf50',
      'completed': '#4caf50',
      'blocked': '#f44336',
      'withdrawn': '#757575',
    };
    return statusMap[status] || '#9e9e9e';
  };

  if (isLoadingTrains) {
    return (
      <div className="legislative-trains">
        <div className="legislative-trains__loading">
          {t('trains.loading') /* fallback to existing key */}
        </div>
      </div>
    );
  }

  return (
    <div className="legislative-trains">
      {/* Header */}
      <MeubHeader
        icon={mdiTrain}
        title={t('trains.title')}
        subtitle={t('trains.subtitle', "The Commission's full legislative programme, grouped by political priority. Browse every dossier and track the ones you care about. For just the files you already follow, see My Tracked Files.")}
        aside={(
          <div className="legislative-trains__stats">
            {piKeywords.length > 0 && (
              <button
                type="button"
                className={`legislative-trains__pi-toggle ${piOnly ? 'legislative-trains__pi-toggle--active' : ''}`}
                onClick={() => {
                  const next = !piOnly;
                  setPiOnly(next);
                  // Enabling the lens: auto-expand the trains that have matches so
                  // the user sees their PI-relevant files immediately.
                  if (next) {
                    setExpandedTrainIds(
                      trains.filter((tr) => (trainInterestCounts[tr.id] || 0) > 0).map((tr) => tr.id),
                    );
                  }
                }}
                title={t('trains.myInterestsHint')}
              >
                <Icon path={piOnly ? mdiStar : mdiStarOutline} size={0.7} />
                {t('trains.myInterests')}
              </button>
            )}
            <span>{t('trains.filesCount', { count: trains.reduce((sum, tr) => sum + tr.total_files, 0) })}</span>
          </div>
        )}
      />

      {/* Batch Analysis Bar */}
      {selectedFileIds.length > 0 && (
        <div className="legislative-trains__batch-bar">
          <div className="legislative-trains__batch-info">
            <Icon path={mdiCheckCircle} size={0.9} />
            <span>{t('trains.filesSelected', { count: selectedFileIds.length })}</span>
          </div>
          <div className="legislative-trains__batch-actions">
            <button
              className="legislative-trains__batch-btn legislative-trains__batch-btn--cancel"
              onClick={clearFileSelection}
              disabled={isAnalyzing}
            >
              {t('trains.cancel')}
            </button>
            <button
              className="legislative-trains__batch-btn legislative-trains__batch-btn--analyze"
              onClick={handleBatchAnalyze}
              disabled={isAnalyzing}
            >
              <Icon path={mdiRobotOutline} size={0.8} />
              {isAnalyzing ? t('trains.analyzing') : t('trains.aiAnalyzeSelected')}
            </button>
          </div>
        </div>
      )}

      {/* Trains List */}
      <div className="legislative-trains__list">
        {trains
          .filter(train => !piOnly || (trainInterestCounts[train.id] || 0) > 0)
          .map(train => {
          const piCount = trainInterestCounts[train.id] || 0;
          const visibleFiles = (train.files || []).filter(f => !piOnly || matchesInterests(f));
          return (
          <div key={train.id} className="legislative-trains__train">
            {/* Train Header */}
            <div
              className="legislative-trains__train-header"
              onClick={() => toggleTrain(train.id)}
            >
              <div className="legislative-trains__train-title">
                <span className="legislative-trains__train-number">
                  {t('trains.priority', { n: train.priority_number })}
                </span>
                <h3>{train.name}</h3>
              </div>
              <div className="legislative-trains__train-meta">
                {piKeywords.length > 0 && piCount > 0 && (
                  <span className="legislative-trains__train-pi" title={t('trains.matchesInterests')}>
                    <Icon path={mdiStar} size={0.6} />
                    {t('trains.inInterests', { count: piCount })}
                  </span>
                )}
                <span className="legislative-trains__train-count">
                  {t('trains.trainFilesCount', { count: train.total_files })}
                </span>
                <Icon
                  path={expandedTrainIds.includes(train.id) ? mdiChevronUp : mdiChevronDown}
                  size={0.9}
                />
              </div>
            </div>

            {/* Files List */}
            {expandedTrainIds.includes(train.id) && train.files && (
              <div className="legislative-trains__files">
                {visibleFiles.map(file => {
                  const isSelected = selectedFileIds.includes(file.file_id);
                  const isEnriched = file.ai_summary && file.ai_policy_classifications;

                  const fileIsTracked = isFileTracked(file.file_id, (file as any).oeil_procedure_ref);

                  return (
                    <div
                      key={file.id}
                      className={`legislative-trains__file ${isSelected ? 'legislative-trains__file--selected' : ''}`}
                    >
                      {/* Selection checkbox */}
                      <div className="legislative-trains__file-checkbox">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={(e) => {
                            e.stopPropagation();
                            toggleFileSelection(file.file_id);
                          }}
                        />
                      </div>

                      {/* File content - clickable */}
                      <div
                        className="legislative-trains__file-content"
                        onClick={() => handleFileClick(file.file_id)}
                      >
                        <div className="legislative-trains__file-header">
                          <Icon path={mdiFileDocument} size={0.7} />
                          <h4>{file.title}</h4>
                          {matchesInterests(file) && (
                            <span className="legislative-trains__file-pi" title={t('trains.matchesInterests')}>
                              <Icon path={mdiStar} size={0.6} />
                            </span>
                          )}
                          {isEnriched && (
                            <span className="legislative-trains__file-enriched" title={t('trains.aiEnriched')}>
                              <Icon path={mdiRobotOutline} size={0.6} />
                            </span>
                          )}
                          {/* Track button */}
                          <button
                            className={`legislative-trains__file-track ${fileIsTracked ? 'legislative-trains__file-track--active' : ''}`}
                            onClick={(e) => handleTrackToggle(e, { id: file.id, file_id: file.file_id, oeil_procedure_ref: (file as any).oeil_procedure_ref })}
                            disabled={isTracking}
                            title={fileIsTracked ? t('common.stopTracking') : t('common.trackThisFile')}
                          >
                            <Icon path={fileIsTracked ? mdiStar : mdiStarOutline} size={0.7} />
                          </button>
                        </div>

                        {file.description && (
                          <p className="legislative-trains__file-description">
                            {file.description}
                          </p>
                        )}

                        {file.ai_summary && (
                          <div className="legislative-trains__file-summary">
                            <strong>{t('trains.aiSummary')}</strong> {file.ai_summary}
                          </div>
                        )}

                        <div className="legislative-trains__file-meta">
                          <span
                            className="legislative-trains__file-status"
                            style={{ backgroundColor: getStatusColor(file.current_status) }}
                          >
                            {file.current_status.replace(/_/g, ' ')}
                          </span>

                          {file.policy_areas && file.policy_areas.length > 0 && (
                            <div className="legislative-trains__file-policies">
                              {file.policy_areas.slice(0, 2).map((policy, idx) => (
                                <span key={idx} className="legislative-trains__file-policy">
                                  {policy}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}

                {visibleFiles.length === 0 && (
                  <div className="legislative-trains__files-empty">
                    {piOnly ? t('trains.noFilesInInterests') : t('trains.noFilesForTrain')}
                  </div>
                )}
              </div>
            )}
          </div>
          );
        })}

        {trains.length === 0 && (
          <div className="legislative-trains__empty">
            <Icon path={mdiTrain} size={2} />
            <p>{t('trains.noTrains')}</p>
            <small>{t('trains.tryRefresh')}</small>
          </div>
        )}
      </div>

      {/* File Detail Modal */}
      <LegislativeFileDetail />
    </div>
  );
};
