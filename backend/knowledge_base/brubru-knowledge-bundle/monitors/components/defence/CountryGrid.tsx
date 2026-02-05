import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { CountryDefenceData } from '@/types/defence';

interface CountryGridProps {
  countries: CountryDefenceData[];
  isLoading?: boolean;
  onCountrySelect?: (countryCode: string) => void;
  selectedCountry?: string;
}

function TrendIndicator({ change }: { change: number }) {
  if (change > 0.5) {
    return (
      <span className="text-primary flex items-center gap-1 text-xs">
        <TrendingUp className="w-3 h-3" />
        +{change.toFixed(1)}%
      </span>
    );
  }
  if (change < -0.5) {
    return (
      <span className="text-destructive flex items-center gap-1 text-xs">
        <TrendingDown className="w-3 h-3" />
        {change.toFixed(1)}%
      </span>
    );
  }
  return (
    <span className="text-muted-foreground flex items-center gap-1 text-xs">
      <Minus className="w-3 h-3" />
      {change.toFixed(1)}%
    </span>
  );
}

function CountryCard({
  country,
  isSelected,
  onClick,
}: {
  country: CountryDefenceData;
  isSelected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`p-4 rounded-lg border transition-all flex flex-col items-center gap-2 text-left w-full ${
        isSelected
          ? 'border-primary bg-primary/5 shadow-md'
          : 'border-border/50 hover:border-primary hover:bg-muted/50'
      }`}
    >
      <img
        src={country.flagUrl}
        alt={`${country.countryName} flag`}
        className="w-10 h-7 rounded shadow-sm object-cover"
        loading="lazy"
      />
      <span className="text-sm font-medium text-secondary text-center">
        {country.countryName}
      </span>
      <span className="text-lg font-bold text-primary">
        {country.gdpPercentage.toFixed(2)}%
      </span>
      <span className="text-xs text-muted-foreground">
        of GDP
      </span>
      <TrendIndicator change={country.yearOverYearChange} />
    </button>
  );
}

function CountryCardSkeleton() {
  return (
    <div className="p-4 rounded-lg border border-border/50 flex flex-col items-center gap-2">
      <Skeleton className="w-10 h-7 rounded" />
      <Skeleton className="h-4 w-20" />
      <Skeleton className="h-6 w-16" />
      <Skeleton className="h-3 w-12" />
      <Skeleton className="h-3 w-14" />
    </div>
  );
}

export function CountryGrid({
  countries,
  isLoading,
  onCountrySelect,
  selectedCountry,
}: CountryGridProps) {
  if (isLoading) {
    return (
      <Card className="border-border/50">
        <CardHeader>
          <CardTitle className="text-xl text-secondary">
            Defence Spending by Country
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-7 gap-4">
            {Array.from({ length: 14 }).map((_, i) => (
              <CountryCardSkeleton key={i} />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border/50">
      <CardHeader>
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <CardTitle className="text-xl text-secondary">
            Defence Spending by Country
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Click a country for detailed view | {countries[0]?.year || 2023} data
          </p>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-7 gap-4">
          {countries.map((country) => (
            <CountryCard
              key={country.countryCode}
              country={country}
              isSelected={selectedCountry === country.countryCode}
              onClick={() => onCountrySelect?.(country.countryCode)}
            />
          ))}
        </div>
        <p className="text-xs text-muted-foreground text-center mt-6">
          Source: Eurostat | Sorted by GDP percentage (highest first)
        </p>
      </CardContent>
    </Card>
  );
}
