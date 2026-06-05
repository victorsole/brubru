import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Icon from '@mdi/react';
import { mdiMagnify, mdiClose, mdiChatProcessingOutline } from '@mdi/js';
import './policy_preferences_selector.css';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

interface PolicyArea {
  name: string;
  description: string;
  aliases?: string[];
}

interface PolicyCategory {
  category: string;
  description: string;
  policy_areas: PolicyArea[];
}

interface PolicyPreferencesSelectorProps {
  selectedPolicies: string[];
  onUpdate: (policies: string[]) => void;
}


/** Lower-case + strip diacritics so "Turkiye"/"turkiye"/accented forms all match. */
const normalise = (value: string): string =>
  value.toLowerCase().normalize('NFD').replace(new RegExp('[\\u0300-\\u036f]', 'g'), '');

export const PolicyPreferencesSelector = ({
  selectedPolicies,
  onUpdate
}: PolicyPreferencesSelectorProps) => {
  const navigate = useNavigate();
  const [selected, setSelected] = useState<string[]>(selectedPolicies || []);
  const [expandedCategories, setExpandedCategories] = useState<string[]>([]);
  const [query, setQuery] = useState('');

  // Canonical taxonomy is served by the backend (single source of truth shared
  // with the Chat). The selector renders identically; it just no longer owns
  // the list. See backend/knowledge_base/policy_taxonomy.json.
  const [taxonomy, setTaxonomy] = useState<PolicyCategory[]>([]);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE_URL}/api/policy-taxonomy`)
      .then((r) => r.json())
      .then((data) => {
        if (!cancelled && Array.isArray(data?.categories)) setTaxonomy(data.categories);
      })
      .catch(() => { /* keep empty; the no-results / loading state covers it */ });
    return () => { cancelled = true; };
  }, []);

  const normalisedQuery = normalise(query.trim());
  const isSearching = normalisedQuery.length > 0;

  // Filter the tree by the search query, matching against category labels, leaf names,
  // leaf descriptions and the seed alias keywords. Returns each surviving category with
  // only its matching leaves.
  const filteredCategories = useMemo(() => {
    if (!isSearching) {
      return taxonomy.map((category) => ({ category, matches: category.policy_areas }));
    }

    return taxonomy
      .map((category) => {
        const categoryHaystack = `${normalise(category.category)} ${normalise(category.description)}`;
        const categoryMatches = categoryHaystack.includes(normalisedQuery);

        const matches = category.policy_areas.filter((policy) => {
          if (categoryMatches) return true;
          const aliasHaystack = (policy.aliases || []).map(normalise).join(' ');
          const haystack = `${normalise(policy.name)} ${normalise(policy.description)} ${aliasHaystack}`;
          return haystack.includes(normalisedQuery);
        });

        return { category, matches };
      })
      .filter((entry) => entry.matches.length > 0);
  }, [isSearching, normalisedQuery, taxonomy]);

  const totalPolicies = taxonomy.flatMap((cat) => cat.policy_areas).length;

  const toggleCategory = (category: string) => {
    setExpandedCategories((prev) =>
      prev.includes(category)
        ? prev.filter((c) => c !== category)
        : [...prev, category]
    );
  };

  const togglePolicy = (policyName: string) => {
    const newSelected = selected.includes(policyName)
      ? selected.filter((p) => p !== policyName)
      : [...selected, policyName];

    setSelected(newSelected);
    onUpdate(newSelected);
  };

  const selectAll = () => {
    const allPolicies = taxonomy.flatMap((cat) => cat.policy_areas.map((pa) => pa.name));
    setSelected(allPolicies);
    onUpdate(allPolicies);
  };

  const clearAll = () => {
    setSelected([]);
    onUpdate([]);
  };

  // Hand the exact thing the user couldn't find (their current search query)
  // to the Chat, flagged as a policy-interest navigation request so the backend
  // routes it to the lightweight taxonomy-mapping flow.
  const askBrubru = () => {
    const params = new URLSearchParams({ context: 'policy_interests' });
    const q = query.trim();
    if (q) {
      params.set('q', q);
      params.set('autofire', '1');
    }
    navigate(`/main?${params.toString()}`);
  };

  return (
    <div className="policy-preferences">
      <div className="policy-preferences__search">
        <Icon path={mdiMagnify} size={0.85} className="policy-preferences__search-icon" />
        <input
          type="search"
          className="policy-preferences__search-input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search policies, e.g. agriculture, trade defence, drones, refugees…"
          aria-label="Search policy areas"
        />
        {query.length > 0 && (
          <button
            type="button"
            className="policy-preferences__search-clear"
            onClick={() => setQuery('')}
            aria-label="Clear search"
          >
            <Icon path={mdiClose} size={0.75} />
          </button>
        )}
      </div>

      <button
        type="button"
        className="policy-preferences__ask-brubru"
        onClick={askBrubru}
      >
        <Icon path={mdiChatProcessingOutline} size={0.8} />
        <span>Can&rsquo;t find what you are looking for? Talk to Brubru!</span>
      </button>

      <div className="policy-preferences__header">
        <p className="policy-preferences__count">
          Selected: <strong>{selected.length}</strong> policy {selected.length === 1 ? 'area' : 'areas'}
        </p>
        <div className="policy-preferences__header-actions">
          <button
            onClick={selectAll}
            className="policy-preferences__select-all"
            disabled={selected.length === totalPolicies}
          >
            Select All
          </button>
          {selected.length > 0 && (
            <button
              onClick={clearAll}
              className="policy-preferences__clear"
            >
              Clear All
            </button>
          )}
        </div>
      </div>

      {isSearching && filteredCategories.length === 0 ? (
        <div className="policy-preferences__no-results">
          <p>
            No policy areas match <strong>&ldquo;{query.trim()}&rdquo;</strong>.
          </p>
          <p className="policy-preferences__no-results-hint">
            Try a broader term, or clear the search to browse all areas.
          </p>
        </div>
      ) : (
        <div className="policy-preferences__categories">
          {filteredCategories.map(({ category, matches }) => {
            const isExpanded = isSearching || expandedCategories.includes(category.category);
            const categorySelectedCount = category.policy_areas.filter((pa) =>
              selected.includes(pa.name)
            ).length;

            return (
              <div key={category.category} className="policy-preferences__category">
                <button
                  className="policy-preferences__category-header"
                  onClick={() => toggleCategory(category.category)}
                  disabled={isSearching}
                >
                  <div className="policy-preferences__category-title">
                    <span className="policy-preferences__category-icon">
                      {isExpanded ? '▼' : '▶'}
                    </span>
                    <div>
                      <h3>{category.category}</h3>
                      <span className="policy-preferences__category-description">
                        {category.description}
                        {categorySelectedCount > 0 && (
                          <span className="policy-preferences__category-selected">
                            {' '}• {categorySelectedCount} selected
                          </span>
                        )}
                      </span>
                    </div>
                  </div>
                </button>

                {isExpanded && (
                  <div className="policy-preferences__policies">
                    {matches.map((policy) => {
                      const isSelected = selected.includes(policy.name);

                      return (
                        <label
                          key={policy.name}
                          className={`policy-preferences__policy ${
                            isSelected ? 'policy-preferences__policy--selected' : ''
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => togglePolicy(policy.name)}
                            className="policy-preferences__checkbox"
                          />
                          <div className="policy-preferences__policy-content">
                            <span className="policy-preferences__policy-name">
                              {policy.name}
                            </span>
                            <span className="policy-preferences__policy-description">
                              {policy.description}
                            </span>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {selected.length > 0 && (
        <div className="policy-preferences__selected-tags">
          <h4>Your selected policy areas:</h4>
          <div className="policy-preferences__tags">
            {selected.map((policyName) => (
              <span key={policyName} className="policy-preferences__tag">
                {policyName}
                <button
                  onClick={() => togglePolicy(policyName)}
                  className="policy-preferences__tag-remove"
                  aria-label={`Remove ${policyName}`}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
