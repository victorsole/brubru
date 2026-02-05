import { useState } from 'react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { BarChart3 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { SourceBadges } from './SourceBadge';
import { FALLBACK_METRICS } from '@/data/cmuFallback';
import type { CMUMetrics } from '@/types/cmu';

interface EUvsUSComparisonProps {
  metrics?: CMUMetrics;
  isLoading?: boolean;
  className?: string;
}

const CHART_COLORS = {
  eu: 'hsl(120, 65%, 45%)',
  us: 'hsl(45, 85%, 50%)',
  grid: 'hsl(120, 20%, 88%)',
};

function ComparisonBarChart({
  title,
  data,
  yAxisFormatter,
}: {
  title: string;
  data: { name: string; value: number; fill: string }[];
  yAxisFormatter?: (value: number) => string;
}) {
  return (
    <div className="bg-muted/20 rounded-lg p-4">
      <h3 className="text-sm font-medium text-secondary mb-4">{title}</h3>
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 10, right: 10, left: 10, bottom: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} vertical={false} />
            <XAxis dataKey="name" fontSize={12} tickLine={false} axisLine={false} />
            <YAxis
              fontSize={10}
              tickLine={false}
              axisLine={false}
              tickFormatter={yAxisFormatter}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'white',
                border: `1px solid ${CHART_COLORS.grid}`,
                borderRadius: '8px',
                boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
              }}
              formatter={(value: number) =>
                yAxisFormatter ? yAxisFormatter(value) : value
              }
            />
            <Bar dataKey="value" radius={[4, 4, 0, 0]}>
              {data.map((entry, index) => (
                <rect key={index} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export function EUvsUSComparison({
  metrics = FALLBACK_METRICS,
  isLoading = false,
  className = '',
}: EUvsUSComparisonProps) {
  const [includeUK, setIncludeUK] = useState(false);

  // Chart data
  const marketCapData = [
    { name: 'EU', value: metrics.euMarketCapGDP, fill: CHART_COLORS.eu },
    { name: 'US', value: metrics.usMarketCapGDP, fill: CHART_COLORS.us },
  ];

  const vcData = [
    { name: 'EU', value: metrics.euVCGDP, fill: CHART_COLORS.eu },
    { name: 'US', value: metrics.usVCGDP, fill: CHART_COLORS.us },
  ];

  const retailData = [
    { name: 'EU', value: metrics.euHouseholdInvGDP, fill: CHART_COLORS.eu },
    { name: 'US', value: metrics.usHouseholdInvGDP, fill: CHART_COLORS.us },
  ];

  const activityData = [
    { name: 'EU', value: metrics.euIPOCount, fill: CHART_COLORS.eu },
    { name: 'US', value: metrics.usIPOCount, fill: CHART_COLORS.us },
  ];

  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-secondary" />
            <CardTitle className="text-xl text-secondary">
              EU vs US Capital Markets Comparison
            </CardTitle>
          </div>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-muted-foreground cursor-pointer">
              <Checkbox
                checked={includeUK}
                onCheckedChange={(checked) => setIncludeUK(checked as boolean)}
              />
              Include UK
            </label>
            <SourceBadges sources={['ecb', 'esma']} size="sm" />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* 4 Bar Charts Row */}
        <div className="grid grid-cols-4 gap-6 mb-6">
          <ComparisonBarChart
            title="Stock Market Cap (% GDP)"
            data={marketCapData}
            yAxisFormatter={(v) => `${v}%`}
          />
          <ComparisonBarChart
            title="VC Investment (% GDP)"
            data={vcData}
            yAxisFormatter={(v) => `${v}%`}
          />
          <ComparisonBarChart
            title="Household Inv. (% GDP)"
            data={retailData}
            yAxisFormatter={(v) => `${v}%`}
          />
          <ComparisonBarChart
            title="IPO Count (2024)"
            data={activityData}
          />
        </div>

        {/* Full-width Integration Line Chart */}
        <div className="bg-muted/20 rounded-lg p-4">
          <h3 className="text-sm font-medium text-secondary mb-4">
            Financial Integration Index (2015-2024)
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={metrics.integrationTrend}
                margin={{ top: 10, right: 30, left: 10, bottom: 10 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
                <XAxis dataKey="year" fontSize={12} tickLine={false} />
                <YAxis
                  fontSize={10}
                  tickLine={false}
                  domain={[0, 0.25]}
                  tickFormatter={(v) => v.toFixed(2)}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'white',
                    border: `1px solid ${CHART_COLORS.grid}`,
                    borderRadius: '8px',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
                  }}
                  formatter={(value: number, name: string) => [
                    value.toFixed(3),
                    name === 'priceIndex' ? 'Price-based Index' : 'Quantity-based Index',
                  ]}
                  labelFormatter={(label) => `Year: ${label}`}
                />
                <Legend
                  formatter={(value) =>
                    value === 'priceIndex' ? 'Price-based Index' : 'Quantity-based Index'
                  }
                />
                <Line
                  type="monotone"
                  dataKey="priceIndex"
                  stroke={CHART_COLORS.eu}
                  strokeWidth={2}
                  dot={{ fill: CHART_COLORS.eu, strokeWidth: 1, r: 3 }}
                  activeDot={{ r: 5 }}
                />
                <Line
                  type="monotone"
                  dataKey="quantityIndex"
                  stroke={CHART_COLORS.us}
                  strokeWidth={2}
                  dot={{ fill: CHART_COLORS.us, strokeWidth: 1, r: 3 }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Legend */}
        <div className="flex justify-center gap-8 mt-6 pt-4 border-t border-border/50">
          <div className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded"
              style={{ backgroundColor: CHART_COLORS.eu }}
            />
            <span className="text-sm text-muted-foreground">European Union</span>
          </div>
          <div className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded"
              style={{ backgroundColor: CHART_COLORS.us }}
            />
            <span className="text-sm text-muted-foreground">United States</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
