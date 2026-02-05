import { Pickaxe } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { GOLD_PRODUCERS, GOLD_METRICS } from '@/data/goldFallback';
import type { GoldProducer } from '@/types/gold';

interface GoldMiningProductionProps {
  producers?: GoldProducer[];
  className?: string;
}

const rankColors = [
  'bg-gradient-to-b from-amber-100 to-amber-50 border-amber-200',
  'bg-gradient-to-b from-gray-100 to-gray-50 border-gray-200',
  'bg-gradient-to-b from-orange-100 to-orange-50 border-orange-200',
  'bg-muted/30 border-border/50',
  'bg-muted/30 border-border/50',
];

const rankBadgeColors = [
  'bg-red-500',
  'bg-blue-500',
  'bg-amber-500',
  'bg-gray-400',
  'bg-gray-400',
];

export function GoldMiningProduction({
  producers = GOLD_PRODUCERS,
  className = '',
}: GoldMiningProductionProps) {
  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Pickaxe className="w-5 h-5 text-secondary" />
            <CardTitle className="text-xl text-secondary">Global Gold Mining Production (2024)</CardTitle>
          </div>
          <span className="text-sm text-muted-foreground">Total: {GOLD_METRICS.mineProduction} (+1% YoY)</span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          {producers.map((producer, idx) => (
            <div
              key={producer.country}
              className={`text-center p-4 rounded-lg border ${rankColors[idx]}`}
            >
              <div className={`w-8 h-8 mx-auto mb-2 rounded-full ${rankBadgeColors[idx]} flex items-center justify-center text-white text-xs font-bold`}>
                {producer.rank}
              </div>
              <p className="text-lg font-bold text-secondary">{producer.production} MT</p>
              <p className="text-sm text-muted-foreground">{producer.country}</p>
              {producer.change ? (
                <p className={`text-xs ${producer.change.startsWith('+') ? 'text-green-600' : 'text-red-500'}`}>
                  {producer.change}
                </p>
              ) : (
                <p className="text-xs text-muted-foreground">{producer.share} share</p>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
