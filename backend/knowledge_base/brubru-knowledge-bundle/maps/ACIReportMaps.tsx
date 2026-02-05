import { useRef, useEffect, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Map, TrendingUp, Flag, DollarSign, Calendar, Clock,
  BarChart3, ExternalLink, Scale
} from 'lucide-react';

// Countries targeted by Trump's Greenland tariffs (ISO A3 codes)
const TARGETED_EU_COUNTRIES = ['DNK', 'SWE', 'FRA', 'NLD', 'FIN', 'DEU'];

// All EU-27 country codes (ISO A3)
const EU_COUNTRIES = [
  'AUT', 'BEL', 'BGR', 'HRV', 'CYP', 'CZE', 'DNK', 'EST', 'FIN', 'FRA',
  'DEU', 'GRC', 'HUN', 'IRL', 'ITA', 'LVA', 'LTU', 'LUX', 'MLT', 'NLD',
  'POL', 'PRT', 'ROU', 'SVK', 'SVN', 'ESP', 'SWE'
];

// Country info for popups
const COUNTRY_INFO: Record<string, { name: string; tariff: string; reason: string; status: string }> = {
  'DNK': { name: 'Denmark', tariff: '10%', reason: 'Greenland sovereignty', status: 'Primary target' },
  'SWE': { name: 'Sweden', tariff: '10%', reason: 'NATO exercises in Greenland', status: 'Targeted' },
  'FRA': { name: 'France', tariff: '10%', reason: 'NATO exercises in Greenland', status: 'Targeted - Requested ACI' },
  'NLD': { name: 'Netherlands', tariff: '10%', reason: 'NATO exercises in Greenland', status: 'Targeted' },
  'FIN': { name: 'Finland', tariff: '10%', reason: 'NATO exercises in Greenland', status: 'Targeted' },
  'DEU': { name: 'Germany', tariff: '10%', reason: 'NATO exercises in Greenland', status: 'Targeted' }
};

// Sectors exposed to ACI countermeasures
const EXPOSED_SECTORS = [
  { sector: 'Defence', companies: 'Lockheed Martin, RTX, Boeing, Northrop Grumman', exposure: 'F-35 (8 countries), Patriot, GBAD contracts', risk: 'High' },
  { sector: 'Cloud Services', companies: 'Microsoft, Amazon (AWS), Google Cloud', exposure: 'Office 365, Azure, Cloud II contracts', risk: 'High' },
  { sector: 'Consulting', companies: 'McKinsey, Deloitte, PwC, Accenture', exposure: 'EU institution advisory contracts', risk: 'Medium' },
  { sector: 'Medical Devices', companies: 'Johnson & Johnson, Medtronic, Abbott', exposure: 'EU healthcare system supplies', risk: 'Medium' },
  { sector: 'Construction', companies: 'Bechtel, Fluor, AECOM', exposure: 'EU infrastructure projects', risk: 'Lower' },
  { sector: 'Energy & Utilities', companies: 'GE, Honeywell', exposure: 'Power generation, grid equipment', risk: 'Medium' },
];

// ACI Timeline stages
const ACI_TIMELINE = [
  { stage: 1, label: 'INITIATION', subtitle: 'Examination Phase', description: 'Commission examines potential coercion (own initiative or member state request). France has formally requested activation.', duration: '~4 months', color: 'amber' },
  { stage: 2, label: 'DETERMINATION', subtitle: 'Council Decision', description: 'Council decides (by implementing act) whether coercion has occurred. Would formally designate US as engaging in economic coercion.', duration: '8-10 weeks', color: 'orange' },
  { stage: 3, label: 'ENGAGEMENT', subtitle: 'Diplomatic Track', description: 'EU seeks dialogue with third country to cease coercion. Runs parallel to examination; may continue during response phase.', duration: 'Ongoing', color: 'blue' },
  { stage: 4, label: 'RESPONSE', subtitle: 'Countermeasures', description: 'Commission adopts countermeasures via implementing act. Can include tariffs, procurement exclusions, FDI restrictions, and more.', duration: '≤6 months', color: 'red' },
];

// Source Badge Component
const SourceBadge = ({ source, variant = 'default' }: { source: string; variant?: 'default' | 'blue' | 'red' | 'amber' }) => {
  const variants = {
    default: 'bg-primary/10 text-primary border-primary/30',
    blue: 'bg-blue-500/10 text-blue-600 border-blue-500/30',
    red: 'bg-red-500/10 text-red-600 border-red-500/30',
    amber: 'bg-amber-500/10 text-amber-700 border-amber-500/30',
  };

  return (
    <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${variants[variant]}`}>
      {source}
    </span>
  );
};

/**
 * Interactive map showing EU countries targeted by Trump's Greenland tariffs
 */
export function GreenlandTariffMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const popup = useRef<maplibregl.Popup | null>(null);
  const [mapLoaded, setMapLoaded] = useState(false);

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
            ],
            tileSize: 256,
            attribution: '&copy; CARTO &copy; OpenStreetMap'
          }
        },
        layers: [{
          id: 'carto-basemap',
          type: 'raster',
          source: 'carto',
          minzoom: 0,
          maxzoom: 19
        }]
      },
      center: [10, 54],
      zoom: 3.5,
      minZoom: 2,
      maxZoom: 8
    });

    map.current.addControl(new maplibregl.NavigationControl(), 'top-right');

    popup.current = new maplibregl.Popup({
      closeButton: false,
      closeOnClick: false,
      className: 'aci-map-popup'
    });

    map.current.on('load', () => {
      setMapLoaded(true);

      map.current!.addSource('countries', {
        type: 'geojson',
        data: 'https://d2ad6b4ur7yvpq.cloudfront.net/naturalearth-3.3.0/ne_50m_admin_0_countries.geojson'
      });

      // Non-targeted EU countries (green)
      map.current!.addLayer({
        id: 'eu-countries',
        type: 'fill',
        source: 'countries',
        paint: {
          'fill-color': '#bbf7d0',
          'fill-opacity': 0.8
        },
        filter: ['all',
          ['in', ['get', 'iso_a3'], ['literal', EU_COUNTRIES]],
          ['!', ['in', ['get', 'iso_a3'], ['literal', TARGETED_EU_COUNTRIES]]]
        ]
      });

      // Targeted EU countries (red)
      map.current!.addLayer({
        id: 'targeted-countries',
        type: 'fill',
        source: 'countries',
        paint: {
          'fill-color': '#ef4444',
          'fill-opacity': 0.7
        },
        filter: ['in', ['get', 'iso_a3'], ['literal', TARGETED_EU_COUNTRIES]]
      });

      // Borders
      map.current!.addLayer({
        id: 'eu-borders',
        type: 'line',
        source: 'countries',
        paint: {
          'line-color': '#ffffff',
          'line-width': 1.5
        },
        filter: ['in', ['get', 'iso_a3'], ['literal', EU_COUNTRIES]]
      });

      // Highlight layer
      map.current!.addLayer({
        id: 'country-highlight',
        type: 'line',
        source: 'countries',
        paint: {
          'line-color': '#1a472a',
          'line-width': 3
        },
        filter: ['==', ['get', 'iso_a3'], '']
      });
    });

    return () => {
      map.current?.remove();
      map.current = null;
    };
  }, []);

  // Mouse events
  useEffect(() => {
    if (!map.current || !mapLoaded) return;

    const handleMouseMove = (e: maplibregl.MapMouseEvent) => {
      const features = map.current!.queryRenderedFeatures(e.point, {
        layers: ['targeted-countries']
      });

      if (features.length > 0) {
        const code = features[0].properties?.iso_a3;
        const info = COUNTRY_INFO[code];

        if (info) {
          map.current!.getCanvas().style.cursor = 'pointer';
          map.current!.setFilter('country-highlight', ['==', ['get', 'iso_a3'], code]);

          popup.current!.setLngLat(e.lngLat)
            .setHTML(`
              <div class="font-semibold text-secondary">${info.name}</div>
              <div class="text-sm text-red-600 font-bold">Tariff: ${info.tariff}</div>
              <div class="text-xs text-muted-foreground mt-1">${info.reason}</div>
              <div class="text-xs text-muted-foreground italic">${info.status}</div>
            `)
            .addTo(map.current!);
        }
      } else {
        map.current!.getCanvas().style.cursor = '';
        map.current!.setFilter('country-highlight', ['==', ['get', 'iso_a3'], '']);
        popup.current!.remove();
      }
    };

    map.current.on('mousemove', handleMouseMove);
    map.current.on('mouseleave', 'targeted-countries', () => {
      map.current!.getCanvas().style.cursor = '';
      map.current!.setFilter('country-highlight', ['==', ['get', 'iso_a3'], '']);
      popup.current!.remove();
    });

    return () => {
      map.current?.off('mousemove', handleMouseMove);
    };
  }, [mapLoaded]);

  return (
    <Card className="mb-8">
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Map className="w-5 h-5 text-red-500" />
            <CardTitle>EU Countries Targeted by Trump's Greenland Tariffs</CardTitle>
          </div>
          <p className="text-sm text-muted-foreground">6 EU Member States face 10% tariffs (rising to 25% by June 2026)</p>
        </div>
        <div className="flex items-center gap-2">
          <SourceBadge source="USTR" variant="blue" />
          <SourceBadge source="Trump Executive Order" variant="red" />
        </div>
      </CardHeader>
      <CardContent>
        <div
          ref={mapContainer}
          className="w-full h-[400px] rounded-lg overflow-hidden"
        />

        {/* Legend */}
        <div className="flex flex-wrap items-center justify-between gap-4 pt-4 mt-4 border-t">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-red-500"></div>
              <span className="text-sm text-muted-foreground">Targeted by 10% tariff (Feb 2026)</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 rounded bg-green-200 border border-green-300"></div>
              <span className="text-sm text-muted-foreground">Other EU-27 (not targeted)</span>
            </div>
          </div>
          <div className="text-xs text-muted-foreground">
            Note: Norway & UK also targeted but not EU members
          </div>
        </div>

        {/* Loading state */}
        {!mapLoaded && (
          <div className="absolute inset-0 flex items-center justify-center bg-muted/50 rounded-lg">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
          </div>
        )}

        {/* Custom popup styles */}
        <style>{`
          .aci-map-popup .maplibregl-popup-content {
            background: hsl(var(--background));
            border: 1px solid hsl(var(--border));
            border-radius: 8px;
            padding: 8px 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
          }
          .aci-map-popup .maplibregl-popup-tip {
            border-top-color: hsl(var(--background));
          }
        `}</style>
      </CardContent>
    </Card>
  );
}

/**
 * Key metrics cards for the ACI report
 */
export function ACIMetricCards() {
  const metrics = [
    {
      icon: TrendingUp,
      value: '10%',
      label: 'Initial Tariff Rate',
      subtext: 'Effective 1 Feb 2026',
      badge: 'Rising to 25%',
      color: 'red'
    },
    {
      icon: Flag,
      value: '6',
      label: 'EU Countries Targeted',
      subtext: 'DK, SE, FR, NL, FI, DE',
      badge: '22% of EU-27',
      color: 'amber'
    },
    {
      icon: DollarSign,
      value: '€100B',
      label: 'EU Retaliation Package',
      subtext: 'Suspended since Jul 2025',
      badge: 'Ready to deploy',
      color: 'green'
    },
    {
      icon: Calendar,
      value: 'Dec 2023',
      label: 'ACI Entry into Force',
      subtext: 'Regulation 2023/2675',
      badge: 'Never used',
      color: 'blue'
    }
  ];

  const colorClasses: Record<string, { bg: string; text: string; badge: string }> = {
    red: { bg: 'bg-red-100', text: 'text-red-600', badge: 'bg-red-100 text-red-600 border-red-200' },
    amber: { bg: 'bg-amber-100', text: 'text-amber-600', badge: 'bg-amber-100 text-amber-600 border-amber-200' },
    green: { bg: 'bg-green-100', text: 'text-green-600', badge: 'bg-green-100 text-green-600 border-green-200' },
    blue: { bg: 'bg-blue-100', text: 'text-blue-600', badge: 'bg-blue-100 text-blue-600 border-blue-200' }
  };

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
      {metrics.map((metric, i) => {
        const Icon = metric.icon;
        const colors = colorClasses[metric.color];
        return (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: i * 0.1 }}
          >
            <Card className="h-full hover:shadow-lg transition-all hover:-translate-y-1">
              <CardContent className="p-5 text-center">
                <div className={`w-14 h-14 mx-auto rounded-full ${colors.bg} flex items-center justify-center mb-3`}>
                  <Icon className={`w-7 h-7 ${colors.text}`} />
                </div>
                <div className="text-3xl font-bold text-secondary mb-1">{metric.value}</div>
                <div className="text-sm text-muted-foreground">{metric.label}</div>
                <div className={`text-xs ${colors.text} font-medium mt-1`}>{metric.subtext}</div>
                <div className="mt-2">
                  <span className={`text-xs px-3 py-1 rounded-full border ${colors.badge}`}>
                    {metric.badge}
                  </span>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        );
      })}
    </div>
  );
}

/**
 * ACI Activation Timeline
 */
export function ACITimeline() {
  const colorClasses: Record<string, { dot: string; label: string }> = {
    amber: { dot: 'bg-amber-200', label: 'bg-amber-100 text-amber-700' },
    orange: { dot: 'bg-orange-200', label: 'bg-orange-100 text-orange-700' },
    blue: { dot: 'bg-blue-200', label: 'bg-blue-100 text-blue-700' },
    red: { dot: 'bg-red-200', label: 'bg-red-100 text-red-700' }
  };

  return (
    <Card className="mb-8 bg-gradient-to-r from-amber-50 to-yellow-50 border-amber-200">
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-amber-200 flex items-center justify-center">
            <Clock className="w-5 h-5 text-amber-700" />
          </div>
          <div>
            <CardTitle className="flex items-center gap-2">
              ACI Activation Timeline
              <span className="text-xs px-2 py-0.5 bg-red-600 text-white rounded font-medium">POTENTIAL</span>
            </CardTitle>
            <p className="text-sm text-muted-foreground">Procedural steps under Regulation 2023/2675</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <SourceBadge source="EUR-Lex" variant="amber" />
          <SourceBadge source="EC Trade" variant="amber" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="relative ml-4">
          {/* Timeline line */}
          <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gradient-to-b from-amber-300 via-orange-300 to-red-400"></div>

          <div className="space-y-6 relative">
            {ACI_TIMELINE.map((item) => {
              const colors = colorClasses[item.color];
              return (
                <div key={item.stage} className="flex gap-4">
                  <div className={`w-8 h-8 rounded-full ${colors.dot} flex items-center justify-center shrink-0 z-10`}>
                    <span className={`font-bold text-sm ${item.color === 'amber' ? 'text-amber-700' : item.color === 'orange' ? 'text-orange-700' : item.color === 'blue' ? 'text-blue-700' : 'text-red-700'}`}>
                      {item.stage}
                    </span>
                  </div>
                  <Card className="flex-1 bg-white">
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <span className={`text-xs px-2 py-0.5 rounded font-medium ${colors.label}`}>
                              {item.label}
                            </span>
                            <span className="text-xs text-muted-foreground">{item.subtitle}</span>
                          </div>
                          <p className="text-sm text-foreground">{item.description}</p>
                        </div>
                        <div className="text-right shrink-0">
                          <div className="text-sm font-medium text-secondary">{item.duration}</div>
                          <div className="text-xs text-muted-foreground">typical duration</div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </div>
              );
            })}
          </div>
        </div>

        <div className="mt-6 pt-4 border-t border-amber-200 flex flex-wrap items-center justify-between gap-2 text-xs text-amber-700">
          <span>Source: Regulation (EU) 2023/2675, EC Trade Q&A</span>
          <span>Timeline can be compressed in urgent cases</span>
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * US Sectors Exposed to ACI Countermeasures
 */
export function ACISectorsTable() {
  const riskColors: Record<string, string> = {
    High: 'bg-red-100 text-red-700',
    Medium: 'bg-amber-100 text-amber-700',
    Lower: 'bg-green-100 text-green-700'
  };

  return (
    <Card className="mb-8">
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <BarChart3 className="w-5 h-5 text-secondary" />
            <CardTitle>US Sectors Exposed to ACI Countermeasures</CardTitle>
          </div>
          <p className="text-sm text-muted-foreground">Potential targets for EU procurement exclusions and market access restrictions</p>
        </div>
        <SourceBadge source="Beresol Analysis" />
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-muted-foreground">
                <th className="pb-3 font-medium">Sector</th>
                <th className="pb-3 font-medium">Key Companies</th>
                <th className="pb-3 font-medium text-right">EU Exposure</th>
                <th className="pb-3 font-medium text-center">Risk Level</th>
              </tr>
            </thead>
            <tbody>
              {EXPOSED_SECTORS.map((sector, i) => (
                <tr key={i} className="border-b border-border/30 hover:bg-muted/50 transition-colors">
                  <td className="py-3 font-medium text-secondary">{sector.sector}</td>
                  <td className="py-3 text-muted-foreground">{sector.companies}</td>
                  <td className="py-3 text-right text-muted-foreground">{sector.exposure}</td>
                  <td className="py-3 text-center">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${riskColors[sector.risk]}`}>
                      {sector.risk}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4 pt-4 border-t text-xs text-muted-foreground">
          Note: Existing contracts would likely be honoured; ACI measures would apply to new procurement and market access.
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Tariff Monitor Banner CTA
 */
export function TariffMonitorBanner() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      className="rounded-xl p-6 mb-8 bg-gradient-to-r from-amber-100 to-yellow-100 border-2 border-amber-400"
    >
      <div className="flex flex-col md:flex-row items-center justify-between gap-6">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-full bg-amber-200 flex items-center justify-center shrink-0">
            <Scale className="w-8 h-8 text-amber-700" />
          </div>
          <div>
            <h3 className="text-xl font-bold text-amber-900 mb-1">Track the Trade War in Real-Time</h3>
            <p className="text-amber-800">Monitor US, EU, and China tariff rates, retaliatory measures, and global trade tensions on Beresol's Tariff & Trade War Monitor.</p>
          </div>
        </div>
        <Link
          to="/tariffs"
          className="shrink-0 inline-flex items-center gap-2 px-6 py-3 bg-amber-600 hover:bg-amber-700 text-white font-semibold rounded-lg transition-colors shadow-lg"
        >
          <span>Open Tariff Monitor</span>
          <ExternalLink className="w-4 h-4" />
        </Link>
      </div>
    </motion.div>
  );
}

/**
 * Complete ACI Report Section - renders all interactive components
 * To be used in ReportPage for the ACI report
 */
export function ACIReportSection({ position }: { position: 'after-summary' | 'after-section-4' | 'after-section-5' | 'after-section-6' | 'after-conclusion' }) {
  switch (position) {
    case 'after-summary':
      return <GreenlandTariffMap />;
    case 'after-section-4':
      return <ACIMetricCards />;
    case 'after-section-5':
      return <ACITimeline />;
    case 'after-section-6':
      return <ACISectorsTable />;
    case 'after-conclusion':
      return <TariffMonitorBanner />;
    default:
      return null;
  }
}
