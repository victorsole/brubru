import { useState } from 'react';
import './policy_preferences_selector.css';

interface PolicyArea {
  name: string;
  url: string;
  description: string;
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

const POLICY_CATEGORIES: PolicyCategory[] = [
  {
    category: 'Core Economic and Market Policies',
    description: '7 areas',
    policy_areas: [
      { name: 'Single Market', url: '', description: 'Free movement of goods, services, capital, and people' },
      { name: 'Competition', url: '', description: 'Ensuring fair competition and preventing monopolies' },
      { name: 'Trade and Economic Security', url: '', description: 'EU trade policy and international economic relations' },
      { name: 'Economic and Financial Affairs', url: '', description: 'Economic policy coordination and financial stability' },
      { name: 'Taxation', url: '', description: 'Tax policy coordination across member states' },
      { name: 'Customs', url: '', description: 'Customs union and border control procedures' },
      { name: 'Business and Industry', url: '', description: 'Industrial policy and business competitiveness' }
    ]
  },
  {
    category: 'Sustainability and Environmental Policies',
    description: '4 areas (European Green Deal)',
    policy_areas: [
      { name: 'Climate Action', url: '', description: 'EU climate policies and carbon reduction' },
      { name: 'Environment', url: '', description: 'Environmental protection and biodiversity' },
      { name: 'Energy', url: '', description: 'Energy policy and renewable energy transition' },
      { name: 'Transport', url: '', description: 'Transport policy and sustainable mobility' }
    ]
  },
  {
    category: 'Digital Transformation',
    description: '2 areas (Europe Fit for Digital Age)',
    policy_areas: [
      { name: 'Digital Policy and Digital Economy', url: '', description: 'Digital single market and e-commerce' },
      { name: 'Communication Networks, Content and Technology', url: '', description: 'Telecommunications and digital infrastructure' }
    ]
  },
  {
    category: 'Agriculture and Natural Resources',
    description: '3 areas',
    policy_areas: [
      { name: 'Agriculture', url: '', description: 'Common Agricultural Policy and rural development' },
      { name: 'Maritime Affairs and Fisheries', url: '', description: 'Fisheries policy and blue economy' },
      { name: 'Food Safety', url: '', description: 'Food standards and safety regulations' }
    ]
  },
  {
    category: 'Cohesion and Development',
    description: '4 areas',
    policy_areas: [
      { name: 'Regional Policy', url: '', description: 'Cohesion policy and regional development' },
      { name: 'Research and Innovation', url: '', description: 'Horizon Europe and research funding' },
      { name: 'Education, Training and Youth', url: '', description: 'Erasmus+ and education policies' },
      { name: 'Culture', url: '', description: 'Cultural programmes and creative industries' }
    ]
  },
  {
    category: 'Social Policies',
    description: '3 areas',
    policy_areas: [
      { name: 'Employment and Social Affairs', url: '', description: 'Labour rights and social protection' },
      { name: 'Health', url: '', description: 'Public health and healthcare policies' },
      { name: 'Consumer Protection', url: '', description: 'Consumer rights and product safety' }
    ]
  },
  {
    category: 'Justice and Home Affairs',
    description: '3 areas',
    policy_areas: [
      { name: 'Justice and Fundamental Rights', url: '', description: 'Rule of law and fundamental rights' },
      { name: 'Migration and Home Affairs', url: '', description: 'Migration policy and border management' },
      { name: 'Women\'s Rights and Gender Equality', url: '', description: 'Gender equality and women\'s empowerment' }
    ]
  },
  {
    category: 'External Relations',
    description: '5 areas',
    policy_areas: [
      { name: 'Foreign and Security Policy', url: '', description: 'Common foreign and security policy' },
      { name: 'Development and Cooperation', url: '', description: 'International development aid' },
      { name: 'Neighbourhood and Enlargement', url: '', description: 'Enlargement and neighbourhood policy' },
      { name: 'Human Rights and Democracy', url: '', description: 'Global human rights advocacy' },
      { name: 'Humanitarian Aid and Civil Protection', url: '', description: 'Emergency response and disaster relief' }
    ]
  },
  {
    category: 'Emerging Strategic Areas',
    description: '3 areas',
    policy_areas: [
      { name: 'Defence and Security', url: '', description: 'European defence and security cooperation' },
      { name: 'Space Policy', url: '', description: 'EU space programme and satellite systems' },
      { name: 'Statistics', url: '', description: 'Eurostat and statistical data' }
    ]
  }
];

export const PolicyPreferencesSelector = ({
  selectedPolicies,
  onUpdate
}: PolicyPreferencesSelectorProps) => {
  const [selected, setSelected] = useState<string[]>(selectedPolicies || []);
  const [expandedCategories, setExpandedCategories] = useState<string[]>([]);

  const toggleCategory = (category: string) => {
    setExpandedCategories(prev =>
      prev.includes(category)
        ? prev.filter(c => c !== category)
        : [...prev, category]
    );
  };

  const togglePolicy = (policyName: string) => {
    let newSelected: string[];

    if (selected.includes(policyName)) {
      newSelected = selected.filter(p => p !== policyName);
    } else {
      newSelected = [...selected, policyName];
    }

    setSelected(newSelected);
    onUpdate(newSelected);
  };

  const selectAll = () => {
    const allPolicies = POLICY_CATEGORIES.flatMap(cat =>
      cat.policy_areas.map(pa => pa.name)
    );
    setSelected(allPolicies);
    onUpdate(allPolicies);
  };

  const clearAll = () => {
    setSelected([]);
    onUpdate([]);
  };

  return (
    <div className="policy-preferences">
      <div className="policy-preferences__header">
        <p className="policy-preferences__count">
          Selected: <strong>{selected.length}</strong> policy {selected.length === 1 ? 'area' : 'areas'}
        </p>
        <div className="policy-preferences__header-actions">
          <button
            onClick={selectAll}
            className="policy-preferences__select-all"
            disabled={selected.length === POLICY_CATEGORIES.flatMap(cat => cat.policy_areas).length}
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

      <div className="policy-preferences__categories">
        {POLICY_CATEGORIES.map((category) => {
          const isExpanded = expandedCategories.includes(category.category);
          const categorySelectedCount = category.policy_areas.filter(pa =>
            selected.includes(pa.name)
          ).length;

          return (
            <div key={category.category} className="policy-preferences__category">
              <button
                className="policy-preferences__category-header"
                onClick={() => toggleCategory(category.category)}
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
                  {category.policy_areas.map((policy) => {
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
