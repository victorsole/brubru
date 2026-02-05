import { useEffect, useState } from 'react';
import {
  Scale, TrendingUp, TrendingDown, Globe, ArrowLeft, RefreshCw, Newspaper,
  LineChart, Map, Landmark, AlertTriangle, ArrowRightLeft, Flag, Shield,
  FileText, ExternalLink, DollarSign, Percent, Calendar, ChevronRight
} from 'lucide-react';
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
import { WorldTariffMap, TariffTrendChart } from '@/components/tariff';
import {
  FALLBACK_COUNTRY_TARIFFS,
  FALLBACK_TRADE_WAR_METRICS,
  FALLBACK_TIMELINE_EVENTS,
  FALLBACK_TARIFF_TRENDS,
  FALLBACK_MONTHLY_TARIFF_TRENDS,
  FALLBACK_TRADE_NEWS,
  FALLBACK_SECTOR_TARIFFS,
  US_TARIFF_RATES,
  EU_MFN_TARIFFS,
  CHINA_TARIFF_RATES,
} from '@/data/tariffFallback';
import { TariffDataSource, DATA_SOURCE_URLS } from '@/types/tariff';

// Source Badge Component
const SourceBadge = ({ source, variant = 'default' }: { source: string; variant?: 'default' | 'accent' | 'blue' | 'red' }) => {
  const variants = {
    default: 'bg-primary/10 text-primary border-primary/30',
    accent: 'bg-accent/10 text-accent border-accent/30',
    blue: 'bg-blue-500/10 text-blue-500 border-blue-500/30',
    red: 'bg-red-500/10 text-red-500 border-red-500/30',
  };

  return (
    <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${variants[variant]}`}>
      {source}
    </span>
  );
};

// Metric Card Component
const TariffMetricCard = ({
  icon: Icon,
  value,
  label,
  trend,
  sources = [],
  color = 'primary',
  badge
}: {
  icon: React.ComponentType<{ className?: string }>;
  value: string;
  label: string;
  trend?: string;
  sources?: string[];
  color?: 'primary' | 'secondary' | 'accent' | 'destructive' | 'blue';
  badge?: { text: string; variant: 'default' | 'destructive' | 'warning' };
}) => {
  const colorClasses = {
    primary: 'text-primary bg-primary/10',
    secondary: 'text-secondary bg-muted/50',
    accent: 'text-accent bg-accent/10',
    destructive: 'text-destructive bg-destructive/10',
    blue: 'text-blue-600 bg-blue-50',
  };

  return (
    <Card className="group hover:shadow-strong transition-all duration-300 hover:-translate-y-2 h-full">
      <CardContent className="p-6 text-center h-full flex flex-col">
        <div className={`mx-auto w-16 h-16 rounded-full flex items-center justify-center mb-4 ${colorClasses[color]}`}>
          <Icon className="w-8 h-8" />
        </div>
        <div className="text-3xl font-bold text-secondary mb-1">{value}</div>
        <div className="text-muted-foreground text-sm">{label}</div>
        {trend && <p className={`text-sm mt-1 font-medium ${color === 'destructive' ? 'text-destructive' : color === 'blue' ? 'text-blue-600' : 'text-primary'}`}>{trend}</p>}
        <div className="flex-1 flex flex-col justify-end mt-2">
          {badge ? (
            <div className={`inline-block text-xs px-3 py-1 rounded-full font-medium mx-auto ${
              badge.variant === 'destructive'
                ? 'bg-gradient-to-r from-destructive to-destructive/80 text-white animate-pulse'
                : badge.variant === 'warning'
                ? 'bg-gradient-to-r from-amber-500 to-amber-400 text-white'
                : 'bg-primary/10 text-primary'
            }`}>
              {badge.text}
            </div>
          ) : (
            <div className="h-6" />
          )}
          {sources.length > 0 && (
            <div className="flex items-center justify-center gap-1 mt-2">
              {sources.map((source, i) => (
                <SourceBadge key={i} source={source} />
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default function TariffDashboard() {
  const [activeMapTab, setActiveMapTab] = useState<'US' | 'EU' | 'China'>('US');

  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  const lastUpdated = new Date().toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });

  // Prepare map data
  const usTariffMapData = Object.entries(US_TARIFF_RATES)
    .filter(([code]) => code !== 'DEFAULT' && code !== 'US')
    .map(([code, data]) => ({
      code,
      rate: data.rate,
      notes: data.notes,
    }));

  const euTariffMapData = Object.entries(EU_MFN_TARIFFS)
    .filter(([code]) => code !== 'DEFAULT')
    .map(([code, data]) => ({
      code,
      rate: data.mfnRate,
      notes: `Weighted avg: ${data.weightedAvg}%`,
    }));

  const chinaTariffMapData = Object.entries(CHINA_TARIFF_RATES)
    .filter(([code]) => code !== 'DEFAULT' && code !== 'CN')
    .map(([code, data]) => ({
      code,
      rate: data.rate,
      notes: data.notes,
    }));

  return (
    <div className="min-h-screen bg-background">
      <SEO
        title="Tariff & Trade War Monitor 2025 - US, EU, China Tariff Tracker"
        description="Real-time tariff intelligence: track US, EU, and China tariff rates, trade war developments, retaliatory measures, and WTO disputes. Live data on Trump 2.0 tariffs, EU countermeasures, and global trade tensions."
        keywords="US tariffs 2025, EU tariffs, China tariffs, trade war tracker, Trump tariffs, EU countermeasures, reciprocal tariffs, USTR, EC Trade, WTO disputes, steel aluminum tariffs, auto tariffs, Section 232, IEEPA tariffs"
        url="/tariffs"
      />
      <BreadcrumbSchema items={[
        { name: 'Home', url: '/' },
        { name: 'Tariff & Trade War Monitor', url: '/tariffs' }
      ]} />
      <Helmet>
        <script type="application/ld+json">
          {JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'WebPage',
            name: 'Tariff & Trade War Monitor 2025',
            description: 'Real-time dashboard tracking global tariffs, trade war developments, and international trade policy.',
            url: 'https://beresol.eu/tariffs',
            mainEntity: {
              '@type': 'Dataset',
              name: 'Global Tariff Data 2025',
              description: 'Comprehensive dataset on US, EU, and China tariff rates, trade agreements, and retaliatory measures.',
              creator: {
                '@type': 'Organization',
                name: 'Beresol',
                url: 'https://beresol.eu'
              },
              keywords: ['US tariffs', 'EU tariffs', 'China tariffs', 'trade war', 'WTO'],
              temporalCoverage: '2018/2025',
            },
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
        <RelatedMonitorBanner currentMonitor="tariffs" className="mb-6" />

        {/* Page Header */}
        <motion.header
          className="text-center mb-12"
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1 }}
        >
          <div className="flex items-center justify-center gap-3 mb-4">
            <motion.div
              className="w-12 h-12 rounded-full bg-destructive/10 flex items-center justify-center"
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ duration: 0.6, delay: 0.2, type: "spring", stiffness: 200 }}
            >
              <Scale className="w-6 h-6 text-destructive" />
            </motion.div>
            <h1 className="text-3xl md:text-4xl font-bold text-secondary">
              Tariff & Trade War Monitor
            </h1>
          </div>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            Real-time tracking of US, EU, and China tariff rates, retaliatory measures, and global trade tensions
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
            <Badge className="bg-destructive/10 text-destructive border-destructive/20">13 Data Sources</Badge>
          </motion.div>
        </motion.header>

        {/* Hero Metrics Row */}
        <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-12" staggerDelay={0.1}>
          <StaggerItem variant="fadeUp">
            <TariffMetricCard
              icon={Percent}
              value="16.8%"
              label="US Avg Tariff Rate (Nov 2025)"
              trend="+14.4pp from 2024"
              sources={['Yale Budget Lab']}
              color="destructive"
              badge={{ text: 'HIGHEST SINCE 1935', variant: 'destructive' }}
            />
          </StaggerItem>
          <StaggerItem variant="fadeUp">
            <TariffMetricCard
              icon={DollarSign}
              value="$250B"
              label="US Tariff Revenue (Annual)"
              trend="$2.5T over 2026-2035"
              sources={['Yale Budget Lab']}
              color="blue"
            />
          </StaggerItem>
          <StaggerItem variant="fadeUp">
            <TariffMetricCard
              icon={Globe}
              value="47"
              label="Active WTO Disputes"
              trend="Record high"
              sources={['WTO']}
              color="accent"
              badge={{ text: 'STRAINED', variant: 'warning' }}
            />
          </StaggerItem>
          <StaggerItem variant="fadeUp">
            <TariffMetricCard
              icon={ArrowRightLeft}
              value="$1T+"
              label="China Trade Surplus"
              trend="First time above $1T"
              sources={['China Customs']}
              color="primary"
            />
          </StaggerItem>
        </StaggerContainer>

        {/* Row 1: Tariff Trend Chart + Trade News */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            {/* Tariff Trend Chart */}
            <div className="lg:col-span-2">
              <Card className="h-full">
                <CardHeader className="flex flex-row items-center justify-between">
                  <div className="flex items-center gap-2">
                    <LineChart className="w-5 h-5 text-secondary" />
                    <CardTitle>Average Tariff Rates</CardTitle>
                  </div>
                  <div className="flex items-center gap-2">
                    <SourceBadge source="Yale Budget Lab" />
                    <SourceBadge source="WTO" />
                  </div>
                </CardHeader>
                <CardContent>
                  <TariffTrendChart yearlyData={FALLBACK_TARIFF_TRENDS} monthlyData={FALLBACK_MONTHLY_TARIFF_TRENDS} />
                  <div className="flex justify-center gap-6 mt-4 pt-4 border-t">
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded bg-blue-500"></div>
                      <span className="text-sm text-muted-foreground">United States</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded bg-green-500"></div>
                      <span className="text-sm text-muted-foreground">European Union</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="w-3 h-3 rounded bg-red-500"></div>
                      <span className="text-sm text-muted-foreground">China</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Trade News */}
            <Card className="h-full flex flex-col">
              <CardHeader className="flex flex-row items-center justify-between pb-3">
                <div className="flex items-center gap-2">
                  <Newspaper className="w-5 h-5 text-accent" />
                  <CardTitle className="text-lg">Trade War News</CardTitle>
                </div>
                <button className="p-2 hover:bg-muted rounded-md transition-colors">
                  <RefreshCw className="w-4 h-4 text-muted-foreground" />
                </button>
              </CardHeader>
              <CardContent className="flex-1 overflow-y-auto space-y-0 p-0">
                {FALLBACK_TRADE_NEWS.slice(0, 5).map((item, i) => (
                  <article key={i} className="p-4 border-b hover:bg-muted/50 transition-colors cursor-pointer">
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <SourceBadge
                        source={item.category}
                        variant={item.category === 'US-China' ? 'red' : item.category === 'US-EU' ? 'blue' : 'default'}
                      />
                      <time className="text-xs text-muted-foreground">
                        {item.pubDate.toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })}
                      </time>
                    </div>
                    <h4 className="font-medium text-secondary text-sm hover:text-primary transition-colors line-clamp-2">
                      {item.title}
                    </h4>
                  </article>
                ))}
              </CardContent>
              <div className="px-4 py-2 border-t bg-muted/30">
                <p className="text-xs text-muted-foreground text-center">
                  Sources: Reuters, EC Trade, USTR, WTO
                </p>
              </div>
            </Card>
          </div>
        </ScrollReveal>

        {/* Row 2: Interactive Tariff Maps */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <Card className="mb-6">
            <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <Map className="w-5 h-5 text-secondary" />
                <CardTitle>Global Tariff Rates by Perspective</CardTitle>
              </div>
              <div className="flex items-center gap-2">
                {/* Map Tabs */}
                <div className="flex bg-muted rounded-lg p-1">
                  {(['US', 'EU', 'China'] as const).map((tab) => (
                    <button
                      key={tab}
                      onClick={() => setActiveMapTab(tab)}
                      className={`px-4 py-2 text-sm font-medium rounded-md transition-all ${
                        activeMapTab === tab
                          ? tab === 'US' ? 'bg-blue-500 text-white shadow-sm' :
                            tab === 'EU' ? 'bg-green-500 text-white shadow-sm' :
                            'bg-red-500 text-white shadow-sm'
                          : 'text-muted-foreground hover:bg-background'
                      }`}
                    >
                      {tab === 'US' ? 'US Tariffs' : tab === 'EU' ? 'EU Tariffs' : 'China Tariffs'}
                    </button>
                  ))}
                </div>
                <SourceBadge source={activeMapTab === 'US' ? 'USTR' : activeMapTab === 'EU' ? 'EC Trade' : 'China Customs'} variant={activeMapTab === 'US' ? 'blue' : activeMapTab === 'EU' ? 'default' : 'red'} />
              </div>
            </CardHeader>
            <CardContent>
              <div className="relative">
                {activeMapTab === 'US' && (
                  <WorldTariffMap
                    data={usTariffMapData}
                    perspective="US"
                    title="US Tariffs on Trading Partners (2025)"
                    subtitle="Showing reciprocal tariffs, bilateral deals, and sector-specific rates"
                    height="450px"
                  />
                )}
                {activeMapTab === 'EU' && (
                  <WorldTariffMap
                    data={euTariffMapData}
                    perspective="EU"
                    title="EU Tariffs on Third Countries (2025)"
                    subtitle="MFN rates and FTA preferential access"
                    height="450px"
                    colorScale={{ min: '#22c55e', mid: '#eab308', max: '#ef4444' }}
                  />
                )}
                {activeMapTab === 'China' && (
                  <WorldTariffMap
                    data={chinaTariffMapData}
                    perspective="China"
                    title="China Tariffs on Trading Partners (2025)"
                    subtitle="Including retaliatory measures on US and EU goods"
                    height="450px"
                    colorScale={{ min: '#22c55e', mid: '#eab308', max: '#ef4444' }}
                  />
                )}
              </div>

              {/* Key Stats */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6 pt-4 border-t">
                <div className={`p-4 rounded-lg ${activeMapTab === 'US' ? 'bg-blue-50 border border-blue-200' : 'bg-muted/30 border'}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <Flag className="w-4 h-4 text-blue-600" />
                    <span className="text-sm font-medium text-secondary">US Tariff Policy</span>
                  </div>
                  <div className="text-2xl font-bold text-blue-600 mb-1">16.8%</div>
                  <div className="text-xs text-muted-foreground">
                    Yale Budget Lab Nov 2025. China: 10%*, EU: 15%, Others: 10%
                  </div>
                </div>
                <div className={`p-4 rounded-lg ${activeMapTab === 'EU' ? 'bg-green-50 border border-green-200' : 'bg-muted/30 border'}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <Landmark className="w-4 h-4 text-green-600" />
                    <span className="text-sm font-medium text-secondary">EU Tariff Policy</span>
                  </div>
                  <div className="text-2xl font-bold text-green-600 mb-1">1.8%</div>
                  <div className="text-xs text-muted-foreground">
                    Trade-weighted MFN. 35+ FTAs at 0%. US: 15% (Aug deal)
                  </div>
                </div>
                <div className={`p-4 rounded-lg ${activeMapTab === 'China' ? 'bg-red-50 border border-red-200' : 'bg-muted/30 border'}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <Globe className="w-4 h-4 text-red-600" />
                    <span className="text-sm font-medium text-secondary">China Tariff Policy</span>
                  </div>
                  <div className="text-2xl font-bold text-red-600 mb-1">5.5%</div>
                  <div className="text-xs text-muted-foreground">
                    Elevated from retaliation. EU pork/dairy: up to 42.7%
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </ScrollReveal>

        {/* Row 3: Sector Tariffs Table */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <Card className="mb-6">
            <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <FileText className="w-5 h-5 text-secondary" />
                <CardTitle>Sector-Specific Tariff Rates</CardTitle>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <SourceBadge source="USTR" variant="blue" />
                <SourceBadge source="TARIC" />
                <SourceBadge source="China Customs" variant="red" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b text-left text-sm text-muted-foreground">
                      <th className="pb-3 font-medium">Sector</th>
                      <th className="pb-3 font-medium">HS Code</th>
                      <th className="pb-3 font-medium text-right">US Tariff</th>
                      <th className="pb-3 font-medium text-right">EU Tariff</th>
                      <th className="pb-3 font-medium text-right">China Tariff</th>
                      <th className="pb-3 font-medium text-right">Trade Vol. ($B)</th>
                      <th className="pb-3 font-medium text-center">Impact</th>
                    </tr>
                  </thead>
                  <tbody className="text-sm">
                    {FALLBACK_SECTOR_TARIFFS.map((sector, i) => (
                      <tr key={i} className="border-b border-border/30 hover:bg-muted/50 transition-colors">
                        <td className="py-3 font-medium text-secondary">{sector.sector}</td>
                        <td className="py-3 text-muted-foreground font-mono text-xs">{sector.hsCode || '-'}</td>
                        <td className={`py-3 text-right font-medium ${sector.usTariff >= 25 ? 'text-red-600' : sector.usTariff >= 15 ? 'text-amber-600' : 'text-green-600'}`}>
                          {sector.usTariff}%
                        </td>
                        <td className={`py-3 text-right font-medium ${sector.euTariff >= 25 ? 'text-red-600' : sector.euTariff >= 15 ? 'text-amber-600' : 'text-green-600'}`}>
                          {sector.euTariff}%
                        </td>
                        <td className={`py-3 text-right font-medium ${sector.chinaTariff >= 25 ? 'text-red-600' : sector.chinaTariff >= 15 ? 'text-amber-600' : 'text-green-600'}`}>
                          {sector.chinaTariff}%
                        </td>
                        <td className="py-3 text-right">${sector.tradingVolume}B</td>
                        <td className="py-3 text-center">
                          <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                            sector.affected === 'High' ? 'bg-red-100 text-red-700' :
                            sector.affected === 'Medium' ? 'bg-amber-100 text-amber-700' :
                            'bg-green-100 text-green-700'
                          }`}>
                            {sector.affected}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="flex items-center justify-between mt-4 pt-4 border-t text-sm text-muted-foreground">
                <span>Showing {FALLBACK_SECTOR_TARIFFS.length} key sectors</span>
                <span>Trade volumes based on 2024 data</span>
              </div>
            </CardContent>
          </Card>
        </ScrollReveal>

        {/* Row 4: Trade War Timeline */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <Card className="mb-6 bg-gradient-to-r from-red-50 to-blue-50 border-red-200">
            <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
                  <AlertTriangle className="w-5 h-5 text-red-600" />
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <CardTitle>2025 Trade War Timeline</CardTitle>
                    <span className="text-[10px] px-2 py-0.5 rounded bg-red-600 text-white font-medium">ONGOING</span>
                  </div>
                  <p className="text-xs text-muted-foreground">Key escalation and de-escalation events</p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <SourceBadge source="USTR" variant="blue" />
                <SourceBadge source="EC Trade" />
                <SourceBadge source="White House" variant="blue" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="relative">
                {/* Timeline line */}
                <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gradient-to-b from-red-300 via-amber-300 to-green-300"></div>

                {/* Timeline events */}
                <div className="space-y-4 ml-12">
                  {FALLBACK_TIMELINE_EVENTS.slice(0, 8).map((event, i) => (
                    <div key={event.id} className="relative">
                      {/* Timeline dot */}
                      <div className={`absolute -left-12 w-8 h-8 rounded-full flex items-center justify-center ${
                        event.action === 'Tariff Increase' || event.action === 'Retaliation' ? 'bg-red-100' :
                        event.action === 'Agreement' || event.action === 'Tariff Decrease' ? 'bg-green-100' :
                        event.action === 'Suspension' ? 'bg-blue-100' : 'bg-amber-100'
                      }`}>
                        {event.action === 'Tariff Increase' || event.action === 'Retaliation' ? (
                          <TrendingUp className="w-4 h-4 text-red-600" />
                        ) : event.action === 'Agreement' || event.action === 'Tariff Decrease' ? (
                          <TrendingDown className="w-4 h-4 text-green-600" />
                        ) : (
                          <Shield className="w-4 h-4 text-amber-600" />
                        )}
                      </div>

                      {/* Event card */}
                      <div className="bg-white rounded-lg p-4 border shadow-sm hover:shadow-md transition-shadow">
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1">
                            <div className="flex items-center gap-2 mb-1">
                              <span className={`text-xs px-2 py-0.5 rounded font-medium ${
                                event.actor === 'US' ? 'bg-blue-100 text-blue-700' :
                                event.actor === 'EU' ? 'bg-green-100 text-green-700' :
                                event.actor === 'China' ? 'bg-red-100 text-red-700' :
                                'bg-gray-100 text-gray-700'
                              }`}>
                                {event.actor}
                              </span>
                              <ChevronRight className="w-3 h-3 text-muted-foreground" />
                              <span className="text-xs text-muted-foreground">{event.target}</span>
                            </div>
                            <p className="text-sm text-secondary font-medium">{event.description}</p>
                            {event.rate && (
                              <div className="mt-2 flex items-center gap-2">
                                {event.previousRate !== undefined && (
                                  <>
                                    <span className="text-xs text-muted-foreground">{event.previousRate}%</span>
                                    <ChevronRight className="w-3 h-3 text-muted-foreground" />
                                  </>
                                )}
                                <span className={`text-sm font-bold ${
                                  event.action === 'Tariff Increase' || event.action === 'Retaliation' ? 'text-red-600' : 'text-green-600'
                                }`}>
                                  {event.rate}%
                                </span>
                              </div>
                            )}
                          </div>
                          <div className="text-right">
                            <div className="text-xs font-medium text-secondary">
                              {event.date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                            </div>
                            <div className="text-[10px] text-muted-foreground">{event.date.getFullYear()}</div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </ScrollReveal>

        {/* Row 5: Key Trade Metrics Comparison */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            {/* US Trade Impact */}
            <Card className="border-blue-200 bg-blue-50/30">
              <CardHeader className="flex flex-row items-center gap-3 pb-3">
                <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                  <Flag className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <CardTitle className="text-lg">United States</CardTitle>
                  <p className="text-xs text-muted-foreground">Trade War Metrics</p>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex justify-between items-center p-3 bg-white rounded-lg border">
                  <span className="text-sm text-muted-foreground">Avg Tariff Applied</span>
                  <span className="text-lg font-bold text-blue-600">{FALLBACK_TRADE_WAR_METRICS.usAvgTariffApplied}%</span>
                </div>
                <div className="flex justify-between items-center p-3 bg-white rounded-lg border">
                  <span className="text-sm text-muted-foreground">Tariff Revenue</span>
                  <span className="text-lg font-bold text-secondary">${FALLBACK_TRADE_WAR_METRICS.usTariffRevenue}B</span>
                </div>
                <div className="flex justify-between items-center p-3 bg-white rounded-lg border">
                  <span className="text-sm text-muted-foreground">Retaliation Faced</span>
                  <span className="text-lg font-bold text-red-600">${FALLBACK_TRADE_WAR_METRICS.usRetaliationFaced}B</span>
                </div>
              </CardContent>
            </Card>

            {/* EU Trade Impact */}
            <Card className="border-green-200 bg-green-50/30">
              <CardHeader className="flex flex-row items-center gap-3 pb-3">
                <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
                  <Landmark className="w-5 h-5 text-green-600" />
                </div>
                <div>
                  <CardTitle className="text-lg">European Union</CardTitle>
                  <p className="text-xs text-muted-foreground">Trade War Metrics</p>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex justify-between items-center p-3 bg-white rounded-lg border">
                  <span className="text-sm text-muted-foreground">Avg MFN Rate</span>
                  <span className="text-lg font-bold text-green-600">{FALLBACK_TRADE_WAR_METRICS.euAvgTariffApplied}%</span>
                </div>
                <div className="flex justify-between items-center p-3 bg-white rounded-lg border">
                  <span className="text-sm text-muted-foreground">Countermeasures</span>
                  <span className="text-lg font-bold text-secondary">€{FALLBACK_TRADE_WAR_METRICS.euCountermeasuresValue}B</span>
                </div>
                <div className="flex justify-between items-center p-3 bg-white rounded-lg border">
                  <span className="text-sm text-muted-foreground">Exports Affected</span>
                  <span className="text-lg font-bold text-amber-600">€{FALLBACK_TRADE_WAR_METRICS.euGoodsAffected}B</span>
                </div>
              </CardContent>
            </Card>

            {/* China Trade Impact */}
            <Card className="border-red-200 bg-red-50/30">
              <CardHeader className="flex flex-row items-center gap-3 pb-3">
                <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center">
                  <Globe className="w-5 h-5 text-red-600" />
                </div>
                <div>
                  <CardTitle className="text-lg">China</CardTitle>
                  <p className="text-xs text-muted-foreground">Trade War Metrics</p>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex justify-between items-center p-3 bg-white rounded-lg border">
                  <span className="text-sm text-muted-foreground">Avg Tariff on US</span>
                  <span className="text-lg font-bold text-red-600">{FALLBACK_TRADE_WAR_METRICS.chinaAvgTariffApplied}%</span>
                </div>
                <div className="flex justify-between items-center p-3 bg-white rounded-lg border">
                  <span className="text-sm text-muted-foreground">Retaliation Value</span>
                  <span className="text-lg font-bold text-secondary">${FALLBACK_TRADE_WAR_METRICS.chinaRetaliationValue}B</span>
                </div>
                <div className="flex justify-between items-center p-3 bg-white rounded-lg border">
                  <span className="text-sm text-muted-foreground">Trade Surplus</span>
                  <span className="text-lg font-bold text-green-600">${(FALLBACK_TRADE_WAR_METRICS.chinaTradeSurplus / 1000).toFixed(2)}T</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </ScrollReveal>

        {/* Row 6: Data Sources */}
        <ScrollReveal variant="fadeUp" delay={0.1}>
          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="text-lg">Data Sources (13)</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
                {[
                  { name: 'Yale Budget Lab', desc: 'US Tariff Analysis', url: 'https://budgetlab.yale.edu/topic/trade' },
                  { name: 'USTR', desc: 'US Tariffs', url: DATA_SOURCE_URLS[TariffDataSource.USTR] },
                  { name: 'EC Trade', desc: 'EU Policy', url: DATA_SOURCE_URLS[TariffDataSource.EC_TRADE] },
                  { name: 'WTO', desc: 'Global Data', url: DATA_SOURCE_URLS[TariffDataSource.WTO] },
                  { name: 'TARIC', desc: 'EU Tariffs', url: DATA_SOURCE_URLS[TariffDataSource.TARIC] },
                  { name: 'China Customs', desc: 'CN Tariffs', url: DATA_SOURCE_URLS[TariffDataSource.CHINA_CUSTOMS] },
                  { name: 'USITC', desc: 'Trade Data', url: DATA_SOURCE_URLS[TariffDataSource.USITC] },
                  { name: 'IMF', desc: 'Trade Stats', url: DATA_SOURCE_URLS[TariffDataSource.IMF] },
                  { name: 'World Bank', desc: 'Indicators', url: DATA_SOURCE_URLS[TariffDataSource.WORLD_BANK] },
                  { name: 'Eurostat', desc: 'EU Stats', url: DATA_SOURCE_URLS[TariffDataSource.EUROSTAT] },
                  { name: 'UNCTAD', desc: 'Trade Data', url: DATA_SOURCE_URLS[TariffDataSource.UNCTAD] },
                  { name: 'Reuters', desc: 'News', url: DATA_SOURCE_URLS[TariffDataSource.REUTERS] },
                  { name: 'Politico', desc: 'Policy News', url: DATA_SOURCE_URLS[TariffDataSource.POLITICO] },
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
                  <span className="font-medium text-secondary">beresol</span> EU Advocacy Hub - Tariff & Trade War Monitor
                </div>
                <div>All data sourced from official government and international trade organisations</div>
              </div>
            </CardContent>
          </Card>
        </ScrollReveal>

        {/* Related Monitors Section */}
        <section className="mb-12">
          <RelatedMonitorsSection currentMonitor="tariffs" />
        </section>

        {/* Feedback Section */}
        <FeedbackSection
          contentType="monitor"
          contentTitle="Tariff & Trade War Monitor"
        />
      </main>
    </div>
  );
}
