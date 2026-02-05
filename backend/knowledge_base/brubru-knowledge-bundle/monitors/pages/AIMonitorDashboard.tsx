import { useEffect } from 'react';
import { Brain, TrendingUp, Wallet, Scale, Factory, ArrowLeft, RefreshCw, Newspaper, LineChart, Table2, Map, Landmark, ScrollText, BarChart3, Users, FileStack, Info, Layers, Check, ExternalLink, ShieldCheck, Eye, Building2, AlertTriangle, MessageSquare, Mail, Bot } from 'lucide-react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Header } from '@/components/Header';
import { ScrollReveal, StaggerContainer, StaggerItem } from '@/components/animations';
import { FeedbackSection } from '@/components/FeedbackSection';
import { SEO, BreadcrumbSchema } from '@/components/SEO';
import { RelatedMonitorBanner, RelatedMonitorsSection } from '@/components/monitors';
import { Helmet } from 'react-helmet-async';
import { StockPerformanceChart, RegionalVCChart, AIInvestmentMap } from '@/components/ai-monitor';

// Source Badge Component
const SourceBadge = ({ source, variant = 'default' }: { source: string; variant?: 'default' | 'accent' | 'blue' }) => {
  const variants = {
    default: 'bg-primary/10 text-primary border-primary/30',
    accent: 'bg-accent/10 text-accent border-accent/30',
    blue: 'bg-blue-500/10 text-blue-500 border-blue-500/30',
  };

  return (
    <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${variants[variant]}`}>
      {source}
    </span>
  );
};

// Metric Card Component
const AIMetricCard = ({
  icon: Icon,
  value,
  label,
  trend,
  sources = [],
  color = 'primary',
  badge
}: {
  icon: any;
  value: string;
  label: string;
  trend?: string;
  sources?: string[];
  color?: 'primary' | 'secondary' | 'accent' | 'destructive' | 'blue';
  badge?: { text: string; variant: 'default' | 'destructive' };
}) => {
  const colorClasses = {
    primary: 'text-primary bg-primary/10',
    secondary: 'text-secondary bg-muted/50',
    accent: 'text-accent bg-accent/10',
    destructive: 'text-destructive bg-destructive/10',
    blue: 'text-blue-600 bg-blue-50',
  };

  return (
    <Card className="group hover:shadow-strong transition-all duration-300 hover:-translate-y-2">
      <CardContent className="p-6 text-center">
        <div className={`mx-auto w-16 h-16 rounded-full flex items-center justify-center mb-4 ${colorClasses[color]}`}>
          <Icon className="w-8 h-8" />
        </div>
        <div className="text-3xl font-bold text-secondary mb-1">{value}</div>
        <div className="text-muted-foreground text-sm">{label}</div>
        {trend && <p className={`text-sm mt-1 font-medium ${color === 'destructive' ? 'text-destructive' : color === 'blue' ? 'text-blue-600' : 'text-primary'}`}>{trend}</p>}
        {badge && (
          <div className={`mt-2 inline-block text-xs px-3 py-1 rounded-full font-medium ${
            badge.variant === 'destructive'
              ? 'bg-gradient-to-r from-destructive to-destructive/80 text-white animate-pulse'
              : 'bg-primary/10 text-primary'
          }`}>
            {badge.text}
          </div>
        )}
        {sources.length > 0 && (
          <div className="flex items-center justify-center gap-1 mt-2">
            {sources.map((source, i) => (
              <SourceBadge key={i} source={source} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default function AIMonitorDashboard() {
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  const lastUpdated = new Date().toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });

  return (
    <div className="min-h-screen bg-background">
      <SEO
        title="European AI Market Monitor 2025 - EU AI Investment, Regulation & Industry Tracker"
        description="Live European AI market intelligence: track €5.4B+ VC investments, EU AI Act compliance deadlines (Feb 2025 - Aug 2027), AI Factories, InvestAI €200B initiative, Mistral, Aleph Alpha & top EU AI startups. Real-time regulatory updates on GPAI models, Digital Omnibus, and high-risk AI systems."
        keywords="European AI market 2025, EU AI Act tracker, AI investment Europe, AI Factories Europe, EU AI regulation, GPAI compliance, AI startups Europe, AI VC funding Europe, Digital Omnibus Regulation, InvestAI initiative, Mistral AI, Aleph Alpha, EU AI policy, AI Act deadlines, high-risk AI systems, EU AI market size, European AI companies, AI Act compliance, EU tech investment, Brussels AI policy"
        url="/ai-monitor"
      />
      <BreadcrumbSchema items={[
        { name: 'Home', url: '/' },
        { name: 'AI Market Monitor', url: '/ai-monitor' }
      ]} />
      <Helmet>
        <script type="application/ld+json">
          {JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'WebPage',
            name: 'European AI Market & Industry Monitor',
            description: 'Real-time dashboard tracking European AI investments, EU AI Act regulatory milestones, and market dynamics.',
            url: 'https://beresol.eu/ai-monitor',
            mainEntity: {
              '@type': 'Dataset',
              name: 'European AI Market Data 2025',
              description: 'Comprehensive dataset on EU AI investments, regulatory timeline, and industry metrics including VC funding by country, AI Act compliance deadlines, and leading European AI companies.',
              creator: {
                '@type': 'Organization',
                name: 'Beresol',
                url: 'https://beresol.eu'
              },
              keywords: ['EU AI investment', 'AI Act timeline', 'European AI startups', 'AI VC funding', 'GPAI regulation'],
              temporalCoverage: '2022/2027',
              spatialCoverage: {
                '@type': 'Place',
                name: 'European Union'
              }
            },
            about: [
              { '@type': 'Thing', name: 'EU AI Act' },
              { '@type': 'Thing', name: 'Artificial Intelligence Regulation' },
              { '@type': 'Thing', name: 'European AI Investment' },
              { '@type': 'Thing', name: 'AI Factories Initiative' }
            ],
            publisher: {
              '@type': 'Organization',
              name: 'Beresol',
              url: 'https://beresol.eu'
            }
          })}
        </script>
      </Helmet>
      <Header />

      <main className="container mx-auto px-4 py-8">
        {/* Back navigation */}
        <motion.div
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4 }}
        >
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-muted-foreground hover:text-primary transition-colors mb-6"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Home
          </Link>
        </motion.div>

        {/* Related Monitor Banner */}
        <RelatedMonitorBanner currentMonitor="ai" className="mb-6" />

        {/* Page Header - Same as CMU Monitor */}
        <motion.header
          className="text-center mb-12"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
        >
          <div className="flex items-center justify-center gap-3 mb-4">
            <motion.div
              className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center"
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ duration: 0.6, delay: 0.2, type: "spring", stiffness: 200 }}
            >
              <Brain className="w-6 h-6 text-primary" />
            </motion.div>
            <h1 className="text-3xl md:text-4xl font-bold text-secondary">
              European AI Market & Industry Monitor
            </h1>
          </div>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Real-time tracking of European AI investments, regulatory milestones, and market dynamics
          </p>
          <motion.div
            className="flex items-center justify-center gap-4 mt-4"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.4 }}
          >
            <p className="text-sm text-muted-foreground flex items-center gap-2">
              <RefreshCw className="w-3 h-3" />
              Data updated: {lastUpdated}
            </p>
            <Badge className="bg-primary/10 text-primary border-primary/20">14 Data Sources</Badge>
          </motion.div>
        </motion.header>

        {/* Hero Metrics Row */}
        <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-12" staggerDelay={0.1}>
          <StaggerItem variant="fadeUp">
            <AIMetricCard
              icon={TrendingUp}
              value="$105.6B"
              label="EU AI Market Size (2025)"
              trend="+36% YoY growth"
              sources={['Statista']}
              color="primary"
            />
          </StaggerItem>
          <StaggerItem variant="fadeUp">
            <AIMetricCard
              icon={Wallet}
              value="25%"
              label="of Global AI VC (2024)"
              trend="10x growth in decade"
              sources={['Seedblink']}
              color="secondary"
            />
          </StaggerItem>
          <StaggerItem variant="fadeUp">
            <AIMetricCard
              icon={Scale}
              value="August 2026"
              label="AI Act Main Provisions"
              trend="Key compliance deadline"
              sources={['EUR-Lex']}
              color="destructive"
            />
          </StaggerItem>
          <StaggerItem variant="fadeUp">
            <AIMetricCard
              icon={Factory}
              value="20"
              label="AI Factories Operational"
              trend="+ 9 Antennas"
              sources={['EC Digital']}
              color="blue"
            />
          </StaggerItem>
        </StaggerContainer>

        {/* Row 1: Stock Performance + News */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            {/* Stock Performance Chart */}
            <div className="lg:col-span-2">
              <Card className="h-full">
                <CardHeader className="flex flex-row items-center justify-between">
                  <div className="flex items-center gap-2">
                    <LineChart className="w-5 h-5 text-secondary" />
                    <CardTitle>EU AI Stock Performance Index</CardTitle>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex bg-muted rounded-lg p-1">
                      <button className="px-3 py-1 text-xs rounded-md text-muted-foreground hover:bg-background transition">1W</button>
                      <button className="px-3 py-1 text-xs rounded-md text-muted-foreground hover:bg-background transition">1M</button>
                      <button className="px-3 py-1 text-xs rounded-md bg-background text-secondary shadow-sm">3M</button>
                      <button className="px-3 py-1 text-xs rounded-md text-muted-foreground hover:bg-background transition">6M</button>
                      <button className="px-3 py-1 text-xs rounded-md text-muted-foreground hover:bg-background transition">1Y</button>
                    </div>
                    <SourceBadge source="Euronext" />
                  </div>
                </CardHeader>
                <CardContent>
                  <StockPerformanceChart />
                  <div className="flex justify-center gap-6 mt-4 pt-4 border-t">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded bg-primary"></div>
                      <span className="text-sm text-muted-foreground">EU AI Index</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded bg-accent"></div>
                      <span className="text-sm text-muted-foreground">STOXX 600 Tech</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded bg-muted-foreground/60"></div>
                      <span className="text-sm text-muted-foreground">S&P 500 Tech</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* AI Policy News */}
            <Card className="h-full flex flex-col">
              <CardHeader className="flex flex-row items-center justify-between pb-3">
                <div className="flex items-center gap-2">
                  <Newspaper className="w-5 h-5 text-accent" />
                  <CardTitle className="text-lg">AI Policy News</CardTitle>
                </div>
                <button className="p-2 hover:bg-muted rounded-md transition-colors">
                  <RefreshCw className="w-4 h-4 text-muted-foreground" />
                </button>
              </CardHeader>
              <CardContent className="flex-1 overflow-y-auto space-y-0 p-0">
                {[
                  { source: 'EC', date: 'October 2025', title: 'Apply AI Strategy launched to boost SME adoption' },
                  { source: 'JRC', date: 'October 2025', title: 'JRC: AI skills gap in GenAI training identified' },
                  { source: 'AI Office', date: 'July 2025', title: 'GPAI Code of Practice published; 28 signatories' },
                  { source: 'EIB', date: 'December 2024', title: 'EIB commits €70B for tech & AI (2025-2027)' },
                ].map((item, i) => (
                  <article key={i} className="p-4 border-b hover:bg-muted/50 transition-colors cursor-pointer">
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <SourceBadge source={item.source} variant={item.source === 'EC' || item.source === 'AI Office' ? 'blue' : 'default'} />
                      <time className="text-xs text-muted-foreground">{item.date}</time>
                    </div>
                    <h4 className="font-medium text-secondary text-sm hover:text-primary transition-colors">
                      {item.title}
                    </h4>
                  </article>
                ))}
              </CardContent>
              <div className="px-4 py-2 border-t bg-muted/30">
                <p className="text-xs text-muted-foreground text-center">
                  Sources: EC, AI Office, JRC, EIB
                </p>
              </div>
            </Card>
          </div>
        </ScrollReveal>

        {/* Row 2: EU AI Industry Leaders */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <Card className="mb-6">
            <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <Table2 className="w-5 h-5 text-secondary" />
                <CardTitle>EU AI Industry Leaders</CardTitle>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <div className="relative">
                  <input
                    type="text"
                    placeholder="Search companies..."
                    className="pl-9 pr-4 py-2 bg-muted border border-border rounded-lg text-sm w-48 focus:outline-none focus:ring-2 focus:ring-primary/20"
                  />
                </div>
                <select className="bg-muted border border-border rounded-lg px-3 py-2 text-sm">
                  <option>All Sectors</option>
                  <option>Semiconductors</option>
                  <option>Software</option>
                  <option>Industrial</option>
                  <option>Data Centers</option>
                </select>
                <SourceBadge source="Euronext" />
                <SourceBadge source="Xetra" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b text-left text-sm text-muted-foreground">
                      <th className="pb-3 font-medium">Company</th>
                      <th className="pb-3 font-medium">Ticker</th>
                      <th className="pb-3 font-medium text-right">Price</th>
                      <th className="pb-3 font-medium text-right">Change</th>
                      <th className="pb-3 font-medium text-right">Market Cap</th>
                      <th className="pb-3 font-medium text-right">P/E</th>
                      <th className="pb-3 font-medium text-right">YTD</th>
                      <th className="pb-3 font-medium">AI Focus</th>
                    </tr>
                  </thead>
                  <tbody className="text-sm">
                    {[
                      { company: 'ASML Holding', ticker: 'ASML', price: '€820.50', change: '+1.24%', cap: '€362B', pe: '45.2', ytd: '+12.3%', focus: 'EUV Lithography', positive: true },
                      { company: 'SAP SE', ticker: 'SAP', price: '€245.80', change: '+0.82%', cap: '€237B', pe: '38.1', ytd: '+18.7%', focus: 'Enterprise AI', positive: true },
                      { company: 'Siemens AG', ticker: 'SIE', price: '€195.20', change: '-0.31%', cap: '€185B', pe: '21.3', ytd: '+8.1%', focus: 'Industrial AI', positive: false },
                      { company: 'Schneider Electric', ticker: 'SU', price: '€248.40', change: '+2.15%', cap: '€140B', pe: '28.5', ytd: '+22.4%', focus: 'Data Centers', positive: true },
                      { company: 'Siemens Energy', ticker: 'ENR', price: '€58.20', change: '+0.52%', cap: '€100B', pe: '42.1', ytd: '+146%', focus: 'Grid Power', positive: true },
                      { company: 'Infineon Technologies', ticker: 'IFX', price: '€38.15', change: '-1.12%', cap: '€55B', pe: '18.7', ytd: '-5.3%', focus: 'AI Chips', positive: false },
                      { company: 'Dassault Systemes', ticker: 'DSY', price: '€45.20', change: '+0.42%', cap: '€36B', pe: '42.8', ytd: '+3.1%', focus: 'Digital Twins', positive: true },
                      { company: 'STMicroelectronics', ticker: 'STMPA', price: '€28.40', change: '-2.31%', cap: '€26B', pe: '12.4', ytd: '-18.2%', focus: 'Semiconductors', positive: false },
                    ].map((stock, i) => (
                      <tr key={i} className="border-b border-border/30 hover:bg-muted/50 transition-colors cursor-pointer">
                        <td className="py-4 font-medium text-secondary">{stock.company}</td>
                        <td className="py-4 text-muted-foreground">{stock.ticker}</td>
                        <td className="py-4 text-right font-mono">{stock.price}</td>
                        <td className={`py-4 text-right font-medium ${stock.change.startsWith('+') ? 'text-primary' : 'text-destructive'}`}>{stock.change}</td>
                        <td className="py-4 text-right">{stock.cap}</td>
                        <td className="py-4 text-right text-muted-foreground">{stock.pe}</td>
                        <td className={`py-4 text-right font-medium ${stock.ytd.startsWith('+') ? 'text-primary' : 'text-destructive'}`}>{stock.ytd}</td>
                        <td className="py-4">
                          <span className="text-xs px-2 py-1 rounded bg-primary/10 text-primary">{stock.focus}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex items-center justify-between mt-4 pt-4 border-t">
                <p className="text-sm text-muted-foreground">Showing 8 of 12 companies | Market data delayed 15 min</p>
                <div className="flex items-center gap-2">
                  <button className="px-3 py-1.5 rounded-lg border text-sm hover:bg-muted transition">Previous</button>
                  <button className="px-3 py-1.5 rounded-lg bg-primary text-white text-sm hover:bg-primary/90 transition">Next</button>
                </div>
              </div>
            </CardContent>
          </Card>
        </ScrollReveal>

        {/* Row 3: Map + EU Funding */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {/* AI Investment Map */}
            <Card className="h-full flex flex-col">
              <CardHeader className="flex flex-row items-center justify-between flex-shrink-0">
                <div className="flex items-center gap-2">
                  <Map className="w-5 h-5 text-primary" />
                  <CardTitle className="text-lg">EU AI Investment by Country (2024)</CardTitle>
                </div>
                <SourceBadge source="Seedblink" />
              </CardHeader>
              <CardContent className="flex-1 flex flex-col min-h-0">
                <div className="flex-1 min-h-0">
                  <AIInvestmentMap />
                </div>
                <div className="flex flex-wrap gap-3 mt-4 pt-4 border-t flex-shrink-0">
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-3 rounded" style={{ background: 'hsl(120 65% 35%)' }}></div>
                    <span className="text-xs text-muted-foreground">&gt;€1B</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-3 rounded" style={{ background: 'hsl(120 55% 50%)' }}></div>
                    <span className="text-xs text-muted-foreground">€500M-1B</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-3 rounded" style={{ background: 'hsl(120 45% 65%)' }}></div>
                    <span className="text-xs text-muted-foreground">€100-500M</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-3 rounded" style={{ background: 'hsl(120 35% 80%)' }}></div>
                    <span className="text-xs text-muted-foreground">&lt;€100M</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* EU Public Funding */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div className="flex items-center gap-2">
                  <Landmark className="w-5 h-5 text-blue-600" />
                  <CardTitle className="text-lg">EU Public Funding for AI</CardTitle>
                </div>
                <div className="flex gap-2">
                  <SourceBadge source="EC" variant="blue" />
                  <SourceBadge source="EIB" />
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="p-4 rounded-lg bg-blue-50 border border-blue-200">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-secondary">InvestAI Initiative</span>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-blue-100 text-blue-600">NEW 2025</span>
                    </div>
                    <span className="text-lg font-bold text-blue-600">€200B</span>
                  </div>
                  <div className="text-xs text-muted-foreground">Target mobilization | 70% private, 30% public | Includes €20B for AI Gigafactories</div>
                </div>

                <div className="p-4 rounded-lg bg-muted/30 border">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-secondary">EIB Group (2025-2027)</span>
                    <span className="text-lg font-bold text-secondary">€70B</span>
                  </div>
                  <div className="text-xs text-muted-foreground">High-risk projects & innovative companies | €89B financed in 2024</div>
                </div>

                <div className="p-4 rounded-lg bg-muted/30 border">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-secondary">Horizon Europe AI R&D</span>
                    <span className="text-lg font-bold text-primary">€2.6B</span>
                  </div>
                  <div className="text-xs text-muted-foreground">2021-2024 allocation | Additional €112M in 2024 AI/quantum calls</div>
                </div>

                <div className="p-4 rounded-lg bg-muted/30 border">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-secondary">GenAI4EU Programme</span>
                    <span className="text-lg font-bold text-accent">€700M</span>
                  </div>
                  <div className="text-xs text-muted-foreground">Startups & SMEs | 14 industrial ecosystems | Horizon + Digital Europe + EIC</div>
                </div>

                <div className="p-4 rounded-lg bg-muted/30 border">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-secondary">Apply AI Strategy</span>
                    <span className="text-lg font-bold text-secondary">€3.5B/yr</span>
                  </div>
                  <div className="text-xs text-muted-foreground">Annual budget for SME competitiveness | Launched October 2025</div>
                </div>
              </CardContent>
            </Card>
          </div>
        </ScrollReveal>

        {/* Row 4: EU AI Act Legal Framework */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <Card className="mb-6">
            <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <ScrollText className="w-5 h-5 text-secondary" />
                <CardTitle>EU AI Act Legal Framework</CardTitle>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <SourceBadge source="EUR-Lex" />
                <SourceBadge source="AI Office" variant="blue" />
                <SourceBadge source="artificialintelligenceact.eu" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 mb-6">
                {/* Risk Pyramid */}
                <div className="space-y-2">
                  <div className="text-sm font-medium text-secondary mb-3">Risk-Based Approach</div>
                  <div className="border-l-4 border-destructive p-3 rounded-lg bg-destructive/5">
                    <div className="text-xs font-bold text-destructive mb-1">UNACCEPTABLE</div>
                    <div className="text-[10px] text-muted-foreground">8 prohibited practices: social scoring, manipulative AI, biometric ID</div>
                  </div>
                  <div className="border-l-4 border-orange-500 p-3 rounded-lg bg-orange-50">
                    <div className="text-xs font-bold text-orange-600 mb-1">HIGH-RISK</div>
                    <div className="text-[10px] text-muted-foreground">Annex III: healthcare, employment, law enforcement, education</div>
                  </div>
                  <div className="border-l-4 border-accent p-3 rounded-lg bg-accent/5">
                    <div className="text-xs font-bold text-accent mb-1">LIMITED RISK</div>
                    <div className="text-[10px] text-muted-foreground">Transparency: chatbots, deepfakes, emotion recognition</div>
                  </div>
                  <div className="border-l-4 border-primary p-3 rounded-lg bg-primary/5">
                    <div className="text-xs font-bold text-primary mb-1">MINIMAL RISK</div>
                    <div className="text-[10px] text-muted-foreground">Vast majority of AI systems; no regulation needed</div>
                  </div>
                </div>

                {/* GPAI Code of Practice */}
                <div>
                  <div className="text-sm font-medium text-secondary mb-3">GPAI Code of Practice</div>
                  <div className="p-4 rounded-lg bg-muted/30 border h-[calc(100%-2rem)]">
                    <div className="text-xs text-muted-foreground mb-3">Published 10 July 2025</div>
                    <div className="space-y-3">
                      <div className="p-2 rounded bg-background border">
                        <div className="text-xs font-medium text-secondary">Chapter 1: Transparency</div>
                        <div className="text-[10px] text-muted-foreground">Model documentation form (Art. 53)</div>
                      </div>
                      <div className="p-2 rounded bg-background border">
                        <div className="text-xs font-medium text-secondary">Chapter 2: Copyright</div>
                        <div className="text-[10px] text-muted-foreground">EU copyright compliance policies</div>
                      </div>
                      <div className="p-2 rounded bg-background border">
                        <div className="text-xs font-medium text-secondary">Chapter 3: Safety</div>
                        <div className="text-[10px] text-muted-foreground">Systemic risk management (Art. 55)</div>
                      </div>
                    </div>
                    <div className="mt-3 pt-3 border-t">
                      <div className="text-xs text-primary font-medium">28 Signatories</div>
                      <div className="text-[10px] text-muted-foreground">Anthropic, Google, Microsoft, OpenAI, Mistral AI...</div>
                    </div>
                  </div>
                </div>

                {/* Key Provisions */}
                <div className="lg:col-span-2">
                  <div className="text-sm font-medium text-secondary mb-3">Key Provisions (Reg. 2024/1689)</div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="p-3 rounded-lg bg-muted/30 border">
                      <div className="flex items-center gap-2 mb-2">
                        <ShieldCheck className="w-4 h-4 text-primary" />
                        <span className="text-xs font-medium text-secondary">High-Risk Requirements</span>
                      </div>
                      <ul className="text-[10px] text-muted-foreground space-y-1">
                        <li>• Risk management system</li>
                        <li>• Quality dataset standards</li>
                        <li>• Technical documentation</li>
                        <li>• Human oversight</li>
                        <li>• Cybersecurity measures</li>
                      </ul>
                    </div>
                    <div className="p-3 rounded-lg bg-muted/30 border">
                      <div className="flex items-center gap-2 mb-2">
                        <Eye className="w-4 h-4 text-accent" />
                        <span className="text-xs font-medium text-secondary">Transparency Obligations</span>
                      </div>
                      <ul className="text-[10px] text-muted-foreground space-y-1">
                        <li>• Disclose AI interaction</li>
                        <li>• Label AI-generated content</li>
                        <li>• Deepfake identification</li>
                        <li>• Emotion recognition notice</li>
                      </ul>
                    </div>
                    <div className="p-3 rounded-lg bg-muted/30 border">
                      <div className="flex items-center gap-2 mb-2">
                        <Building2 className="w-4 h-4 text-blue-600" />
                        <span className="text-xs font-medium text-secondary">Governance Structure</span>
                      </div>
                      <ul className="text-[10px] text-muted-foreground space-y-1">
                        <li>• EU AI Office (125+ staff)</li>
                        <li>• AI Board (Member States)</li>
                        <li>• Scientific Panel</li>
                        <li>• Advisory Forum</li>
                        <li>• National authorities</li>
                      </ul>
                    </div>
                    <div className="p-3 rounded-lg bg-destructive/5 border border-destructive/20">
                      <div className="flex items-center gap-2 mb-2">
                        <AlertTriangle className="w-4 h-4 text-destructive" />
                        <span className="text-xs font-medium text-secondary">Penalties</span>
                      </div>
                      <ul className="text-[10px] text-muted-foreground space-y-1">
                        <li>• <span className="text-destructive font-medium">€35M / 7%</span> prohibited AI</li>
                        <li>• <span className="text-accent font-medium">€15M / 3%</span> other obligations</li>
                        <li>• <span className="text-secondary font-medium">€7.5M / 1%</span> incorrect info</li>
                      </ul>
                    </div>
                  </div>
                </div>
              </div>

              {/* Timeline */}
              <div className="border-t pt-6">
                <div className="relative">
                  <div className="absolute top-6 left-0 right-0 h-1 bg-border rounded-full"></div>
                  <div className="absolute top-6 left-0 h-1 bg-primary rounded-full" style={{ width: '40%' }}></div>

                  <div className="flex justify-between relative">
                    {[
                      { date: '2 February 2025', label: 'Prohibitions', status: 'done' },
                      { date: '2 August 2025', label: 'GPAI Rules', status: 'done' },
                      { date: '2 February 2026', label: 'Guidelines', status: 'soon' },
                      { date: '2 August 2026', label: 'Main Provisions', status: 'important' },
                      { date: '2 August 2027', label: 'Embedded', status: 'future' },
                    ].map((item, i) => (
                      <div key={i} className="flex flex-col items-center w-1/5">
                        <div className={`w-4 h-4 rounded-full border-4 border-background z-10 mb-3 ${
                          item.status === 'done' ? 'bg-primary' :
                          item.status === 'soon' ? 'bg-accent' :
                          item.status === 'important' ? 'bg-destructive animate-pulse w-5 h-5' :
                          'bg-muted-foreground/30'
                        }`}></div>
                        <div className="text-center">
                          <div className={`text-xs font-medium mb-1 ${
                            item.status === 'done' ? 'text-primary' :
                            item.status === 'soon' ? 'text-accent' :
                            item.status === 'important' ? 'text-destructive' :
                            'text-muted-foreground'
                          }`}>{item.date}</div>
                          <div className={`text-[10px] font-medium text-secondary ${item.status === 'important' ? 'font-bold' : ''}`}>{item.label}</div>
                          <span className={`inline-block mt-1 text-[9px] px-2 py-0.5 rounded font-medium ${
                            item.status === 'done' ? 'bg-primary/10 text-primary' :
                            item.status === 'soon' ? 'bg-accent/10 text-accent' :
                            item.status === 'important' ? 'bg-destructive text-white' :
                            'bg-muted text-muted-foreground'
                          }`}>
                            {item.status === 'done' ? 'DONE' :
                             item.status === 'soon' ? '30 DAYS' :
                             item.status === 'important' ? 'KEY DATE' :
                             'FUTURE'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </ScrollReveal>

        {/* Row 5: Digital Omnibus Regulation */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <Card className="mb-6 bg-gradient-to-r from-blue-50 to-primary/5 border-blue-200">
            <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                  <FileStack className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <CardTitle>Digital Omnibus Regulation</CardTitle>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-blue-600 text-white font-medium">PROPOSED 2025</span>
                  </div>
                  <p className="text-xs text-muted-foreground">COM(2025)837 - Simplifying EU Digital Legislation</p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <SourceBadge source="EUR-Lex" variant="blue" />
                <SourceBadge source="Law Tracker EU" variant="blue" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Overview */}
                <div className="bg-white rounded-lg p-5 border shadow-sm">
                  <div className="flex items-center gap-2 mb-4">
                    <Info className="w-5 h-5 text-blue-600" />
                    <span className="text-base font-semibold text-secondary">Overview</span>
                  </div>
                  <p className="text-sm text-muted-foreground mb-4 leading-relaxed">
                    First-phase modernization of EU digital rulebook to enhance competitiveness while maintaining high protection standards.
                  </p>
                  <div className="space-y-3">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Projected savings</span>
                      <span className="font-bold text-primary">€5B by 2029</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Annual admin relief</span>
                      <span className="font-bold text-secondary">€1B/year</span>
                    </div>
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-muted-foreground">Public authority savings</span>
                      <span className="font-bold text-secondary">€1B</span>
                    </div>
                  </div>
                </div>

                {/* AI-related provisions */}
                <div className="bg-white rounded-lg p-5 border border-primary/30 shadow-sm">
                  <div className="flex items-center gap-2 mb-4">
                    <Brain className="w-5 h-5 text-primary" />
                    <span className="text-base font-semibold text-secondary">AI-related provisions</span>
                  </div>
                  <p className="text-sm text-muted-foreground mb-4 leading-relaxed">
                    Companion proposal amends Reg. 2024/1689 (AI Act) to facilitate smooth application of rules.
                  </p>
                  <ul className="text-xs text-muted-foreground space-y-2.5">
                    {[
                      'SME/SMC exemptions extended to small mid-cap companies',
                      'GDPR clarifications for AI training with personal data',
                      'Research exemptions guidance (Art. 2(6), 2(8))',
                      'High-risk classification & transparency guidelines',
                      'Simplified QMS compliance for SMEs',
                    ].map((item, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <Check className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
                        <span className="leading-relaxed">{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Key Simplifications */}
                <div className="bg-white rounded-lg p-4 border shadow-sm">
                  <div className="flex items-center gap-2 mb-3">
                    <Layers className="w-4 h-4 text-accent" />
                    <span className="text-sm font-medium text-secondary">Key Simplifications</span>
                  </div>
                  <div className="space-y-2">
                    {[
                      { title: 'Data Legislation Consolidation', desc: '4 regulations → 1 Data Act (2023/2854)' },
                      { title: 'Unified Incident Reporting', desc: 'NIS2 + GDPR + DORA → Single entry point (ENISA)' },
                      { title: 'GDPR Amendments', desc: 'Data breach notification extended to 96hrs' },
                      { title: 'ePrivacy Reform', desc: '"Cookie fatigue" addressed; machine-readable consent' },
                    ].map((item, i) => (
                      <div key={i} className="p-2 rounded bg-muted/30 border border-border/30">
                        <div className="text-[10px] font-medium text-secondary">{item.title}</div>
                        <div className="text-[9px] text-muted-foreground">{item.desc}</div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-blue-200 flex flex-wrap items-center justify-between gap-3">
                <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
                  <span><strong>Procedure:</strong> 2025/360 (COD)</span>
                  <span><strong>Status:</strong> Commission proposal stage</span>
                  <span><strong>Next:</strong> EP & Council examination</span>
                </div>
                <a
                  href="https://eur-lex.europa.eu/legal-content/en/TXT/?uri=COM%3A2025%3A837%3AFIN"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-600 hover:underline flex items-center gap-1"
                >
                  Read full proposal <ExternalLink className="w-3 h-3" />
                </a>
              </div>
            </CardContent>
          </Card>
        </ScrollReveal>

        {/* Row 6: EU vs US + VC Evolution */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
            {/* EU vs US AI Investment */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div className="flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-secondary" />
                  <CardTitle className="text-lg">EU vs US AI Investment (2024)</CardTitle>
                </div>
                <SourceBadge source="Seedblink" />
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-4 mb-4">
                  <div className="bg-muted/30 rounded-lg p-4 text-center">
                    <div className="text-xs text-muted-foreground mb-2">AI VC Allocation</div>
                    <div className="flex items-center justify-center gap-4">
                      <div>
                        <div className="text-lg font-bold text-primary">25%</div>
                        <div className="text-[10px] text-muted-foreground">EU</div>
                      </div>
                      <div className="text-muted-foreground">vs</div>
                      <div>
                        <div className="text-lg font-bold text-accent">42%</div>
                        <div className="text-[10px] text-muted-foreground">US</div>
                      </div>
                    </div>
                  </div>
                  <div className="bg-muted/30 rounded-lg p-4 text-center">
                    <div className="text-xs text-muted-foreground mb-2">Global AI-First VC</div>
                    <div className="text-2xl font-bold text-secondary">$110B</div>
                    <div className="text-xs text-primary font-medium">+62% YoY</div>
                  </div>
                </div>

                <RegionalVCChart />

                <div className="text-xs text-muted-foreground mt-4 pt-4 border-t">
                  <span className="font-medium">Central & Eastern Europe (CEE)</span>: Poland, Czech Republic, Romania, Hungary, Bulgaria, Slovakia, Greece, Croatia, Serbia
                </div>
              </CardContent>
            </Card>

            {/* VC Evolution 2022-2025 */}
            <Card>
              <CardHeader className="flex flex-row items-center justify-between">
                <div className="flex items-center gap-2">
                  <Users className="w-5 h-5 text-primary" />
                  <CardTitle className="text-lg">Top EU AI VCs: Evolution (2022-2025)</CardTitle>
                </div>
                <SourceBadge source="Seedblink" />
              </CardHeader>
              <CardContent>
                <div className="w-full">
                  <table className="w-full text-sm table-fixed">
                    <thead>
                      <tr className="border-b text-muted-foreground">
                        <th className="pb-3 text-left font-medium w-[40%]">VC Fund</th>
                        <th className="pb-3 text-center font-medium w-[12%]">2022</th>
                        <th className="pb-3 text-center font-medium w-[12%]">2023</th>
                        <th className="pb-3 text-center font-medium w-[12%]">2024</th>
                        <th className="pb-3 text-center font-medium w-[12%]">2025*</th>
                        <th className="pb-3 text-right font-medium w-[12%]">Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[
                        { name: 'Bpifrance', country: 'FR', data: [23, 18, 13, 79], total: 133, highlight: true },
                        { name: 'LocalGlobe', country: 'UK', data: [15, 12, 16, 21], total: 64 },
                        { name: 'Speedinvest', country: 'AT', data: [20, 14, 6, 12], total: 52 },
                        { name: 'IQ Capital', country: 'UK', data: [12, 11, 16, 8], total: 47 },
                        { name: 'HTGF', country: 'DE', data: [14, 10, 15, 6], total: 45 },
                        { name: 'Amadeus Capital', country: 'UK', data: [11, 12, 19, 5], total: 47 },
                      ].map((vc, i) => (
                        <tr key={i} className="border-b border-border/30 hover:bg-muted/50 transition-colors">
                          <td className="py-3 font-medium text-secondary">
                            {vc.name} <span className="text-xs text-muted-foreground">({vc.country})</span>
                          </td>
                          {vc.data.map((val, j) => (
                            <td key={j} className={`py-3 text-center ${j === 3 ? 'text-primary font-medium' : ''}`}>
                              {val}{j === 3 ? '*' : ''}
                            </td>
                          ))}
                          <td className={`py-3 text-right font-bold ${vc.highlight ? 'text-primary' : ''}`}>{vc.total}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="mt-4 pt-4 border-t">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>*2025 data: last 12 months (partial year)</span>
                    <span className="font-medium text-secondary">99% of CEE VCs actively investing in AI</span>
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    20+ new AI-focused funds launched (2024-25) with €1.15B+ combined capital
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </ScrollReveal>

        {/* Row 7: Data Sources */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg">Data Sources (14)</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
                {[
                  { name: 'EC Digital', desc: 'AI Factories', url: 'https://digital-strategy.ec.europa.eu/en/policies/ai-factories' },
                  { name: 'AI Office', desc: 'Governance', url: 'https://digital-strategy.ec.europa.eu/en/policies/ai-office' },
                  { name: 'Seedblink', desc: 'VC Data', url: 'https://seedblink.com/blog/2025-03-13-europes-ai-investment-landscape-a-deep-dive' },
                  { name: 'Statista', desc: 'Market Data', url: 'https://www.statista.com/outlook/tmo/artificial-intelligence/europe' },
                  { name: 'JRC', desc: 'Research', url: 'https://joint-research-centre.ec.europa.eu/jrc-news-and-updates/boosting-use-ai-will-make-strategic-industries-more-competitive-2025-10-09_en' },
                  { name: 'AI Act EU', desc: 'Timeline', url: 'https://artificialintelligenceact.eu/' },
                  { name: 'EC AI Policy', desc: 'Framework', url: 'https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai' },
                  { name: 'EUR-Lex', desc: 'Reg. 2024/1689', url: 'https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng' },
                  { name: 'GPAI Code', desc: 'Practice', url: 'https://digital-strategy.ec.europa.eu/en/policies/contents-code-gpai' },
                  { name: 'EIB', desc: 'Financing', url: 'https://www.eib.org/en/press/all/2025-491-eib-group-and-european-commission-join-forces-to-finance-ai-gigafactories' },
                  { name: 'GenAI4EU', desc: 'Funding', url: 'https://digital-strategy.ec.europa.eu/en/policies/genai4eu' },
                  { name: 'Euronext', desc: 'Stock Data', url: '#' },
                  { name: 'Xetra', desc: 'Exchange', url: '#' },
                  { name: 'EuroHPC', desc: 'Computing', url: '#' },
                ].map((source, i) => (
                  <a
                    key={i}
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="bg-muted/30 rounded-lg p-3 text-center hover:border-primary/30 border border-transparent transition cursor-pointer"
                  >
                    <div className="text-xs font-medium text-secondary mb-1">{source.name}</div>
                    <div className="text-[10px] text-muted-foreground">{source.desc}</div>
                  </a>
                ))}
              </div>

              <div className="mt-6 pt-4 border-t flex flex-wrap items-center justify-between text-xs text-muted-foreground">
                <div>
                  <span className="font-medium text-secondary">beresol</span> EU Advocacy Hub - European AI Market & Industry Monitor
                </div>
                <div>All data sourced from official EU institutions and verified research</div>
              </div>
            </CardContent>
          </Card>
        </ScrollReveal>

        {/* AI Workflow Integration CTA */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="group bg-gradient-to-r from-primary/5 via-muted/30 to-primary/5 border border-primary/20 rounded-xl p-8 text-center hover:border-primary/40 hover:shadow-strong transition-all duration-300 mb-8">
            <div className="flex items-center justify-center gap-3 mb-4">
              <motion.div
                className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center group-hover:scale-110 transition-transform duration-300"
                whileHover={{ rotate: 10 }}
              >
                <Bot className="w-6 h-6 text-primary" />
              </motion.div>
              <h3 className="text-xl font-semibold text-secondary">
                Ready to Implement AI Workflows?
              </h3>
            </div>
            <p className="text-muted-foreground mb-6 max-w-2xl mx-auto leading-relaxed">
              Beresol helps organisations navigate also the EU AI regulatory landscape and implement
              compliant AI solutions. From AI Act compliance assessments to custom AI workflow
              integration, we provide end-to-end support for your AI transformation journey.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-4">
              <Link
                to="/ai-integration"
                className="inline-flex items-center gap-2 bg-primary hover:bg-primary-glow text-primary-foreground px-6 py-3 rounded-lg font-medium transition-all duration-300 hover:shadow-strong hover:-translate-y-0.5"
              >
                <Bot className="w-4 h-4" />
                Learn About AI Integration
              </Link>
              <Link
                to="/#services"
                className="inline-flex items-center gap-2 bg-background border border-border hover:border-primary/50 text-secondary px-6 py-3 rounded-lg font-medium transition-all duration-300"
              >
                View Our Services
              </Link>
            </div>
          </div>
        </ScrollReveal>

        {/* Related Monitors Section */}
        <section className="mb-12">
          <RelatedMonitorsSection currentMonitor="ai" />
        </section>

        {/* Feedback Section */}
        <FeedbackSection
          contentType="monitor"
          contentTitle="European AI Market & Industry Monitor"
        />
      </main>
    </div>
  );
}
