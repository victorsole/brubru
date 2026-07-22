// frontend/src/components/admin/tenderator_management.tsx
import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { useAuth } from '../../hooks/use_auth';
import { AdminStatsCard } from './shared/admin_stats_card';
import './tenderator_management.css';
import { uiDateLocale } from '../../i18n/config';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Types
interface TenderStats {
  total_tenders: number;
  open_tenders: number;
  closed_tenders: number;
  awarded_tenders: number;
  tenders_this_week: number;
  tenders_by_country: Record<string, number>;
  tenders_by_sector: Record<string, number>;
  average_value: number | null;
  total_profiles: number;
  active_profiles: number;
  total_matches: number;
  saved_matches: number;
  fetch_jobs_count: number;
  last_fetch_at: string | null;
}

interface TenderSummary {
  id: number;
  publication_number: string;
  title: string;
  official_name: string | null;
  buyer_country: string | null;
  cpv_main: string | null;
  estimated_value: number | null;
  submission_deadline: string | null;
  status: string;
  sme_suitability_score: number | null;
  source: string | null;
  created_at: string | null;
  match_count: number;
}

interface FetchJob {
  id: number;
  job_id: string;
  job_type: string;
  source: string;
  status: string;
  tenders_found: number;
  tenders_new: number;
  tenders_updated: number;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
}

interface ProfileSummary {
  id: number;
  user_email: string;
  user_name: string | null;
  company_name: string | null;
  company_size: string | null;
  countries_count: number;
  cpv_count: number;
  match_count: number;
  is_active: boolean;
  created_at: string;
}

type TabType = 'dashboard' | 'tenders' | 'profiles' | 'matches' | 'fetch' | 'settings';

// CPV Sector mapping
const CPV_SECTORS: Record<string, string> = {
  '03': 'Agriculture',
  '09': 'Energy',
  '14': 'Mining',
  '15': 'Food',
  '18': 'Clothing',
  '22': 'Printing',
  '30': 'Office Equipment',
  '31': 'Electrical',
  '32': 'Radio/TV',
  '33': 'Medical',
  '34': 'Transport',
  '35': 'Security',
  '37': 'Musical',
  '38': 'Laboratory',
  '39': 'Furniture',
  '42': 'Industrial',
  '43': 'Mining Equipment',
  '44': 'Construction',
  '45': 'Construction Works',
  '48': 'Software',
  '50': 'Repair/Maintenance',
  '51': 'Installation',
  '55': 'Hotels',
  '60': 'Transport Services',
  '63': 'Logistics',
  '64': 'Postal',
  '65': 'Utilities',
  '66': 'Finance',
  '70': 'Real Estate',
  '71': 'Engineering',
  '72': 'IT Services',
  '73': 'Research',
  '75': 'Public Admin',
  '76': 'Oil/Gas',
  '77': 'Agriculture Services',
  '79': 'Business Services',
  '80': 'Education',
  '85': 'Healthcare',
  '90': 'Environmental',
  '92': 'Recreation',
  '98': 'Other Services'
};

export const TenderatorManagement = () => {
  const { token } = useAuth();
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');
  const [stats, setStats] = useState<TenderStats | null>(null);
  const [tenders, setTenders] = useState<TenderSummary[]>([]);
  const [profiles, setProfiles] = useState<ProfileSummary[]>([]);
  const [fetchJobs, setFetchJobs] = useState<FetchJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [countryFilter, setCountryFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  // Fetch configuration
  const [fetchDays, setFetchDays] = useState(7);
  const [fetchCountries, setFetchCountries] = useState('');
  const [fetchMaxValue, setFetchMaxValue] = useState(5000000);

  const headers = { Authorization: `Bearer ${token}` };

  // Fetch statistics
  const fetchStats = useCallback(async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/admin/tenders/stats`, { headers });
      setStats(response.data);
    } catch (err: any) {
      console.error('Failed to fetch stats:', err);
      setError(err.response?.data?.detail || 'Failed to load statistics');
    }
  }, [token]);

  // Fetch tenders list
  const fetchTenders = useCallback(async () => {
    try {
      const params: Record<string, any> = {
        page: currentPage,
        page_size: 20
      };
      if (searchQuery) params.search = searchQuery;
      if (countryFilter) params.country = countryFilter;
      if (statusFilter) params.status_filter = statusFilter;

      const response = await axios.get(`${API_BASE_URL}/api/admin/tenders`, {
        headers,
        params
      });
      setTenders(response.data.tenders);
      setTotalPages(response.data.total_pages);
    } catch (err: any) {
      console.error('Failed to fetch tenders:', err);
    }
  }, [token, currentPage, searchQuery, countryFilter, statusFilter]);

  // Fetch profiles
  const fetchProfiles = useCallback(async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/admin/tenders/profiles`, {
        headers,
        params: { page: 1, page_size: 50 }
      });
      setProfiles(response.data.profiles);
    } catch (err: any) {
      console.error('Failed to fetch profiles:', err);
    }
  }, [token]);

  // Fetch job logs
  const fetchJobLogs = useCallback(async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/admin/tenders/fetch-logs`, {
        headers,
        params: { page: 1, page_size: 20 }
      });
      setFetchJobs(response.data.jobs);
    } catch (err: any) {
      console.error('Failed to fetch job logs:', err);
    }
  }, [token]);

  // Initial load
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await fetchStats();
      setLoading(false);
    };
    loadData();
  }, [fetchStats]);

  // Load tab-specific data
  useEffect(() => {
    if (activeTab === 'tenders') fetchTenders();
    if (activeTab === 'profiles') fetchProfiles();
    if (activeTab === 'fetch') fetchJobLogs();
  }, [activeTab, fetchTenders, fetchProfiles, fetchJobLogs]);

  // Actions
  const handleTriggerFetch = async (source: 'ted_api' | 'ted_sparql') => {
    setActionLoading(true);
    try {
      const endpoint = source === 'ted_api'
        ? `${API_BASE_URL}/api/admin/tenders/fetch`
        : `${API_BASE_URL}/api/admin/tenders/fetch-sparql`;

      const params: any = {
        days_back: fetchDays,
        max_value: fetchMaxValue,
        source
      };
      if (fetchCountries) {
        params.countries = fetchCountries.split(',').map(c => c.trim());
      }

      await axios.post(endpoint, params, { headers });
      alert(`Fetch job started successfully (${source})`);
      await fetchJobLogs();
      await fetchStats();
    } catch (err: any) {
      alert(`Failed to start fetch: ${err.response?.data?.detail || err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleRunMatching = async () => {
    setActionLoading(true);
    try {
      const response = await axios.post(
        `${API_BASE_URL}/api/admin/tenders/run-matching`,
        {},
        { headers }
      );
      alert(`Matching completed: ${response.data.matches_created} new matches`);
      await fetchStats();
    } catch (err: any) {
      alert(`Matching failed: ${err.response?.data?.detail || err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleSendNotifications = async (type: string) => {
    setActionLoading(true);
    try {
      await axios.post(
        `${API_BASE_URL}/api/admin/tenders/send-notifications`,
        {},
        { headers, params: { notification_type: type } }
      );
      alert('Notifications sent successfully');
    } catch (err: any) {
      alert(`Failed to send notifications: ${err.response?.data?.detail || err.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeleteTender = async (id: number) => {
    if (!confirm('Are you sure you want to delete this tender?')) return;

    try {
      await axios.delete(`${API_BASE_URL}/api/admin/tenders/${id}`, { headers });
      await fetchTenders();
      await fetchStats();
    } catch (err: any) {
      alert(`Failed to delete tender: ${err.response?.data?.detail || err.message}`);
    }
  };

  const handleExport = async (format: 'csv' | 'json') => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/admin/tenders/export`, {
        headers,
        params: { format, status_filter: statusFilter, country: countryFilter }
      });

      if (format === 'csv') {
        const blob = new Blob([response.data.csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `tenders_export_${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
      } else {
        const blob = new Blob([JSON.stringify(response.data.tenders, null, 2)], { type: 'application/json' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `tenders_export_${new Date().toISOString().split('T')[0]}.json`;
        a.click();
      }
    } catch (err: any) {
      alert(`Export failed: ${err.response?.data?.detail || err.message}`);
    }
  };

  // Format helpers
  const formatValue = (value: number | null) => {
    if (value === null) return '-';
    return `€${value.toLocaleString()}`;
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString(uiDateLocale(), {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  const getSectorName = (cpv: string | null) => {
    if (!cpv) return 'Unknown';
    const prefix = cpv.substring(0, 2);
    return CPV_SECTORS[prefix] || prefix;
  };

  if (loading) {
    return (
      <div className="tenderator-mgmt">
        <div className="tenderator-mgmt__loading">Loading Tenderator data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="tenderator-mgmt">
        <div className="tenderator-mgmt__error">
          <p>{error}</p>
          <button className="btn btn--primary" onClick={fetchStats}>Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="tenderator-mgmt">
      {/* Header */}
      <div className="tenderator-mgmt__header">
        <h2>
          <span className="mdi mdi-briefcase-search"></span>
          Tenderator Management
        </h2>
        <div className="tenderator-mgmt__actions">
          <button
            className="btn btn--secondary btn--small"
            onClick={() => { fetchStats(); fetchTenders(); }}
          >
            <span className="mdi mdi-refresh"></span> Refresh
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="tenderator-mgmt__tabs">
        {(['dashboard', 'tenders', 'profiles', 'fetch', 'settings'] as TabType[]).map(tab => (
          <button
            key={tab}
            className={`tenderator-mgmt__tab ${activeTab === tab ? 'tenderator-mgmt__tab--active' : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Dashboard Tab */}
      {activeTab === 'dashboard' && stats && (
        <div className="tenderator-mgmt__dashboard">
          {/* Stats Grid */}
          <div className="tenderator-mgmt__stats-grid">
            <AdminStatsCard
              icon="briefcase"
              title="Total Tenders"
              value={stats.total_tenders}
              subtitle={`${stats.tenders_this_week} added this week`}
            />
            <AdminStatsCard
              icon="briefcase-check"
              title="Open Tenders"
              value={stats.open_tenders}
              subtitle={`${stats.closed_tenders} closed, ${stats.awarded_tenders} awarded`}
              variant="success"
            />
            <AdminStatsCard
              icon="account-group"
              title="Active Profiles"
              value={stats.active_profiles}
              subtitle={`${stats.total_profiles} total profiles`}
            />
            <AdminStatsCard
              icon="link-variant"
              title="Total Matches"
              value={stats.total_matches}
              subtitle={`${stats.saved_matches} saved by users`}
            />
            <AdminStatsCard
              icon="currency-eur"
              title="Average Value"
              value={stats.average_value ? formatValue(stats.average_value) : 'N/A'}
              subtitle="Across all tenders"
            />
            <AdminStatsCard
              icon="cloud-download"
              title="Fetch Jobs"
              value={stats.fetch_jobs_count}
              subtitle={stats.last_fetch_at ? `Last: ${formatDate(stats.last_fetch_at)}` : 'Never'}
            />
          </div>

          {/* Charts Section */}
          <div className="tenderator-mgmt__charts">
            <div className="tenderator-mgmt__chart-card">
              <h3>Tenders by Country</h3>
              <div className="tenderator-mgmt__chart-list">
                {Object.entries(stats.tenders_by_country)
                  .sort((a, b) => b[1] - a[1])
                  .slice(0, 10)
                  .map(([country, count]) => (
                    <div key={country} className="tenderator-mgmt__chart-item">
                      <span className="tenderator-mgmt__chart-label">{country}</span>
                      <div className="tenderator-mgmt__chart-bar-container">
                        <div
                          className="tenderator-mgmt__chart-bar"
                          style={{ width: `${(count / Math.max(...Object.values(stats.tenders_by_country))) * 100}%` }}
                        />
                      </div>
                      <span className="tenderator-mgmt__chart-value">{count}</span>
                    </div>
                  ))}
              </div>
            </div>

            <div className="tenderator-mgmt__chart-card">
              <h3>Tenders by Sector</h3>
              <div className="tenderator-mgmt__chart-list">
                {Object.entries(stats.tenders_by_sector)
                  .sort((a, b) => b[1] - a[1])
                  .slice(0, 10)
                  .map(([cpv, count]) => (
                    <div key={cpv} className="tenderator-mgmt__chart-item">
                      <span className="tenderator-mgmt__chart-label">{CPV_SECTORS[cpv] || cpv}</span>
                      <div className="tenderator-mgmt__chart-bar-container">
                        <div
                          className="tenderator-mgmt__chart-bar tenderator-mgmt__chart-bar--sector"
                          style={{ width: `${(count / Math.max(...Object.values(stats.tenders_by_sector))) * 100}%` }}
                        />
                      </div>
                      <span className="tenderator-mgmt__chart-value">{count}</span>
                    </div>
                  ))}
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="tenderator-mgmt__quick-actions">
            <h3>Quick Actions</h3>
            <div className="tenderator-mgmt__action-buttons">
              <button
                className="btn btn--primary"
                onClick={() => handleTriggerFetch('ted_api')}
                disabled={actionLoading}
              >
                <span className="mdi mdi-cloud-download"></span>
                Fetch New Tenders
              </button>
              <button
                className="btn btn--secondary"
                onClick={handleRunMatching}
                disabled={actionLoading}
              >
                <span className="mdi mdi-link-variant"></span>
                Run Matching
              </button>
              <button
                className="btn btn--secondary"
                onClick={() => handleSendNotifications('weekly')}
                disabled={actionLoading}
              >
                <span className="mdi mdi-email-send"></span>
                Send Digests
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Tenders Tab */}
      {activeTab === 'tenders' && (
        <div className="tenderator-mgmt__tenders">
          {/* Filters */}
          <div className="tenderator-mgmt__filters">
            <input
              type="text"
              placeholder="Search tenders..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="tenderator-mgmt__search"
            />
            <select
              value={countryFilter}
              onChange={(e) => setCountryFilter(e.target.value)}
              className="tenderator-mgmt__select"
            >
              <option value="">All Countries</option>
              {stats && Object.keys(stats.tenders_by_country).sort().map(country => (
                <option key={country} value={country}>{country}</option>
              ))}
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="tenderator-mgmt__select"
            >
              <option value="">All Status</option>
              <option value="open">Open</option>
              <option value="closed">Closed</option>
              <option value="awarded">Awarded</option>
              <option value="cancelled">Cancelled</option>
            </select>
            <button className="btn btn--secondary btn--small" onClick={fetchTenders}>
              <span className="mdi mdi-magnify"></span> Search
            </button>
            <button className="btn btn--outline btn--small" onClick={() => handleExport('csv')}>
              <span className="mdi mdi-download"></span> Export CSV
            </button>
          </div>

          {/* Tenders Table */}
          <div className="tenderator-mgmt__table-container">
            <table className="tenderator-mgmt__table">
              <thead>
                <tr>
                  <th>Publication #</th>
                  <th>Title</th>
                  <th>Country</th>
                  <th>Sector</th>
                  <th>Value</th>
                  <th>Deadline</th>
                  <th>Status</th>
                  <th>SME Score</th>
                  <th>Matches</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {tenders.map(tender => (
                  <tr key={tender.id}>
                    <td>
                      <a
                        href={`https://ted.europa.eu/udl?uri=TED:NOTICE:${tender.publication_number}:TEXT:EN:HTML`}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {tender.publication_number}
                      </a>
                    </td>
                    <td className="tenderator-mgmt__title-cell" title={tender.title}>
                      {tender.title.substring(0, 60)}...
                    </td>
                    <td>{tender.buyer_country || '-'}</td>
                    <td>{getSectorName(tender.cpv_main)}</td>
                    <td>{formatValue(tender.estimated_value)}</td>
                    <td>{formatDate(tender.submission_deadline)}</td>
                    <td>
                      <span className={`tenderator-mgmt__status tenderator-mgmt__status--${tender.status}`}>
                        {tender.status}
                      </span>
                    </td>
                    <td>
                      {tender.sme_suitability_score !== null
                        ? `${tender.sme_suitability_score.toFixed(0)}%`
                        : '-'}
                    </td>
                    <td>{tender.match_count}</td>
                    <td>
                      <button
                        className="btn btn--icon btn--danger"
                        onClick={() => handleDeleteTender(tender.id)}
                        title="Delete"
                      >
                        <span className="mdi mdi-delete"></span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="tenderator-mgmt__pagination">
            <button
              className="btn btn--outline btn--small"
              disabled={currentPage <= 1}
              onClick={() => setCurrentPage(p => p - 1)}
            >
              Previous
            </button>
            <span>Page {currentPage} of {totalPages}</span>
            <button
              className="btn btn--outline btn--small"
              disabled={currentPage >= totalPages}
              onClick={() => setCurrentPage(p => p + 1)}
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Profiles Tab */}
      {activeTab === 'profiles' && (
        <div className="tenderator-mgmt__profiles">
          <div className="tenderator-mgmt__table-container">
            <table className="tenderator-mgmt__table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Company</th>
                  <th>Size</th>
                  <th>Countries</th>
                  <th>Sectors</th>
                  <th>Matches</th>
                  <th>Status</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {profiles.map(profile => (
                  <tr key={profile.id}>
                    <td>
                      <div className="tenderator-mgmt__user-cell">
                        <strong>{profile.user_email}</strong>
                        {profile.user_name && <span>{profile.user_name}</span>}
                      </div>
                    </td>
                    <td>{profile.company_name || '-'}</td>
                    <td>{profile.company_size || '-'}</td>
                    <td>{profile.countries_count}</td>
                    <td>{profile.cpv_count}</td>
                    <td>{profile.match_count}</td>
                    <td>
                      <span className={`tenderator-mgmt__status tenderator-mgmt__status--${profile.is_active ? 'open' : 'closed'}`}>
                        {profile.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td>{formatDate(profile.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Fetch Jobs Tab */}
      {activeTab === 'fetch' && (
        <div className="tenderator-mgmt__fetch">
          {/* Fetch Configuration */}
          <div className="tenderator-mgmt__fetch-config">
            <h3>Fetch Configuration</h3>
            <div className="tenderator-mgmt__fetch-form">
              <div className="tenderator-mgmt__form-group">
                <label>Days to look back</label>
                <input
                  type="number"
                  min={1}
                  max={90}
                  value={fetchDays}
                  onChange={(e) => setFetchDays(parseInt(e.target.value) || 7)}
                />
              </div>
              <div className="tenderator-mgmt__form-group">
                <label>Countries (comma-separated)</label>
                <input
                  type="text"
                  placeholder="e.g., BE,FR,DE"
                  value={fetchCountries}
                  onChange={(e) => setFetchCountries(e.target.value)}
                />
              </div>
              <div className="tenderator-mgmt__form-group">
                <label>Max value (EUR)</label>
                <input
                  type="number"
                  min={0}
                  value={fetchMaxValue}
                  onChange={(e) => setFetchMaxValue(parseInt(e.target.value) || 5000000)}
                />
              </div>
            </div>
            <div className="tenderator-mgmt__fetch-buttons">
              <button
                className="btn btn--primary"
                onClick={() => handleTriggerFetch('ted_api')}
                disabled={actionLoading}
              >
                <span className="mdi mdi-cloud-download"></span>
                Fetch from TED API
              </button>
              <button
                className="btn btn--secondary"
                onClick={() => handleTriggerFetch('ted_sparql')}
                disabled={actionLoading}
              >
                <span className="mdi mdi-database"></span>
                Fetch from SPARQL
              </button>
            </div>
          </div>

          {/* Fetch Job History */}
          <div className="tenderator-mgmt__fetch-history">
            <h3>Fetch Job History</h3>
            <div className="tenderator-mgmt__table-container">
              <table className="tenderator-mgmt__table">
                <thead>
                  <tr>
                    <th>Job ID</th>
                    <th>Type</th>
                    <th>Source</th>
                    <th>Status</th>
                    <th>Found</th>
                    <th>New</th>
                    <th>Updated</th>
                    <th>Duration</th>
                    <th>Started</th>
                  </tr>
                </thead>
                <tbody>
                  {fetchJobs.map(job => (
                    <tr key={job.id}>
                      <td><code>{job.job_id}</code></td>
                      <td>{job.job_type}</td>
                      <td>{job.source}</td>
                      <td>
                        <span className={`tenderator-mgmt__status tenderator-mgmt__status--${job.status === 'completed' ? 'open' : job.status === 'failed' ? 'closed' : 'pending'}`}>
                          {job.status}
                        </span>
                      </td>
                      <td>{job.tenders_found}</td>
                      <td>{job.tenders_new}</td>
                      <td>{job.tenders_updated}</td>
                      <td>{job.duration_seconds ? `${job.duration_seconds.toFixed(1)}s` : '-'}</td>
                      <td>{formatDate(job.started_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Settings Tab */}
      {activeTab === 'settings' && (
        <div className="tenderator-mgmt__settings">
          <div className="tenderator-mgmt__settings-card">
            <h3>Tenderator Settings</h3>
            <p className="tenderator-mgmt__settings-info">
              Configure default values and automation settings for the Tenderator feature.
            </p>

            <div className="tenderator-mgmt__settings-form">
              <div className="tenderator-mgmt__form-group">
                <label>Default Max Value (EUR)</label>
                <input type="number" defaultValue={5000000} />
                <span className="tenderator-mgmt__form-hint">Maximum tender value for SME filtering</span>
              </div>

              <div className="tenderator-mgmt__form-group">
                <label>Fetch Frequency</label>
                <select defaultValue="weekly">
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                  <option value="bi-weekly">Bi-weekly</option>
                </select>
              </div>

              <div className="tenderator-mgmt__form-group">
                <label>Match Score Threshold</label>
                <input type="number" min={0} max={100} defaultValue={50} />
                <span className="tenderator-mgmt__form-hint">Minimum score to create a match (0-100)</span>
              </div>

              <div className="tenderator-mgmt__form-group tenderator-mgmt__form-group--checkbox">
                <label>
                  <input type="checkbox" defaultChecked />
                  Enable automatic matching
                </label>
              </div>

              <div className="tenderator-mgmt__form-group tenderator-mgmt__form-group--checkbox">
                <label>
                  <input type="checkbox" defaultChecked />
                  Enable automatic notifications
                </label>
              </div>
            </div>

            <button className="btn btn--primary">
              <span className="mdi mdi-content-save"></span>
              Save Settings
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
