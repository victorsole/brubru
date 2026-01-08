// frontend/src/components/admin/feedback_management.tsx
import { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import './admin_common.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface Feedback {
  id: string;
  user_id: string | null;
  feedback_type: string;
  title: string;
  description: string;
  priority: string;
  status: string;
  category: string | null;
  affected_feature: string | null;
  created_at: string;
  updated_at: string;
}

export const FeedbackManagement = () => {
  const { token } = useAuth();
  const [feedbacks, setFeedbacks] = useState<Feedback[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    fetchFeedbacks();
  }, [page, statusFilter, typeFilter]);

  const fetchFeedbacks = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_BASE_URL}/api/feedback/admin/all`, {
        headers: { Authorization: `Bearer ${token}` },
        params: {
          page,
          page_size: 50,
          search: searchQuery || undefined,
          status_filter: statusFilter || undefined,
          type_filter: typeFilter || undefined
        }
      });
      setFeedbacks(response.data.feedback_items);
      setTotal(response.data.total);
      setError(null);
    } catch (err: any) {
      console.error('Failed to fetch feedback:', err);
      setError(err.response?.data?.detail || 'Failed to load feedback');
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = () => {
    setPage(1);
    fetchFeedbacks();
  };

  if (loading && feedbacks.length === 0) {
    return <div className="admin-section__loading">Loading feedback...</div>;
  }

  if (error && feedbacks.length === 0) {
    return (
      <div className="admin-section__error">
        <p>{error}</p>
        <button className="btn btn--primary btn--small" onClick={fetchFeedbacks}>Retry</button>
      </div>
    );
  }

  return (
    <div className="admin-section">
      <div className="admin-section__header">
        <h2>Feedback Management</h2>
        <div className="admin-section__actions">
          <input
            type="text"
            placeholder="Search feedback..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
            className="admin-section__search"
          />
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="admin-section__filter"
          >
            <option value="">All Statuses</option>
            <option value="new">New</option>
            <option value="in_review">In Review</option>
            <option value="in_progress">In Progress</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
            <option value="wont_fix">Won't Fix</option>
          </select>
          <select
            value={typeFilter}
            onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }}
            className="admin-section__filter"
          >
            <option value="">All Types</option>
            <option value="bug">Bug</option>
            <option value="feature_request">Feature Request</option>
            <option value="general">General</option>
            <option value="chat_rating">Chat Feedback</option>
            <option value="hallucination">Hallucination Report</option>
            <option value="other">Other</option>
          </select>
          <button className="btn btn--primary btn--small" onClick={handleSearch}>
            Search
          </button>
        </div>
      </div>

      <div className="admin-section__stats">
        <span>Total Feedback: <strong>{total}</strong></span>
        <span>Showing: <strong>{feedbacks.length}</strong></span>
      </div>

      <div className="admin-section__table-container">
        <table className="admin-section__table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Type</th>
              <th>Status</th>
              <th>Priority</th>
              <th>Category</th>
              <th>Feature</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {feedbacks.map((feedback) => (
              <tr key={feedback.id}>
                <td>
                  <strong>{feedback.title}</strong>
                  <br />
                  <small className="admin-section__text-muted">
                    {feedback.description.substring(0, 100)}
                    {feedback.description.length > 100 && '...'}
                  </small>
                </td>
                <td>
                  <span className="admin-section__badge admin-section__badge--type">
                    {feedback.feedback_type.replace('_', ' ')}
                  </span>
                </td>
                <td>
                  <span className={`admin-section__badge admin-section__badge--${feedback.status}`}>
                    {feedback.status.replace('_', ' ')}
                  </span>
                </td>
                <td>
                  <span className={`admin-section__badge admin-section__badge--priority-${feedback.priority}`}>
                    {feedback.priority}
                  </span>
                </td>
                <td>{feedback.category || '-'}</td>
                <td>{feedback.affected_feature || '-'}</td>
                <td>{new Date(feedback.created_at).toLocaleDateString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > 50 && (
        <div className="admin-section__pagination">
          <button
            className="btn btn--secondary btn--small"
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Previous
          </button>
          <span>Page {page} of {Math.ceil(total / 50)}</span>
          <button
            className="btn btn--secondary btn--small"
            onClick={() => setPage(p => p + 1)}
            disabled={page >= Math.ceil(total / 50)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};
