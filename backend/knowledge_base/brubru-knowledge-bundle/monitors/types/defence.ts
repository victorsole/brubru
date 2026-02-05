// EU Defence Monitor Types

export interface CountryDefenceData {
  countryCode: string;
  countryName: string;
  flagUrl: string;
  year: number;
  expenditure: number; // in millions EUR
  gdpPercentage: number;
  perCapita: number;
  yearOverYearChange: number;
}

export interface DefenceSpendingTrend {
  year: number;
  totalEU: number;
  avgGdpPercentage: number;
  // Global comparison data (in millions EUR)
  totalUS?: number;
  totalChina?: number;
  totalRussia?: number;
  // GDP percentages for global comparison
  gdpUS?: number;
  gdpChina?: number;
  gdpRussia?: number;
}

export interface DefenceNewsItem {
  id: string;
  title: string;
  link: string;
  pubDate: Date;
  source: string;
  sourceUrl: string;
  description?: string;
}

export interface LegislationItem {
  id: string;
  celexNumber: string;
  title: string;
  type: 'Regulation' | 'Directive' | 'Decision' | 'Recommendation' | 'Other';
  date: Date;
  status: 'Proposed' | 'In Progress' | 'Adopted' | 'In Force';
  eurLexUrl: string;
  summary?: string;
}

export interface PescoProject {
  id: string;
  name: string;
  domain: 'Training' | 'Land' | 'Maritime' | 'Air' | 'Cyber' | 'Strategic Enablers' | 'Space';
  coordinator: string;
  participants: string[];
  status: 'Active' | 'Completed' | 'Planning';
  description: string;
}

export interface DefenceMetrics {
  totalExpenditure: number;
  avgGdpPercentage: number;
  yearOverYearChange: number;
  pescoProjects: number;
  lastUpdated: Date;
}

// EU27 country codes and names
export const EU_COUNTRIES: { code: string; name: string; flagEmoji: string }[] = [
  { code: 'AT', name: 'Austria', flagEmoji: '🇦🇹' },
  { code: 'BE', name: 'Belgium', flagEmoji: '🇧🇪' },
  { code: 'BG', name: 'Bulgaria', flagEmoji: '🇧🇬' },
  { code: 'HR', name: 'Croatia', flagEmoji: '🇭🇷' },
  { code: 'CY', name: 'Cyprus', flagEmoji: '🇨🇾' },
  { code: 'CZ', name: 'Czechia', flagEmoji: '🇨🇿' },
  { code: 'DK', name: 'Denmark', flagEmoji: '🇩🇰' },
  { code: 'EE', name: 'Estonia', flagEmoji: '🇪🇪' },
  { code: 'FI', name: 'Finland', flagEmoji: '🇫🇮' },
  { code: 'FR', name: 'France', flagEmoji: '🇫🇷' },
  { code: 'DE', name: 'Germany', flagEmoji: '🇩🇪' },
  { code: 'EL', name: 'Greece', flagEmoji: '🇬🇷' },
  { code: 'HU', name: 'Hungary', flagEmoji: '🇭🇺' },
  { code: 'IE', name: 'Ireland', flagEmoji: '🇮🇪' },
  { code: 'IT', name: 'Italy', flagEmoji: '🇮🇹' },
  { code: 'LV', name: 'Latvia', flagEmoji: '🇱🇻' },
  { code: 'LT', name: 'Lithuania', flagEmoji: '🇱🇹' },
  { code: 'LU', name: 'Luxembourg', flagEmoji: '🇱🇺' },
  { code: 'MT', name: 'Malta', flagEmoji: '🇲🇹' },
  { code: 'NL', name: 'Netherlands', flagEmoji: '🇳🇱' },
  { code: 'PL', name: 'Poland', flagEmoji: '🇵🇱' },
  { code: 'PT', name: 'Portugal', flagEmoji: '🇵🇹' },
  { code: 'RO', name: 'Romania', flagEmoji: '🇷🇴' },
  { code: 'SK', name: 'Slovakia', flagEmoji: '🇸🇰' },
  { code: 'SI', name: 'Slovenia', flagEmoji: '🇸🇮' },
  { code: 'ES', name: 'Spain', flagEmoji: '🇪🇸' },
  { code: 'SE', name: 'Sweden', flagEmoji: '🇸🇪' },
];
