/**
 * Dashboard Tab Component
 *
 * Shows user activity overview, quick stats, and tracked legislation.
 * Part of My EU Bubble - Phase 3: Frontend
 */

import { useEffect, useRef } from 'react';
import Icon from '@mdi/react';
import { mdiFileDocument, mdiFileEdit, mdiNewspaper, mdiStar } from '@mdi/js';
import { useBubble } from '../../hooks/use_bubble';
import { useAuth } from '../../hooks/use_auth';
import { TenderatorWidget } from './tenderator_widget';
import { LegislativeUpdatesWidget } from './legislative_updates_widget';
import { DashboardCockpit } from './dashboard_cockpit';
import './dashboard_tab.css';

export const DashboardTab = () => {
  const {
    documents,
    userStats,
    documentStats,
    fetchDocuments,
    fetchUserStats,
    fetchDocumentStats,
  } = useBubble();
  const { user } = useAuth();
  const hasLoadedRef = useRef(false);

  useEffect(() => {
    // Prevent duplicate loads
    if (hasLoadedRef.current) {
      console.log('⏭️ Dashboard already loaded, skipping fetch');
      return;
    }

    console.log('🔄 Dashboard mounting - fetching stats...');
    hasLoadedRef.current = true;

    // Fetch with small delays to avoid overwhelming the connection pool
    const loadData = async () => {
      try {
        await fetchUserStats();
        await new Promise(resolve => setTimeout(resolve, 100));
        await fetchDocumentStats();
        await new Promise(resolve => setTimeout(resolve, 100));
        await fetchDocuments();
      } catch (error) {
        console.error('Failed to load dashboard data:', error);
      }
    };

    loadData();
  }, []);

  useEffect(() => {
    console.log('📊 documentStats updated:', documentStats);
  }, [documentStats]);

  const recentDocuments = documents.slice(0, 5);

  // Parse user's policy interests
  const userPolicyInterests = (() => {
    if (!user?.policy_interests) return [];
    try {
      const interests = typeof user.policy_interests === 'string'
        ? JSON.parse(user.policy_interests)
        : user.policy_interests;
      return Array.isArray(interests) ? interests : [];
    } catch (e) {
      console.error('Failed to parse policy interests', e);
      return [];
    }
  })();

  // Check if a policy area matches user's interests
  const isPolicyInterest = (policyArea: string) => {
    return userPolicyInterests.includes(policyArea);
  };

  // Merge user's policy interests with document policy areas
  const getMergedPolicyAreas = () => {
    const documentPolicyAreas = documentStats?.by_policy_area || {};
    const merged: Record<string, number> = { ...documentPolicyAreas };

    // Add user's policy interests with 0 count if not already present
    userPolicyInterests.forEach(interest => {
      if (!(interest in merged)) {
        merged[interest] = 0;
      }
    });

    // Convert to array and sort: interests first (with blue stars), then by count
    return Object.entries(merged)
      .sort(([areaA, countA], [areaB, countB]) => {
        const aIsInterest = isPolicyInterest(areaA);
        const bIsInterest = isPolicyInterest(areaB);

        // Interests first
        if (aIsInterest && !bIsInterest) return -1;
        if (!aIsInterest && bIsInterest) return 1;

        // Then by count (descending)
        return countB - countA;
      })
      .slice(0, 10); // Show top 10
  };

  return (
    <div className="dashboard-tab">
      {/* Welcome Section */}
      <div className="dashboard-tab__welcome">
        <h2>Welcome to Your EU Bubble</h2>
        <p>Your personalised EU policy cockpit</p>
      </div>

      {/* Monitoring cockpit — the six-tile front door of My EU Bubble. */}
      <DashboardCockpit />

      {/* Quick Stats */}
      <div className="dashboard-tab__stats-grid">
        <div className="dashboard-tab__stat-card">
          <div className="dashboard-tab__stat-icon">
            <Icon path={mdiFileDocument} size={1.5} color="#0693E3" />
          </div>
          <div className="dashboard-tab__stat-content">
            <div className="dashboard-tab__stat-value">
              {documentStats?.total_documents || 0}
            </div>
            <div className="dashboard-tab__stat-label">Total Documents</div>
          </div>
        </div>

        <div className="dashboard-tab__stat-card">
          <div className="dashboard-tab__stat-icon">
            <Icon path={mdiFileEdit} size={1.5} color="#0693E3" />
          </div>
          <div className="dashboard-tab__stat-content">
            <div className="dashboard-tab__stat-value">
              {documentStats?.total_amendments || 0}
            </div>
            <div className="dashboard-tab__stat-label">Amendments</div>
          </div>
        </div>

        <div className="dashboard-tab__stat-card">
          <div className="dashboard-tab__stat-icon">
            <Icon path={mdiNewspaper} size={1.5} color="#0693E3" />
          </div>
          <div className="dashboard-tab__stat-content">
            <div className="dashboard-tab__stat-value">
              {userStats?.total_reads || 0}
            </div>
            <div className="dashboard-tab__stat-label">Articles Read</div>
          </div>
        </div>

        <div className="dashboard-tab__stat-card">
          <div className="dashboard-tab__stat-icon">
            <Icon path={mdiStar} size={1.5} color="#0693E3" />
          </div>
          <div className="dashboard-tab__stat-content">
            <div className="dashboard-tab__stat-value">
              {userStats?.total_saves || 0}
            </div>
            <div className="dashboard-tab__stat-label">Saved Items</div>
          </div>
        </div>
      </div>

      {/* Widget Row */}
      <div className="dashboard-tab__widget-row">
        <TenderatorWidget />
        <LegislativeUpdatesWidget />
      </div>

      {/* Two Column Layout */}
      <div className="dashboard-tab__content-grid">
        {/* Left Column: Recent Activity */}
        <div className="dashboard-tab__section">
          <h3 className="dashboard-tab__section-title">Recent Activity</h3>

          <div className="dashboard-tab__activity-list">
            <h4 className="dashboard-tab__subsection-title">Recent Documents</h4>
            {recentDocuments.length === 0 ? (
              <p className="dashboard-tab__empty">No documents yet. Create your first document!</p>
            ) : (
              <div className="dashboard-tab__document-list">
                {recentDocuments.map(doc => (
                  <div key={doc.id} className="dashboard-tab__document-item">
                    <div className="dashboard-tab__document-type-badge" data-type={doc.document_type}>
                      {doc.document_type}
                    </div>
                    <div className="dashboard-tab__document-info">
                      <div className="dashboard-tab__document-title">{doc.title}</div>
                      <div className="dashboard-tab__document-meta">
                        {new Date(doc.updated_at).toLocaleDateString()} • {doc.word_count || 0} words
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Insights */}
        <div className="dashboard-tab__section">
          <h3 className="dashboard-tab__section-title">Your Insights</h3>

          {/* Policy Area Breakdown */}
          <div className="dashboard-tab__insight-card">
            <h4 className="dashboard-tab__insight-title">Top Policy Areas</h4>
            {(() => {
              const mergedAreas = getMergedPolicyAreas();
              return mergedAreas.length > 0 ? (
                <div className="dashboard-tab__policy-list">
                  {mergedAreas.map(([area, count]) => (
                    <div key={area} className="dashboard-tab__policy-item">
                      <div className="dashboard-tab__policy-name">
                        {isPolicyInterest(area) && (
                          <Icon
                            path={mdiStar}
                            size={0.7}
                            color="#0693E3"
                            style={{ marginRight: '0.5rem' }}
                          />
                        )}
                        {area}
                      </div>
                      <div className="dashboard-tab__policy-count">{count}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="dashboard-tab__empty">
                  No policy areas yet. <a href="/profile" style={{ color: '#0693E3' }}>Set your interests</a> in your profile.
                </p>
              );
            })()}
          </div>

          {/* Favorite Sources */}
          <div className="dashboard-tab__insight-card">
            <h4 className="dashboard-tab__insight-title">Favorite News Sources</h4>
            {userStats && userStats.favorite_sources.length > 0 ? (
              <div className="dashboard-tab__source-list">
                {userStats.favorite_sources.map((source, idx) => (
                  <div key={idx} className="dashboard-tab__source-item">
                    {source}
                  </div>
                ))}
              </div>
            ) : (
              <p className="dashboard-tab__empty">Start reading to see your favorite sources</p>
            )}
          </div>

          {/* Document Type Breakdown */}
          <div className="dashboard-tab__insight-card">
            <h4 className="dashboard-tab__insight-title">Document Breakdown</h4>
            {documentStats && Object.keys(documentStats.by_type || {}).length > 0 ? (
              <div className="dashboard-tab__type-breakdown">
                {Object.entries(documentStats.by_type || {}).map(([type, count]) => (
                  <div key={type} className="dashboard-tab__type-row">
                    <div className="dashboard-tab__type-label">{type}</div>
                    <div className="dashboard-tab__type-bar">
                      <div
                        className="dashboard-tab__type-fill"
                        style={{
                          width: `${(count / (documentStats.total_documents || 1)) * 100}%`,
                        }}
                      />
                    </div>
                    <div className="dashboard-tab__type-count">{count}</div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="dashboard-tab__empty">No documents created yet</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
