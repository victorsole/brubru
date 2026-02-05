import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

const aiInvestmentData: Record<string, { name: string; amount: string; value: number; rank: number }> = {
  'FRA': { name: 'France', amount: '€1.3B+', value: 1300, rank: 1 },
  'DEU': { name: 'Germany', amount: '€910M', value: 910, rank: 2 },
  'GBR': { name: 'United Kingdom', amount: '€645M', value: 645, rank: 3 },
  'NLD': { name: 'Netherlands', amount: '€430M', value: 430, rank: 4 },
  'SWE': { name: 'Sweden', amount: '€280M', value: 280, rank: 5 },
  'POL': { name: 'Poland', amount: '€200M', value: 200, rank: 6 },
  'ESP': { name: 'Spain', amount: '€180M', value: 180, rank: 7 },
  'ITA': { name: 'Italy', amount: '€150M', value: 150, rank: 8 },
  'IRL': { name: 'Ireland', amount: '€120M', value: 120, rank: 9 },
  'FIN': { name: 'Finland', amount: '€100M', value: 100, rank: 10 },
  'DNK': { name: 'Denmark', amount: '€95M', value: 95, rank: 11 },
  'BEL': { name: 'Belgium', amount: '€85M', value: 85, rank: 12 },
  'AUT': { name: 'Austria', amount: '€75M', value: 75, rank: 13 },
  'NOR': { name: 'Norway', amount: '€70M', value: 70, rank: 14 },
  'CHE': { name: 'Switzerland', amount: '€65M', value: 65, rank: 15 },
  'PRT': { name: 'Portugal', amount: '€55M', value: 55, rank: 16 },
  'CZE': { name: 'Czech Republic', amount: '€45M', value: 45, rank: 17 },
  'ROU': { name: 'Romania', amount: '€40M', value: 40, rank: 18 },
  'HUN': { name: 'Hungary', amount: '€35M', value: 35, rank: 19 },
  'GRC': { name: 'Greece', amount: '€30M', value: 30, rank: 20 },
};

function getCountryColor(isoCode: string): string {
  const data = aiInvestmentData[isoCode];
  if (!data) return '#e8e8e8';
  const value = data.value;
  if (value >= 1000) return '#1a5c1a';
  if (value >= 500) return '#2d7a2d';
  if (value >= 200) return '#3aa33a';
  if (value >= 100) return '#5cb85c';
  if (value >= 50) return '#7dcc7d';
  return '#9dd99d';
}

export function AIInvestmentMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [tooltip, setTooltip] = useState<{ visible: boolean; x: number; y: number; content: string }>({
    visible: false,
    x: 0,
    y: 0,
    content: '',
  });

  useEffect(() => {
    if (!mapContainer.current || map.current) return;

    map.current = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          carto: {
            type: 'raster',
            tiles: ['https://basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}.png'],
            tileSize: 256,
          },
        },
        layers: [
          {
            id: 'carto-layer',
            type: 'raster',
            source: 'carto',
          },
        ],
      },
      center: [10, 50],
      zoom: 3.2,
      maxZoom: 5,
      minZoom: 2.5,
    });

    map.current.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');

    map.current.on('load', () => {
      fetch('https://raw.githubusercontent.com/leakyMirror/map-of-europe/master/GeoJSON/europe.geojson')
        .then((response) => response.json())
        .then((geojson) => {
          if (!map.current) return;

          map.current.addSource('countries', {
            type: 'geojson',
            data: geojson,
          });

          // Build match expression for colors
          const colorExpression: any[] = ['match', ['get', 'ISO3']];
          Object.keys(aiInvestmentData).forEach((iso) => {
            colorExpression.push(iso, getCountryColor(iso));
          });
          colorExpression.push('#e8e8e8'); // default

          map.current.addLayer({
            id: 'countries-fill',
            type: 'fill',
            source: 'countries',
            paint: {
              'fill-color': colorExpression,
              'fill-opacity': 0.8,
            },
          });

          map.current.addLayer({
            id: 'countries-border',
            type: 'line',
            source: 'countries',
            paint: {
              'line-color': '#ffffff',
              'line-width': 1,
            },
          });

          map.current.addLayer({
            id: 'countries-highlight',
            type: 'fill',
            source: 'countries',
            paint: {
              'fill-color': '#1a5c1a',
              'fill-opacity': 0.3,
            },
            filter: ['==', 'ISO3', ''],
          });
        });
    });

    return () => {
      if (map.current) {
        map.current.remove();
        map.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!map.current) return;

    const handleMouseMove = (e: maplibregl.MapMouseEvent) => {
      const features = map.current?.queryRenderedFeatures(e.point, { layers: ['countries-fill'] });
      if (features && features.length > 0) {
        const feature = features[0];
        const isoCode = feature.properties?.ISO3;
        const data = aiInvestmentData[isoCode];

        map.current?.getCanvas().style.setProperty('cursor', 'pointer');
        map.current?.setFilter('countries-highlight', ['==', 'ISO3', isoCode]);

        if (data) {
          setTooltip({
            visible: true,
            x: e.point.x + 15,
            y: e.point.y + 15,
            content: `<strong>${data.name}</strong><br/>AI VC (2024): <span style="color: hsl(120, 65%, 45%); font-weight: 600;">${data.amount}</span><br/><span style="color: #888; font-size: 10px;">Rank #${data.rank} in Europe</span>`,
          });
        } else {
          setTooltip({
            visible: true,
            x: e.point.x + 15,
            y: e.point.y + 15,
            content: `<strong>${feature.properties?.NAME || 'Unknown'}</strong><br/><span style="color: #888;">No data available</span>`,
          });
        }
      }
    };

    const handleMouseLeave = () => {
      map.current?.getCanvas().style.setProperty('cursor', '');
      map.current?.setFilter('countries-highlight', ['==', 'ISO3', '']);
      setTooltip((prev) => ({ ...prev, visible: false }));
    };

    map.current.on('mousemove', 'countries-fill', handleMouseMove);
    map.current.on('mouseleave', 'countries-fill', handleMouseLeave);

    return () => {
      map.current?.off('mousemove', 'countries-fill', handleMouseMove);
      map.current?.off('mouseleave', 'countries-fill', handleMouseLeave);
    };
  }, []);

  return (
    <div className="relative h-full min-h-[320px] w-full rounded-lg overflow-hidden">
      <div ref={mapContainer} className="absolute inset-0" />
      {tooltip.visible && (
        <div
          className="absolute bg-white px-3 py-2 rounded-md shadow-lg border border-border text-xs pointer-events-none z-10"
          style={{ left: tooltip.x, top: tooltip.y }}
          dangerouslySetInnerHTML={{ __html: tooltip.content }}
        />
      )}
    </div>
  );
}
