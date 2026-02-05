import { useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { DefenceSpendingTrend } from '@/types/defence';

interface DefenceSpendingChartProps {
  data: DefenceSpendingTrend[];
  isLoading?: boolean;
}

const CHART_COLORS = {
  primary: 'hsl(120, 65%, 45%)',   // EU - Green
  secondary: 'hsl(170, 50%, 15%)',
  accent: 'hsl(45, 85%, 50%)',
  grid: 'hsl(120, 20%, 88%)',
  us: 'hsl(220, 70%, 50%)',        // US - Blue
  china: 'hsl(0, 70%, 50%)',       // China - Red
  russia: 'hsl(280, 60%, 50%)',    // Russia - Purple
};

export function DefenceSpendingChart({ data, isLoading }: DefenceSpendingChartProps) {
  const [activeMetric, setActiveMetric] = useState<'total' | 'gdp'>('total');

  if (isLoading) {
    return (
      <Card className="border-border/50">
        <CardHeader>
          <Skeleton className="h-6 w-48" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-[400px] w-full" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border/50 w-full h-full flex flex-col">
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-xl text-secondary">
          Comparing Defence Spending
        </CardTitle>
        <div className="flex gap-2">
          <button
            onClick={() => setActiveMetric('total')}
            className={`px-3 py-1 text-sm rounded-md transition-colors ${
              activeMetric === 'total'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
            }`}
          >
            Total (€B)
          </button>
          <button
            onClick={() => setActiveMetric('gdp')}
            className={`px-3 py-1 text-sm rounded-md transition-colors ${
              activeMetric === 'gdp'
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-muted/80'
            }`}
          >
            % GDP
          </button>
        </div>
      </CardHeader>
      <CardContent className="flex-1 flex flex-col">
        <ResponsiveContainer width="100%" height="100%" minHeight={400}>
          <LineChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
            <XAxis
              dataKey="year"
              stroke={CHART_COLORS.secondary}
              fontSize={12}
              tickLine={false}
            />
            <YAxis
              stroke={CHART_COLORS.secondary}
              fontSize={12}
              tickLine={false}
              tickFormatter={(value) =>
                activeMetric === 'total'
                  ? `€${(value / 1000).toFixed(0)}B`
                  : `${value.toFixed(1)}%`
              }
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'white',
                border: `1px solid ${CHART_COLORS.grid}`,
                borderRadius: '8px',
                boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
              }}
              formatter={(value: number, name: string) =>
                activeMetric === 'total'
                  ? [`€${(value / 1000).toFixed(0)}B`, name]
                  : [`${value.toFixed(2)}%`, name]
              }
              labelFormatter={(label) => `Year: ${label}`}
            />
            <Legend />
            {activeMetric === 'total' ? (
              <>
                <Line
                  type="monotone"
                  dataKey="totalUS"
                  name="United States"
                  stroke={CHART_COLORS.us}
                  strokeWidth={2}
                  dot={{ fill: CHART_COLORS.us, strokeWidth: 1, r: 3 }}
                  activeDot={{ r: 5 }}
                />
                <Line
                  type="monotone"
                  dataKey="totalChina"
                  name="China"
                  stroke={CHART_COLORS.china}
                  strokeWidth={2}
                  dot={{ fill: CHART_COLORS.china, strokeWidth: 1, r: 3 }}
                  activeDot={{ r: 5 }}
                />
                <Line
                  type="monotone"
                  dataKey="totalEU"
                  name="EU-27"
                  stroke={CHART_COLORS.primary}
                  strokeWidth={3}
                  dot={{ fill: CHART_COLORS.primary, strokeWidth: 2, r: 4 }}
                  activeDot={{ r: 6, fill: CHART_COLORS.accent }}
                />
                <Line
                  type="monotone"
                  dataKey="totalRussia"
                  name="Russia"
                  stroke={CHART_COLORS.russia}
                  strokeWidth={2}
                  dot={{ fill: CHART_COLORS.russia, strokeWidth: 1, r: 3 }}
                  activeDot={{ r: 5 }}
                />
              </>
            ) : (
              <>
                <Line
                  type="monotone"
                  dataKey="gdpUS"
                  name="United States"
                  stroke={CHART_COLORS.us}
                  strokeWidth={2}
                  dot={{ fill: CHART_COLORS.us, strokeWidth: 1, r: 3 }}
                  activeDot={{ r: 5 }}
                />
                <Line
                  type="monotone"
                  dataKey="gdpRussia"
                  name="Russia"
                  stroke={CHART_COLORS.russia}
                  strokeWidth={2}
                  dot={{ fill: CHART_COLORS.russia, strokeWidth: 1, r: 3 }}
                  activeDot={{ r: 5 }}
                />
                <Line
                  type="monotone"
                  dataKey="gdpChina"
                  name="China"
                  stroke={CHART_COLORS.china}
                  strokeWidth={2}
                  dot={{ fill: CHART_COLORS.china, strokeWidth: 1, r: 3 }}
                  activeDot={{ r: 5 }}
                />
                <Line
                  type="monotone"
                  dataKey="avgGdpPercentage"
                  name="EU-27"
                  stroke={CHART_COLORS.primary}
                  strokeWidth={3}
                  dot={{ fill: CHART_COLORS.primary, strokeWidth: 2, r: 4 }}
                  activeDot={{ r: 6, fill: CHART_COLORS.accent }}
                />
              </>
            )}
          </LineChart>
        </ResponsiveContainer>
        <p className="text-xs text-muted-foreground text-center mt-4">
          Source: Eurostat COFOG GF02 (EU), SIPRI Military Expenditure Database (US, China, Russia)
        </p>
      </CardContent>
    </Card>
  );
}
