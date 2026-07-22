/**
 * Sectors selector — controlled vocabulary of the 20 EU economic-activity
 * categories Brubru personalises against. Pure UI; persistence is done by
 * the parent via `onUpdate` (which calls the auth /me PATCH endpoint).
 */

import { useTranslation } from 'react-i18next';
import './sectors_selector.css';

export interface SectorOption {
  slug: string;
  label: string;
  description: string;
}

// `label` / `description` are the English defaults; translated strings live
// under `sectors.<slug>.label` / `sectors.<slug>.description` and are
// resolved at render time.

export const SECTORS: SectorOption[] = [
  { slug: 'agriculture_food', label: 'Agriculture & Food', description: 'Farming, food processing, agri-trade' },
  { slug: 'automotive_mobility', label: 'Automotive & Mobility', description: 'Vehicles, batteries, mobility services' },
  { slug: 'banking_finance', label: 'Banking, Finance & Insurance', description: 'Credit, capital markets, insurance' },
  { slug: 'chemicals_pharma', label: 'Chemicals & Pharmaceuticals', description: 'Industrial chemicals, medicines, biotech' },
  { slug: 'construction_real_estate', label: 'Construction & Real Estate', description: 'Buildings, infrastructure, property' },
  { slug: 'defence_aerospace', label: 'Defence & Aerospace', description: 'Defence industry, space, dual-use tech' },
  { slug: 'digital_tech', label: 'Digital & Tech', description: 'Software, AI, cloud, telecoms, platforms' },
  { slug: 'education_research', label: 'Education & Research', description: 'Universities, schools, research orgs' },
  { slug: 'energy_utilities', label: 'Energy & Utilities', description: 'Electricity, gas, hydrogen, grid' },
  { slug: 'environment_climate', label: 'Environment & Climate', description: 'Environmental NGOs, climate consultancies' },
  { slug: 'health_social_care', label: 'Health & Social Care', description: 'Hospitals, providers, public health' },
  { slug: 'manufacturing_industry', label: 'Manufacturing & Industry', description: 'Heavy industry, steel, materials' },
  { slug: 'maritime_fisheries', label: 'Maritime & Fisheries', description: 'Shipping, ports, fishing' },
  { slug: 'media_communication', label: 'Media & Communication', description: 'Publishers, broadcasters, advertising' },
  { slug: 'mining_raw_materials', label: 'Mining & Raw Materials', description: 'Critical raw materials, mining' },
  { slug: 'public_sector', label: 'Public Sector', description: 'Government, agencies, municipalities' },
  { slug: 'retail_consumer', label: 'Retail & Consumer Goods', description: 'Retailers, consumer brands, e-commerce' },
  { slug: 'services_consulting', label: 'Services & Consulting', description: 'Legal, advisory, professional services' },
  { slug: 'transport_logistics', label: 'Transport & Logistics', description: 'Logistics, rail, air, road freight' },
  { slug: 'civil_society', label: 'Civil Society & NGOs', description: 'Advocacy, foundations, think tanks' },
];

interface SectorsSelectorProps {
  selectedSectors: string[];
  onUpdate: (sectors: string[]) => void;
}

export const SectorsSelector = ({ selectedSectors, onUpdate }: SectorsSelectorProps) => {
  const { t } = useTranslation();

  const toggle = (slug: string) => {
    if (selectedSectors.includes(slug)) {
      onUpdate(selectedSectors.filter((s) => s !== slug));
    } else {
      onUpdate([...selectedSectors, slug]);
    }
  };

  return (
    <div className="sectors-selector">
      <div className="sectors-selector__hint">
        {t('sectors.hint', 'Select the sectors you operate in. Brubru uses these to filter Dashboard tiles, calendar events, and consultations to what matters to you.')}
      </div>
      <div className="sectors-selector__grid">
        {SECTORS.map((sector) => {
          const selected = selectedSectors.includes(sector.slug);
          return (
            <button
              type="button"
              key={sector.slug}
              className={`sectors-selector__chip ${
                selected ? 'sectors-selector__chip--selected' : ''
              }`}
              onClick={() => toggle(sector.slug)}
              aria-pressed={selected}
            >
              <span className="sectors-selector__label">{t(`sectors.${sector.slug}.label`, sector.label)}</span>
              <span className="sectors-selector__desc">{t(`sectors.${sector.slug}.description`, sector.description)}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};
