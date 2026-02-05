export type PolicyArea = 'energy' | 'digital' | 'trade' | 'health' | 'transport' | 'agriculture' | 'economic';

export interface Report {
  id: string;
  slug: string;
  title: string;
  subtitle?: string;
  description: string;
  author: string;
  publishedDate: string;
  policyArea: PolicyArea;
  filePath: string;
  readingTime: number;
  featured?: boolean;
}

export const policyAreaLabels: Record<PolicyArea, string> = {
  energy: 'Energy & Climate',
  digital: 'Digital Policy',
  trade: 'Trade & Economics',
  health: 'Health & MedTech',
  transport: 'Transport & Mobility',
  agriculture: 'Agriculture & Food',
  economic: 'EU Strategy & Competitiveness'
};

export const policyAreaColors: Record<PolicyArea, string> = {
  energy: 'bg-amber-500/10 text-amber-700 border-amber-500/20',
  digital: 'bg-blue-500/10 text-blue-700 border-blue-500/20',
  trade: 'bg-emerald-500/10 text-emerald-700 border-emerald-500/20',
  health: 'bg-rose-500/10 text-rose-700 border-rose-500/20',
  transport: 'bg-violet-500/10 text-violet-700 border-violet-500/20',
  agriculture: 'bg-lime-500/10 text-lime-700 border-lime-500/20',
  economic: 'bg-indigo-500/10 text-indigo-700 border-indigo-500/20'
};

export const reports: Report[] = [
  {
    id: '1',
    slug: 'iberian-blackout',
    title: 'EU Critical Infrastructure Resilience',
    subtitle: 'The Iberian Blackout Case Study',
    description: 'Analysis of the April 2025 Power Grid Failure and EU Policy Implications. Examines the CER and NIS2 Directives, interconnection infrastructure deficits, and investment requirements for European grid resilience.',
    author: 'Victor Solé Ferioli',
    publishedDate: '2025-04-30',
    policyArea: 'energy',
    filePath: '/open_reports/iberian_blackout.md',
    readingTime: 15,
    featured: true
  },
  {
    id: '2',
    slug: 'eu-mercosur',
    title: 'The EU-Mercosur Agreement',
    subtitle: 'Implications for European Agri-Food Sectors',
    description: 'Comprehensive analysis of the landmark EU-Mercosur trade agreement concluded in December 2024. Examines tariff provisions, agricultural quotas, environmental commitments, and ratification prospects.',
    author: 'Victor Solé Ferioli',
    publishedDate: '2025-04-30',
    policyArea: 'trade',
    filePath: '/open_reports/eu-mercosur.md',
    readingTime: 18,
    featured: true
  },
  {
    id: '3',
    slug: 'mediterranean-fisheries',
    title: 'Mediterranean Fisheries Under Pressure',
    subtitle: 'EU Bottom Trawling Regulation Reform',
    description: 'Analysis of the Western Mediterranean Multi-Annual Plan entering its permanent phase in 2025. Examines stock recovery, fishing effort reductions, MPA coverage, and the balance between ecological sustainability and fishing community viability.',
    author: 'Victor Solé Ferioli',
    publishedDate: '2024-12-15',
    policyArea: 'transport',
    filePath: '/open_reports/mediterranean-fisheries.md',
    readingTime: 20,
    featured: false
  },
  {
    id: '4',
    slug: 'ukraine-in-eu',
    title: "Ukraine's Path to EU Membership",
    subtitle: 'The €136 Billion Question Reshaping Europe',
    description: 'Comprehensive analysis of budgetary, institutional, and agricultural implications of Ukrainian EU accession. Examines €110-136 billion net transfers, CAP reform requirements, Maastricht criteria gaps, and the political obstacles to enlargement.',
    author: 'Victor Solé Ferioli',
    publishedDate: '2025-12-01',
    policyArea: 'trade',
    filePath: '/open_reports/ukraine-in-eu.md',
    readingTime: 22,
    featured: true
  },
  {
    id: '5',
    slug: 'eu-rrf',
    title: 'EU Recovery and Resilience Facility',
    subtitle: 'Implementation Reaches Critical Juncture',
    description: 'Analysis of the €650 billion RRF as it approaches the August 2026 deadline. Examines absorption rates, ECA audit findings, milestone achievement by policy pillar, REPowerEU energy outcomes, and the extension debate.',
    author: 'Victor Solé Ferioli',
    publishedDate: '2025-12-15',
    policyArea: 'trade',
    filePath: '/open_reports/eu-rff.md',
    readingTime: 20,
    featured: true
  },
  {
    id: '6',
    slug: 'ai-act-implementation',
    title: 'The AI Act Implementation Challenge',
    subtitle: "Europe's Regulatory Leap into the Unknown",
    description: 'Analysis of the world\'s first comprehensive AI regulation. Examines compliance burdens, high-risk classification disputes, AI Office capacity, GPAI model rules, and global regulatory divergence.',
    author: 'Victor Solé Ferioli',
    publishedDate: '2025-06-15',
    policyArea: 'digital',
    filePath: '/open_reports/ai-act-implementation.md',
    readingTime: 18,
    featured: true
  },
  {
    id: '7',
    slug: 'cbam-carbon-border',
    title: 'Carbon Border Adjustment Mechanism',
    subtitle: "The EU's Climate Trade Gambit",
    description: 'Analysis of the world\'s first carbon border tax as it enters full implementation. Examines sector impacts, third-country reactions, WTO challenges, compliance costs, and environmental effectiveness.',
    author: 'Victor Solé Ferioli',
    publishedDate: '2025-12-23',
    policyArea: 'trade',
    filePath: '/open_reports/cbam-carbon-border.md',
    readingTime: 20,
    featured: true
  },
  {
    id: '8',
    slug: 'eu-agri-food-days-2025',
    title: 'EU Agri-Food Days 2025',
    subtitle: 'CAP Post-2027 and the Future of European Agriculture',
    description: 'Comprehensive research brief from the third edition of EU Agri-Food Days (15-17 December 2025). Covers the post-2027 CAP proposal with €300B income support, EU Agricultural Outlook 2035, EU-FarmBook launch, EIB €3B loan package, and EU-Mercosur safeguards.',
    author: 'Victor Solé Ferioli',
    publishedDate: '2025-12-20',
    policyArea: 'agriculture',
    filePath: '/open_reports/eu-agri-food-days-2025.md',
    readingTime: 25,
    featured: true
  },
  {
    id: '9',
    slug: 'eu-anti-coercion-instrument',
    title: 'The EU Anti-Coercion Instrument',
    subtitle: "The EU's Most Powerful Trade Defence Tool Against US Tariffs",
    description: "Analysis of how the EU could deploy its Anti-Coercion Instrument (ACI) against Trump's Greenland tariffs. Examines the legal framework, activation timeline, available countermeasures, and strategic implications for businesses.",
    author: 'Victor Solé Ferioli',
    publishedDate: '2026-01-19',
    policyArea: 'trade',
    filePath: '/open_reports/aci.md',
    readingTime: 15,
    featured: true
  },
  {
    id: '10',
    slug: 'eu-strategic-blueprint-2024',
    title: "The EU's 2024 Strategic Blueprint",
    subtitle: 'Three Reports Reshaping Europe: Letta, Draghi, Niinistö',
    description: 'Synthesis of three landmark 2024 reports—Letta on Single Market, Draghi on competitiveness, Niinistö on defence—that together propose 500+ recommendations and €800B+ in annual investment to transform the European Union.',
    author: 'Victor Solé Ferioli',
    publishedDate: '2025-10-01',
    policyArea: 'economic',
    filePath: '/open_reports/letta_draghi_niinisto.md',
    readingTime: 20,
    featured: true
  },
  {
    id: '11',
    slug: 'crisi-ferroviaria',
    title: 'Crisi ferroviària a Catalunya',
    subtitle: 'Infrafinançament crònic i mecanismes de finançament europeu',
    description: "Anàlisi de les causes estructurals de la crisi ferroviària catalana i els instruments de finançament europeu disponibles per revertir dècades d'infrafinançament. Primer informe en català.",
    author: 'Victor Solé Ferioli',
    publishedDate: '2026-01-23',
    policyArea: 'transport',
    filePath: '/open_reports/crisi_ferroviaria.md',
    readingTime: 12,
    featured: true
  }
];

export const getReportBySlug = (slug: string): Report | undefined => {
  return reports.find(report => report.slug === slug);
};

export const getReportsByPolicyArea = (area: PolicyArea): Report[] => {
  return reports.filter(report => report.policyArea === area);
};

export const formatReportDate = (dateString: string): string => {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric'
  });
};
