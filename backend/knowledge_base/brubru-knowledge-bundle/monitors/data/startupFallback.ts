import type {
  CountryStartupData,
  StartupLegislation,
  EUFundingProgram,
  FundingComparison,
  StartupMetrics,
  DataSource,
} from '@/types/startup';

export const STARTUP_METRICS: StartupMetrics = {
  ecosystemValue: '$4.2T',
  activeUnicorns: 630,
  newUnicorns2025: 27,
  vcFunding2024: '$51B',
  vcFundingChange: '-5%',
  activeStartups: '36K+',
  newFounders2025: '28,000+',
  techGdpShare: '15%',
  deeptechShare: '38%',
  defenceTech2025: '$2.1B',
  defenceTechChange: '+65%',
  euIpoMedian: '$48M',
  usIpoMedian: '$650M',
  singleMarketTariff: '110%',
};

export const COUNTRY_STARTUP_DATA: CountryStartupData[] = [
  { iso: 'GBR', name: 'United Kingdom', unicorns: 150, funding2024: '$14.4B', globalRank: 2, keyHubs: ['London', 'Manchester', 'Cambridge'] },
  { iso: 'DEU', name: 'Germany', unicorns: 30, funding2024: '$7.4B', globalRank: 7, keyHubs: ['Berlin', 'Munich', 'Hamburg'] },
  { iso: 'FRA', name: 'France', unicorns: 45, funding2024: '$7.1B', globalRank: 8, keyHubs: ['Paris', 'Lyon', 'Toulouse'] },
  { iso: 'SWE', name: 'Sweden', unicorns: 41, funding2024: '$2.4B', globalRank: 6, keyHubs: ['Stockholm', 'Gothenburg'] },
  { iso: 'NLD', name: 'Netherlands', unicorns: 15, funding2024: '$3.1B', globalRank: 10, keyHubs: ['Amsterdam', 'Eindhoven'] },
  { iso: 'CHE', name: 'Switzerland', unicorns: 12, funding2024: '$2.8B', globalRank: 9, keyHubs: ['Zurich', 'Lausanne', 'Zug'] },
  { iso: 'EST', name: 'Estonia', unicorns: 11, funding2024: '$303M', globalRank: 11, keyHubs: ['Tallinn'] },
  { iso: 'POL', name: 'Poland', unicorns: 18, funding2024: '$2.3B', globalRank: 20, keyHubs: ['Warsaw', 'Krakow'] },
  { iso: 'ESP', name: 'Spain', unicorns: 18, funding2024: '$2.9B', globalRank: 12, keyHubs: ['Barcelona', 'Madrid'] },
  { iso: 'IRL', name: 'Ireland', unicorns: 9, funding2024: '$1.2B', globalRank: 16, keyHubs: ['Dublin'] },
  { iso: 'UKR', name: 'Ukraine', unicorns: 9, funding2024: '$286M', globalRank: 46, keyHubs: ['Kyiv', 'Lviv'] },
  { iso: 'FIN', name: 'Finland', unicorns: 7, funding2024: '$1.5B', globalRank: 14, keyHubs: ['Helsinki', 'Oulu'] },
  { iso: 'CZE', name: 'Czech Republic', unicorns: 6, funding2024: '$255M', globalRank: 25, keyHubs: ['Prague', 'Brno'] },
  { iso: 'TUR', name: 'Turkey', unicorns: 5, funding2024: '-', globalRank: 40, keyHubs: ['Istanbul', 'Ankara'] },
  { iso: 'PRT', name: 'Portugal', unicorns: 5, funding2024: '$886M', globalRank: 33, keyHubs: ['Lisbon', 'Porto'] },
  { iso: 'ITA', name: 'Italy', unicorns: 4, funding2024: '$959M', globalRank: 27, keyHubs: ['Milan', 'Rome', 'Turin'] },
  { iso: 'NOR', name: 'Norway', unicorns: 5, funding2024: '$500M', globalRank: 15, keyHubs: ['Oslo', 'Bergen'] },
  { iso: 'DNK', name: 'Denmark', unicorns: 3, funding2024: '$800M', globalRank: 17, keyHubs: ['Copenhagen', 'Aarhus'] },
  { iso: 'LTU', name: 'Lithuania', unicorns: 3, funding2024: '$298M', globalRank: 19, keyHubs: ['Vilnius'] },
  { iso: 'ROU', name: 'Romania', unicorns: 3, funding2024: '$150M', globalRank: 35, keyHubs: ['Bucharest', 'Cluj-Napoca'] },
  { iso: 'HRV', name: 'Croatia', unicorns: 3, funding2024: '$50M', globalRank: 50, keyHubs: ['Zagreb'] },
  { iso: 'AUT', name: 'Austria', unicorns: 3, funding2024: '$519M', globalRank: 26, keyHubs: ['Vienna', 'Linz'] },
  { iso: 'BEL', name: 'Belgium', unicorns: 3, funding2024: '$1.04B', globalRank: 23, keyHubs: ['Brussels', 'Ghent', 'Antwerp'] },
  { iso: 'HUN', name: 'Hungary', unicorns: 1, funding2024: '$100M', globalRank: 58, keyHubs: ['Budapest'] },
  { iso: 'GRC', name: 'Greece', unicorns: 1, funding2024: '$150M', globalRank: 57, keyHubs: ['Athens'] },
  { iso: 'BGR', name: 'Bulgaria', unicorns: 0, funding2024: '$50M', globalRank: 40, keyHubs: ['Sofia'] },
  { iso: 'SVN', name: 'Slovenia', unicorns: 0, funding2024: '$30M', globalRank: 45, keyHubs: ['Ljubljana'] },
  { iso: 'LVA', name: 'Latvia', unicorns: 0, funding2024: '$40M', globalRank: 49, keyHubs: ['Riga'] },
  { iso: 'SVK', name: 'Slovakia', unicorns: 0, funding2024: '$35M', globalRank: 45, keyHubs: ['Bratislava'] },
  { iso: 'SRB', name: 'Serbia', unicorns: 0, funding2024: '$25M', globalRank: 55, keyHubs: ['Belgrade'] },
  { iso: 'MNE', name: 'Montenegro', unicorns: 0, funding2024: '-', globalRank: 80, keyHubs: ['Podgorica'] },
  { iso: 'MKD', name: 'North Macedonia', unicorns: 0, funding2024: '-', globalRank: 75, keyHubs: ['Skopje'] },
  { iso: 'ALB', name: 'Albania', unicorns: 0, funding2024: '-', globalRank: 85, keyHubs: ['Tirana'] },
  { iso: 'LUX', name: 'Luxembourg', unicorns: 0, funding2024: '$100M', globalRank: 35, keyHubs: ['Luxembourg City'] },
  { iso: 'MLT', name: 'Malta', unicorns: 0, funding2024: '$20M', globalRank: 60, keyHubs: ['Valletta'] },
  { iso: 'CYP', name: 'Cyprus', unicorns: 0, funding2024: '$30M', globalRank: 55, keyHubs: ['Nicosia', 'Limassol'] },
];

export const LEGISLATION_IN_FORCE: StartupLegislation[] = [
  {
    id: 'startup-strategy',
    title: 'EU Startup & Scaleup Strategy',
    description: 'COM(2025) 270 - May 2025',
    status: 'in_force',
    timeline: 'Adopted',
    url: 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=celex:52025DC0270',
  },
  {
    id: 'siu',
    title: 'Savings & Investments Union',
    description: 'March 2025',
    status: 'in_force',
    timeline: 'Adopted',
    url: 'https://finance.ec.europa.eu/regulation-and-supervision/savings-and-investments-union_en',
  },
  {
    id: 'data-act',
    title: 'Data Act',
    description: 'In force Sept 2025',
    status: 'in_force',
    timeline: 'In Force',
    url: 'https://eur-lex.europa.eu/eli/reg/2023/2854/oj/eng',
  },
  {
    id: 'gber',
    title: 'GBER Art. 22 (State Aid)',
    description: 'Extended to 2026',
    status: 'in_force',
    timeline: 'In Force',
    url: 'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A02014R0651-20230701',
  },
];

export const LEGISLATION_PROPOSED: StartupLegislation[] = [
  {
    id: '28th-regime',
    title: '28th Regime / EU-Inc',
    description: 'VdL announced at Davos',
    status: 'proposed',
    timeline: 'Mar 2026',
    url: 'https://www.eu-inc.org/',
  },
  {
    id: 'innovation-act',
    title: 'European Innovation Act',
    description: 'Sandbox framework',
    status: 'proposed',
    timeline: 'Q1 2026',
    url: 'https://research-and-innovation.ec.europa.eu/news/all-research-and-innovation-news/commission-concludes-public-consultation-european-innovation-act-2025-12-04_en',
  },
  {
    id: 'startup-definitions',
    title: 'Startup/Scaleup Definitions',
    description: 'Harmonized EU-wide',
    status: 'proposed',
    timeline: 'Q1 2026',
    url: 'https://research-and-innovation.ec.europa.eu/strategy/strategy-research-and-innovation/jobs-and-economy/eu-startup-and-scaleup-strategy_en',
  },
  {
    id: 'cloud-ai-act',
    title: 'Cloud & AI Development Act',
    description: 'Infrastructure focus',
    status: 'proposed',
    timeline: 'Q1 2026',
    url: 'https://www.europarl.europa.eu/thinktank/en/document/EPRS_BRI(2025)779251',
  },
];

export const LEGISLATION_UPCOMING: StartupLegislation[] = [
  {
    id: 'quantum-act',
    title: 'Quantum Act',
    description: 'Quantum tech framework',
    status: 'upcoming',
    timeline: 'Q2 2026',
    url: 'https://digital-strategy.ec.europa.eu/en/news/commission-invites-contributions-shape-future-eu-quantum-act',
  },
  {
    id: 'euveca-review',
    title: 'EuVECA Regulation Review',
    description: 'Widen investable assets',
    status: 'upcoming',
    timeline: 'Q3 2026',
    url: 'https://www.europarl.europa.eu/legislative-train/package-action-plan-for-capital-markets-union/file-review-of-euveca-and-eusef-legislation',
  },
  {
    id: 'ai-sandboxes',
    title: 'AI Act Sandboxes',
    description: 'Member State deadline',
    status: 'upcoming',
    timeline: 'Aug 2026',
    url: 'https://www.europarl.europa.eu/RegData/etudes/BRIE/2022/733544/EPRS_BRI(2022)733544_EN.pdf',
  },
  {
    id: 'ip-valuation',
    title: 'IP Valuation Framework',
    description: 'IP-backed financing',
    status: 'upcoming',
    timeline: 'Q2 2027',
    url: 'https://intellectual-property-helpdesk.ec.europa.eu/regional-helpdesks/european-ip-helpdesk/europe-ip-specials/intellectual-property-valuation_en',
  },
];

export const LEGISLATION_RUMOURED: StartupLegislation[] = [
  {
    id: 'stock-options',
    title: 'Stock Options Directive',
    description: 'Part of 28th Regime pkg',
    status: 'rumoured',
    timeline: 'TBD',
  },
  {
    id: 'corporate-network',
    title: 'European Corporate Network',
    description: 'CVC integration',
    status: 'rumoured',
    timeline: '2026?',
  },
  {
    id: 'era-act',
    title: 'ERA (Research Area) Act',
    description: 'R&I harmonization',
    status: 'rumoured',
    timeline: 'Q3 2026?',
  },
  {
    id: 'merger-guidelines',
    title: 'Horizontal Merger Guidelines',
    description: 'Innovation competition',
    status: 'rumoured',
    timeline: '2027?',
  },
];

export const EU_FUNDING_PROGRAMS: EUFundingProgram[] = [
  {
    name: 'European Innovation Council',
    description: 'Horizon Europe 2021-2027',
    totalBudget: '$10.1B',
    subPrograms: [
      { name: 'Pathfinder', budget: '$262M' },
      { name: 'Accelerator', budget: '$634M' },
      { name: 'STEP Scale-up', budget: '$300M' },
    ],
  },
  {
    name: 'European Tech Champions Initiative',
    description: 'Fund-of-funds for scale-ups',
    totalBudget: '$3.9B',
    stats: [
      { label: 'Companies supported', value: '16' },
      { label: 'Unicorns', value: '9' },
      { label: 'Capital mobilised', value: '$10B' },
    ],
  },
  {
    name: 'TechEU Programme',
    description: 'EIB Group 2025-2027',
    totalBudget: '$70B',
    stats: [
      { label: 'Target mobilisation', value: '$250B' },
    ],
  },
  {
    name: 'European Investment Fund',
    description: "Europe's largest LP",
    totalBudget: '$144B',
    stats: [
      { label: 'AUM', value: '$144B' },
      { label: 'Channeled in 2024', value: '$14.4B' },
    ],
  },
];

export const FUNDING_COMPARISONS: FundingComparison[] = [
  {
    metric: 'Total VC Investment (2024)',
    euValue: '$51B',
    usValue: '$220B',
    gap: '4.3x',
    percentage: 23,
  },
  {
    metric: 'AI Funding (2024)',
    euValue: '$14B',
    usValue: '$146B',
    gap: '10.4x',
    percentage: 9.6,
  },
  {
    metric: 'Companies valued >$10B',
    euValue: '48',
    usValue: '206',
    gap: '4.3x',
    percentage: 23,
  },
  {
    metric: 'VC Dry Powder',
    euValue: '$59B',
    usValue: '$308B',
    gap: '5.2x',
    percentage: 19,
  },
  {
    metric: 'Institutional Investor Share',
    euValue: '30%',
    usValue: '72%',
    gap: '2.4x',
    percentage: 42,
  },
];

export const DATA_SOURCES: DataSource[] = [
  { name: 'Atomico', description: 'State of European Tech', url: 'https://www.stateofeuropeantech.com/' },
  { name: 'Dealroom', description: 'Startup Database', url: 'https://dealroom.co/guides/europe' },
  { name: 'StartupBlink', description: 'Global Index', url: 'https://lp.startupblink.com/report/' },
  { name: 'Crunchbase', description: 'Funding Data', url: 'https://news.crunchbase.com/' },
  { name: 'EIC', description: 'EU Innovation Council', url: 'https://eic.ec.europa.eu/' },
  { name: 'EIF', description: 'Investment Fund', url: 'https://www.eif.org/' },
  { name: 'EBAN', description: 'Angel Network', url: 'https://www.eban.org/' },
  { name: 'Invest Europe', description: 'PE/VC Association', url: 'https://www.investeurope.eu/' },
  { name: 'EUR-Lex', description: 'EU Law', url: 'https://eur-lex.europa.eu/' },
  { name: 'Sifted', description: 'EU Startup News', url: 'https://sifted.eu/' },
  { name: 'PitchBook', description: 'VC Reports', url: 'https://pitchbook.com/' },
  { name: 'Bruegel', description: 'Policy Research', url: 'https://www.bruegel.org/' },
];
