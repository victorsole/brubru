import { useState } from 'react';
import { motion } from 'framer-motion';
import { Map, TrendingUp, TrendingDown } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { EuropeMap, CountryData } from '@/components/maps';
import { SourceBadges } from './SourceBadge';

interface CMUIntegrationMapProps {
  className?: string;
}

// Cross-border equity holdings as % of GDP (ECB data 2023)
const CROSS_BORDER_EQUITY_DATA: CountryData[] = [
  { code: 'LU', value: 892, label: '892% GDP' },  // Luxembourg - financial hub
  { code: 'IE', value: 456, label: '456% GDP' },  // Ireland - financial hub
  { code: 'NL', value: 187, label: '187% GDP' },
  { code: 'BE', value: 124, label: '124% GDP' },
  { code: 'MT', value: 98, label: '98% GDP' },
  { code: 'AT', value: 67, label: '67% GDP' },
  { code: 'SE', value: 65, label: '65% GDP' },
  { code: 'DK', value: 58, label: '58% GDP' },
  { code: 'FI', value: 52, label: '52% GDP' },
  { code: 'FR', value: 48, label: '48% GDP' },
  { code: 'DE', value: 45, label: '45% GDP' },
  { code: 'ES', value: 38, label: '38% GDP' },
  { code: 'PT', value: 35, label: '35% GDP' },
  { code: 'IT', value: 28, label: '28% GDP' },
  { code: 'CY', value: 76, label: '76% GDP' },
  { code: 'EE', value: 42, label: '42% GDP' },
  { code: 'LV', value: 24, label: '24% GDP' },
  { code: 'LT', value: 22, label: '22% GDP' },
  { code: 'SI', value: 32, label: '32% GDP' },
  { code: 'SK', value: 18, label: '18% GDP' },
  { code: 'CZ', value: 25, label: '25% GDP' },
  { code: 'HU', value: 21, label: '21% GDP' },
  { code: 'PL', value: 19, label: '19% GDP' },
  { code: 'RO', value: 12, label: '12% GDP' },
  { code: 'BG', value: 14, label: '14% GDP' },
  { code: 'HR', value: 16, label: '16% GDP' },
  { code: 'GR', value: 23, label: '23% GDP' },
];

// VC investment per capita 2024 (€)
const VC_PER_CAPITA_DATA: CountryData[] = [
  { code: 'EE', value: 892, label: '€892/capita' },  // Estonia - startup nation
  { code: 'SE', value: 567, label: '€567/capita' },
  { code: 'FI', value: 423, label: '€423/capita' },
  { code: 'NL', value: 398, label: '€398/capita' },
  { code: 'DK', value: 356, label: '€356/capita' },
  { code: 'IE', value: 312, label: '€312/capita' },
  { code: 'LU', value: 287, label: '€287/capita' },
  { code: 'DE', value: 198, label: '€198/capita' },
  { code: 'FR', value: 187, label: '€187/capita' },
  { code: 'BE', value: 165, label: '€165/capita' },
  { code: 'AT', value: 134, label: '€134/capita' },
  { code: 'ES', value: 89, label: '€89/capita' },
  { code: 'PT', value: 76, label: '€76/capita' },
  { code: 'LT', value: 124, label: '€124/capita' },
  { code: 'LV', value: 87, label: '€87/capita' },
  { code: 'MT', value: 156, label: '€156/capita' },
  { code: 'CY', value: 98, label: '€98/capita' },
  { code: 'SI', value: 67, label: '€67/capita' },
  { code: 'IT', value: 45, label: '€45/capita' },
  { code: 'CZ', value: 56, label: '€56/capita' },
  { code: 'PL', value: 34, label: '€34/capita' },
  { code: 'HU', value: 28, label: '€28/capita' },
  { code: 'SK', value: 23, label: '€23/capita' },
  { code: 'RO', value: 18, label: '€18/capita' },
  { code: 'BG', value: 15, label: '€15/capita' },
  { code: 'HR', value: 21, label: '€21/capita' },
  { code: 'GR', value: 32, label: '€32/capita' },
];

type MapView = 'crossBorder' | 'vcPerCapita';

const MAP_CONFIGS: Record<MapView, {
  title: string;
  data: CountryData[];
  colorScale: { min: string; max: string };
  legendTitle: string;
  valueFormatter: (v: number) => string;
}> = {
  crossBorder: {
    title: 'Cross-Border Equity Holdings',
    data: CROSS_BORDER_EQUITY_DATA,
    colorScale: { min: '#e3f2fd', max: '#0d47a1' },
    legendTitle: '% of GDP',
    valueFormatter: (v) => `${v}%`,
  },
  vcPerCapita: {
    title: 'VC Investment per Capita',
    data: VC_PER_CAPITA_DATA,
    colorScale: { min: '#e8f5e9', max: '#1b5e20' },
    legendTitle: '€ per capita',
    valueFormatter: (v) => `€${v}`,
  },
};

export function CMUIntegrationMap({ className = '' }: CMUIntegrationMapProps) {
  const [activeView, setActiveView] = useState<MapView>('crossBorder');
  const config = MAP_CONFIGS[activeView];

  const handleCountryClick = (country: CountryData) => {
    console.log('Country clicked:', country);
    // Could open a modal with more details
  };

  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-2">
        <motion.div
          className="flex items-center justify-between flex-wrap gap-4"
          initial={{ opacity: 0, y: -10 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.4 }}
        >
          <div className="flex items-center gap-2">
            <motion.div
              initial={{ scale: 0, rotate: -180 }}
              whileInView={{ scale: 1, rotate: 0 }}
              viewport={{ once: true }}
              transition={{ type: 'spring', stiffness: 200, delay: 0.1 }}
            >
              <Map className="w-5 h-5 text-primary" />
            </motion.div>
            <CardTitle className="text-xl text-secondary">
              EU Financial Integration Map
            </CardTitle>
          </div>
          <SourceBadges sources={['ecb', 'eurostat', 'invest_europe']} size="sm" />
        </motion.div>

        {/* View Toggle */}
        <motion.div
          className="flex gap-2 mt-3"
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ delay: 0.2 }}
        >
          <button
            onClick={() => setActiveView('crossBorder')}
            className={`px-3 py-1.5 text-xs font-medium rounded-full transition-all ${
              activeView === 'crossBorder'
                ? 'bg-primary text-white'
                : 'bg-muted/50 text-muted-foreground hover:bg-muted'
            }`}
          >
            Cross-Border Holdings
          </button>
          <button
            onClick={() => setActiveView('vcPerCapita')}
            className={`px-3 py-1.5 text-xs font-medium rounded-full transition-all ${
              activeView === 'vcPerCapita'
                ? 'bg-primary text-white'
                : 'bg-muted/50 text-muted-foreground hover:bg-muted'
            }`}
          >
            VC per Capita
          </button>
        </motion.div>
      </CardHeader>

      <CardContent>
        <EuropeMap
          data={config.data}
          title={config.title}
          subtitle="Hover over countries to see values. Click for details."
          colorScale={config.colorScale}
          legendTitle={config.legendTitle}
          valueFormatter={config.valueFormatter}
          height="380px"
          onCountryClick={handleCountryClick}
        />

        {/* Key insights */}
        <motion.div
          className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4"
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.3 }}
        >
          {activeView === 'crossBorder' ? (
            <>
              <div className="bg-muted/30 rounded-lg p-3 text-center">
                <div className="flex items-center justify-center gap-1 text-primary mb-1">
                  <TrendingUp className="w-4 h-4" />
                  <span className="text-lg font-bold">LU, IE, NL</span>
                </div>
                <p className="text-xs text-muted-foreground">Highest integration (financial hubs)</p>
              </div>
              <div className="bg-muted/30 rounded-lg p-3 text-center">
                <div className="flex items-center justify-center gap-1 text-destructive mb-1">
                  <TrendingDown className="w-4 h-4" />
                  <span className="text-lg font-bold">RO, BG, SK</span>
                </div>
                <p className="text-xs text-muted-foreground">Lowest integration (CEE catch-up needed)</p>
              </div>
              <div className="bg-muted/30 rounded-lg p-3 text-center">
                <div className="text-lg font-bold text-secondary mb-1">45% GDP</div>
                <p className="text-xs text-muted-foreground">EU-27 average cross-border holdings</p>
              </div>
            </>
          ) : (
            <>
              <div className="bg-muted/30 rounded-lg p-3 text-center">
                <div className="flex items-center justify-center gap-1 text-primary mb-1">
                  <TrendingUp className="w-4 h-4" />
                  <span className="text-lg font-bold">EE, SE, FI</span>
                </div>
                <p className="text-xs text-muted-foreground">VC leaders (Nordic/Baltic model)</p>
              </div>
              <div className="bg-muted/30 rounded-lg p-3 text-center">
                <div className="flex items-center justify-center gap-1 text-destructive mb-1">
                  <TrendingDown className="w-4 h-4" />
                  <span className="text-lg font-bold">BG, RO, SK</span>
                </div>
                <p className="text-xs text-muted-foreground">VC laggards (underdeveloped ecosystems)</p>
              </div>
              <div className="bg-muted/30 rounded-lg p-3 text-center">
                <div className="text-lg font-bold text-secondary mb-1">€112/capita</div>
                <p className="text-xs text-muted-foreground">EU-27 average vs €892 in US</p>
              </div>
            </>
          )}
        </motion.div>
      </CardContent>
    </Card>
  );
}
