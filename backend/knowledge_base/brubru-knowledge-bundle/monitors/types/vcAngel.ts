// VC & Angel Ecosystem Types

export interface VCMarketMetrics {
  euGlobalShare: string;
  usGlobalShare: string;
  chinaGlobalShare: string;
  euAvgFundSize: string;
  usAvgFundSize: string;
  euUnicorns: number;
  usUnicorns: number;
  euPensionFundShare: string;
  usPensionFundShare: string;
}

export interface VCLegislation {
  id: string;
  name: string;
  shortName: string;
  legalBasis: string;
  status: 'in_force' | 'under_review' | 'transposition' | 'proposed';
  statusLabel: string;
  description: string;
  keyProvisions: string[];
  eurLexUrl?: string;
  deadline?: string;
}

export interface AngelTaxScheme {
  countryCode: string;
  countryName: string;
  schemeName: string;
  taxRelief: string;
  maxInvestment: string;
  holdingPeriod: string;
  conditions: string;
}

export interface ELTIFDataPoint {
  year: number;
  fundsMarketed: number;
  aumBillions: number;
}

export interface VCKeyDate {
  date: string;
  event: string;
  status: 'past' | 'current' | 'upcoming';
}

export interface VCInstitution {
  name: string;
  role: string;
  url: string;
  type: 'eu' | 'industry';
}
