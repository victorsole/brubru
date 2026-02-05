import { useState } from 'react';
import { BarChart3, ExternalLink } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { GOLD_ETFS } from '@/data/goldFallback';
import type { GoldETF, ETFFilter } from '@/types/gold';

interface GoldETFsTableProps {
  etfs?: GoldETF[];
  className?: string;
}

export function GoldETFsTable({
  etfs = GOLD_ETFS,
  className = '',
}: GoldETFsTableProps) {
  const [filter, setFilter] = useState<ETFFilter>('all');

  const filteredETFs = filter === 'all'
    ? etfs
    : etfs.filter(etf => etf.region === filter);

  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-secondary" />
            <CardTitle className="text-xl text-secondary">Gold ETFs Comparison</CardTitle>
          </div>
          <div className="flex gap-2">
            {(['all', 'eu', 'us'] as ETFFilter[]).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-3 py-1 text-xs rounded-full font-medium transition-colors ${
                  filter === f
                    ? 'bg-amber-500 text-amber-900'
                    : 'bg-muted text-muted-foreground hover:bg-muted/80'
                }`}
              >
                {f === 'all' ? 'All' : f === 'eu' ? 'European' : 'US-Listed'}
              </button>
            ))}
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-3 px-4 font-medium text-muted-foreground">ETF Name</th>
                <th className="text-left py-3 px-4 font-medium text-muted-foreground">Ticker</th>
                <th className="text-right py-3 px-4 font-medium text-muted-foreground">AUM</th>
                <th className="text-right py-3 px-4 font-medium text-muted-foreground">TER</th>
                <th className="text-right py-3 px-4 font-medium text-muted-foreground">YTD Return</th>
                <th className="text-center py-3 px-4 font-medium text-muted-foreground">Exchange</th>
              </tr>
            </thead>
            <tbody>
              {filteredETFs.map((etf) => (
                <tr
                  key={etf.ticker}
                  className={`border-b border-border/50 hover:bg-muted/30 transition-colors ${
                    etf.region === 'eu' ? 'bg-blue-50/50' : ''
                  }`}
                >
                  <td className="py-3 px-4 font-medium text-secondary">
                    <div className="flex items-center gap-2">
                      {etf.name}
                      {etf.region === 'eu' && (
                        <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-[10px]">EU</span>
                      )}
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <span className="px-2 py-1 bg-amber-100 text-amber-700 rounded text-xs font-medium">
                      {etf.ticker}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">{etf.aum}</td>
                  <td className={`py-3 px-4 text-right ${etf.ter === '0.00%' ? 'font-medium text-green-600' : ''}`}>
                    {etf.ter}
                  </td>
                  <td className="py-3 px-4 text-right font-medium text-green-600">{etf.ytdReturn}</td>
                  <td className="py-3 px-4 text-center">
                    <span className="text-xs text-muted-foreground">{etf.exchange}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-100">
          <p className="text-xs text-blue-700">
            <strong>European Advantage:</strong> Xetra-Gold (4GLD) offers 0% TER and physical delivery option - the most cost-effective gold ETF in Europe.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
