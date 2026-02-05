import { useState } from 'react';
import { TrendingUp } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { GOLD_METRICS, CHART_DATA } from '@/data/goldFallback';
import type { ChartTimeframe } from '@/types/gold';

interface GoldPriceChartProps {
  className?: string;
}

const TIMEFRAMES: ChartTimeframe[] = ['1D', '1W', '1M', '1Y', '5Y'];

export function GoldPriceChart({ className = '' }: GoldPriceChartProps) {
  const [activeTimeframe, setActiveTimeframe] = useState<ChartTimeframe>('1M');
  const chartInfo = CHART_DATA[activeTimeframe];

  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-amber-500" />
            <CardTitle className="text-xl text-secondary">Gold Spot Price (XAU/USD)</CardTitle>
          </div>
          <div className="flex gap-2">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                onClick={() => setActiveTimeframe(tf)}
                className={`px-3 py-1 text-xs rounded-full font-medium transition-colors ${
                  activeTimeframe === tf
                    ? 'bg-amber-500 text-amber-900'
                    : 'bg-muted text-muted-foreground hover:bg-muted/80'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* Chart Placeholder */}
        <div className="bg-gradient-to-r from-amber-50 to-yellow-50 rounded-lg h-64 flex items-center justify-center relative overflow-hidden">
          <svg className="absolute inset-0 w-full h-full" viewBox="0 0 800 250" preserveAspectRatio="none">
            <defs>
              <linearGradient id="goldGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" style={{ stopColor: '#D4AF37', stopOpacity: 0.3 }} />
                <stop offset="100%" style={{ stopColor: '#D4AF37', stopOpacity: 0 }} />
              </linearGradient>
            </defs>
            <path d="M0,200 Q100,180 150,160 T300,140 T450,100 T600,80 T750,60 L800,50 L800,250 L0,250 Z" fill="url(#goldGradient)"/>
            <path d="M0,200 Q100,180 150,160 T300,140 T450,100 T600,80 T750,60 L800,50" stroke="#D4AF37" fill="none" strokeWidth="2"/>
          </svg>
          <div className="absolute top-4 left-4 bg-white/90 backdrop-blur-sm rounded-lg px-3 py-2 shadow">
            <p className="text-xs text-muted-foreground">All-Time High</p>
            <p className="text-lg font-bold text-amber-600">${GOLD_METRICS.allTimeHigh.toLocaleString()}</p>
            <p className="text-[10px] text-muted-foreground">{GOLD_METRICS.allTimeHighDate}</p>
          </div>
        </div>
        <div className="flex justify-between mt-4 text-xs text-muted-foreground">
          <span>Open: {chartInfo.open}</span>
          <span>High: {chartInfo.high}</span>
          <span>Low: {chartInfo.low}</span>
          <span>Prev Close: {chartInfo.prev}</span>
        </div>
      </CardContent>
    </Card>
  );
}
