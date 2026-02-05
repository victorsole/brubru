import { useRef, useEffect, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { motion } from 'framer-motion';

// Country name mapping for major economies
const COUNTRY_NAMES: Record<string, string> = {
  US: 'United States', CA: 'Canada', MX: 'Mexico',
  CN: 'China', JP: 'Japan', KR: 'South Korea', TW: 'Taiwan',
  IN: 'India', VN: 'Vietnam', ID: 'Indonesia', TH: 'Thailand',
  MY: 'Malaysia', SG: 'Singapore', PH: 'Philippines',
  AU: 'Australia', NZ: 'New Zealand',
  GB: 'United Kingdom', DE: 'Germany', FR: 'France', IT: 'Italy',
  ES: 'Spain', NL: 'Netherlands', BE: 'Belgium', PL: 'Poland',
  SE: 'Sweden', AT: 'Austria', IE: 'Ireland', CH: 'Switzerland',
  NO: 'Norway', DK: 'Denmark', FI: 'Finland', PT: 'Portugal',
  GR: 'Greece', CZ: 'Czechia', RO: 'Romania', HU: 'Hungary',
  BR: 'Brazil', AR: 'Argentina', CL: 'Chile', CO: 'Colombia',
  SA: 'Saudi Arabia', AE: 'UAE', IL: 'Israel', TR: 'Turkey',
  ZA: 'South Africa', EG: 'Egypt', NG: 'Nigeria',
  RU: 'Russia', UA: 'Ukraine',
};

// EU member states
const EU_COUNTRIES = [
  'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR',
  'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL',
  'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE'
];

export interface TariffCountryData {
  code: string;
  rate: number;
  label?: string;
  notes?: string;
}

export interface WorldTariffMapProps {
  data: TariffCountryData[];
  perspective: 'US' | 'EU' | 'China';
  title?: string;
  subtitle?: string;
  colorScale?: {
    min: string;
    mid: string;
    max: string;
  };
  height?: string;
  className?: string;
  showLegend?: boolean;
}

// Generate color based on tariff rate
function getTariffColor(rate: number, colorScale: { min: string; mid: string; max: string }) {
  // Color scale: 0% = green, 25% = yellow, 50%+ = red
  const parseHex = (hex: string) => {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
      r: parseInt(result[1], 16),
      g: parseInt(result[2], 16),
      b: parseInt(result[3], 16)
    } : { r: 0, g: 0, b: 0 };
  };

  const minColor = parseHex(colorScale.min);
  const midColor = parseHex(colorScale.mid);
  const maxColor = parseHex(colorScale.max);

  let r, g, b;
  if (rate <= 15) {
    // Green to yellow
    const ratio = rate / 15;
    r = Math.round(minColor.r + (midColor.r - minColor.r) * ratio);
    g = Math.round(minColor.g + (midColor.g - minColor.g) * ratio);
    b = Math.round(minColor.b + (midColor.b - minColor.b) * ratio);
  } else {
    // Yellow to red
    const ratio = Math.min((rate - 15) / 35, 1);
    r = Math.round(midColor.r + (maxColor.r - midColor.r) * ratio);
    g = Math.round(midColor.g + (maxColor.g - midColor.g) * ratio);
    b = Math.round(midColor.b + (maxColor.b - midColor.b) * ratio);
  }

  return `rgb(${r}, ${g}, ${b})`;
}

export function WorldTariffMap({
  data,
  perspective,
  title,
  subtitle,
  colorScale = { min: '#22c55e', mid: '#eab308', max: '#ef4444' },
  height = '400px',
  className = '',
  showLegend = true,
}: WorldTariffMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const popup = useRef<maplibregl.Popup | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  const dataLookup = new Map(data.map(d => [d.code, d]));

  // Map center based on perspective
  const mapCenter: [number, number] =
    perspective === 'US' ? [-95, 38] :
    perspective === 'China' ? [105, 35] :
    [10, 50];

  const mapZoom = perspective === 'EU' ? 3.2 : 1.8;

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
      center: mapCenter,
      zoom: mapZoom,
      minZoom: 1,
      maxZoom: 8,
    });

    map.current.addControl(new maplibregl.NavigationControl(), 'top-right');

    popup.current = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      className: 'tariff-map-popup',
    });

    map.current.on('load', () => {
      setMapLoaded(true);

      map.current!.addSource('countries', {
        type: 'geojson',
        data: 'https://d2ad6b4ur7yvpq.cloudfront.net/naturalearth-3.3.0/ne_50m_admin_0_countries.geojson',
      });

      // Add fill layer for all countries
      map.current!.addLayer({
        id: 'country-fills',
        type: 'fill',
        source: 'countries',
        paint: {
          'fill-color': '#e5e7eb',
          'fill-opacity': 0.8,
        },
      });

      // Add border layer
      map.current!.addLayer({
        id: 'country-borders',
        type: 'line',
        source: 'countries',
        paint: {
          'line-color': '#ffffff',
          'line-width': 0.5,
        },
      });

      // Highlight the perspective country
      const perspectiveCode = perspective === 'US' ? 'US' : perspective === 'China' ? 'CN' : null;

      if (perspectiveCode) {
        map.current!.addLayer({
          id: 'perspective-highlight',
          type: 'line',
          source: 'countries',
          paint: {
            'line-color': '#1e40af',
            'line-width': 3,
          },
          filter: ['==', ['get', 'iso_a2'], perspectiveCode],
        });
      }

      // EU perspective: highlight EU border
      if (perspective === 'EU') {
        map.current!.addLayer({
          id: 'eu-highlight',
          type: 'line',
          source: 'countries',
          paint: {
            'line-color': '#1e40af',
            'line-width': 2,
          },
          filter: ['in', ['get', 'iso_a2'], ['literal', EU_COUNTRIES]],
        });
      }

      // Add hover highlight layer
      map.current!.addLayer({
        id: 'country-hover',
        type: 'line',
        source: 'countries',
        paint: {
          'line-color': '#1f2937',
          'line-width': 2,
        },
        filter: ['==', ['get', 'iso_a2'], ''],
      });
    });

    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, [perspective]);

  // Update country colors when data changes
  useEffect(() => {
    if (!map.current || !mapLoaded) return;

    const colorExpression: maplibregl.ExpressionSpecification = ['case'];

    // Self-country gets blue
    if (perspective === 'US') {
      colorExpression.push(['==', ['get', 'iso_a2'], 'US'], '#3b82f6');
    } else if (perspective === 'China') {
      colorExpression.push(['==', ['get', 'iso_a2'], 'CN'], '#ef4444');
    } else if (perspective === 'EU') {
      // EU countries get blue
      EU_COUNTRIES.forEach(code => {
        colorExpression.push(['==', ['get', 'iso_a2'], code], '#3b82f6');
      });
    }

    // Add colors for countries with data
    data.forEach(({ code, rate }) => {
      // Skip self
      if ((perspective === 'US' && code === 'US') ||
          (perspective === 'China' && code === 'CN') ||
          (perspective === 'EU' && EU_COUNTRIES.includes(code))) {
        return;
      }
      const color = getTariffColor(rate, colorScale);
      colorExpression.push(['==', ['get', 'iso_a2'], code], color);
    });

    colorExpression.push('#e5e7eb'); // Default gray

    map.current.setPaintProperty('country-fills', 'fill-color', colorExpression);
  }, [data, perspective, colorScale, mapLoaded]);

  // Handle mouse events
  useEffect(() => {
    if (!map.current || !mapLoaded) return;

    const handleMouseMove = (e: maplibregl.MapMouseEvent) => {
      const features = map.current!.queryRenderedFeatures(e.point, {
        layers: ['country-fills'],
      });

      if (features.length > 0) {
        const feature = features[0];
        const countryCode = feature.properties?.['iso_a2'];

        if (countryCode) {
          map.current!.getCanvas().style.cursor = 'pointer';
          map.current!.setFilter('country-hover', ['==', ['get', 'iso_a2'], countryCode]);

          const countryData = dataLookup.get(countryCode);
          const countryName = COUNTRY_NAMES[countryCode] || feature.properties?.['name'] || countryCode;

          let html = `<div class="font-medium text-secondary">${countryName}</div>`;

          if (countryData) {
            const rateColor = countryData.rate <= 10 ? 'text-green-600' :
                             countryData.rate <= 25 ? 'text-amber-600' : 'text-red-600';
            html += `<div class="text-lg font-bold ${rateColor}">${countryData.rate}%</div>`;
            if (countryData.notes) {
              html += `<div class="text-xs text-muted-foreground max-w-[200px]">${countryData.notes}</div>`;
            }
          } else {
            html += `<div class="text-sm text-muted-foreground">No specific tariff data</div>`;
          }

          popup.current!.setLngLat(e.lngLat).setHTML(html).addTo(map.current!);
        }
      } else {
        map.current!.getCanvas().style.cursor = '';
        map.current!.setFilter('country-hover', ['==', ['get', 'iso_a2'], '']);
        popup.current!.remove();
      }
    };

    map.current.on('mousemove', handleMouseMove);

    return () => {
      map.current?.off('mousemove', handleMouseMove);
    };
  }, [mapLoaded, data, perspective]);

  return (
    <motion.div
      className={`relative rounded-lg overflow-hidden bg-muted/20 ${className}`}
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.5 }}
    >
      {(title || subtitle) && (
        <div className="p-4 pb-2">
          {title && <h3 className="text-sm font-medium text-secondary">{title}</h3>}
          {subtitle && <p className="text-xs text-muted-foreground mt-1">{subtitle}</p>}
        </div>
      )}

      <div
        ref={mapContainer}
        style={{ height }}
        className="w-full"
      />

      {showLegend && (
        <motion.div
          className="absolute bottom-4 left-4 bg-background/90 backdrop-blur-sm rounded-lg p-3 shadow-lg"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.5 }}
        >
          <div className="text-xs font-medium text-secondary mb-2">Tariff Rate</div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">0%</span>
            <div
              className="w-20 h-3 rounded"
              style={{
                background: `linear-gradient(to right, ${colorScale.min}, ${colorScale.mid}, ${colorScale.max})`
              }}
            />
            <span className="text-xs text-muted-foreground">50%+</span>
          </div>
          <div className="flex items-center gap-2 mt-2">
            <div className="w-3 h-3 rounded bg-blue-500"></div>
            <span className="text-xs text-muted-foreground">
              {perspective === 'US' ? 'United States' : perspective === 'EU' ? 'European Union' : 'China'}
            </span>
          </div>
        </motion.div>
      )}

      {!mapLoaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-muted/50">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
        </div>
      )}

      <style>{`
        .tariff-map-popup .maplibregl-popup-content {
          background: hsl(var(--background));
          border: 1px solid hsl(var(--border));
          border-radius: 8px;
          padding: 8px 12px;
          box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .tariff-map-popup .maplibregl-popup-tip {
          border-top-color: hsl(var(--background));
        }
      `}</style>
    </motion.div>
  );
}
