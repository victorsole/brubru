import { Zap, ExternalLink } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TOKENIZED_GOLD } from '@/data/goldFallback';
import type { TokenizedGold } from '@/types/gold';

interface TokenizedGoldSectionProps {
  tokens?: TokenizedGold[];
  className?: string;
}

export function TokenizedGoldSection({
  tokens = TOKENIZED_GOLD,
  className = '',
}: TokenizedGoldSectionProps) {
  return (
    <Card className={`border-border/50 ${className}`}>
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <Zap className="w-5 h-5 text-purple-600" />
          <CardTitle className="text-xl text-secondary">Tokenized Gold (24/7 Trading)</CardTitle>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          Blockchain-based gold tokens backed 1:1 by physical gold
        </p>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {tokens.map((token) => (
            <div
              key={token.symbol}
              className={`p-4 rounded-lg border ${
                token.symbol === 'PAXG'
                  ? 'bg-gradient-to-r from-amber-50 to-yellow-50 border-amber-200'
                  : 'bg-gradient-to-r from-green-50 to-emerald-50 border-green-200'
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                    token.symbol === 'PAXG'
                      ? 'bg-gradient-to-br from-amber-400 to-amber-600'
                      : 'bg-green-500'
                  }`}>
                    <span className={`font-bold text-xs ${token.symbol === 'PAXG' ? 'text-amber-900' : 'text-white'}`}>
                      {token.symbol}
                    </span>
                  </div>
                  <div>
                    <p className="font-semibold text-secondary">{token.name}</p>
                    <p className="text-xs text-muted-foreground">{token.issuer}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-xl font-bold text-secondary">${token.price.toLocaleString()}</p>
                  <p className="text-xs text-green-600">{token.change}</p>
                </div>
              </div>
              <div className={`flex justify-between text-xs text-muted-foreground pt-2 border-t ${
                token.symbol === 'PAXG' ? 'border-amber-200' : 'border-green-200'
              }`}>
                <span>Market Cap: <strong className="text-secondary">{token.marketCap}</strong></span>
                <span>24h Vol: <strong className="text-secondary">{token.volume24h}</strong></span>
                <span>Share: <strong className="text-secondary">{token.marketShare}</strong></span>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4 p-3 bg-purple-50 rounded-lg border border-purple-100">
          <p className="text-xs text-purple-700">
            <strong>MiCA Note:</strong> PAXG/XAUT classified as Asset-Referenced Tokens. Dutch AFM transitional period ends 30 June 2025.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
