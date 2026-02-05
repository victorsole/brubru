import { ExternalLink, Euro, Rocket, Shield, Building2, Cpu } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

interface FundingProgramme {
  id: string;
  name: string;
  shortName: string;
  budget: string;
  period: string;
  description: string;
  type: 'fund' | 'programme' | 'facility' | 'loan';
  url: string;
}

interface FundingProject {
  id: string;
  name: string;
  recipient: string;
  amount: string;
  category: string;
  source: string;
}

const FUNDING_PROGRAMMES: FundingProgramme[] = [
  {
    id: 'edf',
    name: 'European Defence Fund',
    shortName: 'EDF',
    budget: '€8B',
    period: '2021-2027',
    description: 'Collaborative defence R&D funding with €2.7B for research and €5.3B for capability development',
    type: 'fund',
    url: 'https://defence-industry-space.ec.europa.eu/eu-defence-industry/european-defence-fund-edf_en',
  },
  {
    id: 'edip',
    name: 'European Defence Industry Programme',
    shortName: 'EDIP',
    budget: '€1.5B',
    period: '2025-2027',
    description: 'Joint procurement incentives and industrial capacity building',
    type: 'programme',
    url: 'https://eda.europa.eu/',
  },
  {
    id: 'epf',
    name: 'European Peace Facility',
    shortName: 'EPF',
    budget: '€17B',
    period: '2021-2027',
    description: 'Off-budget instrument for military operations and assistance (€6.1B mobilized for Ukraine)',
    type: 'facility',
    url: 'https://www.eeas.europa.eu/eeas/european-peace-facility_en',
  },
  {
    id: 'safe',
    name: 'Security Action for Europe',
    shortName: 'SAFE',
    budget: '€150B',
    period: '2025-2030',
    description: 'Proposed EU loan mechanism under ReArm Europe plan',
    type: 'loan',
    url: 'https://commission.europa.eu/',
  },
  {
    id: 'eib',
    name: 'EIB Security & Defence',
    shortName: 'EIB',
    budget: '€4.5B/yr',
    period: '2026 target',
    description: '5% of EIB financing dedicated to dual-use, cybersecurity, and defence infrastructure',
    type: 'facility',
    url: 'https://www.eib.org/en/projects/topics/security-defence/index',
  },
  {
    id: 'mff2028',
    name: 'EU Budget 2028-2034',
    shortName: 'MFF',
    budget: '€131B',
    period: '2028-2034',
    description: 'Proposed 5x increase for defence & space in next long-term EU budget',
    type: 'fund',
    url: 'https://commission.europa.eu/strategy-and-policy/eu-budget/long-term-eu-budget/eu-budget-2028-2034_en',
  },
];

const EXAMPLE_PROJECTS: FundingProject[] = [
  { id: '1', name: 'EURODRONE', recipient: 'Airbus, Dassault, Leonardo', amount: '€100M+', category: 'Air Systems', source: 'EDF' },
  { id: '2', name: 'ESSOR (Software Radio)', recipient: 'Multi-country consortium', amount: '€100M', category: 'Communications', source: 'EDF' },
  { id: '3', name: 'Leonardo R&D', recipient: 'Leonardo (Italy)', amount: '€260M', category: 'Defence Tech', source: 'EIB' },
  { id: '4', name: 'Thales Aeronautics', recipient: 'Thales (France)', amount: '€450M', category: 'Radar/Avionics', source: 'EIB' },
  { id: '5', name: 'Military Base', recipient: 'Lithuania', amount: '€540M', category: 'Infrastructure', source: 'EIB' },
  { id: '6', name: 'Satellite Network', recipient: 'Sateliot (Spain)', amount: '€30M', category: 'Space', source: 'EIB' },
];

const FUNDING_PORTALS = [
  {
    name: 'EU Funding & Tenders',
    url: 'https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/home',
    description: 'Official EU grants and tenders portal',
  },
  {
    name: 'TED Tenders',
    url: 'https://ted.europa.eu/en/',
    description: 'Public procurement notices',
  },
  {
    name: 'Horizon Europe',
    url: 'https://research-and-innovation.ec.europa.eu/funding/funding-opportunities/funding-programmes-and-open-calls/horizon-europe_en',
    description: 'R&D funding including security cluster',
  },
  {
    name: 'EDA Procurement',
    url: 'https://eda.europa.eu/what-we-do/procurement',
    description: 'Defence agency contracts',
  },
];

function getTypeColor(type: FundingProgramme['type']) {
  switch (type) {
    case 'fund':
      return 'bg-primary/10 text-primary border-primary/30';
    case 'programme':
      return 'bg-accent/10 text-secondary border-accent/30';
    case 'facility':
      return 'bg-secondary/10 text-secondary border-secondary/30';
    case 'loan':
      return 'bg-blue-100 text-blue-800 border-blue-300';
    default:
      return 'bg-muted text-muted-foreground';
  }
}

function getTypeLabel(type: FundingProgramme['type']) {
  switch (type) {
    case 'fund':
      return 'EU Fund';
    case 'programme':
      return 'Programme';
    case 'facility':
      return 'Facility';
    case 'loan':
      return 'Loan';
    default:
      return type;
  }
}

export function DefenceFunding() {
  const totalCurrentFunding = '€26.5B';
  const proposedFunding = '€281B';

  return (
    <Card className="border-border/50">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Euro className="w-5 h-5 text-accent" />
            <CardTitle className="text-xl text-secondary">
              EU Defence Funding
            </CardTitle>
          </div>
          <div className="flex gap-4 text-sm">
            <div className="text-right">
              <span className="text-muted-foreground">Current (2021-27): </span>
              <span className="font-semibold text-primary">{totalCurrentFunding}</span>
            </div>
            <div className="text-right">
              <span className="text-muted-foreground">Proposed (2028-34): </span>
              <span className="font-semibold text-accent">{proposedFunding}</span>
            </div>
          </div>
        </div>
        <p className="text-sm text-muted-foreground mt-1">
          EU-level funding programmes for defence research, procurement, and industrial capacity
        </p>
      </CardHeader>
      <CardContent>
        {/* Funding Programmes Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          {FUNDING_PROGRAMMES.map((programme) => (
            <a
              key={programme.id}
              href={programme.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block p-4 rounded-lg border border-border hover:border-primary hover:bg-muted/30 transition-colors group"
            >
              <div className="flex items-start justify-between mb-2">
                <Badge variant="outline" className={`text-xs ${getTypeColor(programme.type)}`}>
                  {getTypeLabel(programme.type)}
                </Badge>
                <span className="text-xs text-muted-foreground">{programme.period}</span>
              </div>
              <div className="flex items-baseline gap-2 mb-1">
                <span className="text-2xl font-bold text-primary">{programme.budget}</span>
                <span className="text-sm font-medium text-secondary">{programme.shortName}</span>
              </div>
              <h3 className="font-medium text-secondary text-sm mb-1 group-hover:text-primary transition-colors">
                {programme.name}
              </h3>
              <p className="text-xs text-muted-foreground line-clamp-2">
                {programme.description}
              </p>
            </a>
          ))}
        </div>

        {/* Example Projects */}
        <div className="mb-6">
          <h3 className="text-sm font-medium text-secondary mb-3 flex items-center gap-2">
            <Rocket className="w-4 h-4" />
            Example Funded Projects
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
            {EXAMPLE_PROJECTS.map((project) => (
              <div
                key={project.id}
                className="p-3 rounded-lg bg-muted/50 text-center"
              >
                <div className="text-xs text-muted-foreground mb-1">{project.source}</div>
                <div className="font-semibold text-primary text-sm">{project.amount}</div>
                <div className="text-xs font-medium text-secondary truncate" title={project.name}>
                  {project.name}
                </div>
                <div className="text-xs text-muted-foreground truncate" title={project.recipient}>
                  {project.recipient}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Funding Portals */}
        <div className="pt-4 border-t border-border">
          <h3 className="text-sm font-medium text-secondary mb-3">Find Funding Opportunities</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {FUNDING_PORTALS.map((portal) => (
              <a
                key={portal.name}
                href={portal.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 p-3 rounded-lg bg-muted/50 hover:bg-muted transition-colors text-sm group"
              >
                <ExternalLink className="w-3 h-3 text-primary flex-shrink-0" />
                <div>
                  <div className="font-medium text-secondary group-hover:text-primary transition-colors">
                    {portal.name}
                  </div>
                  <div className="text-xs text-muted-foreground">{portal.description}</div>
                </div>
              </a>
            ))}
          </div>
        </div>

        <p className="text-xs text-muted-foreground text-center mt-4">
          Sources: European Commission, EIB, European Parliament | Data as of 2025
        </p>
      </CardContent>
    </Card>
  );
}
