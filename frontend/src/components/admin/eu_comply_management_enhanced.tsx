/**
 * Enhanced EU Law Comply Management Component
 *
 * Admin interface with:
 * - Model selection for requirement extraction
 * - Semantic search across requirements
 * - RAG chatbot for compliance Q&A
 * - Real-time progress tracking
 */

import { useState, useEffect } from 'react';
import { useAuth } from '../../hooks/use_auth';
import './eu_comply_management.css';

interface ClusterStats {
  id: number;
  name: string;
  policy_area: string;
  description: string;
  law_count: number;
  requirement_count: number;
  extraction_status: 'idle' | 'pending' | 'running' | 'completed' | 'failed';
  extraction_progress: number;
}

interface AIModel {
  id: string;
  name: string;
  type: string;
  quality: string;
  speed: string;
  memory_gb: number;
}

interface SearchResult {
  requirement_id: number;
  requirement_text: string;
  article: string;
  criticality: string;
  applicable_entity?: string;
  score: number;
}

interface ChatResponse {
  answer: string;
  confidence: number;
  retrieved_count: number;
  sources?: Array<{
    law_celex?: string;
    law_title?: string;
    article: string;
    requirement_text: string;
    criticality: string;
    relevance_score: number;
  }>;
}

type Tab = 'extraction' | 'search' | 'chatbot';

export const EUComplyManagementEnhanced = () => {
  const { token } = useAuth();
  const [activeTab, setActiveTab] = useState<Tab>('extraction');
  const [clusters, setClusters] = useState<ClusterStats[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>('gpt-4');
  const [availableModels, setAvailableModels] = useState<AIModel[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [_error, setError] = useState<string | null>(null);
  const [extractingClusters, setExtractingClusters] = useState<Set<number>>(new Set());

  // Search state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchCluster, setSearchCluster] = useState<number | null>(null);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  // Chatbot state
  const [chatQuestion, setChatQuestion] = useState('');
  const [chatCluster, setChatCluster] = useState<number | null>(null);
  const [chatResponse, setChatResponse] = useState<ChatResponse | null>(null);
  const [chatting, setChatting] = useState(false);

  useEffect(() => {
    fetchClusters();
    fetchModels();
  }, []);

  useEffect(() => {
    if (extractingClusters.size === 0) return;

    const interval = setInterval(() => {
      extractingClusters.forEach((clusterId) => {
        fetchExtractionStatus(clusterId);
      });
    }, 3000);

    return () => clearInterval(interval);
  }, [extractingClusters]);

  const fetchClusters = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch('http://localhost:8000/api/admin/eu-comply/clusters/stats', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) throw new Error('Failed to fetch cluster stats');

      const data: ClusterStats[] = await response.json();
      setClusters(data);

      const running = new Set<number>();
      data.forEach(cluster => {
        if (cluster.extraction_status === 'running' || cluster.extraction_status === 'pending') {
          running.add(cluster.id);
        }
      });
      setExtractingClusters(running);

    } catch (err) {
      console.error('Error fetching clusters:', err);
      setError('Failed to load cluster statistics');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchModels = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/admin/eu-comply/models/available', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) return;

      const data = await response.json();
      setAvailableModels(data.models);
    } catch (err) {
      console.error('Error fetching models:', err);
    }
  };

  const fetchExtractionStatus = async (clusterId: number) => {
    try {
      const response = await fetch(
        `http://localhost:8000/api/admin/eu-comply/clusters/${clusterId}/extraction-status`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) return;

      const status = await response.json();

      setClusters(prev => prev.map(cluster =>
        cluster.id === clusterId
          ? {
              ...cluster,
              extraction_status: status.status,
              extraction_progress: status.progress,
            }
          : cluster
      ));

      if (status.status === 'completed' || status.status === 'failed') {
        setExtractingClusters(prev => {
          const next = new Set(prev);
          next.delete(clusterId);
          return next;
        });

        if (status.status === 'completed') {
          setTimeout(fetchClusters, 1000);
        }
      }

    } catch (err) {
      console.error(`Error fetching extraction status for cluster ${clusterId}:`, err);
    }
  };

  const startExtraction = async (clusterId: number) => {
    try {
      const response = await fetch(
        `http://localhost:8000/api/admin/eu-comply/clusters/${clusterId}/extract-with-model?model=${selectedModel}`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to start extraction');
      }

      setExtractingClusters(prev => new Set(prev).add(clusterId));
      setClusters(prev => prev.map(cluster =>
        cluster.id === clusterId
          ? { ...cluster, extraction_status: 'pending' as const, extraction_progress: 0 }
          : cluster
      ));

    } catch (err) {
      console.error('Error starting extraction:', err);
      alert(err instanceof Error ? err.message : 'Failed to start extraction');
    }
  };

  const performSearch = async () => {
    if (!searchQuery.trim()) return;

    setSearching(true);
    try {
      const params = new URLSearchParams({
        query: searchQuery,
        top_k: '10',
        min_score: '0.5',
      });

      if (searchCluster) {
        params.append('cluster_id', searchCluster.toString());
      }

      const response = await fetch(
        `http://localhost:8000/api/admin/eu-comply/search/requirements?${params}`,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) throw new Error('Search failed');

      const data = await response.json();
      setSearchResults(data.results);
    } catch (err) {
      console.error('Search error:', err);
      alert('Search failed. Please try again.');
    } finally {
      setSearching(false);
    }
  };

  const askChatbot = async () => {
    if (!chatQuestion.trim()) return;

    setChatting(true);
    setChatResponse(null);

    try {
      const params = new URLSearchParams({
        question: chatQuestion,
        top_k: '5',
      });

      if (chatCluster) {
        params.append('cluster_id', chatCluster.toString());
      }

      const response = await fetch(
        `http://localhost:8000/api/admin/eu-comply/chatbot/ask?${params}`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) throw new Error('Chatbot request failed');

      const data = await response.json();
      setChatResponse(data);
    } catch (err) {
      console.error('Chatbot error:', err);
      alert('Chatbot request failed. Please try again.');
    } finally {
      setChatting(false);
    }
  };

  const getStatusColor = (status: ClusterStats['extraction_status']) => {
    switch (status) {
      case 'completed': return '#10b981';
      case 'running': return '#3b82f6';
      case 'pending': return '#f59e0b';
      case 'failed': return '#ef4444';
      default: return '#6b7280';
    }
  };

  const getCriticalityColor = (criticality: string) => {
    switch (criticality) {
      case 'critical': return '#ef4444';
      case 'important': return '#f59e0b';
      case 'recommended': return '#3b82f6';
      default: return '#6b7280';
    }
  };

  if (isLoading) {
    return (
      <div className="eu-comply-management">
        <div className="eu-comply-management__loading">
          <div className="spinner"></div>
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="eu-comply-management">
      <div className="eu-comply-management__header">
        <h2>EU Law Comply - AI-Powered Management</h2>
        <p className="eu-comply-management__subtitle">
          Extract requirements, search semantically, and get AI-powered compliance answers
        </p>
      </div>

      {/* Tab Navigation */}
      <nav className="eu-comply-tabs">
        <button
          className={`eu-comply-tab ${activeTab === 'extraction' ? 'eu-comply-tab--active' : ''}`}
          onClick={() => setActiveTab('extraction')}
        >
          <span className="mdi mdi-robot"></span>
          Extraction
        </button>
        <button
          className={`eu-comply-tab ${activeTab === 'search' ? 'eu-comply-tab--active' : ''}`}
          onClick={() => setActiveTab('search')}
        >
          <span className="mdi mdi-magnify"></span>
          Semantic Search
        </button>
        <button
          className={`eu-comply-tab ${activeTab === 'chatbot' ? 'eu-comply-tab--active' : ''}`}
          onClick={() => setActiveTab('chatbot')}
        >
          <span className="mdi mdi-chat"></span>
          AI Assistant
        </button>
      </nav>

      {/* Extraction Tab */}
      {activeTab === 'extraction' && (
        <div className="eu-comply-content">
          {/* Model Selection */}
          <div className="model-selector">
            <label htmlFor="model-select">
              <span className="mdi mdi-brain"></span>
              AI Model:
            </label>
            <select
              id="model-select"
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="model-select"
            >
              {availableModels.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.id === 'gpt-4' ? '🔥 ' : ''}
                  {model.id.toUpperCase()} - {model.quality} quality, {model.speed} speed
                </option>
              ))}
            </select>
            <span className="model-hint">
              {selectedModel === 'gpt-4'
                ? '💰 Premium quality, higher cost'
                : '💚 Open-source, 95% cost savings'}
            </span>
          </div>

          {/* Stats */}
          <div className="eu-comply-management__stats">
            <div className="stat-card">
              <div className="stat-card__label">Total Clusters</div>
              <div className="stat-card__value">{clusters.length}</div>
            </div>
            <div className="stat-card">
              <div className="stat-card__label">Total Laws</div>
              <div className="stat-card__value">
                {clusters.reduce((sum, c) => sum + c.law_count, 0).toLocaleString()}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-card__label">Total Requirements</div>
              <div className="stat-card__value">
                {clusters.reduce((sum, c) => sum + c.requirement_count, 0).toLocaleString()}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-card__label">Jobs Running</div>
              <div className="stat-card__value">{extractingClusters.size}</div>
            </div>
          </div>

          {/* Clusters */}
          <div className="eu-comply-management__clusters">
            {clusters.map((cluster) => (
              <div key={cluster.id} className="cluster-card">
                <div className="cluster-card__header">
                  <div>
                    <h3 className="cluster-card__name">{cluster.name}</h3>
                    <span className="cluster-card__policy">{cluster.policy_area}</span>
                  </div>
                  <div
                    className="cluster-card__status"
                    style={{ backgroundColor: getStatusColor(cluster.extraction_status) }}
                  >
                    {cluster.extraction_status === 'running' ? 'Extracting...' : cluster.extraction_status}
                  </div>
                </div>

                <p className="cluster-card__description">{cluster.description}</p>

                <div className="cluster-card__stats">
                  <div className="cluster-stat">
                    <span className="mdi mdi-file-document-multiple"></span>
                    <span>{cluster.law_count} laws</span>
                  </div>
                  <div className="cluster-stat">
                    <span className="mdi mdi-gavel"></span>
                    <span>{cluster.requirement_count} requirements</span>
                  </div>
                </div>

                {(cluster.extraction_status === 'running' || cluster.extraction_status === 'pending') && (
                  <div className="cluster-card__progress">
                    <div className="progress-bar">
                      <div
                        className="progress-bar__fill"
                        style={{ width: `${cluster.extraction_progress}%` }}
                      ></div>
                    </div>
                    <span className="progress-label">{cluster.extraction_progress}%</span>
                  </div>
                )}

                <div className="cluster-card__actions">
                  <button
                    onClick={() => startExtraction(cluster.id)}
                    disabled={
                      cluster.extraction_status === 'running' ||
                      cluster.extraction_status === 'pending'
                    }
                    className="button button-primary"
                  >
                    {cluster.extraction_status === 'running' || cluster.extraction_status === 'pending'
                      ? 'Extracting...'
                      : `Extract with ${selectedModel.toUpperCase()}`}
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Semantic Search Tab */}
      {activeTab === 'search' && (
        <div className="eu-comply-content">
          <div className="search-section">
            <h3>
              <span className="mdi mdi-magnify"></span>
              Semantic Search
            </h3>
            <p className="search-description">
              Find requirements by meaning, not just keywords. Powered by AI embeddings.
            </p>

            <div className="search-form">
              <div className="search-input-group">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && performSearch()}
                  placeholder="e.g., 'data protection obligations for controllers'"
                  className="search-input"
                />
                <select
                  value={searchCluster || ''}
                  onChange={(e) => setSearchCluster(e.target.value ? Number(e.target.value) : null)}
                  className="search-cluster-select"
                >
                  <option value="">All Clusters</option>
                  {clusters.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
                <button
                  onClick={performSearch}
                  disabled={searching || !searchQuery.trim()}
                  className="button button-primary"
                >
                  {searching ? 'Searching...' : 'Search'}
                </button>
              </div>
            </div>

            {searchResults.length > 0 && (
              <div className="search-results">
                <h4>{searchResults.length} Results</h4>
                {searchResults.map((result, idx) => (
                  <div key={idx} className="search-result-card">
                    <div className="search-result-header">
                      <span className="search-result-article">{result.article}</span>
                      <span
                        className="search-result-criticality"
                        style={{ backgroundColor: getCriticalityColor(result.criticality) }}
                      >
                        {result.criticality}
                      </span>
                      <span className="search-result-score">
                        {(result.score * 100).toFixed(0)}% match
                      </span>
                    </div>
                    <p className="search-result-text">{result.requirement_text}</p>
                    {result.applicable_entity && (
                      <p className="search-result-entity">
                        <span className="mdi mdi-account-group"></span>
                        Applicable to: {result.applicable_entity}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Chatbot Tab */}
      {activeTab === 'chatbot' && (
        <div className="eu-comply-content">
          <div className="chatbot-section">
            <h3>
              <span className="mdi mdi-robot"></span>
              AI Compliance Assistant
            </h3>
            <p className="chatbot-description">
              Ask questions about EU law compliance. Powered by RAG (Retrieval-Augmented Generation).
            </p>

            <div className="chatbot-form">
              <div className="chatbot-input-group">
                <select
                  value={chatCluster || ''}
                  onChange={(e) => setChatCluster(e.target.value ? Number(e.target.value) : null)}
                  className="chatbot-cluster-select"
                >
                  <option value="">All Areas</option>
                  {clusters.map((c) => (
                    <option key={c.id} value={c.id}>{c.name}</option>
                  ))}
                </select>
              </div>

              <textarea
                value={chatQuestion}
                onChange={(e) => setChatQuestion(e.target.value)}
                placeholder="e.g., 'What are the main obligations for VLOPs under the DSA?'"
                className="chatbot-textarea"
                rows={3}
              />

              <button
                onClick={askChatbot}
                disabled={chatting || !chatQuestion.trim()}
                className="button button-primary chatbot-button"
              >
                {chatting ? 'Thinking...' : 'Ask AI Assistant'}
              </button>
            </div>

            {chatResponse && (
              <div className="chatbot-response">
                <div className="chatbot-answer-header">
                  <h4>
                    <span className="mdi mdi-comment-quote"></span>
                    Answer
                  </h4>
                  <span className="chatbot-confidence">
                    Confidence: {(chatResponse.confidence * 100).toFixed(0)}%
                  </span>
                </div>

                <div className="chatbot-answer-text">{chatResponse.answer}</div>

                {chatResponse.sources && chatResponse.sources.length > 0 && (
                  <div className="chatbot-sources">
                    <h5>
                      <span className="mdi mdi-book-open-variant"></span>
                      Sources ({chatResponse.sources.length})
                    </h5>
                    {chatResponse.sources.map((source, idx) => (
                      <div key={idx} className="chatbot-source-card">
                        <div className="chatbot-source-header">
                          <span className="chatbot-source-celex">{source.law_celex}</span>
                          <span className="chatbot-source-article">{source.article}</span>
                          <span
                            className="chatbot-source-criticality"
                            style={{ backgroundColor: getCriticalityColor(source.criticality) }}
                          >
                            {source.criticality}
                          </span>
                        </div>
                        <p className="chatbot-source-text">{source.requirement_text}</p>
                        <p className="chatbot-source-relevance">
                          Relevance: {(source.relevance_score * 100).toFixed(0)}%
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
