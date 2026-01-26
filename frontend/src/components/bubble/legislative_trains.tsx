/**
 * Legislative Trains Component
 *
 * Displays EU Commission legislative trains and their legislative files.
 * Allows users to view file details and select files for AI analysis.
 */

import { useEffect } from 'react';
import Icon from '@mdi/react';
import { mdiTrain, mdiFileDocument, mdiRobotOutline, mdiCheckCircle, mdiChevronDown, mdiChevronUp, mdiStar, mdiStarOutline } from '@mdi/js';
import { useLegislativeTrains } from '../../hooks/use_legislative_trains';
import { LegislativeFileDetail } from './legislative_file_detail';
import './legislative_trains.css';
import { useState } from 'react';

export const LegislativeTrains = () => {
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

  useEffect(() => {
    // Fetch trains and tracked files on mount
    fetchTrains();
    fetchTrackedFiles();
  }, []);

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
          Loading legislative trains...
        </div>
      </div>
    );
  }

  return (
    <div className="legislative-trains">
      {/* Header */}
      <div className="legislative-trains__header">
        <div className="legislative-trains__header-left">
          <Icon path={mdiTrain} size={1.2} />
          <h2>EU Commission Legislative Trains</h2>
        </div>
        <div className="legislative-trains__stats">
          <span>{trains.reduce((sum, t) => sum + t.total_files, 0)} legislative files</span>
        </div>
      </div>

      {/* Batch Analysis Bar */}
      {selectedFileIds.length > 0 && (
        <div className="legislative-trains__batch-bar">
          <div className="legislative-trains__batch-info">
            <Icon path={mdiCheckCircle} size={0.9} />
            <span>{selectedFileIds.length} files selected</span>
          </div>
          <div className="legislative-trains__batch-actions">
            <button
              className="legislative-trains__batch-btn legislative-trains__batch-btn--cancel"
              onClick={clearFileSelection}
              disabled={isAnalyzing}
            >
              Cancel
            </button>
            <button
              className="legislative-trains__batch-btn legislative-trains__batch-btn--analyze"
              onClick={handleBatchAnalyze}
              disabled={isAnalyzing}
            >
              <Icon path={mdiRobotOutline} size={0.8} />
              {isAnalyzing ? 'Analyzing...' : 'AI Analyze Selected'}
            </button>
          </div>
        </div>
      )}

      {/* Trains List */}
      <div className="legislative-trains__list">
        {trains.map(train => (
          <div key={train.id} className="legislative-trains__train">
            {/* Train Header */}
            <div
              className="legislative-trains__train-header"
              onClick={() => toggleTrain(train.id)}
            >
              <div className="legislative-trains__train-title">
                <span className="legislative-trains__train-number">
                  Priority {train.priority_number}
                </span>
                <h3>{train.name}</h3>
              </div>
              <div className="legislative-trains__train-meta">
                <span className="legislative-trains__train-count">
                  {train.total_files} files
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
                {train.files.map(file => {
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
                          {isEnriched && (
                            <span className="legislative-trains__file-enriched" title="AI Enriched">
                              <Icon path={mdiRobotOutline} size={0.6} />
                            </span>
                          )}
                          {/* Track button */}
                          <button
                            className={`legislative-trains__file-track ${fileIsTracked ? 'legislative-trains__file-track--active' : ''}`}
                            onClick={(e) => handleTrackToggle(e, { id: file.id, file_id: file.file_id, oeil_procedure_ref: (file as any).oeil_procedure_ref })}
                            disabled={isTracking}
                            title={fileIsTracked ? 'Stop tracking' : 'Track this file'}
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
                            <strong>AI Summary:</strong> {file.ai_summary}
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

                {train.files.length === 0 && (
                  <div className="legislative-trains__files-empty">
                    No legislative files found for this train
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {trains.length === 0 && (
          <div className="legislative-trains__empty">
            <Icon path={mdiTrain} size={2} />
            <p>No legislative trains found</p>
            <small>Try refreshing the legislative trains in the admin panel</small>
          </div>
        )}
      </div>

      {/* File Detail Modal */}
      <LegislativeFileDetail />
    </div>
  );
};
