/**
 * Background Selector Component
 *
 * Allows users to choose a personalized background for their pages
 */

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import './background_selector.css';

interface BackgroundSelectorProps {
  selectedBackground: string;
  onSelect: (background: string) => void;
}

// Available backgrounds from /public/assets/backgrounds.
// `name` is the English default; `nameKey` resolves the translated label.
const BACKGROUNDS = [
  { id: 'default', nameKey: 'profile.backgrounds.default', name: 'Default', preview: null },
  { id: 'amsterdam.jpg', nameKey: 'profile.backgrounds.amsterdam', name: 'Amsterdam', preview: '/assets/backgrounds/amsterdam.jpg' },
  { id: 'amsterdam_canals.jpg', nameKey: 'profile.backgrounds.amsterdamCanals', name: 'Amsterdam Canals', preview: '/assets/backgrounds/amsterdam_canals.jpg' },
  { id: 'athens.jpg', nameKey: 'profile.backgrounds.athens', name: 'Athens', preview: '/assets/backgrounds/athens.jpg' },
  { id: 'aurora.jpg', nameKey: 'profile.backgrounds.aurora', name: 'Aurora Borealis', preview: '/assets/backgrounds/aurora.jpg' },
  { id: 'barcelona.jpg', nameKey: 'profile.backgrounds.barcelona', name: 'Barcelona', preview: '/assets/backgrounds/barcelona.jpg' },
  { id: 'brussels.jpg', nameKey: 'profile.backgrounds.brussels', name: 'Brussels', preview: '/assets/backgrounds/brussels.jpg' },
  { id: 'canal.jpg', nameKey: 'profile.backgrounds.canal', name: 'Canal', preview: '/assets/backgrounds/canal.jpg' },
  { id: 'church.jpg', nameKey: 'profile.backgrounds.church', name: 'Church', preview: '/assets/backgrounds/church.jpg' },
  { id: 'colosseo.jpg', nameKey: 'profile.backgrounds.colosseum', name: 'Colosseum', preview: '/assets/backgrounds/colosseo.jpg' },
  { id: 'dome.jpg', nameKey: 'profile.backgrounds.dome', name: 'Dome', preview: '/assets/backgrounds/dome.jpg' },
  { id: 'eu.jpg', nameKey: 'profile.backgrounds.eu', name: 'European Union', preview: '/assets/backgrounds/eu.jpg' },
  { id: 'firenze.jpg', nameKey: 'profile.backgrounds.florence', name: 'Florence', preview: '/assets/backgrounds/firenze.jpg' },
  { id: 'greece.jpg', nameKey: 'profile.backgrounds.greece', name: 'Greece', preview: '/assets/backgrounds/greece.jpg' },
  { id: 'lake.jpg', nameKey: 'profile.backgrounds.lake', name: 'Lake', preview: '/assets/backgrounds/lake.jpg' },
  { id: 'london.jpg', nameKey: 'profile.backgrounds.london', name: 'London', preview: '/assets/backgrounds/london.jpg' },
  { id: 'map.jpg', nameKey: 'profile.backgrounds.map', name: 'Map', preview: '/assets/backgrounds/map.jpg' },
  { id: 'map_car.jpg', nameKey: 'profile.backgrounds.mapCompass', name: 'Map & Compass', preview: '/assets/backgrounds/map_car.jpg' },
  { id: 'netherlands.jpg', nameKey: 'profile.backgrounds.netherlands', name: 'Netherlands', preview: '/assets/backgrounds/netherlands.jpg' },
  { id: 'paris.jpg', nameKey: 'profile.backgrounds.paris', name: 'Paris', preview: '/assets/backgrounds/paris.jpg' },
  { id: 'santorini.jpg', nameKey: 'profile.backgrounds.santorini', name: 'Santorini', preview: '/assets/backgrounds/santorini.jpg' },
  { id: 'venezia.jpg', nameKey: 'profile.backgrounds.venice', name: 'Venice', preview: '/assets/backgrounds/venezia.jpg' },
];

export const BackgroundSelector = ({ selectedBackground, onSelect }: BackgroundSelectorProps) => {
  const { t } = useTranslation();
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="background-selector">
      <div className="background-selector__current">
        <div className="background-selector__preview">
          {selectedBackground === 'default' ? (
            <div className="background-selector__preview-default">
              <span>{t('profile.backgrounds.defaultBackground', 'Default Background')}</span>
            </div>
          ) : (
            <img
              src={`/assets/backgrounds/${selectedBackground}`}
              alt={t('profile.backgrounds.selectedAlt', 'Selected background')}
              className="background-selector__preview-image"
            />
          )}
        </div>
        <button
          type="button"
          className="background-selector__toggle"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          {isExpanded
            ? t('profile.backgrounds.hide', 'Hide Backgrounds')
            : t('profile.backgrounds.change', 'Change Background')}
        </button>
      </div>

      {isExpanded && (
        <div className="background-selector__grid">
          {BACKGROUNDS.map(bg => (
            <button
              key={bg.id}
              type="button"
              className={`background-selector__item ${
                selectedBackground === bg.id ? 'background-selector__item--selected' : ''
              }`}
              onClick={() => onSelect(bg.id)}
            >
              {bg.preview ? (
                <img
                  src={bg.preview}
                  alt={t(bg.nameKey, bg.name)}
                  className="background-selector__item-image"
                />
              ) : (
                <div className="background-selector__item-default">
                  <span>{t('profile.backgrounds.default', 'Default')}</span>
                </div>
              )}
              <div className="background-selector__item-name">{t(bg.nameKey, bg.name)}</div>
              {selectedBackground === bg.id && (
                <div className="background-selector__item-check">✓</div>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
