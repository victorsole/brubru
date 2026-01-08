// frontend/src/components/tenders/bid_checklist.tsx
import { useState, useEffect } from 'react';
import type { Tender } from '../../pages/tenderator_page';
import { useAuth } from '../../hooks/use_auth';
import './bid_checklist.css';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface ESPDRequirement {
  id: string;
  type: 'exclusion' | 'selection';
  category: string;
  requirement: string;
  document_needed: string;
  mandatory: boolean;
  description?: string;
  issuing_authority?: string;
  website?: string;
}

interface ChecklistState {
  [key: string]: boolean;
}

interface BidChecklistProps {
  tender: Tender;
  onBack: () => void;
  onAskChatbot: (question: string) => void;
}

export const BidChecklist = ({ tender, onBack, onAskChatbot }: BidChecklistProps) => {
  const { token } = useAuth();
  const [requirements, setRequirements] = useState<ESPDRequirement[]>([]);
  const [checklist, setChecklist] = useState<ChecklistState>({});
  const [isLoading, setIsLoading] = useState(true);
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'pending' | 'completed'>('all');

  // Fetch requirements from API or use defaults
  useEffect(() => {
    const fetchRequirements = async () => {
      setIsLoading(true);
      try {
        const response = await fetch(`${API_URL}/api/tenders/${tender.id}/checklist`, {
          headers: { 'Authorization': `Bearer ${token}` },
        });

        if (response.ok) {
          const data = await response.json();
          setRequirements(data.requirements || []);
        } else {
          // Use default ESPD requirements
          setRequirements(getDefaultRequirements(tender.buyer_country));
        }
      } catch (err) {
        console.error('Failed to fetch requirements:', err);
        setRequirements(getDefaultRequirements(tender.buyer_country));
      } finally {
        setIsLoading(false);
      }
    };

    fetchRequirements();

    // Load saved checklist state from localStorage
    const savedChecklist = localStorage.getItem(`checklist-${tender.id}`);
    if (savedChecklist) {
      setChecklist(JSON.parse(savedChecklist));
    }
  }, [tender.id, tender.buyer_country]);

  // Save checklist state to localStorage
  const handleCheckItem = (requirementId: string) => {
    const newChecklist = {
      ...checklist,
      [requirementId]: !checklist[requirementId],
    };
    setChecklist(newChecklist);
    localStorage.setItem(`checklist-${tender.id}`, JSON.stringify(newChecklist));
  };

  // Calculate progress
  const totalRequired = requirements.filter(r => r.mandatory).length;
  const completedRequired = requirements.filter(r => r.mandatory && checklist[r.id]).length;
  const totalOptional = requirements.filter(r => !r.mandatory).length;
  const completedOptional = requirements.filter(r => !r.mandatory && checklist[r.id]).length;
  const progressPercent = totalRequired > 0 ? Math.round((completedRequired / totalRequired) * 100) : 0;

  // Group requirements by category
  const groupedRequirements = requirements.reduce((acc, req) => {
    if (!acc[req.category]) {
      acc[req.category] = [];
    }
    acc[req.category].push(req);
    return acc;
  }, {} as Record<string, ESPDRequirement[]>);

  // Filter requirements
  const filterRequirements = (reqs: ESPDRequirement[]) => {
    if (filter === 'pending') {
      return reqs.filter(r => !checklist[r.id]);
    }
    if (filter === 'completed') {
      return reqs.filter(r => checklist[r.id]);
    }
    return reqs;
  };

  const getCategoryIcon = (category: string): string => {
    if (category.toLowerCase().includes('criminal')) return 'mdi-gavel';
    if (category.toLowerCase().includes('tax')) return 'mdi-cash-multiple';
    if (category.toLowerCase().includes('social')) return 'mdi-account-group';
    if (category.toLowerCase().includes('insolvency')) return 'mdi-alert-circle';
    if (category.toLowerCase().includes('economic')) return 'mdi-chart-line';
    if (category.toLowerCase().includes('technical')) return 'mdi-wrench';
    if (category.toLowerCase().includes('professional')) return 'mdi-certificate';
    if (category.toLowerCase().includes('quality')) return 'mdi-check-decagram';
    return 'mdi-file-document';
  };

  return (
    <div className="bid-checklist">
      {/* Header */}
      <div className="bid-checklist__header">
        <button className="bid-checklist__back" onClick={onBack}>
          <span className="mdi mdi-arrow-left"></span>
          Back
        </button>
        <div className="bid-checklist__title-section">
          <h2>ESPD Document Checklist</h2>
          <p className="bid-checklist__tender-ref">
            For: {tender.title} ({tender.publication_number})
          </p>
        </div>
      </div>

      {/* Progress Card */}
      <div className="bid-checklist__progress-card">
        <div className="bid-checklist__progress-main">
          <div className="bid-checklist__progress-circle">
            <svg viewBox="0 0 36 36">
              <path
                className="bid-checklist__progress-bg"
                d="M18 2.0845
                  a 15.9155 15.9155 0 0 1 0 31.831
                  a 15.9155 15.9155 0 0 1 0 -31.831"
              />
              <path
                className="bid-checklist__progress-fill"
                strokeDasharray={`${progressPercent}, 100`}
                d="M18 2.0845
                  a 15.9155 15.9155 0 0 1 0 31.831
                  a 15.9155 15.9155 0 0 1 0 -31.831"
              />
            </svg>
            <span className="bid-checklist__progress-value">{progressPercent}%</span>
          </div>
          <div className="bid-checklist__progress-info">
            <h3>Your Progress</h3>
            <p>
              <strong>{completedRequired}</strong> of <strong>{totalRequired}</strong> mandatory items completed
            </p>
            <p className="bid-checklist__progress-optional">
              {completedOptional} of {totalOptional} optional items completed
            </p>
          </div>
        </div>
        <div className="bid-checklist__progress-actions">
          <button
            className="bid-checklist__help-btn"
            onClick={() => onAskChatbot(`Help me understand the ESPD requirements for tender ${tender.publication_number}. What documents do I need to prepare and what are the exclusion grounds?`)}
          >
            <span className="mdi mdi-chat-question"></span>
            Get Help
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="bid-checklist__filters">
        <button
          className={`bid-checklist__filter ${filter === 'all' ? 'bid-checklist__filter--active' : ''}`}
          onClick={() => setFilter('all')}
        >
          All ({requirements.length})
        </button>
        <button
          className={`bid-checklist__filter ${filter === 'pending' ? 'bid-checklist__filter--active' : ''}`}
          onClick={() => setFilter('pending')}
        >
          Pending ({requirements.filter(r => !checklist[r.id]).length})
        </button>
        <button
          className={`bid-checklist__filter ${filter === 'completed' ? 'bid-checklist__filter--active' : ''}`}
          onClick={() => setFilter('completed')}
        >
          Completed ({requirements.filter(r => checklist[r.id]).length})
        </button>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="bid-checklist__loading">
          <span className="mdi mdi-loading mdi-spin"></span>
          Loading checklist...
        </div>
      )}

      {/* Checklist Content */}
      {!isLoading && (
        <div className="bid-checklist__content">
          {/* Exclusion Grounds (Part III) */}
          <div className="bid-checklist__section">
            <h3 className="bid-checklist__section-title">
              <span className="mdi mdi-shield-alert"></span>
              Part III: Exclusion Grounds
            </h3>
            <p className="bid-checklist__section-desc">
              Documents proving you are not subject to exclusion from public procurement.
            </p>

            {Object.entries(groupedRequirements)
              .filter(([_, reqs]) => reqs.some(r => r.type === 'exclusion'))
              .map(([category, reqs]) => {
                const exclusionReqs = filterRequirements(reqs.filter(r => r.type === 'exclusion'));
                if (exclusionReqs.length === 0) return null;

                const categoryCompleted = exclusionReqs.filter(r => checklist[r.id]).length;
                const isExpanded = expandedCategory === `exclusion-${category}`;

                return (
                  <div key={`exclusion-${category}`} className="bid-checklist__category">
                    <button
                      className="bid-checklist__category-header"
                      onClick={() => setExpandedCategory(isExpanded ? null : `exclusion-${category}`)}
                    >
                      <div className="bid-checklist__category-left">
                        <span className={`mdi ${getCategoryIcon(category)}`}></span>
                        <span className="bid-checklist__category-name">{category}</span>
                        <span className="bid-checklist__category-count">
                          {categoryCompleted}/{exclusionReqs.length}
                        </span>
                      </div>
                      <span className={`mdi ${isExpanded ? 'mdi-chevron-up' : 'mdi-chevron-down'}`}></span>
                    </button>

                    {isExpanded && (
                      <div className="bid-checklist__category-items">
                        {exclusionReqs.map((req) => (
                          <ChecklistItem
                            key={req.id}
                            requirement={req}
                            isChecked={checklist[req.id] || false}
                            onToggle={() => handleCheckItem(req.id)}
                            onAskHelp={() => onAskChatbot(`Explain the requirement "${req.requirement}" for ESPD Part III. What document do I need? ${req.document_needed ? `The suggested document is: ${req.document_needed}` : ''}`)}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
          </div>

          {/* Selection Criteria (Part IV) */}
          <div className="bid-checklist__section">
            <h3 className="bid-checklist__section-title">
              <span className="mdi mdi-clipboard-check"></span>
              Part IV: Selection Criteria
            </h3>
            <p className="bid-checklist__section-desc">
              Documents demonstrating your suitability and qualifications for the contract.
            </p>

            {Object.entries(groupedRequirements)
              .filter(([_, reqs]) => reqs.some(r => r.type === 'selection'))
              .map(([category, reqs]) => {
                const selectionReqs = filterRequirements(reqs.filter(r => r.type === 'selection'));
                if (selectionReqs.length === 0) return null;

                const categoryCompleted = selectionReqs.filter(r => checklist[r.id]).length;
                const isExpanded = expandedCategory === `selection-${category}`;

                return (
                  <div key={`selection-${category}`} className="bid-checklist__category">
                    <button
                      className="bid-checklist__category-header"
                      onClick={() => setExpandedCategory(isExpanded ? null : `selection-${category}`)}
                    >
                      <div className="bid-checklist__category-left">
                        <span className={`mdi ${getCategoryIcon(category)}`}></span>
                        <span className="bid-checklist__category-name">{category}</span>
                        <span className="bid-checklist__category-count">
                          {categoryCompleted}/{selectionReqs.length}
                        </span>
                      </div>
                      <span className={`mdi ${isExpanded ? 'mdi-chevron-up' : 'mdi-chevron-down'}`}></span>
                    </button>

                    {isExpanded && (
                      <div className="bid-checklist__category-items">
                        {selectionReqs.map((req) => (
                          <ChecklistItem
                            key={req.id}
                            requirement={req}
                            isChecked={checklist[req.id] || false}
                            onToggle={() => handleCheckItem(req.id)}
                            onAskHelp={() => onAskChatbot(`Explain the requirement "${req.requirement}" for ESPD Part IV. What document do I need? ${req.document_needed ? `The suggested document is: ${req.document_needed}` : ''}`)}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
          </div>
        </div>
      )}

      {/* Footer Actions */}
      <div className="bid-checklist__footer">
        <button
          className="bid-checklist__export-btn"
          onClick={() => {
            // Export checklist as JSON
            const data = {
              tender_id: tender.id,
              publication_number: tender.publication_number,
              checklist: checklist,
              progress: progressPercent,
              exported_at: new Date().toISOString(),
            };
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `checklist-${tender.publication_number}.json`;
            a.click();
          }}
        >
          <span className="mdi mdi-download"></span>
          Export Checklist
        </button>
        <button
          className="bid-checklist__submit-btn"
          onClick={() => onAskChatbot(`I've completed ${progressPercent}% of the ESPD requirements for tender ${tender.publication_number}. What are the next steps to submit my bid?`)}
        >
          <span className="mdi mdi-send"></span>
          Get Submission Help
        </button>
      </div>
    </div>
  );
};

// Individual checklist item component
interface ChecklistItemProps {
  requirement: ESPDRequirement;
  isChecked: boolean;
  onToggle: () => void;
  onAskHelp: () => void;
}

const ChecklistItem = ({ requirement, isChecked, onToggle, onAskHelp }: ChecklistItemProps) => {
  return (
    <div className={`bid-checklist__item ${isChecked ? 'bid-checklist__item--checked' : ''}`}>
      <label className="bid-checklist__item-checkbox">
        <input
          type="checkbox"
          checked={isChecked}
          onChange={onToggle}
        />
        <span className="bid-checklist__checkmark">
          <span className="mdi mdi-check"></span>
        </span>
      </label>
      <div className="bid-checklist__item-content">
        <div className="bid-checklist__item-header">
          <span className="bid-checklist__item-requirement">{requirement.requirement}</span>
          {requirement.mandatory ? (
            <span className="bid-checklist__item-badge bid-checklist__item-badge--mandatory">Required</span>
          ) : (
            <span className="bid-checklist__item-badge bid-checklist__item-badge--optional">Optional</span>
          )}
        </div>
        <p className="bid-checklist__item-document">
          <span className="mdi mdi-file-document-outline"></span>
          {requirement.document_needed}
        </p>
        {requirement.issuing_authority && (
          <p className="bid-checklist__item-authority">
            <span className="mdi mdi-domain"></span>
            Issuing authority: {requirement.issuing_authority}
            {requirement.website && (
              <a href={requirement.website} target="_blank" rel="noopener noreferrer">
                <span className="mdi mdi-open-in-new"></span>
              </a>
            )}
          </p>
        )}
      </div>
      <button className="bid-checklist__item-help" onClick={onAskHelp} title="Get help with this requirement">
        <span className="mdi mdi-help-circle"></span>
      </button>
    </div>
  );
};

// Default ESPD requirements when API is unavailable
function getDefaultRequirements(_country: string): ESPDRequirement[] {
  const requirements: ESPDRequirement[] = [
    // Part III - Exclusion Grounds
    {
      id: 'exc-a1',
      type: 'exclusion',
      category: 'A - Criminal convictions',
      requirement: 'No convictions for participation in criminal organisation',
      document_needed: 'Criminal record certificate or self-declaration',
      mandatory: true,
    },
    {
      id: 'exc-a2',
      type: 'exclusion',
      category: 'A - Criminal convictions',
      requirement: 'No convictions for corruption',
      document_needed: 'Criminal record certificate or self-declaration',
      mandatory: true,
    },
    {
      id: 'exc-a3',
      type: 'exclusion',
      category: 'A - Criminal convictions',
      requirement: 'No convictions for fraud',
      document_needed: 'Criminal record certificate or self-declaration',
      mandatory: true,
    },
    {
      id: 'exc-a4',
      type: 'exclusion',
      category: 'A - Criminal convictions',
      requirement: 'No convictions for money laundering or terrorist financing',
      document_needed: 'Criminal record certificate or self-declaration',
      mandatory: true,
    },
    {
      id: 'exc-b1',
      type: 'exclusion',
      category: 'B - Payment of taxes',
      requirement: 'No outstanding tax obligations',
      document_needed: 'Tax compliance certificate',
      mandatory: true,
    },
    {
      id: 'exc-b2',
      type: 'exclusion',
      category: 'B - Payment of social security',
      requirement: 'No outstanding social security contributions',
      document_needed: 'Social security compliance certificate',
      mandatory: true,
    },
    {
      id: 'exc-c1',
      type: 'exclusion',
      category: 'C - Insolvency',
      requirement: 'Not in bankruptcy or insolvency proceedings',
      document_needed: 'Certificate from commercial register or self-declaration',
      mandatory: true,
    },
    {
      id: 'exc-d1',
      type: 'exclusion',
      category: 'D - Professional misconduct',
      requirement: 'No grave professional misconduct',
      document_needed: 'Self-declaration',
      mandatory: true,
    },
    {
      id: 'exc-d2',
      type: 'exclusion',
      category: 'D - Conflicts of interest',
      requirement: 'No conflicts of interest with contracting authority',
      document_needed: 'Self-declaration',
      mandatory: true,
    },

    // Part IV - Selection Criteria
    {
      id: 'sel-a1',
      type: 'selection',
      category: 'A - Professional suitability',
      requirement: 'Enrolled in relevant professional register',
      document_needed: 'Extract from professional/trade register',
      mandatory: true,
    },
    {
      id: 'sel-a2',
      type: 'selection',
      category: 'A - Professional suitability',
      requirement: 'Authorized to perform the contract activities',
      document_needed: 'Authorization or license certificate',
      mandatory: false,
    },
    {
      id: 'sel-b1',
      type: 'selection',
      category: 'B - Economic and financial standing',
      requirement: 'Minimum annual turnover in the relevant business area',
      document_needed: 'Audited financial statements (last 3 years)',
      mandatory: true,
    },
    {
      id: 'sel-b2',
      type: 'selection',
      category: 'B - Economic and financial standing',
      requirement: 'Professional liability insurance',
      document_needed: 'Insurance certificate',
      mandatory: false,
    },
    {
      id: 'sel-c1',
      type: 'selection',
      category: 'C - Technical and professional ability',
      requirement: 'References from similar projects',
      document_needed: 'List of principal deliveries/services (last 3-5 years)',
      mandatory: true,
    },
    {
      id: 'sel-c2',
      type: 'selection',
      category: 'C - Technical and professional ability',
      requirement: 'Qualified technical staff',
      document_needed: 'CVs of key personnel, educational/professional qualifications',
      mandatory: true,
    },
    {
      id: 'sel-c3',
      type: 'selection',
      category: 'C - Technical and professional ability',
      requirement: 'Technical equipment and tools',
      document_needed: 'Description of technical equipment and facilities',
      mandatory: false,
    },
    {
      id: 'sel-d1',
      type: 'selection',
      category: 'D - Quality assurance',
      requirement: 'Quality management certification',
      document_needed: 'ISO 9001 certificate or equivalent',
      mandatory: false,
    },
    {
      id: 'sel-d2',
      type: 'selection',
      category: 'D - Environmental management',
      requirement: 'Environmental management certification',
      document_needed: 'ISO 14001 certificate, EMAS registration, or equivalent',
      mandatory: false,
    },
  ];

  return requirements;
}
