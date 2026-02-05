import { useRef, useEffect, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { motion } from 'framer-motion';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Map as MapIcon } from 'lucide-react';
import { COUNTRY_STARTUP_DATA } from '@/data/startupFallback';
import type { CountryStartupData, MapMetric } from '@/types/startup';

// All countries to display (EU-27 + associated)
const ALL_COUNTRIES = [
  'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR',
  'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL',
  'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE',
  // Non-EU countries
  'GB', 'CH', 'NO', 'UA', 'RS', 'ME', 'MK', 'AL', 'TR'
];

const EU_COUNTRIES = [
  'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR',
  'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL',
  'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'
];

// ISO-3 to ISO-2 mapping
const ISO3_TO_ISO2: Record<string, string> = {
  AUT: 'AT', BEL: 'BE', BGR: 'BG', HRV: 'HR', CYP: 'CY', CZE: 'CZ',
  DNK: 'DK', EST: 'EE', FIN: 'FI', FRA: 'FR', DEU: 'DE', GRC: 'GR',
  HUN: 'HU', IRL: 'IE', ITA: 'IT', LVA: 'LV', LTU: 'LT', LUX: 'LU',
  MLT: 'MT', NLD: 'NL', POL: 'PL', PRT: 'PT', ROU: 'RO', SVK: 'SK',
  SVN: 'SI', ESP: 'ES', SWE: 'SE', GBR: 'GB', CHE: 'CH', NOR: 'NO',
  UKR: 'UA', SRB: 'RS', MNE: 'ME', MKD: 'MK', ALB: 'AL', TUR: 'TR'
};

const COLOR_SCALES: Record<MapMetric, { min: string; max: string }> = {
  unicorns: { min: '#dcfce7', max: '#166534' },
  funding: { min: '#dbeafe', max: '#1e40af' },
  rank: { min: '#ffedd5', max: '#c2410c' },
};

const METRIC_CONFIG: Record<MapMetric, { label: string; getValue: (d: CountryStartupData) => number; format: (v: number) => string }> = {
  unicorns: {
    label: 'Unicorns',
    getValue: (d) => d.unicorns,
    format: (v) => v.toString(),
  },
  funding: {
    label: '2024 Funding',
    getValue: (d) => {
      const str = d.funding2024;
      if (str === '-') return 0;
      const num = parseFloat(str.replace(/[$B]/g, '').replace('M', ''));
      return str.includes('B') ? num * 1000 : num;
    },
    format: (v) => v >= 1000 ? `$${(v/1000).toFixed(1)}B` : `$${v.toFixed(0)}M`,
  },
  rank: {
    label: 'Global Rank',
    getValue: (d) => 100 - d.globalRank, // Invert so higher is better
    format: (v) => `#${100 - v}`,
  },
};

interface StartupEcosystemMapProps {
  className?: string;
}

function getColor(value: number, min: number, max: number, colorScale: { min: string; max: string }) {
  const ratio = max === min ? 0.5 : (value - min) / (max - min);
  const parseHex = (hex: string) => {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
      r: parseInt(result[1], 16),
      g: parseInt(result[2], 16),
      b: parseInt(result[3], 16)
    } : { r: 0, g: 0, b: 0 };
  };
  const minColor = parseHex(colorScale.min);
  const maxColor = parseHex(colorScale.max);
  const r = Math.round(minColor.r + (maxColor.r - minColor.r) * ratio);
  const g = Math.round(minColor.g + (maxColor.g - minColor.g) * ratio);
  const b = Math.round(minColor.b + (maxColor.b - minColor.b) * ratio);
  return `rgb(${r}, ${g}, ${b})`;
}

export function StartupEcosystemMap({ className = '' }: StartupEcosystemMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const popup = useRef<maplibregl.Popup | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [activeMetric, setActiveMetric] = useState<MapMetric>('unicorns');

  // Create data lookup (ISO-3 to data)
  const dataLookup = new Map(COUNTRY_STARTUP_DATA.map(d => [d.iso, d]));

  // Calculate min/max for current metric
  const config = METRIC_CONFIG[activeMetric];
  const values = COUNTRY_STARTUP_DATA.map(d => config.getValue(d)).filter(v => v > 0);
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);

  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          'carto': {
            type: 'raster',
            tiles: [
              'https://a.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}.png',
              'https://b.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}.png',
              'https://c.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}.png',
            ],
            tileSize: 256,
            attribution: '&copy; <a href="https://carto.com/">CARTO</a>',
          },
        },
        layers: [
          {
            id: 'carto-basemap',
            type: 'raster',
            source: 'carto',
            minzoom: 0,
            maxzoom: 19,
          },
        ],
      },
      center: [15, 50],
      zoom: 3.3,
      minZoom: 2,
      maxZoom: 8,
    });

    map.current.addControl(new maplibregl.NavigationControl(), 'top-right');

    popup.current = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      className: 'startup-map-popup',
    });

    map.current.on('load', () => {
      setMapLoaded(true);

      map.current!.addSource('countries', {
        type: 'geojson',
        data: 'https://d2ad6b4ur7yvpq.cloudfront.net/naturalearth-3.3.0/ne_50m_admin_0_countries.geojson',
      });

      // Add fill layer for all tracked countries
      map.current!.addLayer({
        id: 'country-fills',
        type: 'fill',
        source: 'countries',
        paint: {
          'fill-color': '#e0e0e0',
          'fill-opacity': 0.9,
        },
        filter: ['in', ['get', 'iso_a2'], ['literal', ALL_COUNTRIES]],
      });

      // Border layer
      map.current!.addLayer({
        id: 'country-borders',
        type: 'line',
        source: 'countries',
        paint: {
          'line-color': '#ffffff',
          'line-width': 1,
        },
        filter: ['in', ['get', 'iso_a2'], ['literal', ALL_COUNTRIES]],
      });

      // Highlight layer
      map.current!.addLayer({
        id: 'country-highlight',
        type: 'line',
        source: 'countries',
        paint: {
          'line-color': '#1a472a',
          'line-width': 2.5,
        },
        filter: ['==', ['get', 'iso_a2'], ''],
      });

      // Dashed border for non-EU countries
      map.current!.addLayer({
        id: 'non-eu-borders',
        type: 'line',
        source: 'countries',
        paint: {
          'line-color': '#9ca3af',
          'line-width': 1.5,
          'line-dasharray': [3, 2],
        },
        filter: ['all',
          ['in', ['get', 'iso_a2'], ['literal', ['GB', 'CH', 'NO', 'UA', 'RS', 'ME', 'MK', 'AL', 'TR']]],
        ],
      });
    });

    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, []);

  // Update colors when metric changes
  useEffect(() => {
    if (!map.current || !mapLoaded) return;

    const colorScale = COLOR_SCALES[activeMetric];
    const colorExpression: maplibregl.ExpressionSpecification = ['case'];

    COUNTRY_STARTUP_DATA.forEach((d) => {
      const iso2 = ISO3_TO_ISO2[d.iso];
      if (!iso2) return;
      const value = config.getValue(d);
      if (value > 0) {
        const color = getColor(value, minValue, maxValue, colorScale);
        colorExpression.push(['==', ['get', 'iso_a2'], iso2], color);
      }
    });

    colorExpression.push('#e5e7eb');
    map.current.setPaintProperty('country-fills', 'fill-color', colorExpression);
  }, [activeMetric, mapLoaded, config, minValue, maxValue]);

  // Mouse events
  useEffect(() => {
    if (!map.current || !mapLoaded) return;

    const handleMouseMove = (e: maplibregl.MapMouseEvent) => {
      const features = map.current!.queryRenderedFeatures(e.point, {
        layers: ['country-fills'],
      });

      if (features.length > 0) {
        const feature = features[0];
        const iso2 = feature.properties?.['iso_a2'];

        if (iso2 && ALL_COUNTRIES.includes(iso2)) {
          map.current!.getCanvas().style.cursor = 'pointer';
          map.current!.setFilter('country-highlight', ['==', ['get', 'iso_a2'], iso2]);

          // Find data for this country
          const iso3 = Object.entries(ISO3_TO_ISO2).find(([, v]) => v === iso2)?.[0];
          const countryData = iso3 ? dataLookup.get(iso3) : null;

          if (countryData) {
            const isEU = EU_COUNTRIES.includes(iso2);
            const value = config.getValue(countryData);

            let html = `
              <div class="font-medium text-secondary">${countryData.name}</div>
              <div class="text-xs text-muted-foreground mb-1">${isEU ? 'EU Member' : 'Associated Country'}</div>
              <div class="text-sm text-primary font-bold">${config.label}: ${config.format(value)}</div>
              <div class="text-xs text-muted-foreground mt-1">Hubs: ${countryData.keyHubs.slice(0, 2).join(', ')}</div>
            `;
            popup.current!.setLngLat(e.lngLat).setHTML(html).addTo(map.current!);
          }
        }
      } else {
        map.current!.getCanvas().style.cursor = '';
        map.current!.setFilter('country-highlight', ['==', ['get', 'iso_a2'], '']);
        popup.current!.remove();
      }
    };

    map.current.on('mousemove', handleMouseMove);
    map.current.on('mouseleave', 'country-fills', () => {
      map.current!.getCanvas().style.cursor = '';
      popup.current!.remove();
    });

    return () => {
      map.current?.off('mousemove', handleMouseMove);
    };
  }, [mapLoaded, activeMetric, config, dataLookup]);

  const colorScale = COLOR_SCALES[activeMetric];

  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-2">
            <MapIcon className="w-5 h-5 text-secondary" />
            <CardTitle className="text-xl text-secondary">European Startup Ecosystem Map</CardTitle>
          </div>
          <div className="flex gap-2">
            {(['unicorns', 'funding', 'rank'] as MapMetric[]).map((metric) => (
              <button
                key={metric}
                onClick={() => setActiveMetric(metric)}
                className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
                  activeMetric === metric
                    ? 'bg-primary text-white'
                    : 'bg-muted text-muted-foreground hover:bg-muted/80'
                }`}
              >
                {METRIC_CONFIG[metric].label}
              </button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent className="relative">
        <div
          ref={mapContainer}
          className="w-full rounded-lg overflow-hidden"
          style={{ height: '450px' }}
        />

        {/* Legend */}
        <motion.div
          className="absolute bottom-6 left-6 bg-background/95 backdrop-blur-sm rounded-lg p-3 shadow-lg"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          key={activeMetric}
        >
          <div className="text-xs font-medium text-secondary mb-2">{config.label}</div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">{config.format(minValue)}</span>
            <div
              className="w-20 h-3 rounded"
              style={{
                background: `linear-gradient(to right, ${colorScale.min}, ${colorScale.max})`
              }}
            />
            <span className="text-xs text-muted-foreground">{config.format(maxValue)}</span>
          </div>
          <div className="mt-2 pt-2 border-t border-border/50 flex gap-3 text-[10px]">
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded border-2 border-white" style={{ backgroundColor: colorScale.max }} />
              <span className="text-muted-foreground">EU Member</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded border-2 border-dashed border-gray-400 bg-gray-200" />
              <span className="text-muted-foreground">Associated</span>
            </div>
          </div>
        </motion.div>

        {/* Loading state */}
        {!mapLoaded && (
          <div className="absolute inset-0 flex items-center justify-center bg-muted/50">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
          </div>
        )}

        <style>{`
          .startup-map-popup .maplibregl-popup-content {
            background: hsl(var(--background));
            border: 1px solid hsl(var(--border));
            border-radius: 8px;
            padding: 8px 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
          }
          .startup-map-popup .maplibregl-popup-tip {
            border-top-color: hsl(var(--background));
          }
        `}</style>
      </CardContent>
    </Card>
  );
}
