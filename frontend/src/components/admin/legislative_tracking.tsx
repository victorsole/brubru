// frontend/src/components/admin/legislative_tracking.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import { AdminStatsCard } from './shared/admin_stats_card';
import { AdminModal } from './shared/admin_modal';
import './admin_common.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface LegislativeTrain {
  id: string;
  title: string;
  description?: string;
  priority?: string;
  file_count?: number;
  status?: string;
  updated_at: string;
}

interface LegislativeFile {
  id: string;
  train_id?: string;
  title: string;
  status: string;
  committee?: string;
  rapporteur?: string;
  next_step?: string;
  updated_at: string;
}

export const LegislativeTracking = () => {
  const { token } = useAuth();
  const [trains, setTrains] = useState<LegislativeTrain[]>([]);
  const [files, setFiles] = useState<LegislativeFile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'trains' | 'files'>('trains');
  const [selectedTrain, setSelectedTrain] = useState<LegislativeTrain | null>(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('all');

  useEffect(() => {
    if (viewMode === 'trains') {
      fetchTrains();
    } else {
      fetchFiles();
    }
  }, [viewMode]);

  const fetchTrains = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_BASE_URL}/api/legislative-train/trains`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      // Handle both array and object response formats
      if (Array.isArray(response.data)) {
        setTrains(response.data);
        setError(null);
      } else if (response.data.trains && Array.isArray(response.data.trains)) {
        // Backend returns {trains: [...], total: ..., commission_term: ...}
        setTrains(response.data.trains);
        setError(null);
      } else {
        console.warn('Trains response is not an array:', response.data);
        setTrains([]);
        setError('Invalid response format from server');
      }
    } catch (err: any) {
      console.error('Failed to fetch trains:', err);
      setError(err.response?.data?.detail || 'Failed to load legislative trains');
      setTrains([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchFiles = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_BASE_URL}/api/legislative-train/carriages`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      // Handle both array and object response formats
      if (Array.isArray(response.data)) {
        setFiles(response.data);
        setError(null);
      } else if (response.data.carriages && Array.isArray(response.data.carriages)) {
        // Backend might return {carriages: [...], total: ...}
        setFiles(response.data.carriages);
        setError(null);
      } else {
        console.warn('Files response is not an array:', response.data);
        setFiles([]);
        setError('Invalid response format from server');
      }
    } catch (err: any) {
      console.error('Failed to fetch files:', err);
      setError(err.response?.data?.detail || 'Failed to load legislative files');
      setFiles([]);
    } finally {
      setLoading(false);
    }
  };

  // Defensive checks to ensure arrays
  const filteredFiles = Array.isArray(files) ? files.filter(file => {
    if (statusFilter !== 'all' && file.status !== statusFilter) return false;
    return true;
  }) : [];

  const stats = {
    total_trains: Array.isArray(trains) ? trains.length : 0,
    total_files: Array.isArray(files) ? files.length : 0,
    in_progress: Array.isArray(files) ? files.filter(f => f.status === 'in_progress' || f.status === 'ongoing').length : 0,
    completed: Array.isArray(files) ? files.filter(f => f.status === 'completed' || f.status === 'adopted').length : 0
  };

  if (loading) {
    return <div className="admin-section__loading">Loading legislative tracking data...</div>;
  }

  return (
    <div className="admin-section">
      <div className="admin-section__header">
        <h2>Legislative Tracking Dashboard</h2>
        <div className="admin-section__actions">
          <div style={{ display: 'flex', gap: '0.5rem', background: '#f3f4f6', borderRadius: '6px', padding: '0.25rem' }}>
            <button
              className={`btn btn--small ${viewMode === 'trains' ? 'btn--primary' : 'btn--secondary'}`}
              onClick={() => setViewMode('trains')}
            >
              <span className="mdi mdi-train"></span>
              Trains
            </button>
            <button
              className={`btn btn--small ${viewMode === 'files' ? 'btn--primary' : 'btn--secondary'}`}
              onClick={() => setViewMode('files')}
            >
              <span className="mdi mdi-file-document"></span>
              Files
            </button>
          </div>
          <button
            className="btn btn--primary btn--small"
            onClick={() => viewMode === 'trains' ? fetchTrains() : fetchFiles()}
          >
            <span className="mdi mdi-refresh"></span>
            Refresh
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
        <AdminStatsCard
          icon="train"
          title="Active Trains"
          value={stats.total_trains}
          subtitle="Policy priority areas"
        />
        <AdminStatsCard
          icon="file-document-multiple"
          title="Legislative Files"
          value={stats.total_files}
          subtitle="Total tracked"
        />
        <AdminStatsCard
          icon="progress-clock"
          title="In Progress"
          value={stats.in_progress}
          subtitle="Active procedures"
          variant="warning"
        />
        <AdminStatsCard
          icon="check-circle"
          title="Completed"
          value={stats.completed}
          subtitle="Adopted legislation"
          variant="success"
        />
      </div>

      {/* Trains View */}
      {viewMode === 'trains' && (
        <div className="admin-section__table-container">
          <table className="admin-section__table">
            <thead>
              <tr>
                <th>Train Title</th>
                <th>Priority</th>
                <th>Files</th>
                <th>Status</th>
                <th>Last Updated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {trains.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: 'center', padding: '2rem' }}>
                    {error || 'No legislative trains found'}
                  </td>
                </tr>
              ) : (
                trains.map((train) => (
                  <tr key={train.id}>
                    <td>
                      <strong>{train.title}</strong>
                      {train.description && (
                        <>
                          <br />
                          <small className="admin-section__text-muted">
                            {train.description.substring(0, 100)}
                            {train.description.length > 100 ? '...' : ''}
                          </small>
                        </>
                      )}
                    </td>
                    <td>
                      {train.priority && (
                        <span className={`admin-section__badge admin-section__badge--priority-${train.priority}`}>
                          {train.priority}
                        </span>
                      )}
                    </td>
                    <td>{train.file_count || 0}</td>
                    <td>
                      <span className={`admin-section__status ${train.status === 'active' ? 'admin-section__status--active' : 'admin-section__status--inactive'}`}>
                        {train.status || 'active'}
                      </span>
                    </td>
                    <td>{new Date(train.updated_at).toLocaleDateString()}</td>
                    <td>
                      <button
                        className="btn btn--secondary btn--small"
                        onClick={() => {
                          setSelectedTrain(train);
                          setShowDetailModal(true);
                        }}
                        title="View details"
                      >
                        <span className="mdi mdi-eye"></span>
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Files View */}
      {viewMode === 'files' && (
        <>
          <div style={{ marginBottom: '1rem' }}>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="admin-section__filter"
            >
              <option value="all">All Statuses</option>
              <option value="in_progress">In Progress</option>
              <option value="ongoing">Ongoing</option>
              <option value="completed">Completed</option>
              <option value="adopted">Adopted</option>
              <option value="blocked">Blocked</option>
            </select>
          </div>
          <div className="admin-section__table-container">
            <table className="admin-section__table">
              <thead>
                <tr>
                  <th>File Title</th>
                  <th>Committee</th>
                  <th>Rapporteur</th>
                  <th>Status</th>
                  <th>Next Step</th>
                  <th>Last Updated</th>
                </tr>
              </thead>
              <tbody>
                {filteredFiles.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ textAlign: 'center', padding: '2rem' }}>
                      {error || 'No legislative files found'}
                    </td>
                  </tr>
                ) : (
                  filteredFiles.map((file) => (
                    <tr key={file.id}>
                      <td>
                        <strong>{file.title}</strong>
                      </td>
                      <td>
                        <small className="admin-section__text-muted">
                          {file.committee || 'N/A'}
                        </small>
                      </td>
                      <td>
                        <small className="admin-section__text-muted">
                          {file.rapporteur || 'N/A'}
                        </small>
                      </td>
                      <td>
                        <span className={`admin-section__badge admin-section__badge--${file.status}`}>
                          {file.status}
                        </span>
                      </td>
                      <td>
                        <small className="admin-section__text-muted">
                          {file.next_step || 'N/A'}
                        </small>
                      </td>
                      <td>{new Date(file.updated_at).toLocaleDateString()}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Train Detail Modal */}
      <AdminModal
        isOpen={showDetailModal}
        onClose={() => setShowDetailModal(false)}
        title="Legislative Train Details"
        size="large"
      >
        {selectedTrain && (
          <div style={{ display: 'grid', gap: '1.5rem' }}>
            <div>
              <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>Title</h4>
              <p style={{ margin: 0, fontWeight: 600, fontSize: '1.125rem' }}>{selectedTrain.title}</p>
            </div>
            {selectedTrain.description && (
              <div>
                <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>Description</h4>
                <p style={{ margin: 0, lineHeight: 1.6 }}>{selectedTrain.description}</p>
              </div>
            )}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <div>
                <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>Priority</h4>
                {selectedTrain.priority && (
                  <span className={`admin-section__badge admin-section__badge--priority-${selectedTrain.priority}`}>
                    {selectedTrain.priority}
                  </span>
                )}
              </div>
              <div>
                <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>File Count</h4>
                <p style={{ margin: 0 }}>{selectedTrain.file_count || 0} files</p>
              </div>
            </div>
            <div>
              <h4 style={{ margin: '0 0 0.5rem', fontSize: '0.875rem', color: '#6b7280' }}>Last Updated</h4>
              <p style={{ margin: 0 }}>{new Date(selectedTrain.updated_at).toLocaleString()}</p>
            </div>
          </div>
        )}
      </AdminModal>
    </div>
  );
};
