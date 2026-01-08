/**
 * Background Selector Component
 *
 * Allows users to choose a personalized background for their pages
 */

import { useState } from 'react';
import './background_selector.css';

interface BackgroundSelectorProps {
  selectedBackground: string;
  onSelect: (background: string) => void;
}

// Available backgrounds from /public/assets/backgrounds
const BACKGROUNDS = [
  { id: 'default', name: 'Default', preview: null },
  { id: 'amsterdam.jpg', name: 'Amsterdam', preview: '/assets/backgrounds/amsterdam.jpg' },
  { id: 'amsterdam_canals.jpg', name: 'Amsterdam Canals', preview: '/assets/backgrounds/amsterdam_canals.jpg' },
  { id: 'athens.jpg', name: 'Athens', preview: '/assets/backgrounds/athens.jpg' },
  { id: 'aurora.jpg', name: 'Aurora Borealis', preview: '/assets/backgrounds/aurora.jpg' },
  { id: 'barcelona.jpg', name: 'Barcelona', preview: '/assets/backgrounds/barcelona.jpg' },
  { id: 'brussels.jpg', name: 'Brussels', preview: '/assets/backgrounds/brussels.jpg' },
  { id: 'canal.jpg', name: 'Canal', preview: '/assets/backgrounds/canal.jpg' },
  { id: 'church.jpg', name: 'Church', preview: '/assets/backgrounds/church.jpg' },
  { id: 'colosseo.jpg', name: 'Colosseum', preview: '/assets/backgrounds/colosseo.jpg' },
  { id: 'dome.jpg', name: 'Dome', preview: '/assets/backgrounds/dome.jpg' },
  { id: 'eu.jpg', name: 'European Union', preview: '/assets/backgrounds/eu.jpg' },
  { id: 'firenze.jpg', name: 'Florence', preview: '/assets/backgrounds/firenze.jpg' },
  { id: 'greece.jpg', name: 'Greece', preview: '/assets/backgrounds/greece.jpg' },
  { id: 'lake.jpg', name: 'Lake', preview: '/assets/backgrounds/lake.jpg' },
  { id: 'london.jpg', name: 'London', preview: '/assets/backgrounds/london.jpg' },
  { id: 'map.jpg', name: 'Map', preview: '/assets/backgrounds/map.jpg' },
  { id: 'map_car.jpg', name: 'Map & Compass', preview: '/assets/backgrounds/map_car.jpg' },
  { id: 'netherlands.jpg', name: 'Netherlands', preview: '/assets/backgrounds/netherlands.jpg' },
  { id: 'paris.jpg', name: 'Paris', preview: '/assets/backgrounds/paris.jpg' },
  { id: 'santorini.jpg', name: 'Santorini', preview: '/assets/backgrounds/santorini.jpg' },
  { id: 'venezia.jpg', name: 'Venice', preview: '/assets/backgrounds/venezia.jpg' },
];

export const BackgroundSelector = ({ selectedBackground, onSelect }: BackgroundSelectorProps) => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="background-selector">
      <div className="background-selector__current">
        <div className="background-selector__preview">
          {selectedBackground === 'default' ? (
            <div className="background-selector__preview-default">
              <span>Default Background</span>
            </div>
          ) : (
            <img
              src={`/assets/backgrounds/${selectedBackground}`}
              alt="Selected background"
              className="background-selector__preview-image"
            />
          )}
        </div>
        <button
          type="button"
          className="background-selector__toggle"
          onClick={() => setIsExpanded(!isExpanded)}
        >
          {isExpanded ? 'Hide Backgrounds' : 'Change Background'}
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
                  alt={bg.name}
                  className="background-selector__item-image"
                />
              ) : (
                <div className="background-selector__item-default">
                  <span>Default</span>
                </div>
              )}
              <div className="background-selector__item-name">{bg.name}</div>
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
