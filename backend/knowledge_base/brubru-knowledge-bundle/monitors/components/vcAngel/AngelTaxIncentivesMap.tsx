import { useRef, useEffect, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { MapPin } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ANGEL_TAX_SCHEMES, getTaxReliefValue } from '@/data/vcAngelFallback';
import type { AngelTaxScheme } from '@/types/vcAngel';

interface AngelTaxIncentivesMapProps {
  schemes?: AngelTaxScheme[];
  className?: string;
}

function getColour(reliefPercent: number): string {
  if (reliefPercent >= 45) return '#059669'; // Green-600
  if (reliefPercent >= 30) return '#10B981'; // Green-500
  if (reliefPercent >= 20) return '#6EE7B7'; // Green-300
  return '#D1FAE5'; // Green-100
}

export function AngelTaxIncentivesMap({
  schemes = ANGEL_TAX_SCHEMES,
  className = '',
}: AngelTaxIncentivesMapProps) {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const popup = useRef<maplibregl.Popup | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [selectedCountry, setSelectedCountry] = useState<AngelTaxScheme | null>(null);

  const schemesLookup = new Map(schemes.map(s => [s.countryCode, s]));

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
      center: [10, 50],
      zoom: 3.5,
      minZoom: 2.5,
      maxZoom: 6,
    });

    map.current.addControl(new maplibregl.NavigationControl(), 'top-right');

    popup.current = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      className: 'angel-map-popup',
    });

    map.current.on('load', () => {
      setMapLoaded(true);

      map.current!.addSource('countries', {
        type: 'geojson',
        data: 'https://d2ad6b4ur7yvpq.cloudfront.net/naturalearth-3.3.0/ne_50m_admin_0_countries.geojson',
      });

      const colourExpression: maplibregl.ExpressionSpecification = ['case'];
      schemes.forEach((s) => {
        const relief = getTaxReliefValue(s);
        colourExpression.push(['==', ['get', 'iso_a2'], s.countryCode], getColour(relief));
      });
      colourExpression.push('#e5e7eb');

      map.current!.addLayer({
        id: 'country-fills',
        type: 'fill',
        source: 'countries',
        paint: {
          'fill-color': colourExpression,
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
  }, [schemes]);

  useEffect(() => {
    if (!map.current || !mapLoaded) return;

    const handleMouseMove = (e: maplibregl.MapMouseEvent) => {
      const features = map.current!.queryRenderedFeatures(e.point, {
        layers: ['country-fills'],
      });

      if (features.length > 0) {
        const iso = features[0].properties?.['iso_a2'];
        const data = schemesLookup.get(iso);

        if (data) {
          map.current!.getCanvas().style.cursor = 'pointer';
          popup.current!.setLngLat(e.lngLat)
            .setHTML(`
              <div class="font-medium text-secondary">${data.countryName}</div>
              <div class="text-sm font-bold text-green-600">${data.taxRelief} tax relief</div>
              <div class="text-xs text-gray-500">${data.schemeName}</div>
            `)
            .addTo(map.current!);
        }
      } else {
        map.current!.getCanvas().style.cursor = '';
        popup.current!.remove();
      }
    };

    const handleClick = (e: maplibregl.MapMouseEvent) => {
      const features = map.current!.queryRenderedFeatures(e.point, {
        layers: ['country-fills'],
      });

      if (features.length > 0) {
        const iso = features[0].properties?.['iso_a2'];
        const data = schemesLookup.get(iso);
        if (data) {
          setSelectedCountry(data);
        }
      }
    };

    map.current.on('mousemove', 'country-fills', handleMouseMove);
    map.current.on('click', 'country-fills', handleClick);
    map.current.on('mouseleave', 'country-fills', () => {
      map.current!.getCanvas().style.cursor = '';
      popup.current!.remove();
    });

    return () => {
      map.current?.off('mousemove', 'country-fills', handleMouseMove);
      map.current?.off('click', 'country-fills', handleClick);
    };
  }, [mapLoaded, schemesLookup]);

  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-2">
            <MapPin className="w-5 h-5 text-green-600" />
            <CardTitle className="text-xl text-secondary">Business Angel Tax Incentives</CardTitle>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 text-xs">
              <div className="w-3 h-3 rounded" style={{ background: '#059669' }} />
              <span className="text-muted-foreground">&ge;45%</span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <div className="w-3 h-3 rounded" style={{ background: '#10B981' }} />
              <span className="text-muted-foreground">30-44%</span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <div className="w-3 h-3 rounded" style={{ background: '#6EE7B7' }} />
              <span className="text-muted-foreground">20-29%</span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <div className="w-3 h-3 rounded" style={{ background: '#D1FAE5' }} />
              <span className="text-muted-foreground">&lt;20%</span>
            </div>
          </div>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Click a country to see scheme details. Tax incentives vary by Member State.
        </p>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Map */}
          <div className="lg:col-span-2">
            <div
              ref={mapContainer}
              className="w-full rounded-lg overflow-hidden"
              style={{ height: '350px' }}
            />
          </div>

          {/* Selected Country Details */}
          <div className="p-4 bg-muted/30 rounded-lg">
            {selectedCountry ? (
              <div className="space-y-3">
                <div>
                  <h4 className="font-semibold text-secondary text-lg">{selectedCountry.countryName}</h4>
                  <p className="text-sm text-primary font-medium">{selectedCountry.schemeName}</p>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Tax Relief:</span>
                    <span className="font-semibold text-green-600">{selectedCountry.taxRelief}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Max Investment:</span>
                    <span className="font-medium text-secondary">{selectedCountry.maxInvestment}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Holding Period:</span>
                    <span className="font-medium text-secondary">{selectedCountry.holdingPeriod}</span>
                  </div>
                </div>
                <div className="pt-2 border-t border-border/50">
                  <p className="text-xs text-muted-foreground">{selectedCountry.conditions}</p>
                </div>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-center">
                <div>
                  <MapPin className="w-8 h-8 text-muted-foreground/50 mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">
                    Click a highlighted country to view tax incentive details
                  </p>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Loading state */}
        {!mapLoaded && (
          <div className="absolute inset-0 flex items-center justify-center bg-muted/50">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-500" />
          </div>
        )}

        <style>{`
          .angel-map-popup .maplibregl-popup-content {
            background: hsl(var(--background));
            border: 1px solid hsl(var(--border));
            border-radius: 8px;
            padding: 8px 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
          }
          .angel-map-popup .maplibregl-popup-tip {
            border-top-color: hsl(var(--background));
          }
        `}</style>
      </CardContent>
    </Card>
  );
}
