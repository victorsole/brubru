import { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine } from 'recharts';
import { TariffTrendData } from '@/types/tariff';
import { MonthlyTariffData } from '@/data/tariffFallback';

interface TariffTrendChartProps {
  yearlyData: TariffTrendData[];
  monthlyData: MonthlyTariffData[];
}

export function TariffTrendChart({ yearlyData, monthlyData }: TariffTrendChartProps) {
  const [view, setView] = useState<'monthly' | 'yearly'>('monthly');

  return (
    <div>
      {/* View Toggle */}
      <div className="flex justify-end mb-4">
        <div className="flex bg-muted rounded-lg p-1">
          <button
            onClick={() => setView('monthly')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
              view === 'monthly'
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'text-muted-foreground hover:bg-background'
            }`}
          >
            Monthly (2024-2026)
          </button>
          <button
            onClick={() => setView('yearly')}
            className={`px-3 py-1.5 text-xs font-medium rounded-md transition-all ${
              view === 'yearly'
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'text-muted-foreground hover:bg-background'
            }`}
          >
            Yearly (2018-2025)
          </button>
        </div>
      </div>

      {/* Key Events Legend for Monthly View */}
      {view === 'monthly' && (
        <div className="flex flex-wrap items-center justify-center gap-4 mb-3 text-xs">
          <div className="flex items-center gap-1.5">
            <div className="w-4 h-0.5 bg-red-500" style={{ borderTop: '2px dashed #ef4444' }}></div>
            <span className="text-muted-foreground">Trump 2.0 (Jan 20)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="w-4 h-0.5 bg-orange-500" style={{ borderTop: '2px dashed #f97316' }}></div>
            <span className="text-muted-foreground">Peak 28% (Apr 12)</span>
          </div>
        </div>
      )}

      <div className="h-[320px]">
        {view === 'monthly' ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={monthlyData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis
                dataKey="date"
                tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 10 }}
                tickLine={{ stroke: 'hsl(var(--border))' }}
                interval={2}
              />
              <YAxis
                tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
                tickLine={{ stroke: 'hsl(var(--border))' }}
                tickFormatter={(value) => `${value}%`}
                domain={[0, 30]}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--background))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: 'hsl(var(--secondary))', fontWeight: 'bold' }}
                formatter={(value: number, name: string) => {
                  const labels: Record<string, string> = {
                    usAvgTariff: 'US',
                    euAvgTariff: 'EU',
                    chinaAvgTariff: 'China',
                  };
                  return [`${value.toFixed(1)}%`, labels[name] || name];
                }}
              />
              {/* Reference line for Trump inauguration */}
              <ReferenceLine
                x="Jan 25"
                stroke="#ef4444"
                strokeDasharray="5 5"
                strokeWidth={1.5}
              />
              {/* Reference line for April Liberation Day peak */}
              <ReferenceLine
                x="Apr 25"
                stroke="#f97316"
                strokeDasharray="3 3"
                strokeWidth={1.5}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="usAvgTariff"
                name="US Avg Tariff"
                stroke="#3b82f6"
                strokeWidth={2.5}
                dot={{ fill: '#3b82f6', strokeWidth: 0, r: 2 }}
                activeDot={{ r: 5, strokeWidth: 0 }}
              />
              <Line
                type="monotone"
                dataKey="euAvgTariff"
                name="EU Avg Tariff"
                stroke="#22c55e"
                strokeWidth={2.5}
                dot={{ fill: '#22c55e', strokeWidth: 0, r: 2 }}
                activeDot={{ r: 5, strokeWidth: 0 }}
              />
              <Line
                type="monotone"
                dataKey="chinaAvgTariff"
                name="China Avg Tariff"
                stroke="#ef4444"
                strokeWidth={2.5}
                dot={{ fill: '#ef4444', strokeWidth: 0, r: 2 }}
                activeDot={{ r: 5, strokeWidth: 0 }}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={yearlyData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis
                dataKey="year"
                tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
                tickLine={{ stroke: 'hsl(var(--border))' }}
              />
              <YAxis
                tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
                tickLine={{ stroke: 'hsl(var(--border))' }}
                tickFormatter={(value) => `${value}%`}
                domain={[0, 20]}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'hsl(var(--background))',
                  border: '1px solid hsl(var(--border))',
                  borderRadius: '8px',
                }}
                labelStyle={{ color: 'hsl(var(--secondary))', fontWeight: 'bold' }}
                formatter={(value: number, name: string) => {
                  const labels: Record<string, string> = {
                    usAvgTariff: 'US',
                    euAvgTariff: 'EU',
                    chinaAvgTariff: 'China',
                  };
                  return [`${value.toFixed(1)}%`, labels[name] || name];
                }}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="usAvgTariff"
                name="US Avg Tariff"
                stroke="#3b82f6"
                strokeWidth={2.5}
                dot={{ fill: '#3b82f6', strokeWidth: 2, r: 4 }}
                activeDot={{ r: 6, strokeWidth: 0 }}
              />
              <Line
                type="monotone"
                dataKey="euAvgTariff"
                name="EU Avg Tariff"
                stroke="#22c55e"
                strokeWidth={2.5}
                dot={{ fill: '#22c55e', strokeWidth: 2, r: 4 }}
                activeDot={{ r: 6, strokeWidth: 0 }}
              />
              <Line
                type="monotone"
                dataKey="chinaAvgTariff"
                name="China Avg Tariff"
                stroke="#ef4444"
                strokeWidth={2.5}
                dot={{ fill: '#ef4444', strokeWidth: 2, r: 4 }}
                activeDot={{ r: 6, strokeWidth: 0 }}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
