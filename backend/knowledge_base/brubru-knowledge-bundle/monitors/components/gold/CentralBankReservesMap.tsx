import { useRef, useEffect, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { motion } from 'framer-motion';
import { Globe } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { CENTRAL_BANK_RESERVES } from '@/data/goldFallback';

interface CentralBankReservesMapProps {
  className?: string;
}

function getColor(reserves: number): string {
  if (reserves > 2000) return '#D4AF37';
  if (reserves > 500) return '#FCD34D';
  if (reserves > 100) return '#FEF3C7';
  return '#f5f5f5';
}

export function CentralBankReservesMap({ className = '' }: CentralBankReservesMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const popup = useRef<maplibregl.Popup | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);

  const reservesLookup = new Map(CENTRAL_BANK_RESERVES.map(r => [r.iso, r]));
  const topFive = CENTRAL_BANK_RESERVES.slice(0, 5);

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
            ],
            tileSize: 256,
          },
        },
        layers: [{
          id: 'carto-basemap',
          type: 'raster',
          source: 'carto',
        }],
      },
      center: [10, 40],
      zoom: 1.5,
      minZoom: 1,
      maxZoom: 6,
    });

    map.current.addControl(new maplibregl.NavigationControl(), 'top-right');

    popup.current = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      className: 'gold-map-popup',
    });

    map.current.on('load', () => {
      setMapLoaded(true);

      map.current!.addSource('countries', {
        type: 'geojson',
        data: 'https://d2ad6b4ur7yvpq.cloudfront.net/naturalearth-3.3.0/ne_50m_admin_0_countries.geojson',
      });

      const colorExpression: maplibregl.ExpressionSpecification = ['case'];
      CENTRAL_BANK_RESERVES.forEach((r) => {
        colorExpression.push(['==', ['get', 'iso_a2'], r.iso], getColor(r.reserves));
      });
      colorExpression.push('#e5e7eb');

      map.current!.addLayer({
        id: 'country-fills',
        type: 'fill',
        source: 'countries',
        paint: {
          'fill-color': colorExpression,
          'fill-opacity': 0.8,
        },
      });

      map.current!.addLayer({
        id: 'country-borders',
        type: 'line',
        source: 'countries',
        paint: {
          'line-color': '#ffffff',
          'line-width': 0.5,
        },
      });
    });

    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, []);

  useEffect(() => {
    if (!map.current || !mapLoaded) return;

    const handleMouseMove = (e: maplibregl.MapMouseEvent) => {
      const features = map.current!.queryRenderedFeatures(e.point, {
        layers: ['country-fills'],
      });

      if (features.length > 0) {
        const iso = features[0].properties?.['iso_a2'];
        const data = reservesLookup.get(iso);

        if (data) {
          map.current!.getCanvas().style.cursor = 'pointer';
          popup.current!.setLngLat(e.lngLat)
            .setHTML(`
              <div class="font-medium text-secondary">${data.name}</div>
              <div class="text-sm font-bold" style="color: #D4AF37">${data.reserves.toLocaleString()} tonnes</div>
              <div class="text-xs text-gray-500">Rank #${data.rank}</div>
            `)
            .addTo(map.current!);
        }
      } else {
        map.current!.getCanvas().style.cursor = '';
        popup.current!.remove();
      }
    };

    map.current.on('mousemove', 'country-fills', handleMouseMove);
    map.current.on('mouseleave', 'country-fills', () => {
      map.current!.getCanvas().style.cursor = '';
      popup.current!.remove();
    });

    return () => {
      map.current?.off('mousemove', 'country-fills', handleMouseMove);
    };
  }, [mapLoaded, reservesLookup]);

  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-2">
            <Globe className="w-5 h-5 text-secondary" />
            <CardTitle className="text-xl text-secondary">Central Bank Gold Reserves</CardTitle>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-xs">
              <div className="w-3 h-3 rounded" style={{ background: '#D4AF37' }} />
              <span className="text-muted-foreground">&gt;2,000 tonnes</span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <div className="w-3 h-3 rounded" style={{ background: '#FCD34D' }} />
              <span className="text-muted-foreground">500-2,000 tonnes</span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <div className="w-3 h-3 rounded" style={{ background: '#FEF3C7' }} />
              <span className="text-muted-foreground">&lt;500 tonnes</span>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div
          ref={mapContainer}
          className="w-full rounded-lg overflow-hidden"
          style={{ height: '400px' }}
        />

        {/* Top 5 countries */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mt-4 pt-4 border-t border-border/50">
          {topFive.map((country) => (
            <div key={country.iso} className="text-center p-3 bg-muted/30 rounded-lg">
              <p className="text-xs text-muted-foreground">{country.name}</p>
              <p className="text-lg font-bold text-secondary">{country.reserves.toLocaleString()}</p>
              <p className="text-[10px] text-muted-foreground">tonnes</p>
            </div>
          ))}
        </div>

        {/* Loading state */}
        {!mapLoaded && (
          <div className="absolute inset-0 flex items-center justify-center bg-muted/50">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-amber-500" />
          </div>
        )}

        <style>{`
          .gold-map-popup .maplibregl-popup-content {
            background: hsl(var(--background));
            border: 1px solid hsl(var(--border));
            border-radius: 8px;
            padding: 8px 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
          }
          .gold-map-popup .maplibregl-popup-tip {
            border-top-color: hsl(var(--background));
          }
        `}</style>
      </CardContent>
    </Card>
  );
}
